"""Client GraphQL tarkov.dev (quêtes) avec cache disque, sans dépendance externe."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

STATIC_URL = "https://json.tarkov.dev/"   # fichiers JSON statiques : c'est ce que lit le site tarkov.dev lui-même
PAGE = 100   # quêtes par requête : des réponses petites passent mieux que la liste complète d'un coup

# Trois niveaux de détail : on essaie du plus riche au plus simple (voir _query)
TASK_LIGHT = """
    id name minPlayerLevel kappaRequired
    trader { name }
    map { normalizedName }
    objectives { id type description optional maps { normalizedName } }
"""
TASK_MID = """
    id name minPlayerLevel
    trader { name }
    objectives { id description }
"""
TASK_MIN = """
    id name
"""

# Corps « zones » : positions des objectifs, récupérées à part et de façon facultative
_Z = "zones { map { normalizedName } position { x y z } outline { x y z } }"
TASK_ZONES = """
    id
    objectives {
      id
      ... on TaskObjectiveBasic { """ + _Z + """ }
      ... on TaskObjectiveMark { """ + _Z + """ }
      ... on TaskObjectiveShoot { """ + _Z + """ }
      ... on TaskObjectiveItem { """ + _Z + """ }
      ... on TaskObjectiveQuestItem { """ + _Z + """ possibleLocations { map { normalizedName } positions { x y z } } }
    }
