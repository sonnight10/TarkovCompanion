"""Test visuel : charge l'interface dans Chromium avec une fausse API pywebview.

Usage : python tests/ui_smoke.py <dossier_de_sortie>
Nécessite : pip install playwright (Chromium déjà installé).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "tarkov_companion" / "ui" / "index.html"
MAPS = json.loads((ROOT / "tarkov_companion" / "data" / "maps.json").read_text(encoding="utf-8"))
out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
out.mkdir(parents=True, exist_ok=True)

TASKS = [
    {"id": "5936d90786f7742b1420ba5b", "name": "Débuter dans le métier", "minPlayerLevel": 1, "kappaRequired": False,
     "trader": {"name": "Prapor"}, "map": {"normalizedName": "customs"},
     "objectives": [{"id": "o1", "type": "shoot", "description": "Éliminer des Scavs à Customs", "optional": False,
                     "maps": [{"normalizedName": "customs"}],
                     "zones": [{"map": {"normalizedName": "customs"}, "position": {"x": 150, "y": 3, "z": -20}}]}]},
    {"id": "5936d90786f7742b1420ba5c", "name": "Chasse au Bandit", "minPlayerLevel": 5, "kappaRequired": True,
     "trader": {"name": "Skier"}, "map": {"normalizedName": "customs"},
     "objectives": [{"id": "o2", "type": "mark", "description": "Marquer le camion", "optional": False,
                     "maps": [{"normalizedName": "customs"}],
                     "zones": [{"map": {"normalizedName": "customs"}, "position": {"x": 300, "y": 3, "z": 60}}]}]},
    {"id": "5936d90786f7742b1420ba60", "name": "Reconnaissance du site", "minPlayerLevel": 3, "kappaRequired": False,
     "trader": {"name": "Thérapeute"}, "map": {"normalizedName": "customs"},
     "objectives": [{"id": "o9", "type": "visit", "description": "Atteindre la zone", "optional": False,
                     "maps": [{"normalizedName": "customs"}],
                     "zones": [{"map": {"normalizedName": "customs"}, "position": {"x": 20, "y": 3, "z": 10},
                                "outline": [{"x": 0, "z": 0}, {"x": 40, "z": 0}, {"x": 40, "z": 20}, {"x": 0, "z": 20}]}]}]},
    {"id": "5936d90786f7742b1420ba5d", "name": "Fouille à l'Usine", "minPlayerLevel": 8, "kappaRequired": False,
     "trader": {"name": "Mécano"}, "map": {"normalizedName": "factory"},
     "objectives": [{"id": "o3", "type": "findItem", "description": "Trouver un item", "optional": True,
                     "maps": [{"normalizedName": "factory"}]}]},
]
STATE = {"quests": {"5936d90786f7742b1420ba5b": "started", "5936d90786f7742b1420ba5c": "started",
                    "5936d90786f7742b1420ba5d": "finished"},
         "current_map": "customs", "in_raid": True, "seq": 4,
         "position": {"x": 120.0, "y": 3.0, "z": -40.0, "yaw": 45.0, "map": "customs", "t": 1},
         "trail": [{"x": 0, "y": 3, "z": 0}, {"x": 60, "y": 3, "z": -20}, {"x": 120, "y": 3, "z": -40}]}
EVENTS = [
    {"seq": 1, "kind": "raid_matched", "data": {}, "ts": "18:09:10"},
    {"seq": 2, "kind": "map", "data": {"map": "customs"}, "ts": "18:09:12"},
    {"seq": 3, "kind": "quest", "data": {"quest_id": "5936d90786f7742b1420ba5b", "status": "started"}, "ts": "18:09:20"},
    {"seq": 4, "kind": "position", "data": {"map": "customs", "x": 120, "y": 3, "z": -40, "yaw": 45}, "ts": "18:09:30"},
]
EXTRACTS = {"customs": [
    {"name": "ZB-1011", "faction": "pmc", "x": 60, "y": 3, "z": -60},
    {"name": "Dorms Car", "faction": "shared", "x": 300, "y": 3, "z": 80},
    {"name": "Scav Trap", "faction": "scav", "x": -50, "y": 3, "z": 40}]}
WATCH = {"logs_ok": True, "shots_ok": True}
CONFIG = {"logs_dir": "D:/Battlestate Games/EFT (live)/Logs", "screenshots_dir": "C:/Users/me/Documents/Escape from Tarkov/Screenshots",
          "language": "fr", "follow_player": True, "show_trail": True, "show_objectives": True,
          "show_extracts": True, "faction": "pmc", "map_style": "schema", "theme": "dark", "accent": "amber", "ui_lang": "fr", "reminder_seconds": 30, "cleanup_screenshots": True}

MOCK = """
(() => {
  const D = %s; let first = true;
  const svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#243042"/>' +
    '<g id="Ground_Level"><path d="M0 50H100M50 0V100" stroke="#3b4d68" stroke-width="2"/><circle cx="50" cy="50" r="20" fill="none" stroke="#3b4d68"/></g>' +
    '<g id="Second_Floor" style="display:none"><rect x="30" y="30" width="40" height="40" fill="#445b7d"/></g></svg>';
  window.pywebview = { api: {
    bootstrap: async () => ({ version: "1.0.0", config: D.CONFIG, maps: D.MAPS, state: D.STATE, watch: D.WATCH }),
    poll: async (since) => { const ev = first ? D.EVENTS : []; first = false; return { events: ev, state: D.STATE, watch: D.WATCH }; },
    run_probe: async () => [{ test: 'Le serveur répond', ok: true, http: 200, ms: 90, detail: '{"__typename":"Query"}' }, { test: 'Quêtes, en français', ok: false, http: 422, ms: 120, detail: '["GraphQL server unavailable. Try again later."]' }],
    get_diagnostics: async () => [{ t: '10:00:00', what: 'tasks-rich', http: 200, ms: 420, attempt: 1, errors: null, n: 512 }],
    cleanup_screenshots: async () => ({ deleted: 3 }),
    get_extracts: async () => ({ maps: D.EXTRACTS, source: "network", error: null }),
    get_tasks: async () => ({ tasks: D.TASKS, source: "network", age: 0, error: null, rich: true }),
    get_map_svg: async () => ({ svg: svg, error: null }),
    set_quest_status: async (id, st) => { if (st) D.STATE.quests[id] = st; else delete D.STATE.quests[id]; return true; },
    check_update: async () => ({ available: true, current: '1.0.0', latest: '1.1.0', error: null, can_install: true }),
    download_update: async () => ({ ok: true, can_install: true }), install_update: async () => { window.__installed = true; return { ok: true }; }, open_update_folder: async () => true,
    set_map: async () => true, set_raid_state: async () => true, set_overlay: async () => true,
    get_raid_diag: async () => ({ lines: ['10:00 TRACE-NetworkGameCreate'], in_raid: false, current_map: 'customs', unresolved_maps: ['x_map'], session: 's', files: [], version: '1' }),
    get_stats: async () => ({ total_raids: 1, total_seconds: 1260, maps: [{ map: 'customs', raids: 1, avg_seconds: 1260, points: 4, heat: [[-100, 40], [-20, 10], [90, -60], [200, -20]] }] }),
    export_backup: async () => ({ ok: true }), import_backup: async () => ({ ok: true, counts: {} }), clear_trail: async () => true,
    save_config: async (c) => { Object.assign(D.CONFIG, c); return { config: D.CONFIG, watch: D.WATCH }; },
    detect_paths: async () => ({ config: D.CONFIG, watch: D.WATCH, found: { logs_dir: "x", screenshots_dir: "y" } }),
    pick_folder: async () => ({ config: D.CONFIG, watch: D.WATCH }),
    get_marks: async () => JSON.parse(JSON.stringify(D.MARKS)),
    add_mark: async (map, x, z, label) => { const m = { id: 'm' + D.MARKS.length, map, x, z, label: label || 'Repère' }; D.MARKS.push(m); return m; },
    delete_mark: async (id) => { D.MARKS = D.MARKS.filter((m) => m.id !== id); return true; },
    get_history: async () => D.HIST.map((r) => ({ id: r.id, map: r.map, start: r.start, duration: r.duration, points: r.points.length })),
    get_raid: async (id) => D.HIST.find((r) => r.id === id) || null,
    delete_raid: async (id) => { D.HIST = D.HIST.filter((r) => r.id !== id); return true; },
    get_log_status: async () => ({ root: 'D:/Logs', root_ok: true, watching: true, quests: { started: 2 }, stats: { session: 'log_x', files: [{ name: 'a push-notifications.log', kind: 'notif', size: 20480 }], chat_blocks: 3, quest_events: 3, unparsed: 0, unparsed_sample: null, last_quest: { quest_id: '5936d90786f7742b1420ba5b', status: 'started', ts: '10:00' }, history_files: 1 } }),
    open_url: async (u) => { window.__opened = u; return true; },
  } };
})();
""" % json.dumps({"MAPS": MAPS, "STATE": STATE, "EVENTS": EVENTS, "WATCH": WATCH, "CONFIG": CONFIG, "TASKS": TASKS, "EXTRACTS": EXTRACTS, "MARKS": [{"id": "m0", "map": "customs", "x": 200, "z": 20, "label": "Cache test"}],
    "HIST": [{"id": "r1", "map": "customs", "start": 1760000000, "duration": 1260, "points": [{"x": -100, "y": 3, "z": 40}, {"x": -20, "y": 3, "z": 10}, {"x": 90, "y": 3, "z": -60}, {"x": 200, "y": 3, "z": -20}]}]})

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium") if Path("/opt/pw-browsers/chromium").exists() else p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.add_init_script(MOCK)
    page.goto(UI.as_uri())
    page.wait_for_selector(".leaflet-image-layer", timeout=8000)
    page.wait_for_timeout(1200)
    page.screenshot(path=str(out / "1-carte.png"))

    # le marqueur doit être au bon endroit : projection du point (120, -40) vs. position écran
    info = page.evaluate("""() => { const m = document.querySelector('.me'); const r = m.getBoundingClientRect();
        return { x: r.x + r.width/2, y: r.y + r.height/2, n: document.querySelectorAll('.leaflet-interactive').length }; }""")
    print("marqueur à l'écran:", info)
    names = page.locator(".ext-name").all_inner_texts()
    print("extractions PMC sur la carte:", names, "| proche:", page.locator(".ext.near .ext-name").all_inner_texts())
    print("liste:", page.locator("#extList .ext-row").all_inner_texts())
    print("coords:", page.locator("#coords").inner_text())
    assert sorted(names) == ["Dorms Car", "ZB-1011"], names          # pas d'extraction Scav en camp PMC
    page.click("#tFaction"); page.wait_for_timeout(400)
    print("après bascule Scav:", sorted(page.locator(".ext-name").all_inner_texts()))
    assert sorted(page.locator(".ext-name").all_inner_texts()) == ["Dorms Car", "Scav Trap"]
    page.click("#tFaction"); page.wait_for_timeout(300)

    page.click('[data-view="quests"]'); page.wait_for_timeout(500)
    page.screenshot(path=str(out / "2-quetes.png"))
    page.click('.q[data-id="5936d90786f7742b1420ba5c"] .q-head'); page.wait_for_timeout(300)
    page.click('[data-s="started"]'); page.wait_for_timeout(300)
    print("quêtes en cours affichées:", page.locator(".q").count())
    page.click('[data-view="journal"]'); page.wait_for_timeout(500)
    page.screenshot(path=str(out / "3-journal.png"))
    print("entrées du journal:", page.locator(".ev").count())
    page.click('[data-view="settings"]'); page.wait_for_timeout(500)
    assert page.input_value("#sReminder") == "30" and page.is_checked("#sCleanup")
    page.click("#sCleanNow"); page.wait_for_timeout(300)
    print("nettoyage:", page.locator("#sCleanMsg").inner_text())
    page.click("#sProbeBtn"); page.wait_for_timeout(400)
    print("sonde:", page.locator("#sDiag").inner_text().replace("\n", " | ")[:160])
    page.screenshot(path=str(out / "4-reglages.png"))

    # style détaillé : tuiles (réponses simulées)
    import base64
    PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    hits = []
    page.route("**/assets.tarkov.dev/**", lambda r: (hits.append(r.request.url), r.fulfill(status=200, content_type="image/png", body=PNG)))
    page.click('[data-view="map"]'); page.wait_for_timeout(300)
    page.click("#tStyle"); page.wait_for_selector(".leaflet-tile", timeout=8000); page.wait_for_timeout(600)
    print("style:", page.locator("#tStyleLabel").inner_text(), "| tuiles:", page.locator(".leaflet-tile").count(), "| ex:", hits[:1])
    assert page.locator("#tStyleLabel").inner_text() == "Détaillé" and hits
    assert page.locator(".leaflet-image-layer").count() == 0
    page.screenshot(path=str(out / "5-detaille.png"))
    page.click("#tStyle"); page.wait_for_selector(".leaflet-image-layer", timeout=8000)
    assert page.locator(".leaflet-tile").count() == 0

    # ── nouvelles fonctions
    page.click('[data-view="map"]'); page.wait_for_timeout(300)
    page.click("#tMeasure")
    box = page.locator("#map").bounding_box()
    page.mouse.click(box["x"] + 300, box["y"] + 300); page.mouse.click(box["x"] + 500, box["y"] + 380); page.wait_for_timeout(300)
    mt = page.locator(".leaflet-tooltip.tip b").all_inner_texts()
    print("mesure:", mt); assert any(t.endswith(" m") for t in mt)
    page.click("#tMeasure")
    page.click("#tMark"); page.mouse.click(box["x"] + 420, box["y"] + 250); page.wait_for_selector("#mkLabel")
    page.fill("#mkLabel", "Point de rendez-vous"); page.press("#mkLabel", "Enter"); page.wait_for_timeout(400)
    print("repères sur carte:", page.locator(".mk").count()); assert page.locator(".mk").count() == 2
    page.click("#tMark")
    print("à faire ici:", page.locator("#todoList .mini").count(), "| pins:", page.locator("#activeList li.loc, #todoList li.loc").count(),
          "| zones dessinées:", page.locator(".leaflet-interactive").count())
    assert page.locator("#todoList .mini").count() == 1 and page.locator("#todoList li.loc").count() == 1
    page.screenshot(path=str(out / "12-a-faire-ici.png"))
    page.click('[data-view="quests"]'); page.wait_for_timeout(400)
    first = page.locator(".q").first.locator(".q-title b").inner_text()
    print("première quête de la liste:", first, "| tag:", page.locator(".q").first.locator(".tag.here").count())
    assert page.locator(".q").first.locator(".tag.here").count() == 1
    page.click('[data-view="settings"]'); page.click("#sLogBtn"); page.wait_for_timeout(400)
    print("diag logs:", page.locator("#sDiag").inner_text().splitlines()[2][:90])
    page.click('[data-view="map"]'); page.wait_for_timeout(400)
    page.click('[data-view="prep"]'); page.wait_for_timeout(500)
    print("prépa:", page.locator("#prepQuests .pq").count(), "quêtes |", page.locator("#prepExt .mini").count(), "extractions |", page.locator("#prepMarks .mini").count(), "repères")
    assert page.locator("#prepMarks .mini").count() == 2
    page.screenshot(path=str(out / "6-preparer.png"))
    page.click('[data-view="history"]'); page.wait_for_timeout(400)
    page.screenshot(path=str(out / "7-historique.png"))
    page.click("[data-raid]"); page.wait_for_selector("#replayBar:not([hidden])", timeout=5000); page.wait_for_timeout(700)
    page.click("#rePlay"); page.wait_for_timeout(1800)
    page.screenshot(path=str(out / "8-replay.png"))
    page.click("#reClose"); assert page.locator("#replayBar").is_hidden()
    page.click('[data-view="credits"]'); page.wait_for_selector('.crow', timeout=5000)
    rows = page.locator(".crow").count(); print("crédits: lignes", rows); assert rows >= 14
    page.click("[data-url]"); assert page.evaluate("window.__opened")
    page.screenshot(path=str(out / "9-credits.png"))
    # mise à jour : barre proposée au lancement, téléchargement puis installation
    page.wait_for_selector("#updateBar:not([hidden])", timeout=8000)
    page.click("#updateGo"); page.wait_for_function("document.querySelector('#updateGo').textContent.includes('Installer')")
    page.click("#updateGo"); page.wait_for_function("window.__installed === true")
    print("mise à jour: OK")
    # nouveautés : HUD, parcours, objets, stats, diagnostic de raid, raccourcis, superposition
    page.click('[data-view="map"]'); page.wait_for_timeout(600)
    print("HUD:", page.locator("#hud").is_visible(), page.inner_text("#hudName") if page.locator("#hud").is_visible() else "-")
    page.click("#tRoute"); page.wait_for_timeout(300)
    print("parcours: numéros", page.locator(".route-n").count()); page.click("#tRoute")
    page.keyboard.press("5"); page.wait_for_selector(".heat-card svg circle", timeout=4000)
    print("stats: points de chaleur", page.locator(".heat-card svg circle").count())
    page.keyboard.press("3"); page.wait_for_timeout(500)
    print("objets à trouver:", page.locator("#itemsBox details").count())
    page.click('[data-view="settings"]'); page.wait_for_timeout(300)
    page.click("#sRaidBtn"); page.wait_for_function("document.querySelector('#sDiag').textContent.includes('NetworkGameCreate')")
    page.select_option("#sRemStyle", "both"); page.fill("#sRemVal", "30"); page.click("#sRemSet"); page.wait_for_timeout(300)
    assert "30 s" in page.inner_text("#sRemList"), page.inner_text("#sRemList")
    page.click("#sExport"); page.wait_for_timeout(200)
    page.click('[data-view="map"]'); page.keyboard.press("g"); page.wait_for_timeout(500)
    assert page.evaluate("document.body.classList.contains('overlay')"); page.screenshot(path=str(out / "13-superposition.png"))
    page.keyboard.press("g"); page.wait_for_timeout(300)
    assert not page.evaluate("document.body.classList.contains('overlay')")
    # thème clair + accent + anglais
    page.click('[data-view="settings"]'); page.wait_for_timeout(300)
    page.click('#sTheme [data-v="light"]'); page.click('#sAccent [data-v="blue"]'); page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.dataset.theme") == "light"
    page.click('#sUiLang [data-v="en"]'); page.wait_for_timeout(500)
    page.screenshot(path=str(out / "10-reglages-en-clair.png"))
    import re
    FR = re.compile(r"[àâçéèêëîïôûùœ]|\b(les|des|une|dans|pour|cette|sont|avec|aucun|aucune|quête|carte|raid|capture)\b", re.I)
    leftovers = {}
    for v in ("map", "prep", "quests", "history", "stats", "journal", "credits", "settings"):
        page.click(f'[data-view="{v}"]'); page.wait_for_timeout(350)
        txt = page.evaluate("document.body.innerText")
        for line in txt.split("\n"):
            if FR.search(line) and "Cache test" not in line and "Point de rendez" not in line and "ZB-" not in line and "Fouille" not in line and "Débuter" not in line and "Chasse" not in line and "Éliminer" not in line and "Marquer" not in line and "Trouver" not in line and "Mécano" not in line:
                leftovers[line.strip()[:110]] = v
    print("TEXTES FRANÇAIS RESTANTS EN ANGLAIS:", len(leftovers))
    for k, v in leftovers.items(): print("  ", v, "|", k)
    page.click('[data-view="map"]'); page.wait_for_timeout(1500)
    page.screenshot(path=str(out / "11-carte-en-clair.png"))
    browser.close()

def _more():
    pass
print("ERREURS JS:", errors if errors else "aucune")
sys.exit(1 if errors else 0)
