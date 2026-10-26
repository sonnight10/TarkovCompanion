"""Surveillance (lecture seule) des fichiers de logs et du dossier de captures.

Technique : sondage périodique, sans dépendance. Pour chaque fichier on retient
l'offset déjà lu ; seuls les nouveaux octets sont analysés.
"""
from __future__ import annotations

import re
import threading
from collections import deque
import time
from pathlib import Path
from typing import Callable, Optional

from . import parser as parse
from . import patterns as P

Emit = Callable[[parse.Event], None]
ENTRY_START = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


class LogWatcher:
    def __init__(self, logs_dir: str, emit: Emit, poll: float = 1.0, read_history: bool = True):
        self.root = Path(logs_dir) if logs_dir else None
        self.emit = emit
        self.poll = poll
        self.read_history = read_history
        self.stats = {"session": None, "files": [], "chat_blocks": 0, "quest_events": 0, "unparsed": 0,
                      "unparsed_sample": None, "last_quest": None, "history_files": 0}
        self.recent: deque = deque(maxlen=40)   # dernières lignes liées aux raids (diagnostic)
        self._offsets: dict[Path, int] = {}
        self._pending: dict[Path, list[str]] = {}
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ── cycle de vie
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="log-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        first = True
        while not self._stop.is_set():
            try:
                self.scan_once(first_pass=first)
            except Exception:  # ne jamais tuer le thread
                pass
            first = False
            self._stop.wait(self.poll)

    # ── scan
    def _session_dir(self) -> Optional[Path]:
        if not self.root or not self.root.is_dir():
            return None
        dirs = [d for d in self.root.iterdir() if d.is_dir()]
        if not dirs and any(self.root.glob("*.log")):   # le dossier choisi est déjà celui d'une session
            return self.root
        return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None

    def scan_once(self, first_pass: bool = False) -> None:
        session = self._session_dir()
        self.stats["session"] = session.name if session else None
        if session is None:
            return
        if first_pass and self.read_history:
            self._replay_history(session)
        files: list = []
        for f in sorted(session.glob("*.log")):
            kind = P.log_kind(f.name)
            if kind is None:
                continue
            self._read_new(f, kind, first_pass)
            try:
                files.append({"name": f.name, "kind": kind, "size": f.stat().st_size})
            except OSError:
                pass
        self.stats["files"] = files

    def _replay_history(self, current: Path) -> None:
        """Rejoue les quêtes des sessions précédentes (ordre chronologique) pour reconstruire l'état."""
        older = sorted((d for d in self.root.iterdir() if d.is_dir() and d != current), key=lambda d: d.name)
        for d in older:
            for f in sorted(d.glob("*.log")):
                if P.log_kind(f.name) != "notif":
                    continue
                try:
                    text = f.read_bytes().decode("utf-8", errors="replace")
                except OSError:
                    continue
                self.stats["history_files"] += 1
                self._consume(f, text, "notif", history=True)

    def _read_new(self, path: Path, kind: str, first_pass: bool) -> None:
        try:
            size = path.stat().st_size
        except OSError:
            return
        offset = self._offsets.get(path)
        if offset is None:
            offset = 0 if self.read_history else size
        if size < offset:        # fichier tronqué / nouveau
            offset = 0
        if size == offset:
            self._offsets[path] = offset
            return
        try:
            with open(path, "rb") as fh:
                fh.seek(offset)
                chunk = fh.read(size - offset)
        except OSError:
            return
        # ne traiter que les lignes complètes
        cut = chunk.rfind(b"\n")
        if cut < 0:
            return
        self._offsets[path] = offset + cut + 1
        text = chunk[:cut].decode("utf-8", errors="replace")
        self._consume(path, text, kind)

    def _consume(self, path: Path, text: str, kind: str, history: bool = False) -> None:
        lines = text.splitlines()
        if kind == "app":
            for line in lines:
                if P.RAID_HINT.search(line):
                    self.recent.append(line.strip()[:260])
                for ev in parse.parse_application_line(line):
                    self.emit(ev)
            return
        # notifications : une entrée peut s'étendre sur plusieurs lignes (JSON indenté)
        block: list[str] = self._pending.pop(path, [])
        for line in lines:
            if ENTRY_START.match(line) and block:
                self._flush(block, history)
                block = []
            block.append(line)
        if block:
            self._flush(block, history)

    def _flush(self, block: list[str], history: bool = False) -> None:
        joined = "\n".join(block)
        ev = parse.parse_quest_block(joined)
        if P.QUEST_ENTRY_MARKER in joined:
            self.stats["chat_blocks"] += 1
            if ev is None:
                self.stats["unparsed"] += 1
                tid = re.search(r'"templateId"\s*:\s*"([^"]*)"', joined)
                typ = re.search(r'"type"\s*:\s*(\d+)', joined)
                self.stats["unparsed_sample"] = {"templateId": tid.group(1)[:80] if tid else None, "type": typ.group(1) if typ else None}
        if ev:
            self.stats["quest_events"] += 1
            self.stats["last_quest"] = {"quest_id": ev.data.get("quest_id"), "status": ev.data.get("status"), "ts": ev.ts}
            if history:
                ev.data["history"] = True
            self.emit(ev)


class ScreenshotWatcher:
    def __init__(self, folder: str, emit: Callable[[dict], None], poll: float = 0.7):
        self.folder = Path(folder) if folder else None
        self.emit = emit
        self.poll = poll
        self._seen: set[str] = set()
        self.session_files: set[str] = set()     # captures apparues PENDANT cette session
        self._files_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._seen = self._names()  # on ignore les anciennes captures
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="shot-watcher", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _names(self) -> set[str]:
        if not self.folder or not self.folder.is_dir():
            return set()
        try:
            return {p.name for p in self.folder.iterdir() if p.suffix.lower() in P.SCREENSHOT_EXT}
        except OSError:
            return set()

    def scan_once(self) -> None:
        current = self._names()
        for name in sorted(current - self._seen):
            pos = parse.parse_screenshot_name(name)
            if pos:
                pos["t"] = time.time()
                with self._files_lock:
                    self.session_files.add(name)
                self.emit(pos)
        self._seen = current

    def cleanup(self) -> int:
        """Supprime les captures vues pendant la session (jamais les plus anciennes).

        Garde-fous : le nom doit suivre le format de capture de Tarkov, rester un simple
        nom de fichier (pas de chemin) et appartenir au dossier surveillé.
        """
        if not self.folder:
            return 0
        removed = 0
        with self._files_lock:
            for name in list(self.session_files):
                if Path(name).name != name or not P.SCREENSHOT_RE.match(name):
                    self.session_files.discard(name)
                    continue
                try:
                    (self.folder / name).unlink()
                    removed += 1
                    self.session_files.discard(name)
                except FileNotFoundError:
                    self.session_files.discard(name)
                except OSError:
                    pass                              # verrouillé : on réessaiera plus tard
        return removed

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.scan_once()
            except Exception:
                pass
            self._stop.wait(self.poll)
