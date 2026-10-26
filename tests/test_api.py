"""Tests du pont Python (sans fenêtre) et du client tarkov.dev (faux serveur local)."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HOME = tempfile.mkdtemp()
os.environ["TARKOV_COMPANION_HOME"] = HOME

from tarkov_companion.app import Api  # noqa: E402
from tarkov_companion.tarkov_api import TarkovAPI  # noqa: E402

ZONE = {"map": {"normalizedName": "customs"}, "position": {"x": 1, "y": 2, "z": 3}}
TASKS = [{"id": "a" * 24, "name": "Test", "trader": {"name": "Prapor"},
          "objectives": [{"id": "o1", "description": "Tuer", "zones": [ZONE]}]}]
BIG = [{"id": f"{i:024d}", "name": f"Q{i}", "trader": {"name": "Prapor"},
        "objectives": [{"id": f"o{i}", "description": "x", "zones": [ZONE]}]} for i in range(250)]


class FakeServer(BaseHTTPRequestHandler):
    mode = "rich_ok"   # rich_ok | rich_rejected | no_paging | paged | down | flaky
    calls = []
    flaky_left = 0     # nombre de réponses « serveur indisponible » avant de redevenir normal
    reject = None      # fonction(corps_de_requête) -> True pour répondre « serveur indisponible » (HTTP 422)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if FakeServer.reject and FakeServer.reject(body):
            FakeServer.calls.append("rejected")
            raw = json.dumps({"errors": ["GraphQL server unavailable. Try again later."]}).encode()
            self.send_response(422)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if FakeServer.mode == "flaky" and FakeServer.flaky_left > 0:
            FakeServer.flaky_left -= 1
            FakeServer.calls.append("flaky")
            raw = json.dumps({"errors": ["GraphQL server unavailable. Try again later."]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        if "extracts" in body["query"]:
            return self._extracts(body["query"])
        zones = "TaskObjectiveBasic" in body["query"]
        paged = "$limit" in body["query"]
        FakeServer.calls.append("zones" if zones else "tasks")
        if FakeServer.mode == "down":
            self.send_response(500); self.end_headers(); return
        if zones and FakeServer.mode == "rich_rejected":
            payload, code = {"errors": [{"message": "Unknown type TaskObjectiveShoot"}]}, 400
        elif paged and FakeServer.mode == "no_paging":
            payload, code = {"errors": [{"message": "Unknown argument limit on field tasks"}]}, 400
        elif paged and FakeServer.mode == "paged":
            v = body["variables"]
            payload, code = {"data": {"tasks": BIG[v["offset"]:v["offset"] + v["limit"]]}}, 200
        elif FakeServer.mode == "paged":
            payload, code = {"data": {"tasks": BIG}}, 200
        else:
            payload, code = {"data": {"tasks": TASKS}}, 200
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _extracts(self, query):
        FakeServer.calls.append("extracts")
        if FakeServer.mode == "down":
            self.send_response(500); self.end_headers(); return
        if "position" in query and FakeServer.mode == "extract_only_outline":
            payload, code = {"errors": [{"message": "Cannot query field position"}]}, 400
        else:
            payload, code = {"data": {"maps": [{"normalizedName": "customs", "extracts": [
                {"name": "ZB-1011", "faction": "pmc", "position": {"x": 10, "y": 1, "z": 20},
                 "outline": [{"x": 0, "y": 0, "z": 0}]},
                {"name": "Dorms Car", "faction": "shared", "position": None,
                 "outline": [{"x": 100, "y": 2, "z": 40}, {"x": 120, "y": 2, "z": 60}]},
                {"name": "Sans position", "faction": "scav", "position": None, "outline": []},
            ]}]}}, 200
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *a):
        pass


class ApiBridgeTests(unittest.TestCase):
    def test_bootstrap_and_demo(self):
        api = Api()
        boot = api.bootstrap()
        self.assertEqual(len(boot["maps"]), 13)
        self.assertIn("watch", boot)
        api.demo()
        r = api.poll(0)
        self.assertEqual(r["state"]["current_map"], "customs")
        self.assertTrue(r["state"]["in_raid"])
        self.assertEqual(len(r["state"]["trail"]), 5)
        self.assertIsNotNone(r["state"]["position"]["t"])
        api.shutdown()

    def test_config_and_quests(self):
        api = Api()
        res = api.save_config({"follow_player": False, "inconnu": 1, "language": 5})
        self.assertFalse(res["config"]["follow_player"])
        self.assertNotIn("inconnu", res["config"])
        self.assertEqual(res["config"]["language"], "fr")   # mauvais type refusé
        api.set_quest_status("b" * 24, "finished")
        self.assertEqual(api.poll(0)["state"]["quests"]["b" * 24], "finished")
        api.set_quest_status("b" * 24, None)
        self.assertNotIn("b" * 24, api.poll(0)["state"]["quests"])

    def test_reminder_and_cleanup_config(self):
        api = Api()
        for bad in (3, 601, -5, "10", True):
            self.assertEqual(api.save_config({"reminder_seconds": bad})["config"]["reminder_seconds"], 0, bad)
        self.assertEqual(api.save_config({"reminder_seconds": 30})["config"]["reminder_seconds"], 30)
        self.assertEqual(api.save_config({"reminder_seconds": 0})["config"]["reminder_seconds"], 0)
        self.assertTrue(api.save_config({"cleanup_screenshots": True})["config"]["cleanup_screenshots"])
        self.assertEqual(api.cleanup_screenshots(), {"deleted": 0})   # pas de watcher : rien à faire

    def test_map_style_config(self):
        api = Api()
        self.assertEqual(api.save_config({"map_style": "detail"})["config"]["map_style"], "detail")
        self.assertEqual(api.save_config({"map_style": "3d"})["config"]["map_style"], "detail")   # valeur inconnue refusée
        self.assertEqual(api.save_config({"map_style": "schema"})["config"]["map_style"], "schema")

    def test_tiles_data(self):
        import json
        from tarkov_companion.maps import MapDB
        maps = {m["id"]: m for m in MapDB().maps}
        for mid in ("customs", "the-lab", "icebreaker"):
            t = maps[mid]["tiles"]
            self.assertIn("{z}/{x}/{y}", t["url"])
            self.assertTrue(t["url"].startswith("https://assets.tarkov.dev/"))
        self.assertNotIn("tiles", maps["lighthouse"])    # pas de version détaillée

    def test_map_svg_rejects_unknown(self):
        self.assertIsNone(Api().get_map_svg("../../etc/passwd")["svg"])

    def test_public_surface(self):
        public = sorted(n for n in dir(Api()) if not n.startswith("_"))
        self.assertEqual(public, ["add_mark", "bootstrap", "check_update", "cleanup_screenshots", "clear_trail", "delete_mark", "delete_raid", "demo", "detect_paths", "download_update",
                                  "export_backup", "get_diagnostics", "get_extracts", "get_history", "get_log_status", "get_map_svg", "get_marks", "get_raid",
                                  "get_raid_diag", "get_stats", "get_tasks", "import_backup", "install_update", "open_update_folder", "open_url",
                                  "pick_folder", "poll", "run_probe", "save_config", "set_map", "set_overlay", "set_quest_status", "set_raid_state", "shutdown"])

    def test_theme_accent_lang_config(self):
        api = Api()
        for k, good, bad in (("theme", "light", "sepia"), ("accent", "violet", "rose"), ("ui_lang", "en", "de")):
            self.assertEqual(api.save_config({k: good})["config"][k], good)
            self.assertEqual(api.save_config({k: bad})["config"][k], good)

    def test_open_url_allowlist(self):
        from tarkov_companion.app import link_allowed
        self.assertTrue(link_allowed("https://github.com/the-hideout/tarkov-dev"))
        self.assertTrue(link_allowed("https://creativecommons.org/licenses/by-nc-sa/4.0/"))
        for bad in ("http://github.com/x", "https://evil.com/github.com", "https://github.com.evil.com/", "file:///etc/passwd", "javascript:alert(1)", ""):
            self.assertFalse(link_allowed(bad), bad)
        self.assertFalse(Api().open_url("https://evil.example/"))

    def test_marks_and_history_api(self):
        api = Api()
        m = api.add_mark("customs", 10, -20, "  Cache  ")
        self.assertEqual((m["map"], m["label"]), ("customs", "Cache"))
        self.assertIsNone(api.add_mark("inconnue", 0, 0, "x"))
        self.assertIsNone(api.add_mark("customs", "abc", 0, "x"))
        self.assertIsNone(api.add_mark("customs", 1e9, 0, "x"))
        self.assertIn(m["id"], [x["id"] for x in api.get_marks()])
        self.assertTrue(api.delete_mark(m["id"]))
        self.assertFalse(api.delete_mark(m["id"]))
        self.assertIsNone(api.get_raid("nope"))
        self.assertFalse(api.delete_raid("nope"))


class StaticObjectiveTests(unittest.TestCase):
    """Les positions d'objectifs des fichiers statiques : position, contour seul, emplacements d'objets."""

    def test_zones_outline_and_possible_locations(self):
        api = TarkovAPI("http://127.0.0.1:1/graphql", Path(tempfile.mkdtemp()) / "t.json")
        api.min_tasks = 1
        files = {
            "regular/tasks": {"data": {"tasks": {"t1": {"id": "t1", "name": "Q", "minPlayerLevel": 3, "trader": "tr1", "map": "m1", "objectives": [
                {"id": "o1", "type": "mark", "description": "Marquer", "optional": False, "maps": ["m1"],
                 "zones": [{"map": "m1", "position": {"x": 10, "y": 1, "z": 20}}]},
                {"id": "o2", "type": "visit", "description": "Aller", "maps": ["m1"],
                 "zones": [{"map": "m1", "outline": [{"x": 0, "y": 0, "z": 0}, {"x": 10, "y": 0, "z": 0}, {"x": 10, "y": 0, "z": 10}, {"x": 0, "y": 0, "z": 10}]}]},
                {"id": "o3", "type": "findQuestItem", "description": "Objet", "maps": ["m1"], "zones": [],
                 "possibleLocations": [{"map": "m1", "positions": [{"x": 5, "y": 1, "z": 6}, {"x": 7, "y": 1, "z": 8}]}]},
                {"id": "o4", "type": "shoot", "description": "Tuer", "maps": ["m1"]}]}}}},
            "regular/maps": {"data": {"maps": {"m1": {"normalizedName": "customs"}}}},
            "regular/traders": {"data": {"tr1": {"name": "Prapor"}}},
        }
        api._get_json = lambda path: files[path] if path in files else (_ for _ in ()).throw(ValueError("x"))
        tasks, _ = api._static_tasks("en")
        objs = {o["id"]: o for o in tasks[0]["objectives"]}
        self.assertEqual(objs["o1"]["zones"][0]["position"], {"x": 10, "y": 1, "z": 20})
        self.assertEqual(objs["o2"]["zones"][0]["position"]["x"], 5.0)          # centre du contour
        self.assertEqual(len(objs["o2"]["zones"][0]["outline"]), 4)
        self.assertEqual(len(objs["o3"]["zones"]), 2)                           # emplacements possibles
        self.assertEqual(objs["o4"]["zones"], [])                               # pas de lieu : aucune zone inventée
        self.assertEqual(objs["o1"]["maps"], [{"normalizedName": "customs"}])
        self.assertEqual(tasks[0]["zones_ok"] if "zones_ok" in tasks[0] else True, True)


class TarkovAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeServer)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}/graphql"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        FakeServer.mode, FakeServer.calls, FakeServer.flaky_left, FakeServer.reject = "rich_ok", [], 0, None

    def tearDown(self):
        FakeServer.reject = None

    def api(self):
        a = TarkovAPI(self.url, Path(tempfile.mkdtemp()) / "cache.json")
        a.retry_delays = (0, 0)       # pas d'attente dans les tests
        a.min_tasks = 1               # le faux serveur n'envoie qu'une quête
        a.min_extract_maps = 1
        return a

    def test_light_query_then_zones(self):
        FakeServer.mode, FakeServer.calls = "rich_ok", []
        r = self.api().fetch_tasks("fr")
        self.assertEqual((r["source"], r["rich"], FakeServer.calls), ("network", True, ["tasks", "zones"]))
        self.assertEqual(r["tasks"][0]["objectives"][0]["zones"], [ZONE])

    def test_zones_are_optional(self):
        FakeServer.mode, FakeServer.calls = "rich_rejected", []
        r = self.api().fetch_tasks("fr")
        self.assertEqual((r["source"], r["rich"]), ("network", False))   # quêtes OK même sans zones
        self.assertEqual([t["id"] for t in r["tasks"]], [TASKS[0]["id"]])

    def test_pagination_collects_every_page(self):
        FakeServer.mode, FakeServer.calls = "paged", []
        r = self.api().fetch_tasks("fr")
        self.assertEqual(len(r["tasks"]), 250)
        self.assertEqual(len({t["id"] for t in r["tasks"]}), 250)
        self.assertGreaterEqual(FakeServer.calls.count("tasks"), 3)       # 3 pages de 100
        self.assertTrue(r["rich"])

    def test_falls_back_to_single_block_when_paging_is_refused(self):
        FakeServer.mode, FakeServer.calls = "no_paging", []
        r = self.api().fetch_tasks("fr")
        self.assertEqual(len(r["tasks"]), 1)
        self.assertEqual(r["source"], "network")

    def test_offline_uses_cache_then_reports_error(self):
        a = self.api()
        FakeServer.mode = "rich_ok"
        a.fetch_tasks("fr")
        FakeServer.mode = "down"
        r = a.fetch_tasks("fr", force=True)
        self.assertEqual(r["source"], "cache")
        self.assertIn("Hors-ligne", r["error"])
        r2 = self.api().fetch_tasks("fr")      # pas de cache du tout
        self.assertEqual((r2["source"], r2["tasks"]), ("none", []))
        self.assertIn("indisponible", r2["error"])


class ResilienceTests(TarkovAPITests):
    def test_transient_errors_are_retried(self):
        FakeServer.mode, FakeServer.calls, FakeServer.flaky_left = "flaky", [], 2
        r = self.api().fetch_tasks("fr")
        self.assertEqual(r["source"], "network")
        self.assertEqual(FakeServer.calls[:3], ["flaky", "flaky", "tasks"])

    def test_persistent_outage_gives_friendly_message(self):
        FakeServer.mode, FakeServer.calls, FakeServer.flaky_left = "flaky", [], 999
        r = self.api().fetch_tasks("fr")
        self.assertEqual((r["source"], r["tasks"]), ("none", []))
        self.assertIn("momentanément indisponible", r["error"])
        self.assertNotIn("GraphQL", r["error"])
        e = self.api().fetch_extracts("fr")
        self.assertIn("momentanément indisponible", e["error"])
        FakeServer.flaky_left = 0

    def test_incomplete_answer_is_rejected_and_not_cached(self):
        FakeServer.mode, FakeServer.calls, FakeServer.flaky_left = "rich_ok", [], 0
        a = self.api()
        a.min_tasks = 30                                  # 1 quête reçue < 30 : réponse suspecte
        r = a.fetch_tasks("fr")
        self.assertEqual(r["tasks"], [])
        self.assertIn("incomplète", r["error"])
        self.assertFalse(a.cache_file.exists())

    def test_stale_incomplete_cache_is_ignored(self):
        FakeServer.mode, FakeServer.calls, FakeServer.flaky_left = "rich_ok", [], 0
        a = self.api()
        a.cache_file.write_text(json.dumps({"lang": "fr", "fetched": time.time(), "tasks": TASKS, "rich": True}), encoding="utf-8")
        a.min_tasks = 30                       # 1 quête en cache : cache d'une réponse incomplète
        r = a.fetch_tasks("fr")
        self.assertNotEqual(r["source"], "cache")
        self.assertIn("tasks", FakeServer.calls)         # le réseau a bien été réinterrogé

    def test_diagnostics_are_recorded(self):
        FakeServer.mode, FakeServer.calls, FakeServer.flaky_left = "flaky", [], 1
        a = self.api()
        a.fetch_tasks("fr")
        self.assertTrue(a.diag)
        self.assertEqual(a.diag[0]["what"], "tasks@0")
        self.assertEqual(a.diag[0]["n"], 1)
        self.assertTrue(a.diag_file.exists())
        FakeServer.flaky_left = 0


class FallbackLadderTests(TarkovAPITests):
    """Le serveur masque ses refus derrière « indisponible » : on doit retomber sur une variante acceptée."""

    def test_french_refused_falls_back_to_english(self):
        FakeServer.reject = lambda b: b["variables"].get("lang") == "fr"
        r = self.api().fetch_tasks("fr")
        self.assertEqual((r["source"], r["lang_used"], r["level"]), ("network", "en", "complet"))
        self.assertEqual(len(r["tasks"]), 1)

    def test_language_argument_refused_falls_back_to_server_default(self):
        FakeServer.reject = lambda b: "$lang" in b["query"]
        r = self.api().fetch_tasks("fr")
        self.assertEqual((r["source"], r["lang_used"], r["level"]), ("network", None, "complet"))

    def test_reduced_fields_when_objectives_are_refused(self):
        FakeServer.reject = lambda b: "objectives" in b["query"]
        r = self.api().fetch_tasks("fr")
        self.assertEqual((r["source"], r["level"], r["rich"]), ("network", "minimal", False))
        self.assertEqual(len(r["tasks"]), 1)

    def test_extracts_fall_back_to_english(self):
        FakeServer.reject = lambda b: b["variables"].get("lang") == "fr"
        r = self.api().fetch_extracts("fr")
        self.assertIn("customs", r["maps"])
        self.assertIsNone(r["error"])

    def test_probe_reports_each_check(self):
        res = self.api().probe()
        self.assertEqual(len(res), 11)
        self.assertTrue(all(r["ok"] for r in res if not r["test"].startswith("Fichier statique")))
        FakeServer.reject = lambda b: b["variables"].get("l") == "fr"
        res = self.api().probe()
        by = {r["test"]: r for r in res}
        self.assertFalse(by["Quêtes, en français"]["ok"])
        self.assertEqual(by["Quêtes, en français"]["http"], 422)
        self.assertIn("unavailable", by["Quêtes, en français"]["detail"])
        self.assertTrue(by["Quêtes, en anglais"]["ok"])


class ExtractTests(TarkovAPITests):
    def test_extracts_position_and_outline_centroid(self):
        FakeServer.mode, FakeServer.calls = "rich_ok", []
        r = self.api().fetch_extracts("fr")
        rows = {e["name"]: e for e in r["maps"]["customs"]}
        self.assertEqual(set(rows), {"ZB-1011", "Dorms Car"})          # l'entrée sans coordonnées est ignorée
        self.assertEqual((rows["ZB-1011"]["x"], rows["ZB-1011"]["z"]), (10, 20))
        self.assertEqual((rows["Dorms Car"]["x"], rows["Dorms Car"]["z"]), (110, 50))   # centroïde du contour
        self.assertEqual(rows["Dorms Car"]["faction"], "shared")

    def test_extracts_fallback_to_outline(self):
        FakeServer.mode, FakeServer.calls = "extract_only_outline", []
        r = self.api().fetch_extracts("fr")
        self.assertIn("Dorms Car", [e["name"] for e in r["maps"]["customs"]])
        self.assertGreater(FakeServer.calls.count("extracts"), 1)

    def test_extracts_offline(self):
        a = self.api()
        FakeServer.mode = "rich_ok"
        a.fetch_extracts("fr")
        FakeServer.mode = "down"
        self.assertEqual(a.fetch_extracts("fr", force=True)["source"], "cache")
        r = self.api().fetch_extracts("fr")
        self.assertEqual((r["source"], r["maps"]), ("none", {}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
