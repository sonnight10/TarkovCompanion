"""Mises à jour via les « Releases » GitHub du dépôt de l'application.

Principe : on publie une nouvelle version sur GitHub (tag « v1.1.0 » + un .zip du dossier compilé).
L'application compare son numéro de version à celui de la dernière Release, propose la mise à jour,
télécharge le .zip, vérifie son empreinte SHA-256 puis le remplace au redémarrage.

Sécurité : seuls des hôtes GitHub en HTTPS sont contactés (redirections comprises), l'empreinte SHA-256
publiée par GitHub (ou un fichier .sha256 joint) est obligatoire, et le contenu du .zip est contrôlé
avant toute installation. Rien n'est installé sans l'accord du joueur.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

from . import APP_NAME, __version__

API_HOSTS = ("api.github.com",)
DOWNLOAD_HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
MAX_ZIP = 400 * 1024 * 1024
MAX_UNPACKED = 1500 * 1024 * 1024
UA = {"User-Agent": f"{APP_NAME}-updater", "Accept": "application/vnd.github+json"}


def parse_version(v: str) -> Optional[tuple]:
    """« v1.2.3 » -> (1, 2, 3). Les préversions (1.2.3-beta) sont refusées."""
    m = re.fullmatch(r"v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})", str(v or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def host_ok(url: str, hosts: tuple) -> bool:
    try:
        u = urllib.parse.urlparse(url)
    except ValueError:
        return False
    h = (u.hostname or "").lower()
    return u.scheme == "https" and any(h == x or h.endswith("." + x) for x in hosts)


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not host_ok(newurl, DOWNLOAD_HOSTS + API_HOSTS):
            raise urllib.error.URLError(f"redirection refusée vers {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, timeout: int = 20):
    return urllib.request.build_opener(_SafeRedirect).open(urllib.request.Request(url, headers=UA), timeout=timeout)


def pick_release(release: dict) -> Optional[dict]:
    """Extrait {version, url, name, size, sha256, notes} d'une Release GitHub, ou None si inutilisable."""
    if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
        return None
    ver = parse_version(release.get("tag_name"))
    if not ver:
        return None
    assets = [a for a in release.get("assets") or [] if isinstance(a, dict)]
    zips = [a for a in assets if str(a.get("name", "")).lower().endswith(".zip")]
    if not zips:
        return None
    zips.sort(key=lambda a: (APP_NAME.lower() not in str(a["name"]).lower(), str(a["name"])))
    a = zips[0]
    sha = None
    d = str(a.get("digest") or "")
    if d.lower().startswith("sha256:") and re.fullmatch(r"[0-9a-fA-F]{64}", d[7:]):
        sha = d[7:].lower()
    sidecar = next((x for x in assets if str(x.get("name", "")).lower() in (str(a["name"]).lower() + ".sha256", "sha256sums.txt")), None)
    return {"version": ".".join(map(str, ver)), "tuple": ver, "name": a["name"], "url": a.get("browser_download_url", ""),
            "size": int(a.get("size") or 0), "sha256": sha, "sha_url": (sidecar or {}).get("browser_download_url"),
            "notes": str(release.get("body") or "")[:1500], "page": release.get("html_url", "")}


