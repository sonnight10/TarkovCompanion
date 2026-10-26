import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tarkov_companion import parser  # noqa: E402
from tarkov_companion.config import Config  # noqa: E402
from tarkov_companion.core import Core  # noqa: E402
from tarkov_companion.maps import MapDB  # noqa: E402
from tarkov_companion.parser import Event  # noqa: E402
from tarkov_companion.watcher import LogWatcher, ScreenshotWatcher  # noqa: E402

QID = "5936d90786f7742b1420ba5b"


def notif_block(template: str, mtype: int, stamp: str = "2026-10-19 18:09:32.585 +00:00") -> str:
    body = {
        "type": "new_message",
        "eventId": "abc",
        "dialogId": "54cb50c76803fa8b248b4571",
        "message": {"_id": "x1", "uid": "54cb50c76803fa8b248b4571", "type": mtype,
                    "dt": 1, "templateId": template, "text": "{\"quoted\": \"}\"}"},
    }
    return f"{stamp}|1.0.0.0.1|Info|push-notifications|Got notification | ChatMessageReceived\n" + json.dumps(body, indent=4) + "\n"


class ParserTests(unittest.TestCase):
    def test_quest_started(self):
        ev = parser.parse_quest_block(notif_block(f"{QID} description", 10))
        self.assertEqual((ev.kind, ev.data), ("quest", {"quest_id": QID, "status": "started"}))
        self.assertEqual(ev.ts, "18:09:32")

    def test_quest_finished_and_failed(self):
        self.assertEqual(parser.parse_quest_block(notif_block(f"{QID} successMessageText", 12)).data["status"], "finished")
        self.assertEqual(parser.parse_quest_block(notif_block(f"{QID} failMessageText", 11)).data["status"], "failed")

    def test_status_from_type_when_suffix_unknown(self):
        self.assertEqual(parser.parse_quest_block(notif_block(f"{QID} inconnu", 12)).data["status"], "finished")

    def test_ignores_non_quest_messages(self):
        self.assertIsNone(parser.parse_quest_block(notif_block("5a0bdfc5bd1eae0a6c0001 welcome", 4)))
        self.assertIsNone(parser.parse_quest_block("2026-10-19 18:00:00.000 +00:00|x|Info|push-notifications|Ping"))

    def test_application_events(self):
        line = "2026-10-19 18:09:32.585 +00:00|1.0|Info|application|scene preset path:maps/factory4_day.bundle"
        evs = parser.parse_application_line(line)
        self.assertEqual([(e.kind, e.data["log_id"]) for e in evs], [("map", "factory4_day")])
        self.assertEqual(parser.parse_application_line("x|y|Info|application|GameStarted")[0].kind, "raid_start")
        self.assertEqual(parser.parse_application_line("x|y|Info|application|UserMatchOver")[0].kind, "raid_end")
        self.assertEqual(parser.parse_application_line("x|y|Info|application|bla bla")[:], [])

    def test_screenshot_name(self):
        name = "2026-10-19[18-09]_-263.1, 4.3, -2.7_0.0, 0.7071, 0.0, 0.7071_8.00 (0).png"
        pos = parser.parse_screenshot_name(name)
        self.assertAlmostEqual(pos["x"], -263.1)
        self.assertAlmostEqual(pos["z"], -2.7)
        self.assertAlmostEqual(pos["yaw"], 90.0, delta=0.01)  # 0.7071 n'est qu'une approximation de sqrt(2)/2
        self.assertIsNone(parser.parse_screenshot_name("capture.png"))


class MapTests(unittest.TestCase):
    def setUp(self):
        self.db = MapDB()

    def test_all_maps_loaded(self):
        self.assertGreaterEqual(len(self.db.maps), 12)
        for m in self.db.maps:
            self.assertEqual(len(m["transform"]), 4)
            self.assertIn(m["rotation"], (0, 90, 180, 270))

    def test_log_ids(self):
        self.assertEqual(self.db.resolve_log_id("bigmap"), "customs")
        self.assertEqual(self.db.resolve_log_id("Factory4_Night"), "factory")
        self.assertEqual(self.db.resolve_log_id("TarkovStreets"), "streets-of-tarkov")
        self.assertIsNone(self.db.resolve_log_id("inconnue"))

    def test_guess(self):
        self.assertEqual(self.db.guess(500, 0), "customs")
        self.assertIsNone(self.db.guess(99999, 99999))


class CoreAndWatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.core = Core(Config(self.tmp / "config.json"), MapDB(), self.tmp)

    def test_tolerant_map_ids(self):
        db = MapDB()
        self.assertEqual(db.resolve_log_id("bigmap_preset"), "customs")
        self.assertEqual(db.resolve_log_id("Factory4_Night"), "factory")
        self.assertIsNone(db.resolve_log_id("inconnue"))

    def test_stale_raid_start_does_not_mean_in_raid(self):
        self.core.handle_event(Event("raid_start", {"t": time.time() - 3600}, "09:00:00"))
        self.assertFalse(self.core.in_raid)
        self.core.handle_event(Event("raid_start", {"t": time.time()}, "10:00:00"))
        self.assertTrue(self.core.in_raid)

    def test_raid_expires(self):
        c = self.core
        c.handle_event(Event("raid_start", {}, "10:00:00"))
        c._raid["start"] -= 80 * 60
        self.assertFalse(c.snapshot()["in_raid"])

    def test_manual_raid_state(self):
        c = self.core
        c.set_raid_state(True)
        self.assertTrue(c.in_raid)
        c.set_raid_state(False)
        self.assertFalse(c.in_raid)

    def test_screenshot_corrects_map_and_marks_raid(self):
        c = self.core
        c.set_map("the-lab")                     # carte « par défaut » erronée
        c.handle_screenshot({"x": 0.0, "y": 4.3, "z": 0.0, "yaw": 0.0})
        self.assertNotEqual(c.current_map, "the-lab")
        self.assertTrue(c.in_raid)
        self.assertEqual(c._raid["map"], c.current_map)

    def test_unresolved_map_tracked(self):
        self.core.handle_event(Event("map", {"log_id": "carte_x"}, "10:00:00"))
        self.assertIn("carte_x", self.core.snapshot()["unresolved_maps"])

    def test_stats_and_backup_roundtrip(self):
        c = self.core
        c.set_map("customs")
        c.set_raid_state(True)
        c.handle_screenshot({"x": 10.0, "y": 1.0, "z": 20.0, "yaw": 0.0})
        c.set_raid_state(False)
        c.handle_event(Event("raid_start", {}, "10:00:00"))
        c.handle_event(Event("raid_end", {}, "10:20:00"))
        st = c.stats()
        self.assertEqual(st["total_raids"], 1)
        self.assertEqual(st["maps"][0]["map"], "customs")
        c.set_quest("q1", "started")
        c.mark_add("customs", 1, 2, "test")
        data = json.loads(json.dumps(c.export_all()))
        other = Core(Config(self.tmp / "c2.json"), MapDB(), Path(tempfile.mkdtemp()))
        counts = other.import_all(data)
        self.assertEqual(counts["quests"], 1)
        self.assertEqual(other.marks[0]["label"], "test")

    def test_import_rejects_foreign_or_bad_data(self):
        with self.assertRaises(ValueError):
            self.core.import_all({"app": "autre"})
        with self.assertRaises(ValueError):
            self.core.import_all([1, 2])
        n = self.core.import_all({"app": "tarkov-companion", "quests": {"a": "bogus", "b": "finished"},
                                  "marks": [{"id": "x", "map": "customs", "x": "evil", "z": 1}],
                                  "history": [{"id": "r", "points": [{"x": "a", "z": 1}, {"x": 1, "z": 2}]}]})
        self.assertEqual(n, {"quests": 1, "history": 1, "marks": 0})
        self.assertEqual(len(self.core.history[0]["points"]), 1)

    def test_reminder_config_validation(self):
        cfg = Config(self.tmp / "cfg2.json")
        cfg.update({"reminder_style": "boom", "reminder_by_map": {"customs": 30, "woods": 2, "x": "a"}})
        self.assertEqual(cfg.get("reminder_style"), "toast")
        self.assertEqual(cfg.get("reminder_by_map"), {"customs": 30})

    def test_quest_persistence(self):
        self.core.handle_event(parser.parse_quest_block(notif_block(f"{QID} description", 10)))
        again = Core(Config(self.tmp / "config.json"), MapDB(), self.tmp)
        self.assertEqual(again.quests[QID], "started")

    def test_raid_history_recorded_and_persisted(self):
        c = self.core
        c.handle_event(Event("raid_matched", {}, "10:00:00"))
        c.handle_event(Event("map", {"log_id": "bigmap"}, "10:00:01"))
        c.handle_event(Event("raid_start", {}, "10:00:02"))
        c.handle_screenshot({"x": 1.0, "y": 2.0, "z": 3.0, "yaw": 0, "file": "a"})
        c.handle_screenshot({"x": 5.0, "y": 2.0, "z": 9.0, "yaw": 0, "file": "b"})
        self.assertEqual(c.history_list(), [])           # raid pas fini : rien d'enregistré
        c.handle_event(Event("raid_end", {}, "10:20:00"))
        h = c.history_list()
        self.assertEqual((len(h), h[0]["map"], h[0]["points"]), (1, "customs", 2))
        again = Core(Config(self.tmp / "config.json"), MapDB(), self.tmp)
        r = again.history_get(h[0]["id"])
        self.assertEqual([p["x"] for p in r["points"]], [1.0, 5.0])
        self.assertTrue(again.history_delete(h[0]["id"]))
        self.assertEqual(again.history_list(), [])
        # un raid abandonné (nouvelle mise en relation) n'est pas enregistré
        c.handle_event(Event("raid_start", {}, "11:00:00")); c.handle_event(Event("raid_matched", {}, "11:01:00"))
        c.handle_event(Event("raid_end", {}, "11:02:00"))
        self.assertEqual(len(c.history_list()), 1)

    def test_log_file_names(self):
        from tarkov_companion import patterns as P
        for n, k in (("2026.10.19_18-00-00_1.0.0.0.1 push-notifications.log", "notif"), ("x push-notifications_000.log", "notif"),
                     ("x application.log", "app"), ("x application_001.log", "app"), ("x network-connection.log", None), ("x errors.log", None)):
            self.assertEqual(P.log_kind(n), k, n)

    def test_log_watcher_stats(self):
        from tarkov_companion.watcher import LogWatcher
        logs = self.tmp / "Logs"; sess = logs / "log_2026.10.19_18-00-00"; sess.mkdir(parents=True)
        (sess / "2026.10.19 push-notifications_000.log").write_text(notif_block(f"{QID} description", 10) + "\n", encoding="utf-8")
        got = []
        w = LogWatcher(str(logs), got.append)
        w.scan_once(first_pass=True)
        self.assertEqual(w.stats["session"], "log_2026.10.19_18-00-00")
        self.assertEqual((w.stats["chat_blocks"], w.stats["quest_events"]), (1, 1))
        self.assertEqual(w.stats["last_quest"]["status"], "started")
        self.assertEqual(w.stats["files"][0]["kind"], "notif")

    def test_duplicate_quest_event_ignored(self):
        ev = parser.parse_quest_block(notif_block(f"{QID} description", 10))
        self.core.handle_event(ev)
        self.core.handle_event(ev)
        self.assertEqual(len(self.core.events), 1)

    def test_log_watcher_end_to_end(self):
        logs = self.tmp / "Logs"
        session = logs / "log_2026.10.19_18-09-32_1.0"
        session.mkdir(parents=True)
        notif = session / "2026.10.19_18-09-32_1.0 push-notifications.log"
        app = session / "2026.10.19_18-09-32_1.0 application.log"
        notif.write_text(notif_block(f"{QID} description", 10), encoding="utf-8")
        app.write_text("2026-10-19 18:09:40.000 +00:00|1|Info|application|scene preset path:maps/bigmap.bundle\n", encoding="utf-8")
        w = LogWatcher(str(logs), self.core.handle_event)
        w.scan_once(first_pass=True)
        self.assertEqual(self.core.quests[QID], "started")
        self.assertEqual(self.core.current_map, "customs")
        # ajout en direct : fin de quête puis ligne incomplète
        with open(notif, "a", encoding="utf-8") as fh:
            fh.write(notif_block(f"{QID} successMessageText", 12))
        with open(app, "a", encoding="utf-8") as fh:
            fh.write("x|y|Info|application|GameStarted\npartial without newline")
        w.scan_once()
        self.assertEqual(self.core.quests[QID], "finished")
        self.assertTrue(self.core.in_raid)
        w.scan_once()  # rien de nouveau : pas de doublon
        self.assertEqual([e["kind"] for e in self.core.events].count("quest"), 2)

    def test_history_replay_rebuilds_quest_state(self):
        logs = self.tmp / "Logs"
        old = logs / "log_2026.10.01_10-00-00_1.0"
        new = logs / "log_2026.10.19_18-09-32_1.0"
        old.mkdir(parents=True); new.mkdir(parents=True)
        other = "5936d90786f7742b1420ba5c"
        (old / "x push-notifications.log").write_text(
            notif_block(f"{QID} description", 10) + notif_block(f"{QID} successMessageText", 12)
            + notif_block(f"{other} description", 10), encoding="utf-8")
        (new / "x push-notifications.log").write_text("", encoding="utf-8")
        import os
        os.utime(new, (time.time() + 5, time.time() + 5))   # la plus récente = session courante
        LogWatcher(str(logs), self.core.handle_event).scan_once(first_pass=True)
        self.assertEqual(self.core.quests, {QID: "finished", other: "started"})
        self.assertEqual(self.core.events, [])               # pas de bruit dans le journal

    def test_screenshot_watcher(self):
        shots = self.tmp / "Screenshots"
        shots.mkdir()
        (shots / "2026-10-19[17-00]_1.0, 1.0, 1.0_0.0, 0.0, 0.0, 1.0_8.00 (0).png").write_bytes(b"x")
        got = []
        w = ScreenshotWatcher(str(shots), got.append)
        w._seen = w._names()          # état initial (comme start())
        w.scan_once()
        self.assertEqual(got, [])      # anciennes captures ignorées
        time.sleep(0.01)
        (shots / "2026-10-19[18-09]_500.0, 5.0, -90.0_0.0, 0.0, 0.0, 1.0_8.00 (0).png").write_bytes(b"x")
        w.scan_once()
        self.assertEqual(len(got), 1)
        self.core.handle_screenshot(got[0])
        self.assertEqual(self.core.current_map, "customs")
        self.assertEqual(self.core.position["x"], 500.0)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.shots = self.tmp / "Screenshots"
        self.shots.mkdir()
        self.old = self.shots / "2026-10-01[10-00]_1.0, 1.0, 1.0_0.0, 0.0, 0.0, 1.0_8.00 (0).png"
        self.old.write_bytes(b"x")                                   # existait avant l'application
        self.w = ScreenshotWatcher(str(self.shots), lambda pos: None)
        self.w._seen = self.w._names()

    def test_only_session_screenshots_are_deleted(self):
        new = self.shots / "2026-10-19[18-09]_5.0, 5.0, 5.0_0.0, 0.0, 0.0, 1.0_8.00 (0).png"
        perso = self.shots / "vacances.png"                          # format inconnu : jamais touché
        new.write_bytes(b"x"); perso.write_bytes(b"x")
        self.w.scan_once()
        self.assertEqual(self.w.cleanup(), 1)
        self.assertFalse(new.exists())
        self.assertTrue(self.old.exists())
        self.assertTrue(perso.exists())
        self.assertEqual(self.w.cleanup(), 0)                         # rien de plus à supprimer

    def test_path_traversal_is_refused(self):
        victim = self.tmp / "secret.png"
        victim.write_bytes(b"x")
        self.w.session_files.add("../secret.png")
        self.w.cleanup()
        self.assertTrue(victim.exists())
        self.assertNotIn("../secret.png", self.w.session_files)

    def test_raid_end_hook_and_reminder(self):
        from tarkov_companion.app import reminder_due
        core = Core(Config(self.tmp / "config.json"), MapDB(), self.tmp)
        calls = []
        core.on_raid_end = lambda: calls.append(1)
        core.handle_event(parser.Event("raid_end", {}, "10:00:00"))   # pas en raid : rien
        self.assertEqual(calls, [])
        core.handle_event(parser.Event("raid_start", {}, "10:00:01"))
        core.handle_event(parser.Event("raid_end", {}, "10:10:00"))
        self.assertEqual(calls, [1])
        self.assertTrue(reminder_due(100, 90, 10, True))
        self.assertFalse(reminder_due(100, 95, 10, True))
        self.assertFalse(reminder_due(100, 0, 10, False))             # jamais hors raid
        self.assertFalse(reminder_due(100, 0, 0, True))               # 0 = désactivé


if __name__ == "__main__":
    unittest.main(verbosity=2)
