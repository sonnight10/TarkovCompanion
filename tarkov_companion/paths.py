"""Détection automatique des dossiers Logs et Screenshots de Tarkov."""
from __future__ import annotations

import os
import string
from pathlib import Path

try:  # Windows uniquement
    import winreg  # type: ignore
except ImportError:  # pragma: no cover
    winreg = None

LOG_FOLDER_NAMES = ["EFT (live)", "Escape from Tarkov", "EFT"]


def _registry_install_dirs() -> list[Path]:
    found: list[Path] = []
    if winreg is None:
        return found
    subkeys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\EscapeFromTarkov",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\EscapeFromTarkov",
    ]
    for sub in subkeys:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, sub) as key:
                value, _ = winreg.QueryValueEx(key, "InstallLocation")
                if value:
                    found.append(Path(value))
        except OSError:
            continue
    return found


def detect_logs_dir() -> str:
    candidates: list[Path] = [p / "Logs" for p in _registry_install_dirs()]
    roots: list[Path] = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            roots.append(Path(f"{letter}:/Battlestate Games"))
        roots.append(Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Battlestate Games")
    else:  # utile pour les tests / Wine
        roots.append(Path.home() / "Battlestate Games")
    for root in roots:
        for name in LOG_FOLDER_NAMES:
            candidates.append(root / name / "Logs")
    for cand in candidates:
        try:
            if cand.is_dir():
                return str(cand)
        except OSError:
            continue
    return ""


def detect_screenshots_dir() -> str:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    candidates = [
        home / "Documents" / "Escape from Tarkov" / "Screenshots",
        home / "OneDrive" / "Documents" / "Escape from Tarkov" / "Screenshots",
        home / "OneDrive" / "Documents" / "Escape From Tarkov" / "Screenshots",
        home / "Documents" / "Escape From Tarkov" / "Screenshots",
    ]
    for cand in candidates:
        try:
            if cand.is_dir():
                return str(cand)
        except OSError:
            continue
    return ""
