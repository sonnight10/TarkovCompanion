"""Pont entre l'interface (pywebview) et le moteur."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional

from . import __version__, updater
from .config import Config, data_dir
from .core import Core
from .maps import MapDB
from .parser import Event
from .paths import detect_logs_dir, detect_screenshots_dir
from .tarkov_api import TarkovAPI
from .watcher import LogWatcher, ScreenshotWatcher

SVG_BASE = "https://assets.tarkov.dev/maps/svg/"
UI_DIR = Path(__file__).parent / "ui"
# liens que l'interface peut ouvrir dans le navigateur (crédits et licences)
LINK_HOSTS = ("tarkov.dev", "github.com", "tarkovbot.eu", "creativecommons.org", "opensource.org", "leafletjs.com", "assets.tarkov.dev")


def link_allowed(url: str) -> bool:
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return False
    host = (u.hostname or "").lower()
    return u.scheme == "https" and any(host == h or host.endswith("." + h) for h in LINK_HOSTS)


def reminder_due(now: float, last: float, interval: int, in_raid: bool) -> bool:
    """Vrai quand il est temps de rappeler au joueur de prendre une capture (jamais hors raid)."""
    return bool(in_raid and interval and now - last >= interval)


def _beep() -> None:
    try:
        import winsound  # Windows uniquement
        winsound.Beep(880, 140)
    except Exception:
        pass


class Api:
    """Seules les méthodes publiques sont visibles depuis JavaScript."""

    def __init__(self):
        self._dir = data_dir()
        self._config = Config()
        self._maps = MapDB()
        self._core = Core(self._config, self._maps, self._dir)
        self._tarkov = TarkovAPI(self._config.get("api_url"), self._dir / "tasks_cache.json")
        self._logw: Optional[LogWatcher] = None
        self._shotw: Optional[ScreenshotWatcher] = None
        self._window = None
        self._update_info = None
        self._update_zip = None
        self._stop_reminder = threading.Event()
        self._reminder_thread = None
        self._core.on_raid_end = self._auto_cleanup
        if not self._config.get("logs_dir"):
            self._config.update({"logs_dir": detect_logs_dir()})
        if not self._config.get("screenshots_dir"):
            self._config.update({"screenshots_dir": detect_screenshots_dir()})
        (self._dir / "maps").mkdir(exist_ok=True)

    # ── interne
    def _attach(self, window) -> None:
        self._window = window

    def _start_watchers(self) -> None:
        self._stop_watchers()
        logs = self._config.get("logs_dir")
        shots = self._config.get("screenshots_dir")
        if logs:
            self._logw = LogWatcher(logs, self._core.handle_event)
            self._logw.start()
        if shots:
            self._shotw = ScreenshotWatcher(shots, self._core.handle_screenshot)
            self._shotw.start()

    def _auto_cleanup(self) -> None:
        if self._config.get("cleanup_screenshots"):
            self._cleanup()

    def _cleanup(self) -> int:
        n = self._shotw.cleanup() if self._shotw else 0
        if n:
            self._core.note("cleanup", {"count": n})
        return n

    def _reminder_loop(self) -> None:
        last = time.time()
        while not self._stop_reminder.is_set():
            by_map = self._config.get("reminder_by_map") or {}
            interval = int(by_map.get(self._core.current_map, self._config.get("reminder_seconds")) or 0)
            now = time.time()
            if reminder_due(now, last, interval, self._core.in_raid):
                last = now
                style = self._config.get("reminder_style")
                if style in ("beep", "both"):
                    _beep()
                if style in ("toast", "both"):
                    self._core.note("reminder", {})
            elif not interval or not self._core.in_raid:
                last = now
            self._stop_reminder.wait(0.5)

    def _stop_watchers(self) -> None:
        for w in (self._logw, self._shotw):
            if w:
                w.stop()
        self._logw = self._shotw = None

    def _watch_status(self) -> dict:
        logs, shots = self._config.get("logs_dir"), self._config.get("screenshots_dir")
        return {
            "logs_ok": bool(logs) and Path(logs).is_dir(),
            "shots_ok": bool(shots) and Path(shots).is_dir(),
        }

    # ── API JS
    def bootstrap(self) -> dict:
        self._start_watchers()
        if not self._reminder_thread:
            self._reminder_thread = threading.Thread(target=self._reminder_loop, name="reminder", daemon=True)
            self._reminder_thread.start()
        return {
            "version": __version__,
            "config": self._config.as_dict(),
            "maps": self._maps.maps,
            "state": self._core.snapshot(),
            "watch": self._watch_status(),
        }

    def poll(self, since: int = 0) -> dict:
        return {
            "events": self._core.events_since(int(since)),
            "state": self._core.snapshot(),
            "watch": self._watch_status(),
        }

    def get_tasks(self, force: bool = False) -> dict:
        return self._tarkov.fetch_tasks(self._config.get("language"), bool(force))

    def get_extracts(self, force: bool = False) -> dict:
        return self._tarkov.fetch_extracts(self._config.get("language"), bool(force))

    def get_log_status(self) -> dict:
        """Ce que le lecteur de logs voit : dossier, session, fichiers, entrées de quêtes reconnues."""
        logs = self._config.get("logs_dir")
        w = self._logw
        counts: dict = {}
        for st in self._core.snapshot()["quests"].values():
            counts[st] = counts.get(st, 0) + 1
        return {"root": logs, "root_ok": bool(logs) and Path(logs).is_dir(), "watching": bool(w),
                "stats": dict(w.stats) if w else None, "quests": counts,
                "unresolved_maps": self._core.snapshot()["unresolved_maps"]}

    def get_raid_diag(self) -> dict:
        """Dernières lignes de logs liées aux raids + état détecté : à joindre en cas de problème de détection."""
        w = self._logw
        st = self._core.snapshot()
        return {"lines": list(w.recent) if w else [], "in_raid": st["in_raid"], "current_map": st["current_map"],
                "unresolved_maps": st["unresolved_maps"], "session": w.stats.get("session") if w else None,
                "files": w.stats.get("files") if w else [], "version": __version__}

    def get_stats(self) -> dict:
        return self._core.stats()

    def _dialog(self, kind: str, filename: str = ""):
        import webview  # import tardif : absent pendant les tests
        types = ("Sauvegarde Tarkov Companion (*.json)",)
        if kind == "save":
            r = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename=filename, file_types=types)
        else:
            r = self._window.create_file_dialog(webview.OPEN_DIALOG, file_types=types)
        if not r:
            return None
        return r if isinstance(r, str) else r[0]

    def export_backup(self) -> dict:
        """Enregistre quêtes, historique et repères dans un fichier choisi par le joueur."""
        if self._window is None:
            return {"ok": False, "error": "Fenêtre indisponible."}
        path = self._dialog("save", "tarkov-companion-sauvegarde.json")
        if not path:
            return {"ok": False, "error": None}
        try:
            Path(path).write_text(json.dumps(self._core.export_all(), ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            return {"ok": False, "error": f"Écriture impossible : {exc}"}
        return {"ok": True, "path": path}

    def import_backup(self) -> dict:
        """Restaure une sauvegarde choisie par le joueur (remplace quêtes, historique et repères)."""
        if self._window is None:
            return {"ok": False, "error": "Fenêtre indisponible."}
        path = self._dialog("open")
        if not path:
            return {"ok": False, "error": None}
        try:
            p = Path(path)
            if p.stat().st_size > 20_000_000:
                return {"ok": False, "error": "Fichier trop volumineux."}
            counts = self._core.import_all(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "counts": counts}

    # ── mises à jour (Releases GitHub)
    def check_update(self, manual: bool = False) -> dict:
        """Cherche une nouvelle version. Au lancement (manual=False) : silencieux si désactivé ou non configuré."""
        repo = str(self._config.get("update_repo") or "")
        if not manual and (not self._config.get("check_updates") or not repo):
            return {"available": False, "current": __version__, "error": None, "skipped": True}
        res = updater.check(repo)
        self._update_info = res.pop("_info", None) if res.get("available") else None
        res["can_install"] = updater.is_frozen() and sys.platform == "win32"
        return res

    def download_update(self) -> dict:
        """Télécharge et vérifie la version proposée par check_update (empreinte SHA-256 obligatoire)."""
        info = self._update_info
        if not info:
            return {"ok": False, "error": "Aucune mise à jour à télécharger : relance la vérification."}
        try:
            path = updater.download(info, self._dir / "updates")
            updater.validate_zip(path)
        except (ValueError, OSError, urllib.error.URLError) as exc:
            return {"ok": False, "error": str(exc)}
        self._update_zip = path
        return {"ok": True, "path": str(path), "can_install": updater.is_frozen() and sys.platform == "win32"}

    def install_update(self) -> dict:
        """Ferme l'application, remplace les fichiers par la nouvelle version et la relance (Windows, version compilée)."""
        if not self._update_zip or not self._update_zip.exists():
            return {"ok": False, "error": "Télécharge d'abord la mise à jour."}
        if not (updater.is_frozen() and sys.platform == "win32"):
            return {"ok": False, "error": "L'installation automatique ne fonctionne qu'avec la version compilée (.exe) sous Windows. Le fichier est téléchargé : décompresse-le à la place de l'ancien dossier."}
        try:
            top = updater.validate_zip(self._update_zip)
            script = updater.make_apply_script(self._update_zip, top, updater.app_dir(), Path(sys.executable).name,
                                               os.getpid(), self._dir / "updates")
            updater.launch_apply(script)
        except (ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}
        threading.Timer(0.8, self._quit).start()
        return {"ok": True}

    def _quit(self) -> None:
        try:
            self.shutdown()
            if self._window is not None:
                self._window.destroy()
        finally:
            os._exit(0)

    def open_update_folder(self) -> bool:
        p = self._update_zip
        if not p or sys.platform != "win32":
            return False
        try:
            subprocess.Popen(["explorer", "/select,", str(p)])
            return True
        except OSError:
            return False

    def set_overlay(self, on: bool) -> bool:
        """Mode superposition : petite fenêtre toujours au premier plan."""
        w = self._window
        if w is None:
            return False
        try:
            w.on_top = bool(on)
            if on:
                self._normal_size = (w.width, w.height)
                w.resize(520, 460)
            elif getattr(self, "_normal_size", None):
                w.resize(*self._normal_size)
        except Exception:
            return False
        return True

    def run_probe(self) -> list:
        """Teste ce que tarkov.dev accepte (requêtes minimales) pour localiser un problème."""
        return self._tarkov.probe()

    def get_diagnostics(self) -> list:
        """Dernières réponses de tarkov.dev (statut, erreurs, nombre d'éléments)."""
        return list(self._tarkov.diag)

    def get_map_svg(self, map_id: str) -> dict:
        m = self._maps.by_id.get(map_id)
        if not m or not m.get("svg") or m["svg"] not in self._maps.svg_files:
            return {"svg": None, "error": "Cette carte n'a pas de fond vectoriel."}
        cache = self._dir / "maps" / m["svg"]
        try:
            if not cache.exists() or cache.stat().st_size < 1000:
                req = urllib.request.Request(SVG_BASE + m["svg"], headers={"User-Agent": "TarkovCompanion/1.0"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    cache.write_bytes(resp.read())
            return {"svg": cache.read_text(encoding="utf-8"), "error": None}
        except (urllib.error.URLError, OSError) as exc:
            return {"svg": None, "error": f"Téléchargement de la carte impossible : {exc}"}

    def set_quest_status(self, quest_id: str, status: Optional[str]) -> bool:
        self._core.set_quest(quest_id, status)
        return True

    def set_map(self, map_id: str) -> bool:
        self._core.set_map(map_id)
        return True

    def set_raid_state(self, active: bool) -> bool:
        """Correction manuelle : indique si l'on est en raid ou au menu."""
        self._core.set_raid_state(bool(active))
        return True

    def clear_trail(self) -> bool:
        self._core.clear_trail()
        return True

    def save_config(self, changes: dict) -> dict:
        self._config.update(changes)
        if "logs_dir" in changes or "screenshots_dir" in changes:
            self._start_watchers()
        return {"config": self._config.as_dict(), "watch": self._watch_status()}

    def detect_paths(self) -> dict:
        found = {"logs_dir": detect_logs_dir(), "screenshots_dir": detect_screenshots_dir()}
        return self.save_config({k: v for k, v in found.items() if v}) | {"found": found}

    def pick_folder(self, key: str) -> dict:
        if key not in ("logs_dir", "screenshots_dir") or self._window is None:
            return {"config": self._config.as_dict(), "watch": self._watch_status()}
        import webview  # import tardif : absent pendant les tests
        picked = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if picked:
            return self.save_config({key: picked[0]})
        return {"config": self._config.as_dict(), "watch": self._watch_status()}

    def cleanup_screenshots(self) -> dict:
        """Supprime maintenant les captures vues pendant cette session."""
        return {"deleted": self._cleanup()}

    # ── historique, repères, liens
    def get_history(self) -> list:
        return self._core.history_list()

    def get_raid(self, raid_id: str) -> Optional[dict]:
        return self._core.history_get(str(raid_id))

    def delete_raid(self, raid_id: str) -> bool:
        return self._core.history_delete(str(raid_id))

    def get_marks(self) -> list:
        return self._core.marks_list()

    def add_mark(self, map_id: str, x: float, z: float, label: str = "") -> Optional[dict]:
        return self._core.mark_add(str(map_id), x, z, label)

    def delete_mark(self, mark_id: str) -> bool:
        return self._core.mark_delete(str(mark_id))

    def open_url(self, url: str) -> bool:
        """Ouvre un lien de crédits dans le navigateur (liste blanche de sites)."""
        if not link_allowed(str(url)):
            return False
        try:
            return bool(webbrowser.open(str(url)))
        except Exception:
            return False

    def demo(self) -> bool:
        """Simule quelques événements pour tester l'interface sans le jeu."""
        c = self._core
        c.handle_event(Event("raid_matched", {}, time.strftime("%H:%M:%S")))
        c.handle_event(Event("map", {"log_id": "bigmap"}, time.strftime("%H:%M:%S")))
        c.handle_event(Event("raid_start", {}, time.strftime("%H:%M:%S")))
        pts = [(-100, 3, 40, 20), (-60, 3, 30, 45), (-10, 3, 10, 80), (40, 3, -20, 120), (90, 3, -60, 150)]
        for x, y, z, yaw in pts:
            c.handle_screenshot({"x": x, "y": y, "z": z, "yaw": yaw, "file": "demo"})
        return True

    def shutdown(self) -> None:
        self._stop_reminder.set()
        self._auto_cleanup()
        self._stop_watchers()
