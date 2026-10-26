"""État de l'application : quêtes, carte courante, position, journal d'événements."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional

from .config import Config
from .maps import MapDB
from .parser import Event

STATUSES = ("started", "finished", "failed")
TRAIL_MAX = 200
RAID_POINTS_MAX = 3000
HISTORY_MAX = 100
MARKS_MAX = 500
LABEL_MAX = 60
STALE_EVENT_S = 180        # un événement de log plus vieux que ça n'est qu'un rejeu d'historique
RAID_MAX_S = 75 * 60       # un raid dure au plus ~60 min : au-delà on considère être revenu au menu


class Core:
    def __init__(self, config: Config, mapdb: MapDB, store_dir: Path):
        self.config = config
        self.maps = mapdb
        self.store = store_dir / "quests.json"
        self._lock = threading.RLock()
        self.quests: dict[str, str] = {}     # quest_id -> status
        self.events: list[dict] = []         # journal (borné)
        self.seq = 0
        self.current_map: Optional[str] = None
        self.in_raid = False
        self.unresolved: list[str] = []      # ids de carte vus dans les logs mais inconnus
        self.position: Optional[dict] = None
        self.trail: list[dict] = []
        self.history_store = store_dir / "history.json"
        self.marks_store = store_dir / "marks.json"
        self.history: list[dict] = []        # raids terminés (le plus récent en dernier)
        self.marks: list[dict] = []          # repères posés par le joueur
        self._raid: Optional[dict] = None    # raid en cours d'enregistrement
        self.on_raid_end = None              # rappel appelé hors verrou à la fin d'un raid
        self._load()

    # ── persistance
    def _load(self) -> None:
        try:
            raw = json.loads(self.store.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.quests = {k: v for k, v in raw.items() if v in STATUSES}
        except (OSError, ValueError):
            pass
        for path, attr in ((self.history_store, "history"), (self.marks_store, "marks")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    setattr(self, attr, [r for r in raw if isinstance(r, dict) and r.get("id")])
            except (OSError, ValueError):
                pass

    def _write(self, path: Path, data) -> None:
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass

    def _save(self) -> None:
        try:
            tmp = self.store.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.quests, indent=1), encoding="utf-8")
            tmp.replace(self.store)
        except OSError:
            pass

    # ── journal
    def _push(self, kind: str, data: dict, ts: str | None = None) -> None:
        self.seq += 1
        item = {"seq": self.seq, "kind": kind, "data": data, "ts": ts or time.strftime("%H:%M:%S")}
        self.events.append(item)
        if len(self.events) > 500:
            del self.events[:100]

    # ── événements de logs
    def handle_event(self, ev: Event) -> None:
        ended = False
        with self._lock:
            if ev.kind == "quest":
                qid, status = ev.data["quest_id"], ev.data["status"]
                if self.quests.get(qid) == status:
                    return
                self.quests[qid] = status
                self._save()
                if not ev.data.get("history"):
                    self._push("quest", {"quest_id": qid, "status": status}, ev.ts)
            elif ev.kind == "map":
                internal = self.maps.resolve_log_id(ev.data["log_id"])
                if not internal:
                    lid = str(ev.data["log_id"])[:60]
                    if lid not in self.unresolved:
                        self.unresolved.append(lid)
                        del self.unresolved[:-10]
                if internal and internal != self.current_map:
                    self.current_map = internal
                    self.trail.clear()
                    self._push("map", {"map": internal}, ev.ts)
            elif self._stale(ev):
                return        # rejeu d'un vieux raid au démarrage : ne change pas l'état actuel
            elif ev.kind == "raid_matched":
                self.in_raid = False
                self._raid = None
                self._push("raid_matched", {}, ev.ts)
            elif ev.kind == "raid_start":
                self._begin_raid()
                self._push("raid_start", {"map": self.current_map}, ev.ts)
            elif ev.kind == "raid_end":
                if self.in_raid:
                    self.in_raid = False
                    ended = True
                    self._finish_raid()
                    self._push("raid_end", {}, ev.ts)
        if ended and self.on_raid_end:
            try:
                self.on_raid_end()
            except Exception:
                pass

    @staticmethod
    def _stale(ev: Event) -> bool:
        t = ev.data.get("t")
        return bool(t) and time.time() - t > STALE_EVENT_S

    def _begin_raid(self) -> None:
        self.in_raid = True
        self._raid = {"id": f"{int(time.time() * 1000)}", "map": self.current_map, "start": time.time(), "points": []}

    def _expire_raid(self) -> None:
        """Un raid qui dure trop longtemps n'est plus un raid : on est revenu au menu sans que le log l'ait dit."""
        if self.in_raid and self._raid and time.time() - self._raid["start"] > RAID_MAX_S:
            self.in_raid = False
            self._raid = None
            self._push("raid_end", {"expired": True})

    # ── captures d'écran
    def handle_screenshot(self, pos: dict) -> None:
        with self._lock:
            # Les coordonnées de la capture sont la vérité : si elles ne tiennent pas dans la carte
            # supposée, on bascule sur la carte qui les contient (souvent la carte du raid en cours).
            cands = self.maps.candidates(pos["x"], pos["z"])
            if self.current_map in cands:
                map_id = self.current_map
            elif cands:
                map_id = cands[0]
            else:
                map_id = self.current_map
            if map_id and map_id != self.current_map:
                self.current_map = map_id
                self.trail.clear()
                self._push("map", {"map": map_id, "guessed": True})
                if self._raid is not None:
                    self._raid["map"] = map_id
            if not self.in_raid:                 # une capture avec position = on est forcément en raid
                self._begin_raid()
                self._raid["map"] = map_id
                self._push("raid_start", {"map": map_id, "from_screenshot": True})
            pos.setdefault("t", time.time())
            self.position = {**pos, "map": map_id}
            self.trail.append({"x": pos["x"], "y": pos["y"], "z": pos["z"]})
            if self._raid is not None and len(self._raid["points"]) < RAID_POINTS_MAX:
                self._raid["points"].append({"x": pos["x"], "y": pos["y"], "z": pos["z"], "t": pos["t"]})
                if map_id and not self._raid.get("map"):
                    self._raid["map"] = map_id
            if len(self.trail) > TRAIL_MAX:
                del self.trail[0]
            self._push("position", {"map": map_id, "x": pos["x"], "y": pos["y"], "z": pos["z"], "yaw": pos["yaw"]})

    def _finish_raid(self) -> None:
        """Enregistre le raid qui vient de se terminer (appelé sous verrou)."""
        r, self._raid = self._raid, None
        if not r:
            return
        r["end"] = time.time()
        r["duration"] = int(r["end"] - r["start"])
        self.history.append(r)
        del self.history[:-HISTORY_MAX]
        self._write(self.history_store, self.history)

    def note(self, kind: str, data: dict) -> None:
        with self._lock:
            self._push(kind, data)

    # ── actions manuelles
    def set_quest(self, quest_id: str, status: Optional[str]) -> None:
        with self._lock:
            if status in STATUSES:
                self.quests[quest_id] = status
            else:
                self.quests.pop(quest_id, None)
            self._save()

    def set_map(self, map_id: str) -> None:
        with self._lock:
            if map_id in self.maps.by_id and map_id != self.current_map:
                self.current_map = map_id
                self.trail.clear()
                self._push("map", {"map": map_id, "manual": True})

    def set_raid_state(self, active: bool) -> None:
        """Correction manuelle de l'état (menu / en raid)."""
        with self._lock:
            if active and not self.in_raid:
                self._begin_raid()
                self._push("raid_start", {"map": self.current_map, "manual": True})
            elif not active and self.in_raid:
                self.in_raid = False
                self._raid = None
                self._push("raid_end", {"manual": True})

    def clear_trail(self) -> None:
        with self._lock:
            self.trail.clear()

    # ── historique des raids
    def history_list(self) -> list:
        with self._lock:
            return [{"id": r["id"], "map": r.get("map"), "start": r["start"], "duration": r.get("duration", 0),
                     "points": len(r.get("points") or [])} for r in reversed(self.history)]

    def history_get(self, raid_id: str) -> Optional[dict]:
        with self._lock:
            return next((dict(r) for r in self.history if r["id"] == raid_id), None)

    def history_delete(self, raid_id: str) -> bool:
        with self._lock:
            n = len(self.history)
            self.history = [r for r in self.history if r["id"] != raid_id]
            if len(self.history) != n:
                self._write(self.history_store, self.history)
            return len(self.history) != n

    # ── repères
    def marks_list(self) -> list:
        with self._lock:
            return [dict(m) for m in self.marks]

    def mark_add(self, map_id: str, x: float, z: float, label: str) -> Optional[dict]:
        with self._lock:
            if map_id not in self.maps.by_id or len(self.marks) >= MARKS_MAX:
                return None
            try:
                x, z = float(x), float(z)
            except (TypeError, ValueError):
                return None
            if not (abs(x) < 1e5 and abs(z) < 1e5):
                return None
            m = {"id": f"m{int(time.time() * 1000)}{len(self.marks)}", "map": map_id, "x": x, "z": z,
                 "label": str(label or "").strip()[:LABEL_MAX] or "Repère"}
            self.marks.append(m)
            self._write(self.marks_store, self.marks)
            return dict(m)

    def mark_delete(self, mark_id: str) -> bool:
        with self._lock:
            n = len(self.marks)
            self.marks = [m for m in self.marks if m["id"] != mark_id]
            if len(self.marks) != n:
                self._write(self.marks_store, self.marks)
            return len(self.marks) != n

    # ── statistiques
    def stats(self) -> dict:
        with self._lock:
            per: dict[str, dict] = {}
            for r in self.history:
                m = r.get("map") or "?"
                d = per.setdefault(m, {"map": m, "raids": 0, "seconds": 0, "points": 0, "heat": []})
                d["raids"] += 1
                d["seconds"] += int(r.get("duration") or 0)
                pts = r.get("points") or []
                d["points"] += len(pts)
                d["heat"].extend([round(p["x"], 1), round(p["z"], 1)] for p in pts if "x" in p and "z" in p)
            out = []
            for d in per.values():
                heat = d["heat"]
                if len(heat) > 800:                      # on borne la taille envoyée à l'interface
                    heat = heat[:: len(heat) // 800 + 1]
                out.append({"map": d["map"], "raids": d["raids"], "avg_seconds": d["seconds"] // d["raids"],
                            "points": d["points"], "heat": heat})
            out.sort(key=lambda x: -x["raids"])
            total = sum(d["raids"] for d in out)
            return {"total_raids": total, "total_seconds": sum(int(r.get("duration") or 0) for r in self.history), "maps": out}

    # ── sauvegarde / restauration
    def export_all(self) -> dict:
        with self._lock:
            return {"app": "tarkov-companion", "version": 1, "quests": dict(self.quests),
                    "history": list(self.history), "marks": list(self.marks)}

    def import_all(self, data) -> dict:
        """Restaure une sauvegarde (contenu validé, rien n'est exécuté). Retourne les quantités importées."""
        if not isinstance(data, dict) or data.get("app") != "tarkov-companion":
            raise ValueError("Ce fichier n'est pas une sauvegarde Tarkov Companion.")
        with self._lock:
            q = data.get("quests")
            if isinstance(q, dict):
                self.quests = {str(k): v for k, v in q.items() if v in STATUSES and len(str(k)) < 80}
                self._save()
            h = data.get("history")
            if isinstance(h, list):
                keep = []
                num = lambda v: type(v) in (int, float)  # noqa: E731
                for r in h:
                    if not (isinstance(r, dict) and isinstance(r.get("id"), str) and isinstance(r.get("points", []), list)):
                        continue
                    pts = [{"x": p["x"], "y": p.get("y", 0), "z": p["z"], "t": p.get("t", 0)} for p in r["points"][:RAID_POINTS_MAX]
                           if isinstance(p, dict) and num(p.get("x")) and num(p.get("z")) and num(p.get("y", 0)) and num(p.get("t", 0))]
                    mp = r.get("map")
                    keep.append({"id": r["id"][:40], "map": mp if mp in self.maps.by_id else None,
                                 "start": r.get("start") if num(r.get("start")) else 0, "end": r.get("end") if num(r.get("end")) else 0,
                                 "duration": int(r.get("duration")) if num(r.get("duration")) else 0, "points": pts})
                self.history = keep[-HISTORY_MAX:]
                self._write(self.history_store, self.history)
            m = data.get("marks")
            if isinstance(m, list):
                keep = []
                for k in m:
                    if (isinstance(k, dict) and isinstance(k.get("id"), str) and isinstance(k.get("map"), str)
                            and all(type(k.get(a)) in (int, float) for a in ("x", "z"))):
                        keep.append({"id": k["id"], "map": k["map"], "x": k["x"], "z": k["z"],
                                     "label": str(k.get("label", ""))[:LABEL_MAX]})
                self.marks = keep[-MARKS_MAX:]
                self._write(self.marks_store, self.marks)
            return {"quests": len(self.quests), "history": len(self.history), "marks": len(self.marks)}

    # ── lecture pour l'interface
    def snapshot(self) -> dict:
        with self._lock:
            self._expire_raid()
            return {
                "quests": dict(self.quests),
                "current_map": self.current_map,
                "in_raid": self.in_raid,
                "unresolved_maps": list(self.unresolved),
                "position": self.position,
                "trail": list(self.trail),
                "seq": self.seq,
            }

    def events_since(self, seq: int) -> list[dict]:
        with self._lock:
            return [e for e in self.events if e["seq"] > seq]
