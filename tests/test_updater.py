import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tarkov_companion import updater  # noqa: E402


def release(tag="v1.1.0", digest=None, name="TarkovCompanion-1.1.0.zip", **kw):
    a = {"name": name, "browser_download_url": f"https://github.com/o/r/releases/download/{tag}/{name}", "size": 10}
    if digest:
        a["digest"] = "sha256:" + digest
    return {"tag_name": tag, "assets": [a], "body": "notes", "html_url": "https://github.com/o/r/releases/tag/" + tag, **kw}


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)


class UpdaterTests(unittest.TestCase):
    def test_versions(self):
        self.assertEqual(updater.parse_version("v1.2.3"), (1, 2, 3))
        self.assertIsNone(updater.parse_version("1.2.3-beta"))
        self.assertIsNone(updater.parse_version("latest"))
        self.assertGreater(updater.parse_version("1.10.0"), updater.parse_version("1.9.9"))

    def test_hosts(self):
        self.assertTrue(updater.host_ok("https://github.com/a/b", updater.DOWNLOAD_HOSTS))
        self.assertTrue(updater.host_ok("https://objects.githubusercontent.com/x", updater.DOWNLOAD_HOSTS))
        self.assertFalse(updater.host_ok("http://github.com/a", updater.DOWNLOAD_HOSTS))
        self.assertFalse(updater.host_ok("https://evilgithub.com/a", updater.DOWNLOAD_HOSTS))
        self.assertFalse(updater.host_ok("https://github.com.evil.io/a", updater.DOWNLOAD_HOSTS))

    def test_pick_release_ignores_draft_prerelease_and_non_zip(self):
        self.assertIsNone(updater.pick_release(release(prerelease=True)))
        self.assertIsNone(updater.pick_release(release(draft=True)))
        r = release(); r["assets"][0]["name"] = "notes.txt"
        self.assertIsNone(updater.pick_release(r))
        self.assertEqual(updater.pick_release(release(digest="a" * 64))["sha256"], "a" * 64)

    def test_check_available_or_not(self):
        import io, json
        def fake(rel):
            return mock.patch.object(updater, "_open", return_value=io.BytesIO(json.dumps(rel).encode()))
        with fake(release("v1.1.0")):
            r = updater.check("o/r", "1.0.0"); self.assertTrue(r["available"]); self.assertEqual(r["latest"], "1.1.0")
        with fake(release("v1.0.0")):
            self.assertFalse(updater.check("o/r", "1.0.0")["available"])
        self.assertIn("configuré", updater.check("pas un depot", "1.0.0")["error"])

    def test_download_requires_and_checks_hash(self):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "src.zip"; make_zip(src, {"TarkovCompanion.exe": "x"})
        data = src.read_bytes()
        good = hashlib.sha256(data).hexdigest()

        class R:
            def __init__(s): s.b = data
            def read(s, n=-1):
                out, s.b = s.b[:n], s.b[n:]; return out
            def __enter__(s): return s
            def __exit__(s, *a): pass
        info = pick = updater.pick_release(release(digest=good))
        with mock.patch.object(updater, "_open", side_effect=lambda *a, **k: R()):
            p = updater.download(info, tmp / "d"); self.assertTrue(p.exists())
            bad = dict(info, sha256="0" * 64)
            with self.assertRaises(ValueError): updater.download(bad, tmp / "d2")
            nosha = dict(info, sha256=None, sha_url=None)
            with self.assertRaises(ValueError): updater.download(nosha, tmp / "d3")
        with self.assertRaises(ValueError): updater.download(dict(info, url="https://evil.example/x.zip"), tmp / "d4")

    def test_validate_zip(self):
        tmp = Path(tempfile.mkdtemp())
        ok = tmp / "ok.zip"; make_zip(ok, {"TarkovCompanion/TarkovCompanion.exe": "x", "TarkovCompanion/a.dll": "y"})
        self.assertEqual(updater.validate_zip(ok), "TarkovCompanion")
        flat = tmp / "flat.zip"; make_zip(flat, {"TarkovCompanion.exe": "x"})
        self.assertEqual(updater.validate_zip(flat), "")
        evil = tmp / "evil.zip"; make_zip(evil, {"TarkovCompanion.exe": "x", "../../x.bat": "y"})
        with self.assertRaises(ValueError): updater.validate_zip(evil)
        noexe = tmp / "noexe.zip"; make_zip(noexe, {"a.txt": "x"})
        with self.assertRaises(ValueError): updater.validate_zip(noexe)

    def test_apply_script(self):
        tmp = Path(tempfile.mkdtemp())
        s = updater.make_apply_script(tmp / "u.zip", "TarkovCompanion", Path("C:/Apps/TC"), "TarkovCompanion.exe", 1234, tmp / "w")
        txt = s.read_text()
        self.assertIn("PID eq 1234", txt)
        self.assertIn("Expand-Archive", txt)
        self.assertIn("TarkovCompanion.exe", txt)


if __name__ == "__main__":
    unittest.main()
