/* Traduction de l'interface (français -> anglais). Le français est la langue d'origine du code :
   chaque texte est cherché tel quel dans EN, sinon dans PAT (motifs avec nombres, noms…). */
"use strict";
(function () {
  const EN = {
    // navigation et titres
    "Carte": "Map", "Préparer": "Prepare", "Quêtes": "Quests", "Historique": "History", "Journal": "Journal", "Crédits": "Credits", "Réglages": "Settings",
    "Préparer le raid": "Prepare the raid", "Historique des raids": "Raid history", "Crédits et licences": "Credits and licenses",
    "Position et objectifs en direct": "Live position and objectives",
    "Quêtes, extractions et repères de la carte choisie": "Quests, extracts and markers for the selected map",
    "Suivi automatique depuis les logs du jeu": "Automatic tracking from the game logs",
    "Tout ce que l'application a détecté": "Everything the app has detected",
    "Dossiers, affichage et fonctionnement": "Folders, display and how it works",
    "Tes raids enregistrés, avec leur trajet": "Your recorded raids, with their route",
    "Auteurs des cartes, sources et licences": "Map authors, sources and licenses",
    // pastilles
    "Hors raid": "Out of raid", "Logs": "Logs", "Captures": "Screenshots", "Dossier des logs": "Logs folder",
    "Dossier des captures d'écran": "Screenshots folder", "Données de quêtes (tarkov.dev)": "Quest data (tarkov.dev)",
    "Logs : surveillés": "Logs: watched", "Logs : introuvables": "Logs: not found",
    "Captures : surveillées": "Screenshots: watched", "Captures : introuvables": "Screenshots: not found",
    "Quêtes : indisponible": "Quests: unavailable", "Quêtes : cache": "Quests: cached", "Quêtes : chargement…": "Quests: loading…", "Quêtes : erreur": "Quests: error",
    // carte
    "Statistiques": "Statistics", "Stats": "Stats", "Tes raids, par carte": "Your raids, per map", "Parcours": "Route", "Superposition": "Overlay", "Extraction la plus proche": "Nearest extraction", "Sauvegarde": "Backup", "Exporter": "Export", "Importer": "Import", "Raccourcis clavier": "Keyboard shortcuts", "Type de rappel": "Reminder type", "Notification discrète": "Discreet notification", "Bip (Windows)": "Beep (Windows)", "Notification + bip": "Notification + beep", "Délai propre à une carte": "Per-map delay", "Appliquer": "Apply", "Diagnostic de raid": "Raid diagnostic", "Copier": "Copy", "Rappel": "Reminder", "Pense à prendre une capture d'écran": "Remember to take a screenshot", "raids enregistrés": "recorded raids", "durée moyenne": "average duration", "temps total": "total time", "Zones les plus visitées : plus un endroit est sombre, plus tu y es passé.": "Most visited areas: the darker a spot, the more you went through it.", "Aucun délai propre à une carte (le délai général s'applique).": "No per-map delay (the general delay applies).", "Diagnostic copié": "Diagnostic copied", "Sauvegarde enregistrée.": "Backup saved.", "Données restaurées.": "Data restored.", "Annulé.": "Cancelled.", "Exporte tes quêtes, ton historique de raids et tes repères dans un fichier (utile pour changer d'ordinateur). L'import remplace les données actuelles.": "Export your quests, raid history and markers to a file (handy when changing computers). Importing replaces the current data.", "Mises à jour": "Updates", "Chercher une mise à jour au lancement": "Check for updates at launch", "Dépôt GitHub des versions (propriétaire/nom)": "GitHub repository of releases (owner/name)", "Rechercher une mise à jour": "Check for updates", "Télécharger": "Download", "Plus tard": "Later", "Les nouvelles versions sont des « Releases » GitHub de ce dépôt (un .zip de la version compilée). Le fichier est vérifié (empreinte SHA-256) avant toute installation, et rien n'est installé sans ton accord.": "New versions are GitHub Releases of this repository (a .zip of the compiled build). The file is verified (SHA-256) before any installation, and nothing is installed without your consent.", "Vue entière": "Whole map", "Voir toute la carte": "Show the whole map", "Cliquer pour corriger : en raid / au menu": "Click to fix: in raid / in menu", "Trajet": "Route", "Afficher le trajet": "Show the route",
    "Objectifs": "Objectives", "Afficher les objectifs": "Show objectives", "Extractions": "Extracts", "Afficher les extractions": "Show extracts",
    "PMC": "PMC", "Scav": "Scav", "Changer de camp (PMC / Scav)": "Switch side (PMC / Scav)",
    "Mesurer": "Measure", "Mesurer une distance : clique deux points sur la carte": "Measure a distance: click two points on the map",
    "Repère": "Marker", "Poser un repère : clique sur la carte": "Drop a marker: click on the map",
    "Effacer": "Clear", "Effacer le trajet": "Clear the route",
    "Schéma": "Schematic", "Détaillé": "Detailed", "Style de la carte : schéma ou détaillé (tuiles tarkov.dev)": "Map style: schematic or detailed (tarkov.dev tiles)",
    "Quêtes en cours": "Active quests", "En attente d'une capture d'écran…": "Waiting for a screenshot…",
    "Chargement du fond de carte…": "Loading the map background…",
    "Fond de carte indisponible. Les positions restent affichées.": "Map background unavailable. Positions are still shown.",
    "Aucune extraction connue pour cette carte et ce camp.": "No known extract for this map and side.",
    "Aucune quête en cours pour cette carte. Elles apparaissent automatiquement dès que tu les acceptes en jeu.": "No active quest for this map. They appear automatically as soon as you accept them in game.",
    "Détails indisponibles (quêtes non chargées)": "Details unavailable (quests not loaded)",
    "Nom du repère (spawn, cache…)": "Marker name (spawn, stash…)", "Ajouter": "Add", "Supprimer": "Delete",
    "Repère refusé (limite atteinte ?)": "Marker refused (limit reached?)", "Départ": "Start",
    "Replay": "Replay", "Rejouer": "Replay", "Pause": "Pause", "Fermer": "Close", "Raid introuvable.": "Raid not found.",
    "2e étage": "2nd floor", "3e étage": "3rd floor", "4e étage": "4th floor", "5e étage": "5th floor", "1er étage": "1st floor",
    "Sous-sol": "Basement", "Souterrain": "Underground", "Tunnels": "Tunnels", "Bunkers": "Bunkers",
    // quêtes
    "Actualiser": "Refresh", "Recharger depuis tarkov.dev": "Reload from tarkov.dev", "Rechercher une quête…": "Search a quest…",
    "Tous les marchands": "All traders", "Toutes les cartes": "All maps", "Toutes": "All", "En cours": "In progress", "À faire": "To do",
    "Terminées": "Completed", "Échouées": "Failed", "Terminée": "Completed", "Échouée": "Failed", "Détails": "Details",
    "Kappa": "Kappa", "Commune": "Shared", "Carte inconnue": "Unknown map", "Aucune extraction connue.": "No known extract.",
    "Mes repères": "My markers", "À faire ici": "To do here", "Rien à faire sur cette carte.": "Nothing to do on this map.", "Sur cette carte": "On this map",
    "Afficher aussi les objectifs des quêtes à faire sur la carte": "Also show objectives of quests still to do on the map",
    "Un point = position de l'objectif connue : clique dessus pour y aller. Les autres n'ont pas de lieu précis.": "A dot = known objective position: click it to go there. Others have no precise location.",
    "Diagnostic des logs": "Log diagnostics", "Lecture…": "Reading…", "Réinitialiser": "Reset", "Aucun objectif détaillé": "No detailed objective", "Niv. ": "Lvl ",
    "Forêt": "Woods", "Échangeur": "Interchange", "Réserve": "Reserve",
    "Aucun repère. Sur la carte, clique sur « Repère » puis sur un point.": "No marker yet. On the map, click “Marker”, then a point.",
    "Aucune quête en cours sur cette carte.": "No active quest on this map.",
    "Quêtes non chargées pour l'instant.": "Quests not loaded yet.",
    "Aucun raid enregistré. Chaque raid terminé apparaît ici avec les points de tes captures d'écran.": "No recorded raid. Each finished raid appears here with the points from your screenshots.",
    "Voir sur la carte": "Show on the map", "Voir le trajet": "View the route",
    // journal
    "Quête acceptée": "Quest accepted", "Quête terminée": "Quest completed", "Quête échouée": "Quest failed", "Carte détectée": "Map detected",
    "Raid trouvé": "Raid found", "Chargement en cours": "Loading", "Raid démarré": "Raid started", "Raid terminé": "Raid ended",
    "Captures supprimées": "Screenshots deleted", "Position mise à jour": "Position updated",
    "Aucun événement pour l'instant. Lance une partie : les quêtes, cartes et raids apparaîtront ici.": "No event yet. Start a game: quests, maps and raids will show up here.",
    // réglages
    "Dossiers surveillés": "Watched folders", "Logs de Tarkov": "Tarkov logs", "Captures d'écran": "Screenshots", "Parcourir": "Browse",
    "Détecter automatiquement": "Detect automatically", "Non trouvé — clique sur Parcourir": "Not found — click Browse",
    "Dossiers trouvés et enregistrés.": "Folders found and saved.", "Rien trouvé : utilise « Parcourir ».": "Nothing found: use “Browse”.",
    "Lecture seule : l'application lit uniquement des fichiers texte et des noms de fichiers. Elle ne touche ni au jeu ni à sa mémoire.": "Read-only: the app only reads text files and file names. It never touches the game or its memory.",
    "Affichage": "Display", "Centrer la carte sur ma position": "Center the map on my position", "Afficher les objectifs des quêtes en cours": "Show active quest objectives",
    "Mon camp": "My side", "PMC (USEC / BEAR)": "PMC (USEC / BEAR)", "Langue des quêtes": "Quest language", "Style des cartes": "Map style",
    "Schéma (vectoriel, léger)": "Schematic (vector, light)", "Détaillé (tuiles tarkov.dev)": "Detailed (tarkov.dev tiles)",
    "Le style détaillé charge les tuiles de tarkov.dev (auteurs : Shebuka, TarkovBOT.eu, tarkov.dev) depuis internet ; il est aussi le seul fond disponible pour Laboratoire, Labyrinthe et Icebreaker. Si une carte n'a pas de version détaillée, le schéma est utilisé.": "The detailed style loads tarkov.dev tiles (authors: Shebuka, TarkovBOT.eu, tarkov.dev) from the internet; it is also the only background for Labs, Labyrinth and Icebreaker. If a map has no detailed version, the schematic one is used.",
    "Apparence": "Appearance", "Thème": "Theme", "Sombre": "Dark", "Clair": "Light", "Couleur d'accent": "Accent color",
    "Ambre": "Amber", "Bleu": "Blue", "Vert": "Green", "Violet": "Violet", "Rouge": "Red", "Langue de l'interface": "Interface language", "Français": "French", "English": "English",
    "Rappel sonore toutes les (secondes)": "Sound reminder every (seconds)",
    "0 = désactivé, sinon entre 5 et 600. Pendant un raid, l'application émet un bip (Windows) : c'est toi qui appuies sur la touche de capture du jeu. L'application n'envoie jamais de touches au jeu.": "0 = off, otherwise 5 to 600. During a raid the app beeps (Windows): you press the game's screenshot key yourself. The app never sends keys to the game.",
    "Supprimer les captures utilisées à la fin du raid": "Delete used screenshots at the end of the raid",
    "Seules les captures apparues": "Only screenshots that appeared", "pendant que l'application tourne": "while the app is running",
    "sont supprimées (définitivement, sans corbeille), y compris celles que tu aurais prises pour toi. Tes anciennes captures ne sont jamais touchées. La suppression a aussi lieu à la fermeture de l'application.": "are deleted (permanently, no recycle bin), including ones you took for yourself. Your older screenshots are never touched. Deletion also happens when the app closes.",
    "Supprimer maintenant les captures de cette session": "Delete this session's screenshots now",
    "Aucune capture à supprimer.": "No screenshot to delete.",
    "Diagnostic réseau": "Network diagnostics",
    "En cas d'erreur sur les quêtes ou les extractions, affiche les dernières réponses de tarkov.dev (utile pour me les transmettre).": "If quests or extracts fail, shows the latest tarkov.dev responses (useful to share them).",
    "Tester la connexion à tarkov.dev": "Test the connection to tarkov.dev", "Afficher le diagnostic": "Show diagnostics", "Recharger quêtes et extractions": "Reload quests and extracts",
    "Aucun appel enregistré pour l'instant.": "No call recorded yet.", "Test en cours (quelques secondes)…": "Testing (a few seconds)…",
    "Comment ça marche": "How it works",
    ": détectées automatiquement dans les logs du jeu quand un marchand t'envoie un message de quête.": ": detected automatically in the game logs when a trader sends you a quest message.",
    ": détectée dans les logs au chargement du raid.": ": detected in the logs when the raid loads.",
    ": le jeu ne l'écrit pas dans ses logs. Appuie sur la touche de capture d'écran du jeu : le nom du fichier contient tes coordonnées, et ton marqueur se déplace.": ": the game does not write it in its logs. Press the game's screenshot key: the file name contains your coordinates and your marker moves.",
    "Position": "Position",
    // toasts
    "Rechargement en cours…": "Reloading…", "Tuiles détaillées indisponibles (internet ?) : retour au style Schéma.": "Detailed tiles unavailable (internet?): back to the schematic style.",
    "Version réduite des données de quêtes : certains détails manquent.": "Reduced quest data: some details are missing.",
    "Impossible de charger les quêtes : ": "Could not load quests: ",
    // préparer / crédits
    "Extractions ": "Extracts ",
    "Auteurs des cartes": "Map authors",
    "Fonds vectoriels et tuiles détaillées créés par la communauté et fournis par tarkov.dev. Merci à leurs auteurs.": "Vector backgrounds and detailed tiles made by the community and provided by tarkov.dev. Thanks to their authors.",
    "Fond vectoriel (schéma)": "Vector background (schematic)", "Tuiles (détaillé)": "Tiles (detailed)",
    "Données et code utilisés": "Data and code used", "À savoir": "Good to know",
    "— quêtes, extractions et fichiers de données (équipe the-hideout et communauté).": "— quests, extracts and data files (the-hideout team and community).",
    "— calibration des cartes (transformation, rotation, étages). Licence MIT.": "— map calibration (transform, rotation, floors). MIT license.",
    "— fonds vectoriels. Licence": "— vector backgrounds. License",
    "(usage non commercial, attribution, partage dans les mêmes conditions).": "(non-commercial use, attribution, share-alike).",
    "— tuiles de la carte Icebreaker.": "— Icebreaker map tiles.", "1.9.4 — affichage des cartes. Licence BSD-2-Clause.": "1.9.4 — map display. BSD-2-Clause license.",
    "— fenêtre de l'application.": "— the application window.",
    "Tarkov Companion est un outil de la communauté,": "Tarkov Companion is a community tool,", "non affilié à Battlestate Games": "not affiliated with Battlestate Games",
    "est une marque de Battlestate Games.": "is a trademark of Battlestate Games.",
    "L'application est en lecture seule : elle lit des fichiers de logs et des noms de fichiers de captures d'écran, sans toucher au jeu ni à sa mémoire.": "The app is read-only: it reads log files and screenshot file names, without touching the game or its memory.",
    "Les fonds de carte ne sont pas fournis avec l'application : ils sont téléchargés depuis tarkov.dev à l'exécution. Leur usage reste non commercial.": "Map backgrounds are not bundled with the app: they are downloaded from tarkov.dev at runtime. Their use remains non-commercial.",
  };
  const FLOOR = (s) => EN[s.trim()] || s;
  const PAT = [
    [/^En raid · (.+)$/, (m) => `In raid · ${m[1]}`],
    [/^(\d+) raids? · durée moyenne (.+) · (\d+) point\(s\) de position$/, (m) => `${m[1]} raid${m[1] === "1" ? "" : "s"} · average duration ${m[2].replace("min", "min")} · ${m[3]} position point(s)`],
    [/^(\d+) quêtes? en cours sur (.+)$/, (m) => `${m[1]} active quest${m[1] === "1" ? "" : "s"} on ${m[2]}`],
    [/^Objets à trouver ou à rapporter \((\d+)\)$/, (m) => `Items to find or hand in (${m[1]})`],
    [/^Délais propres : (.+)$/, (m) => `Per-map delays: ${m[1]}`],
    [/^… et (\d+) autres \(onglet Préparer\)\.$/, (m) => `… and ${m[1]} more (Prepare tab).`],
    [/^(.+) \(à faire\)$/, (m) => `${m[1]} (to do)`],
    [/^(.+) · position connue$/, (m) => `${m[1]} · known position`],
    [/^Afficher plus \((\d+)\)$/, (m) => `Show more (${m[1]})`],
    [/^Niv\. (\d+)$/, (m) => `Lvl ${m[1]}`],
    [/^(.+) \(optionnel\)$/, (m) => `${m[1]} (optional)`],
    [/^(Tarkov Companion v[\d.]+) · voir l'onglet Crédits pour les auteurs et licences$/, (m) => `${m[1]} · see the Credits tab for authors and licenses`],
    [/^Quêtes : (\d+)$/, (m) => `Quests: ${m[1]}`],
    [/^\/ (\d+) terminées$/, (m) => `/ ${m[1]} completed`],
    [/^(\d+) capture\(s\) supprimée\(s\)\.$/, (m) => `${m[1]} screenshot(s) deleted.`],
    [/^(\d+) fichier\(s\) de cette session$/, (m) => `${m[1]} file(s) from this session`],
    [/^Carte : (.+)$/, (m) => `Map: ${m[1]}`],
    [/^Quête (\w{6})…$/, (m) => `Quest ${m[1]}…`],
    [/^Afficher\/masquer (.+)$/, (m) => `Show/hide ${FLOOR(m[1])}`],
    [/^(Quête acceptée|Quête terminée|Quête échouée) : (.+)$/, (m) => `${EN[m[1]]}: ${m[2]}`],
    [/^(.+) \(déduite de la position\)$/, (m) => `${m[1]} (deduced from position)`],
    [/^(.+) \(manuel\)$/, (m) => `${m[1]} (manual)`],
    [/^(.+) \(facultatif\)$/, (m) => `${m[1]} (optional)`],
    [/^En cours \((\d+)\)$/, (m) => `In progress (${m[1]})`],
    [/^À faire \((\d+)\)$/, (m) => `To do (${m[1]})`],
    [/^… et (\d+) autres \(voir l'onglet Quêtes\)\.$/, (m) => `… and ${m[1]} more (see the Quests tab).`],
    [/^(.+) · Niv\. (\d+)$/, (m) => `${m[1]} · Lvl ${m[2]}`],
    [/^(X -?[\d.]+ · Z -?[\d.]+) · (\d+) m de toi$/, (m) => `${m[1]} · ${m[2]} m from you`],
    [/^X (-?[\d.]+) · Z (-?[\d.]+) · Hauteur (-?[\d.]+) · (\d+)°(?: · Extraction proche : (.+) \((\d+) m\))?$/,
      (m) => `X ${m[1]} · Z ${m[2]} · Height ${m[3]} · ${m[4]}°` + (m[5] ? ` · Nearest extract: ${m[5]} (${m[6]} m)` : "")],
    [/^Quêtes chargées en (.+) : tarkov\.dev a refusé la langue choisie\.$/, (m) => `Quests loaded in ${m[1] === "anglais" ? "English" : "the server's default language"}: tarkov.dev refused the chosen language.`],
  ];
  let lang = "fr", busy = false, obs = null;
  const textOrig = new WeakMap(), attrOrig = new WeakMap();
  const ATTRS = ["title", "placeholder"];

  function tr(s) {
    const k = s.replace(/\s+/g, " ").trim();
    if (!k) return s;
    let v = EN[k];
    if (v === undefined) for (const [re, fn] of PAT) { const m = k.match(re); if (m) { v = fn(m); break; } }
    if (v === undefined) return s;
    return s.slice(0, s.length - s.trimStart().length) + v + s.slice(s.trimEnd().length);
  }
  const skip = (n) => { const p = n.parentElement; return !p || /^(SCRIPT|STYLE)$/.test(p.tagName) || p.closest("[data-no-i18n]"); };

  function textNode(n) {
    if (skip(n)) return;
    if (lang === "en") {
      const o = textOrig.has(n) ? textOrig.get(n) : n.nodeValue;
      textOrig.set(n, o);
      const t = tr(o);
      if (t !== n.nodeValue) n.nodeValue = t;
    } else if (textOrig.has(n)) { n.nodeValue = textOrig.get(n); textOrig.delete(n); }
  }
  function attrs(el) {
    for (const a of ATTRS) {
      if (!el.hasAttribute || !el.hasAttribute(a)) continue;
      const store = attrOrig.get(el) || {};
      if (lang === "en") {
        if (store[a] === undefined || el.getAttribute(a) !== store[a + "_en"]) store[a] = el.getAttribute(a);
        const t = tr(store[a]); store[a + "_en"] = t; attrOrig.set(el, store);
        if (t !== el.getAttribute(a)) el.setAttribute(a, t);
      } else if (store[a] !== undefined) { el.setAttribute(a, store[a]); delete store[a]; delete store[a + "_en"]; }
    }
  }
  function walk(root) {
    if (!root) return;
    busy = true;
    try {
      if (root.nodeType === 3) textNode(root);
      else {
        const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
        let n = w.currentNode;
        do { if (n.nodeType === 3) textNode(n); else if (n.nodeType === 1) attrs(n); } while ((n = w.nextNode()));
      }
    } finally { busy = false; if (obs) obs.takeRecords(); }
  }
  function start() {
    if (obs) return;
    obs = new MutationObserver((recs) => {
      if (busy) return;
      for (const r of recs) {
        if (r.type === "childList") r.addedNodes.forEach((n) => walk(n));
        else if (r.type === "characterData") textNode(r.target);
        else if (r.type === "attributes") { busy = true; attrs(r.target); busy = false; }
      }
      obs.takeRecords();
    });
    obs.observe(document.body, { childList: true, characterData: true, subtree: true, attributes: true, attributeFilter: ATTRS });
  }
  window.I18N = {
    get lang() { return lang; },
    setLang(l) {
      l = l === "en" ? "en" : "fr";
      if (l === lang) return;
      lang = l; document.documentElement.lang = l;
      walk(document.body);
    },
    t: (s) => (lang === "en" ? tr(s) : s),
  };
  if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);
})();
