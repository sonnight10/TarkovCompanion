"""Expressions régulières pour lire les logs de Tarkov.

Le format des logs n'est pas documenté par Battlestate : si un patch change une
ligne, c'est ICI (et seulement ici) qu'il faut ajuster les motifs.
"""
import re

# ── En-tête d'une entrée de log : "2026-10-19 18:09:32.585 +00:00|1.0.x|Info|application|..."
TS_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}:\d{2})(?:\.\d+)? (?P<tz>[+-]\d{2}:\d{2})\|"
)

# ── Fichiers de logs surveillés (nom de fichier en minuscules)
# Le jeu nomme parfois ses fichiers "... push-notifications.log" et parfois "... push-notifications_000.log"
NOTIFICATION_NAME = re.compile(r"notifications(?:_\d+)?\.log$", re.IGNORECASE)
APPLICATION_NAME = re.compile(r"application(?:_\d+)?\.log$", re.IGNORECASE)


def log_kind(filename: str):
    """'notif', 'app' ou None selon le nom du fichier de log."""
    if NOTIFICATION_NAME.search(filename):
        return "notif"
    if APPLICATION_NAME.search(filename):
        return "app"
    return None

# ── Quêtes : messages de chat envoyés par les marchands
QUEST_ENTRY_MARKER = "ChatMessageReceived"
QUEST_ID_RE = re.compile(r"^[0-9a-f]{24}$")
# suffixe du templateId -> statut
QUEST_SUFFIX_STATUS = {
    "description": "started",
    "failmessagetext": "failed",
    "successmessagetext": "finished",
}
# type de message -> statut (secours si le suffixe est inconnu)
QUEST_TYPE_STATUS = {10: "started", 11: "failed", 12: "finished"}

# ── Carte / raid (application.log)
MAP_SCENE = re.compile(r"scene preset path:\s*maps/(?P<map>[A-Za-z0-9_\-]+)\.bundle", re.IGNORECASE)
MAP_LOCATION = re.compile(r"\bLocation\s*[:=]\s*'?(?P<map>[A-Za-z0-9_\-]+)'?")
MAP_LOCATION_CONTEXT = re.compile(r"Matching|GameCreate|LocationLoaded|raid", re.IGNORECASE)
RAID_MATCHED = re.compile(r"TRACE-NetworkGameCreate")
RAID_STARTED = re.compile(r"\bGameStarted\b")
RAID_ENDED = re.compile(r"UserMatchOver|\bGameDestroyed\b")

# ── Captures d'écran : "2026-10-19[18-09]_-263.1, 4.3, -2.7_0.0, 0.1, 0.0, 1.0_8.00 (0).png"
_F = r"-?\d+(?:\.\d+)?"
SCREENSHOT_RE = re.compile(
    rf"^(?P<date>\d{{4}}-\d{{2}}-\d{{2}})\[(?P<h>\d{{2}})-(?P<m>\d{{2}})\]_"
    rf"(?P<x>{_F}), (?P<y>{_F}), (?P<z>{_F})_"
    rf"(?P<qx>{_F}), (?P<qy>{_F}), (?P<qz>{_F}), (?P<qw>{_F})_"
)
SCREENSHOT_EXT = (".png", ".jpg", ".jpeg", ".bmp")

# Lignes de application.log utiles pour diagnostiquer la détection des raids (affichées dans le diagnostic).
RAID_HINT = re.compile(r"raid|match|location|scene preset|GameStarted|GameCreate|GameDestroyed|NetworkGame|UserMatchOver", re.IGNORECASE)
