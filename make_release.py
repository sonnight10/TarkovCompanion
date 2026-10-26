"""Prépare une nouvelle version à publier : python make_release.py
1. change __version__ dans tarkov_companion/__init__.py (ex. 1.1.0), 2. lance build_exe.bat,
3. lance ce script : il crée TarkovCompanion-<version>.zip (+ .sha256) à partir de dist/TarkovCompanion,
4. sur GitHub : Releases > Draft a new release, tag v<version>, joins le .zip (et le .sha256), Publish."""
import hashlib
import re
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
version = re.search(r'__version__ = "([^"]+)"', (root / "tarkov_companion" / "__init__.py").read_text(encoding="utf-8")).group(1)
folder = root / "dist" / "TarkovCompanion"
if not (folder / "TarkovCompanion.exe").exists():
    sys.exit("dist/TarkovCompanion/TarkovCompanion.exe introuvable : lance d'abord build_exe.bat.")
out = root / "dist" / f"TarkovCompanion-{version}"
zip_path = Path(shutil.make_archive(str(out), "zip", root_dir=folder.parent, base_dir="TarkovCompanion"))
sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
(zip_path.parent / (zip_path.name + ".sha256")).write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")
print(f"Version {version}\nFichier : {zip_path}\nSHA-256 : {sha}\nPublie-le comme Release GitHub avec le tag v{version}.")