"""


def _tasks_query(body: str, paged: bool, use_lang: bool = True) -> str:
    decl = (["$lang: LanguageCode"] if use_lang else []) + (["$limit: Int", "$offset: Int"] if paged else [])
    args = (["lang: $lang"] if use_lang else []) + (["limit: $limit", "offset: $offset"] if paged else [])
    head = "query" + ("(" + ", ".join(decl) + ")" if decl else "")
    call = "tasks" + ("(" + ", ".join(args) + ")" if args else "")
    return head + " { " + call + " {" + body + "} }"


CACHE_TTL = 12 * 3600
EXTRACT_TTL = 24 * 3600
MIN_TASKS = 30            # le jeu compte plusieurs centaines de quêtes : moins = réponse incomplète
MIN_EXTRACT_MAPS = 5      # idem pour les cartes ayant des extractions
TRANSIENT = re.compile(r"unavailable|try again|timeout|timed out|temporar|overload|rate|HTTP 5\d\d", re.I)


def friendly(errors) -> str:
    text = json.dumps(errors, ensure_ascii=False) if errors else ""
    if TRANSIENT.search(text):
        return "tarkov.dev est momentanément indisponible (nouvelle tentative automatique)"
    return (text[:200] or "réponse vide")

# Variantes essayées dans l'ordre : le schéma exact n'a pas pu être vérifié, on s'adapte.
EXTRACT_FIELDS = [
    "extracts { name faction position { x y z } }",
    "extracts { name position { x y z } }",
    "extracts { name faction outline { x y z } }",
    "extracts { name faction position { x y z } outline { x y z } }",
]


def _extract_query(fields: str, use_lang: bool = True) -> str:
    if use_lang:
        return "query($lang: LanguageCode) { maps(lang: $lang) { normalizedName " + fields + " } }"
    return "{ maps { normalizedName " + fields + " } }"


def _langs(lang: str) -> list:
    """Langues essayées dans l'ordre : celle demandée, l'anglais, puis aucune (valeur par défaut du serveur)."""
    out = [lang]
    if lang != "en":
        out.append("en")
    return out + [None]


def _extract_point(e: dict):
    pos = e.get("position")
    if isinstance(pos, dict) and pos.get("x") is not None and pos.get("z") is not None:
        return pos["x"], pos.get("y") or 0, pos["z"]
    pts = [p for p in (e.get("outline") or []) if p and p.get("x") is not None and p.get("z") is not None]
    if pts:
        n = len(pts)
        return sum(p["x"] for p in pts) / n, sum((p.get("y") or 0) for p in pts) / n, sum(p["z"] for p in pts) / n
    return None


def normalize_extracts(maps: list) -> dict:
    out: dict = {}
    for m in maps or []:
        rows = []
        for e in m.get("extracts") or []:
            pt = _extract_point(e)
            if not pt or not e.get("name"):
                continue
            faction = str(e.get("faction") or "shared").lower()
            rows.append({"name": e["name"], "faction": faction, "x": pt[0], "y": pt[1], "z": pt[2]})
        if rows:
            out[m["normalizedName"]] = rows
    return out



class TarkovAPI:
    def __init__(self, url: str, cache_file: Path):
        self.url = url
        self.static_url = STATIC_URL
        self.cache_file = cache_file
        self.extract_cache = cache_file.with_name("extracts_cache.json")
        self.diag_file = cache_file.with_name("api_diag.json")
        self.retry_delays = (1.5, 4.0)       # secondes entre deux tentatives
        self.min_tasks = MIN_TASKS
        self.min_extract_maps = MIN_EXTRACT_MAPS
        self.diag: list = []
        self._last: dict = {}

    # ── diagnostic (aide à comprendre un échec réseau)
    def _commit(self, what: str, n=None) -> None:
        entry = {"t": time.strftime("%H:%M:%S"), "what": what, **self._last, "n": n}
        self.diag.append(entry)
        del self.diag[:-30]
        try:
            self.diag_file.write_text(json.dumps(self.diag, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _cached(self, lang: str):
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if payload.get("lang") != lang or len(payload.get("tasks") or []) < self.min_tasks:
                return None            # cache d'une réponse incomplète (ancienne version) : ignoré
            return payload
        except (OSError, ValueError):
            return None

    def _variants(self, query: str, variables: dict):
        """Façons d'envoyer la requête GraphQL (en-têtes honnêtes) : POST, puis GET."""
        body = json.dumps({"query": query, "variables": variables}).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "TarkovCompanion/1.0"}
        qs = urllib.parse.urlencode({"query": query, "variables": json.dumps(variables)})
        get_url = self.url + ("&" if "?" in self.url else "?") + qs
        yield "POST", urllib.request.Request(self.url, data=body, headers=headers)
        if len(get_url) < 7000:
            yield "GET", urllib.request.Request(get_url, headers={k: v for k, v in headers.items() if k != "Content-Type"})

    def _once(self, query: str, variables: dict):
        status, data, first = None, {}, None
        for name, req in self._variants(query, variables):
            try:
                with urllib.request.urlopen(req, timeout=40) as resp:
                    status, data = resp.status, json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:   # GraphQL renvoie parfois 400/422/500 + corps JSON utile
                try:
                    status, data = exc.code, json.loads(exc.read().decode("utf-8"))
                except ValueError:
                    status, data = exc.code, {"errors": [f"HTTP {exc.code}"]}
            self.last_variant = name
            first = first or (status, data)
            if status == 200 and isinstance(data, dict) and data.get("data"):
                return status, data
            if status is not None and status >= 500 and status != 503:
                break
        return first if first else (status, data)

    def _post(self, query: str, lang, extra: dict | None = None, retries: bool = True) -> dict:
        """Une requête GraphQL avec réessais si le serveur annonce être indisponible."""
        last_exc = None
        data: dict = {}
        delays = self.retry_delays if retries else ()
        for attempt in range(len(delays) + 1):
            t0 = time.time()
            try:
                status, data = self._once(query, {**({"lang": lang} if lang is not None else {}), **(extra or {})})
                last_exc = None
            except (urllib.error.URLError, OSError) as exc:
                status, data, last_exc = None, {}, exc
            errors = data.get("errors") if isinstance(data, dict) else None
            self._last = {"http": status, "ms": int((time.time() - t0) * 1000), "attempt": attempt + 1,
                          "via": getattr(self, "last_variant", None), "errors": (json.dumps(errors, ensure_ascii=False)[:240] if errors else (str(last_exc)[:240] if last_exc else None))}
            has_data = isinstance(data, dict) and bool(data.get("data"))
            transient = last_exc is not None or (not has_data and (status is None or status >= 500 or TRANSIENT.search(json.dumps(errors or ""))))
            if not transient or attempt == len(delays):
                break
            time.sleep(delays[attempt])
        if last_exc is not None:
            raise last_exc
        return data if isinstance(data, dict) else {}

    def _collect(self, what: str, body: str, lang, retries: bool = True):
        """Toutes les quêtes pour `body` : par pages (limit/offset), sinon d'un seul bloc.

        Retourne (liste, erreurs). Une page qui échoue après réessais interrompt la collecte.
        """
        out, seen, errors, got_page = [], set(), None, False
        for offset in range(0, PAGE * 20, PAGE):
            data = self._post(_tasks_query(body, True, lang is not None), lang, {"limit": PAGE, "offset": offset}, retries)
            page = (data.get("data") or {}).get("tasks")
            self._commit(f"{what}@{offset}", None if page is None else len(page))
            if page is None:
                errors = data.get("errors") or errors
                break
            got_page = True
            fresh = [t for t in page if t and t.get("id") not in seen]
            for t in fresh:
                seen.add(t["id"])
                out.append(t)
            if len(page) < PAGE or not fresh:
                return out, None
        if got_page:
            return out, errors            # collecte interrompue en cours de route (ou plafond de pages)
        data = self._post(_tasks_query(body, False, lang is not None), lang, None, retries)   # pagination refusée : un seul bloc
        page = (data.get("data") or {}).get("tasks") or []
        self._commit(f"{what}-bloc", len(page))
        return [t for t in page if t], (data.get("errors") or errors)

    def _merge_zones(self, tasks: list, lang) -> bool:
        """Ajoute les positions d'objectifs (facultatif : un échec laisse les quêtes intactes)."""
        try:
            extra, _ = self._collect("zones", TASK_ZONES, lang, retries=False)
        except (urllib.error.URLError, OSError, ValueError):
            return False
        zones = {t["id"]: {o["id"]: o.get("zones") for o in (t.get("objectives") or []) if o and o.get("zones")}
                 for t in extra if t and t.get("id")}
        found = False
        for t in tasks:
            by_obj = zones.get(t.get("id")) or {}
            for o in t.get("objectives") or []:
                if o and by_obj.get(o.get("id")):
                    o["zones"] = by_obj[o["id"]]
                    found = True
        return found

    def _query(self, lang: str):
        """Essaie, du plus riche au plus simple : langue demandée, anglais, sans langue, moins de champs.

        Le serveur peut refuser une variante précise (langue indisponible, champ non géré) tout en
        acceptant les suivantes. Retourne (quêtes, positions_ok, langue_utilisée, niveau).
        """
        plan = []
        for i, lg in enumerate(_langs(lang)):
            plan.append((("tasks" if i == 0 else f"tasks[{lg or 'sans-langue'}]"), TASK_LIGHT, lg, "complet"))
        plan += [("tasks[réduit]", TASK_MID, None, "réduit"), ("tasks[minimal]", TASK_MIN, None, "minimal")]
        best, errors = [], None
        for n, (what, body, lg, level) in enumerate(plan):
            tasks, errs = self._collect(what, body, lg, retries=(n == 0))
            if len(tasks) >= self.min_tasks:
                return tasks, (level == "complet" and self._merge_zones(tasks, lg)), lg, level
            if len(tasks) > len(best):
                best = tasks
            errors = errs or errors
        if best:
            raise ValueError(f"réponse incomplète ({len(best)} quêtes reçues)")
        raise ValueError(friendly(errors))

    # ── fichiers statiques json.tarkov.dev (même source que le site tarkov.dev)
    def _get_json(self, path: str):
        req = urllib.request.Request(self.static_url + path, headers={
            "Accept": "application/json", "User-Agent": "TarkovCompanion/1.0"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                status, payload = resp.status, json.loads(resp.read().decode("utf-8"))
            self._last = {"http": status, "ms": int((time.time() - t0) * 1000), "attempt": 1, "errors": None}
            return payload
        except urllib.error.HTTPError as exc:
            self._last = {"http": exc.code, "ms": int((time.time() - t0) * 1000), "attempt": 1, "errors": f"HTTP {exc.code}"}
            raise
        except (urllib.error.URLError, OSError, ValueError) as exc:
            self._last = {"http": None, "ms": int((time.time() - t0) * 1000), "attempt": 1, "errors": str(exc)[:200]}
            raise

    def _static(self, path: str, lang):
        """Données d'un fichier statique, textes traduits. Retourne (data, langue_utilisée)."""
        data = self._get_json(path).get("data")
        if not isinstance(data, (dict, list)):
            raise ValueError("fichier statique vide")
        lang_used = None
        tables = []
        for lg in ([lang, "en"] if lang and lang != "en" else ["en"] if lang else []):
            try:
                tables.append((lg, self._get_json(f"{path}_{lg}").get("data") or {}))
            except (urllib.error.URLError, OSError, ValueError):
                continue
        if tables:
            lang_used = tables[0][0]
            dicts = [t for _, t in tables]

            def tr(v):
                if isinstance(v, str):
                    for d in dicts:
                        if v in d:
                            return d[v]
                    return v
                if isinstance(v, list):
                    return [tr(x) for x in v]
                if isinstance(v, dict):
                    return {k: tr(x) for k, x in v.items()}
                return v
            data = tr(data)
        return data, lang_used

    def _static_tasks(self, lang: str):
        tdata, lang_used = self._static("regular/tasks", lang)
        self._commit("statique:tasks", len(tdata.get("tasks") or {}))
        mdata, _ = self._static("regular/maps", lang)
        self._commit("statique:maps", len(mdata.get("maps") or {}))
        try:
            traders, _ = self._static("regular/traders", lang)
        except (urllib.error.URLError, OSError, ValueError):
            traders = {}
        mnames = {k: (v or {}).get("normalizedName") for k, v in (mdata.get("maps") or {}).items()}

        def mref(mid):
            return {"normalizedName": mnames[mid]} if mnames.get(mid) else None

        def mname(ref):
            """Nom normalisé d'une carte à partir d'un id, d'un dict ou d'un nom."""
            if isinstance(ref, dict):
                ref = ref.get("normalizedName") or ref.get("id")
            if not isinstance(ref, str):
                return None
            return mnames.get(ref) or (ref if ref in mnames.values() else None)

        def obj_out(o):
            omaps = [r for r in (mname(m) for m in o.get("maps") or []) if r]
            zones = []
            for z in o.get("zones") or []:
                if not isinstance(z, dict):
                    continue
                pt = _extract_point(z)
                zmap = mname(z.get("map")) or (omaps[0] if len(omaps) == 1 else None)
                if pt and zmap:
                    zone = {"map": {"normalizedName": zmap}, "position": {"x": pt[0], "y": pt[1], "z": pt[2]}}
                    outline = [{"x": p["x"], "z": p["z"]} for p in (z.get("outline") or [])
                               if isinstance(p, dict) and p.get("x") is not None and p.get("z") is not None]
                    if len(outline) >= 3:
                        zone["outline"] = outline
                    zones.append(zone)
            for loc in o.get("possibleLocations") or []:   # objets de quête : emplacements possibles
                lmap = mname(loc.get("map")) if isinstance(loc, dict) else None
                for p in (loc.get("positions") or []) if isinstance(loc, dict) else []:
                    if lmap and isinstance(p, dict) and p.get("x") is not None and p.get("z") is not None:
                        zones.append({"map": {"normalizedName": lmap}, "position": {"x": p["x"], "y": p.get("y") or 0, "z": p["z"]}})
            return {"id": o.get("id"), "type": o.get("type"), "description": o.get("description") or "",
                    "optional": bool(o.get("optional")),
                    "maps": [{"normalizedName": r} for r in omaps], "zones": zones}

        tasks = []
        for t in (tdata.get("tasks") or {}).values():
            tr_ = traders.get(t.get("trader")) if isinstance(traders, dict) else None
            tasks.append({"id": t.get("id"), "name": t.get("name") or "", "minPlayerLevel": t.get("minPlayerLevel"),
                          "kappaRequired": bool(t.get("kappaRequired")),
                          "trader": {"name": (tr_ or {}).get("name") or ""},
                          "map": mref(t.get("map")),
                          "objectives": [obj_out(o) for o in t.get("objectives") or []]})
        return tasks, lang_used

    def _static_extracts(self, lang: str):
        mdata, lang_used = self._static("regular/maps", lang)
        maps = normalize_extracts(list((mdata.get("maps") or {}).values()))
        self._commit("statique:extractions", sum(len(v) for v in maps.values()))
        return maps, lang_used

    def probe(self) -> list:
        """Petits tests isolés pour voir ce que le serveur accepte (aide au diagnostic)."""
        tests = [
            ("Le serveur répond", "{ __typename }", {}),
            ("Objets (items)", "{ items(limit: 1) { id } }", {}),
            ("Quêtes, sans langue", "{ tasks(limit: 1) { id name } }", {}),
            ("Quêtes, en anglais", "query($l: LanguageCode) { tasks(lang: $l, limit: 1) { id name } }", {"l": "en"}),
            ("Quêtes, en français", "query($l: LanguageCode) { tasks(lang: $l, limit: 1) { id name } }", {"l": "fr"}),
            ("Quêtes avec objectifs", "{ tasks(limit: 2) { id objectives { id description } } }", {}),
            ("Cartes", "{ maps { normalizedName } }", {}),
            ("Cartes avec extractions", "{ maps { normalizedName extracts { name } } }", {}),
        ]
        out = []
        for label, path in (("Fichier statique : quêtes", "regular/tasks"), ("Fichier statique : cartes", "regular/maps"),
                            ("Fichier statique : marchands", "regular/traders")):
            t0 = time.time()
            try:
                body = self._get_json(path)
                n = len((body.get("data") or {}).get("tasks") or (body.get("data") or {}).get("maps") or body.get("data") or {})
                ok, status, detail = n > 0, self._last.get("http"), f"{n} éléments"
            except (urllib.error.URLError, OSError, ValueError) as exc:
                ok, status, detail = False, getattr(exc, "code", None), str(exc)[:200]
            out.append({"test": label, "ok": ok, "http": status, "ms": int((time.time() - t0) * 1000), "detail": detail})
        for label, query, variables in tests:
            t0 = time.time()
            try:
                status, data = self._once(query, variables)
                errors = data.get("errors") if isinstance(data, dict) else None
                ok = bool(isinstance(data, dict) and data.get("data")) and not errors
                detail = json.dumps(errors, ensure_ascii=False)[:200] if errors else json.dumps(data.get("data"), ensure_ascii=False)[:90]
            except (urllib.error.URLError, OSError, ValueError) as exc:
                status, ok, detail = None, False, str(exc)[:200]
            out.append({"test": label, "ok": ok, "http": status, "ms": int((time.time() - t0) * 1000), "detail": detail})
        self.diag.extend({"t": time.strftime("%H:%M:%S"), "what": "test: " + r["test"], "http": r["http"], "ms": r["ms"],
                          "attempt": 1, "errors": None if r["ok"] else r["detail"], "n": None} for r in out)
        del self.diag[:-30]
        return out

    def fetch_tasks(self, lang: str = "fr", force: bool = False) -> dict:
        """Retourne {"tasks": [...], "source": "network|cache", "error": str|None, "lang_used", "level", ...}."""
        cached = self._cached(lang)
        if cached and not force and time.time() - cached.get("fetched", 0) < CACHE_TTL:
            return {"tasks": cached["tasks"], "source": "cache", "age": time.time() - cached["fetched"], "error": None,
                    "rich": cached.get("rich", False), "lang_used": cached.get("lang_used", lang), "level": cached.get("level", "complet")}
        try:
            try:
                tasks, lang_used = self._static_tasks(lang)
                if len(tasks) < self.min_tasks:
                    raise ValueError("liste de quêtes incomplète")
                rich, level = True, "statique"
            except (urllib.error.URLError, OSError, ValueError, AttributeError, TypeError):
                tasks, rich, lang_used, level = self._query(lang)
            self.cache_file.write_text(
                json.dumps({"lang": lang, "fetched": time.time(), "tasks": tasks, "rich": rich,
                            "lang_used": lang_used, "level": level}, ensure_ascii=False),
                encoding="utf-8",
            )
            return {"tasks": tasks, "source": "network", "age": 0, "error": None, "rich": rich, "lang_used": lang_used, "level": level}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            if cached:
                return {"tasks": cached["tasks"], "source": "cache", "age": time.time() - cached.get("fetched", 0),
                        "error": f"Hors-ligne, cache utilisé ({exc})", "rich": cached.get("rich", False),
                        "lang_used": cached.get("lang_used", lang), "level": cached.get("level", "complet")}
            return {"tasks": [], "source": "none", "age": 0, "error": f"API indisponible : {exc}", "rich": False,
                    "lang_used": None, "level": None}

    # ── extractions
    def _cached_extracts(self, lang: str):
        try:
            payload = json.loads(self.extract_cache.read_text(encoding="utf-8"))
            if payload.get("lang") != lang or len(payload.get("maps") or {}) < self.min_extract_maps:
                return None
            return payload
        except (OSError, ValueError):
            return None

    def fetch_extracts(self, lang: str = "fr", force: bool = False) -> dict:
        """Retourne {"maps": {nom_carte: [{name, faction, x, y, z}]}, "source", "error"}."""
        cached = self._cached_extracts(lang)
        if cached and not force and time.time() - cached.get("fetched", 0) < EXTRACT_TTL:
            return {"maps": cached["maps"], "source": "cache", "error": None}
        best: dict = {}
        last_errors = None
        try:
            maps, _ = self._static_extracts(lang)
            if len(maps) >= self.min_extract_maps:
                self.extract_cache.write_text(
                    json.dumps({"lang": lang, "fetched": time.time(), "maps": maps}, ensure_ascii=False), encoding="utf-8")
                return {"maps": maps, "source": "network", "error": None}
        except (urllib.error.URLError, OSError, ValueError, AttributeError, TypeError):
            pass
        try:
            first = True
            for lg in _langs(lang):
                for i, fields in enumerate(EXTRACT_FIELDS, 1):
                    data = self._post(_extract_query(fields, lg is not None), lg, None, retries=first)
                    first = False
                    maps = normalize_extracts((data.get("data") or {}).get("maps"))
                    self._commit(f"extracts[{lg or 'sans-langue'}]-{i}", sum(len(v) for v in maps.values()))
                    if len(maps) >= self.min_extract_maps:
                        self.extract_cache.write_text(
                            json.dumps({"lang": lang, "fetched": time.time(), "maps": maps}, ensure_ascii=False),
                            encoding="utf-8")
                        return {"maps": maps, "source": "network", "error": None}
                    if len(maps) > len(best):
                        best = maps
                    last_errors = data.get("errors") or last_errors
        except (urllib.error.URLError, OSError, ValueError) as exc:
            last_errors = [str(exc)]
        if cached:
            return {"maps": cached["maps"], "source": "cache", "error": f"Hors-ligne, cache utilisé ({friendly(last_errors)})"}
        if best:   # données partielles : utilisables mais jamais mises en cache
            return {"maps": best, "source": "network", "error": "Données d'extraction incomplètes"}
        return {"maps": {}, "source": "none", "error": f"Extractions indisponibles : {friendly(last_errors)}"}
