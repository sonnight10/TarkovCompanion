"""Base des cartes (calibration issue de tarkov-dev, licence MIT)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

DATA_FILE = Path(__file__).parent / "data" / "maps.json"

# alias renvoyés par l'API des quêtes -> id interne
ALIASES = {"night-factory": "factory", "factory-night": "factory"}


class MapDB:
    def __init__(self, path: Path = DATA_FILE):
        self.maps: list[dict] = json.loads(path.read_text(encoding="utf-8"))
        self.by_id = {m["id"]: m for m in self.maps}
        self.by_log = {}
        for m in self.maps:
            for log_id in m.get("log_ids", []):
                self.by_log[log_id.lower()] = m["id"]
        self.svg_files = {m["svg"] for m in self.maps if m.get("svg")}

    def normalize(self, name: Optional[str]) -> Optional[str]:
        if not name:
            return None
        name = ALIASES.get(name, name)
        return name if name in self.by_id else None

    _SUFFIX = re.compile(r"(?:_preset|_day|_night|_high|_low|_summer|_winter|_base)+$")

    def resolve_log_id(self, log_id: str) -> Optional[str]:
        """Id de carte d'après le nom vu dans les logs (tolère « bigmap_preset », « factory4_day », etc.)."""
        k = (log_id or "").lower().strip()
        if k in self.by_log:
            return self.by_log[k]
        k2 = self._SUFFIX.sub("", k)
        if k2 in self.by_log:
            return self.by_log[k2]
        if len(k2) >= 5:
            for key, mid in self.by_log.items():
                if len(key) >= 5 and (k2.startswith(key) or key.startswith(k2)):
                    return mid
        return None

    def candidates(self, x: float, z: float) -> list:
        """Toutes les cartes dont les limites contiennent le point, de la plus petite à la plus grande."""
        out = []
        for m in self.maps:
            (x1, z1), (x2, z2) = m["bounds"]
            lo_x, hi_x = sorted((x1, x2))
            lo_z, hi_z = sorted((z1, z2))
            if lo_x <= x <= hi_x and lo_z <= z <= hi_z:
                out.append(((hi_x - lo_x) * (hi_z - lo_z), m["id"]))
        return [mid for _, mid in sorted(out)]

    def guess(self, x: float, z: float) -> Optional[str]:
        """Devine la carte d'après les limites (la plus petite qui contient le point)."""
        best, best_area = None, None
        for m in self.maps:
            (x1, z1), (x2, z2) = m["bounds"]
            lo_x, hi_x = sorted((x1, x2))
            lo_z, hi_z = sorted((z1, z2))
            if lo_x <= x <= hi_x and lo_z <= z <= hi_z:
                area = (hi_x - lo_x) * (hi_z - lo_z)
                if best is None or area < best_area:
                    best, best_area = m["id"], area
        return best