def check(repo: str, current: str = __version__) -> dict:
    """Interroge GitHub. Retourne {available, current, latest, ...} ou {error}."""
    if not REPO_RE.match(repo or ""):
        return {"available": False, "current": current, "error": "Dépôt de mises à jour non configuré (Réglages)."}
    try:
        with _open(f"https://api.github.com/repos/{repo}/releases/latest") as r:
            rel = json.loads(r.read(2_000_000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        msg = "Aucune version publiée sur ce dépôt." if exc.code == 404 else f"GitHub a répondu HTTP {exc.code}."
        return {"available": False, "current": current, "error": msg}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"available": False, "current": current, "error": f"Vérification impossible : {exc}"}
    info = pick_release(rel)
    if not info:
        return {"available": False, "current": current, "error": "La dernière version publiée n'a pas de fichier .zip utilisable."}
    cur = parse_version(current) or (0, 0, 0)
    out = {"available": info["tuple"] > cur, "current": current, "latest": info["version"], "name": info["name"],
           "size": info["size"], "notes": info["notes"], "page": info["page"], "error": None, "_info": info}
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(info: dict, dest_dir: Path) -> Path:
    """Télécharge le .zip, vérifie sa taille et son SHA-256. Lève ValueError en cas de doute."""
    if not host_ok(info.get("url", ""), DOWNLOAD_HOSTS):
        raise ValueError("Adresse de téléchargement refusée.")
    sha = info.get("sha256")
    if not sha and info.get("sha_url") and host_ok(info["sha_url"], DOWNLOAD_HOSTS):
        with _open(info["sha_url"]) as r:
            txt = r.read(100_000).decode("utf-8", "replace")
        m = re.search(r"\b([0-9a-fA-F]{64})\b", txt)
        sha = m.group(1).lower() if m else None
    if not sha:
        raise ValueError("Cette version n'a pas d'empreinte SHA-256 : installation refusée par sécurité.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", info["name"])
    target = dest_dir / safe
    tmp = target.with_suffix(".part")
    total = 0
    with _open(info["url"], timeout=60) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_ZIP:
                f.close(); tmp.unlink(missing_ok=True)
                raise ValueError("Fichier trop volumineux.")
            f.write(chunk)
    if sha256_file(tmp) != sha:
        tmp.unlink(missing_ok=True)
        raise ValueError("L'empreinte du fichier téléchargé ne correspond pas : il est peut-être corrompu ou modifié.")
    tmp.replace(target)
    return target


def validate_zip(path: Path) -> str:
    """Contrôle le contenu (pas de chemin qui sort du dossier, taille raisonnable, exécutable présent). Retourne le dossier racine ('' si aucun)."""
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError("Archive invalide.") from exc
    with z:
        names = z.namelist()
        if sum(i.file_size for i in z.infolist()) > MAX_UNPACKED:
            raise ValueError("Archive trop volumineuse une fois décompressée.")
        for n in names:
            p = Path(n.replace("\\", "/"))
            if p.is_absolute() or ".." in p.parts or re.match(r"^[A-Za-z]:", n):
                raise ValueError("Archive refusée : chemin suspect.")
        roots = {n.replace("\\", "/").split("/")[0] for n in names if n.strip("/")}
        flat = [n.replace("\\", "/") for n in names]
        exe = f"{APP_NAME}.exe"
        if not any(n == exe or n.endswith("/" + exe) for n in flat):
            raise ValueError(f"Archive refusée : {exe} introuvable (ce n'est pas une version compilée).")
        top = next(iter(roots)) if len(roots) == 1 and not (f"{APP_NAME}.exe" in flat) else ""
        return top


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def make_apply_script(zip_path: Path, top: str, app_dir: Path, exe_name: str, pid: int, work: Path) -> Path:
    """Écrit le script qui attend la fermeture de l'application, copie la nouvelle version puis relance."""
    work.mkdir(parents=True, exist_ok=True)
    stage = work / "stage"
    script = work / "apply_update.bat"
    src = f"{stage}\\{top}" if top else str(stage)
    lines = [
        "@echo off",
        "setlocal",
        ":wait",
        f'tasklist /FI "PID eq {pid}" 2>nul | find "{pid}" >nul',
        "if not errorlevel 1 (timeout /t 1 /nobreak >nul & goto wait)",
        f'if exist "{stage}" rmdir /s /q "{stage}"',
        f'powershell -NoProfile -Command "Expand-Archive -LiteralPath \'{zip_path}\' -DestinationPath \'{stage}\' -Force"',
        f'xcopy "{src}\\*" "{app_dir}\\" /E /I /Y /Q >nul',
        f'start "" "{app_dir}\\{exe_name}"',
        f'rmdir /s /q "{stage}"',
        "endlocal",
    ]
    script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return script


def launch_apply(script: Path) -> None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=flags, close_fds=True)


def app_dir() -> Path:
    return Path(sys.executable).resolve().parent if is_frozen() else Path(__file__).resolve().parents[1]
