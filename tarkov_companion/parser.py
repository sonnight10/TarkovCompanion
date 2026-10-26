"""Transforme des lignes/blocs de logs en événements structurés."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from . import patterns as P


@dataclass
class Event:
    kind: str                      # quest | map | raid_start | raid_end | raid_matched
    data: dict = field(default_factory=dict)
    ts: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "data": self.data, "ts": self.ts}


def _ts(line: str) -> str:
    m = P.TS_RE.match(line)
    if not m:
        return datetime.now().strftime("%H:%M:%S")
    return m.group("time")


def _epoch(line: str) -> Optional[float]:
    """Horodatage complet d'une ligne de log (secondes epoch) ou None."""
    m = P.TS_RE.match(line)
    if not m:
        return None
    try:
        return datetime.fromisoformat(f"{m.group('date')}T{m.group('time')}{m.group('tz')}").timestamp()
    except ValueError:
        return None


def _extract_json(text: str) -> Optional[dict]:
    """Extrait le premier objet JSON équilibré d'un bloc de texte."""
    start = text.find("{")
    if start < 0:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except ValueError:
                    return None
    return None


def parse_quest_block(block: str) -> Optional[Event]:
    """Bloc d'une entrée 'ChatMessageReceived' d'un marchand."""
    if P.QUEST_ENTRY_MARKER not in block:
        return None
    obj = _extract_json(block)
    if not obj:
        return None
    message = obj.get("message") if isinstance(obj.get("message"), dict) else obj
    template = str(message.get("templateId", ""))
    if not template:
        return None
    parts = template.split(" ")
    quest_id = parts[0]
    if not P.QUEST_ID_RE.match(quest_id):
        return None
    status = None
    if len(parts) > 1:
        status = P.QUEST_SUFFIX_STATUS.get(parts[-1].lower())
    if status is None:
        status = P.QUEST_TYPE_STATUS.get(message.get("type"))
    if status is None:
        return None
    return Event("quest", {"quest_id": quest_id, "status": status}, _ts(block.splitlines()[0]))


def parse_application_line(line: str) -> list[Event]:
    events: list[Event] = []
    ts = _ts(line)
    t = _epoch(line)
    tdata = {"t": t} if t else {}
    if P.RAID_MATCHED.search(line):          # avant la carte : la carte de CETTE mise en relation prime
        events.append(Event("raid_matched", dict(tdata), ts))
    m = P.MAP_SCENE.search(line)
    if m:
        events.append(Event("map", {"log_id": m.group("map"), **tdata}, ts))
    else:
        m = P.MAP_LOCATION.search(line)
        if m and P.MAP_LOCATION_CONTEXT.search(line):
            events.append(Event("map", {"log_id": m.group("map"), **tdata}, ts))
    if P.RAID_STARTED.search(line):
        events.append(Event("raid_start", dict(tdata), ts))
    if P.RAID_ENDED.search(line):
        events.append(Event("raid_end", dict(tdata), ts))
    return events


def parse_screenshot_name(name: str) -> Optional[dict]:
    """Retourne position + rotation depuis le nom d'un fichier de capture."""
    m = P.SCREENSHOT_RE.match(name)
    if not m:
        return None
    x, y, z = (float(m.group(k)) for k in "xyz")
    qx, qy, qz, qw = (float(m.group(k)) for k in ("qx", "qy", "qz", "qw"))
    # Yaw (rotation autour de l'axe vertical Y) depuis le quaternion, en degrés
    yaw = (
        180.0 / 3.141592653589793
        * __import__("math").atan2(2 * (qw * qy + qx * qz), 1 - 2 * (qy * qy + qz * qz))
    )
    return {"x": x, "y": y, "z": z, "yaw": yaw % 360, "file": name}
