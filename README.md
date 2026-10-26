# Tarkov Companion

Application de bureau (Python) pour *Escape from Tarkov* :

- **Carte interactive** avec ta position, ton trajet et les objectifs de tes quêtes en cours
- **Suivi automatique des quêtes** à partir des logs du jeu
- **Extractions** de la carte selon ton camp (PMC ou Scav), avec l'extraction la plus proche et sa distance
- **Rappel sonore** de capture et **nettoyage automatique** des captures utilisées
- **Journal** des événements détectés (quête acceptée/terminée, carte, raid)
- **Préparer le raid** : quêtes en cours et à faire sur la carte choisie, extractions de ton camp, repères
- **Mesure et repères** sur la carte : distance entre deux points, repères nommés enregistrés
- **Historique des raids** : carte, durée, trajet (points de tes captures), avec replay animé
- **Apparence** : thème sombre ou clair, 5 couleurs d'accent, interface en français ou en anglais
- **Crédits** : auteurs des cartes, sources et licences (onglet dédié)

## Sécurité (BattlEye)

L'application est en **lecture seule** : elle lit des fichiers texte (les logs) et les *noms* de fichiers du dossier de captures d'écran. Elle n'injecte rien, ne lit pas la mémoire du jeu et ne touche à aucun processus.

## Installation (Windows)

1. Installe [Python 3.10+](https://www.python.org/downloads/) (coche « Add python.exe to PATH »).
2. Dézippe le dossier, double-clique sur **`Lancer.bat`**. Au premier lancement, il installe `pywebview` (fenêtre native via Edge WebView2, déjà présent sur Windows 10/11).

À la main : `pip install -r requirements.txt` puis `python main.py`.

Essai sans le jeu : `python main.py --demo` (simule un raid sur Customs).

## Comment ça marche

| Fonction | Source | Précision |
|---|---|---|
| Quêtes (acceptée / terminée / échouée) | `Logs/.../push-notifications.log` | Automatique, en direct ; au 1er lancement, l'historique des sessions encore présentes dans `Logs` est rejoué pour reconstruire ton état |
| Carte et début/fin de raid | `Logs/.../application.log` | Automatique, en direct |
| **Position** | Nom des fichiers du dossier *Screenshots* | **À la demande** : un point par capture d'écran |
| Extractions (nom, camp, position) | tarkov.dev (cache 24 h) | Disponibles pour tout le monde ; le « plus proche » exige une position (capture d'écran) |
| Fond de carte, objectifs, noms de quêtes | tarkov.dev (téléchargés puis mis en cache) | Nécessite internet au 1er lancement |

**La position n'est pas continue** : le jeu n'écrit pas ta position dans ses logs. Chaque fois que tu prends une capture d'écran en jeu, le nom du fichier contient tes coordonnées et ton orientation ; l'application place alors ton marqueur et trace le trajet entre les captures. Le suivi continu exigerait de lire la mémoire du jeu, ce qui est interdit et fait risquer le bannissement : ce n'est donc volontairement pas proposé.

Les dossiers sont détectés automatiquement (`...\Battlestate Games\...\Logs` et `Documents\Escape from Tarkov\Screenshots`). Sinon : *Réglages → Parcourir*.

Si une quête ancienne n'apparaît pas (logs déjà supprimés par le jeu), tu peux régler son état à la main dans l'onglet Quêtes.

Données enregistrées dans `%APPDATA%\TarkovCompanion` (config, quêtes, cache, fonds de carte).

**Quêtes sur la carte** : les quêtes en cours et à faire sur la carte passent en premier (panneau de la carte, onglet Quêtes) ; leurs objectifs ont un point (et un contour de zone quand il existe) sur la carte, bleu pour les quêtes à faire (réglable : *Afficher aussi les objectifs des quêtes à faire*). Beaucoup d'objectifs (« tuer N Scavs », « remettre des objets ») n'ont pas de lieu précis dans les données de tarkov.dev : ils n'ont donc pas de point. Si le suivi automatique ne se déclenche pas : *Réglages → Diagnostic réseau → Diagnostic des logs* montre ce que l'application lit (dossier, fichiers, messages reconnus).

**Style des cartes** : bouton « Schéma / Détaillé » dans la barre d'outils de la carte (ou *Réglages → Style des cartes*). *Schéma* = fond vectoriel léger ; *Détaillé* = tuiles de tarkov.dev (même calibration, étages inclus), chargées depuis internet. Le détaillé est aussi le seul fond de Laboratoire, Labyrinthe et Icebreaker. Les cartes sans version détaillée (Lighthouse, Terminal, Streets) gardent le schéma. Si les tuiles ne se chargent pas, l'application revient seule au schéma. Les images 2D/3D du site ne sont pas intégrées : elles ne sont pas calibrées et ne permettent pas d'afficher ta position. Tuiles : Shebuka, TarkovBOT.eu et tarkov.dev (non redistribuées ; vérifie leurs conditions d'usage).

**Repères, historique** : *Mesurer* (barre d'outils de la carte) : clique deux points, la distance s'affiche en mètres. *Repère* : clique un point, donne-lui un nom ; les repères sont enregistrés (`marks.json`) et listés dans *Préparer*. Chaque raid terminé est enregistré (`history.json`, 100 derniers) avec les points de tes captures d'écran ; *Historique → Voir le trajet* l'affiche sur la carte, avec un bouton *Rejouer*. Un raid abandonné n'est pas enregistré.

**Extractions et spawn** : l'application affiche les extractions de ton camp (réglable dans la barre d'outils ou les Réglages), mais ne sait pas quelles extractions te sont réellement ouvertes selon ton point d'apparition : le jeu ne l'écrit pas dans les logs et je n'ai pas pu confirmer que tarkov.dev fournit cette correspondance. Certaines extractions conditionnelles (clé, objet, coopération) ne sont donc pas distinguées.

**Captures d'écran (Réglages)** :
- *Rappel sonore* toutes les N secondes (5 à 600, 0 = désactivé) : pendant un raid, l'application émet un bip (Windows) et c'est toi qui appuies sur la touche de capture du jeu. Le rappel dépend de la détection du raid dans les logs.
- *Suppression à la fin du raid* (désactivée par défaut) : seules les captures apparues pendant que l'application tourne et au format de capture de Tarkov sont supprimées, définitivement (pas de corbeille). Tes anciennes captures et les fichiers d'un autre format ne sont jamais touchés. La suppression a aussi lieu à la fermeture de l'application, et un bouton permet de la lancer à la demande.
- **Volontairement absent** : l'application n'envoie jamais de touche au jeu. Automatiser la capture reviendrait à piloter le jeu par programme (risque pour ton compte) et à créer un suivi quasi temps réel de ta position en raid.

**Si tarkov.dev est indisponible** : l'API publique est parfois surchargée (« GraphQL server unavailable »). Les quêtes sont demandées par petites pages de 100 (les positions d'objectifs à part, et de façon facultative : sans elles, les quêtes s'affichent quand même). L'application réessaie seule (plusieurs fois de suite, puis toutes les 15 à 60 s), n'enregistre jamais une réponse incomplète et utilise son cache quand il existe. Si le serveur refuse une demande précise (le français, ou certains champs) en la déguisant en « indisponible », l'application retombe automatiquement sur l'anglais, puis sans langue, puis sur une version réduite des quêtes. *Réglages → Diagnostic réseau* contient un bouton **Tester la connexion** (huit petites requêtes qui montrent ce que le serveur accepte ou refuse) et affiche les dernières réponses reçues.

## Si une mise à jour du jeu casse la détection

Le format des logs n'est pas documenté officiellement et peut changer. Tous les motifs de lecture sont dans **`tarkov_companion/patterns.py`** (et seulement là). Le journal de l'application montre ce qui est détecté, ce qui aide à comprendre ce qui a changé.

## Points à vérifier sur ton PC

Ces éléments n'ont pas pu être testés avec un vrai jeu :

1. Le format réel de tes logs (les motifs reposent sur le format connu de TarkovMonitor) ;
2. Le téléchargement des fonds de carte, des quêtes et des extractions depuis tarkov.dev (le schéma des extractions n'a pas pu être vérifié : l'application essaie plusieurs variantes de requête et affiche une erreur claire si aucune ne marche). Le réseau était bloqué dans l'environnement de développement ;
3. L'orientation de la flèche (convention Unity : 0° = axe +Z) ;
4. L'alignement des étages sur certaines cartes (bascule automatique selon la hauteur).

## Tests

```
python -m unittest tests.test_engine tests.test_api
```

`tests/ui_smoke.py` charge l'interface dans Chromium avec une fausse API et produit des captures (nécessite `playwright`).

## Crédits et licences

- Code de l'application : à ta convenance.
- Calibration des cartes (transformation, rotation, limites, étages) : [the-hideout/tarkov-dev](https://github.com/the-hideout/tarkov-dev) (MIT).
- Fonds de carte SVG : [the-hideout/tarkov-dev-svg-maps](https://github.com/the-hideout/tarkov-dev-svg-maps), **CC BY-NC-SA 4.0** (usage non commercial, attribution). Ils sont téléchargés à l'exécution et ne sont pas redistribués dans ce dossier. Leur usage dans des outils de triche est explicitement interdit.
- Données de quêtes : API publique [tarkov.dev](https://tarkov.dev).
- Leaflet 1.9.4 (BSD-2), embarqué dans `ui/vendor/`.

## Carte entière et état « en raid »

- La carte n'est **plus recentrée** sur le joueur : elle reste toujours visible en entier (impossible de dézoomer au-delà de la vue complète). Le bouton **Vue entière** revient à cette vue après un zoom.
- Les anciens événements de raid présents dans les logs au démarrage sont ignorés ; un raid « oublié » expire au bout de ~75 min ; la **pastille « En raid / Hors raid »** (en haut) est cliquable pour corriger l'état à la main.
- À chaque capture d'écran, la carte est corrigée d'après les coordonnées (si elles ne tiennent pas dans la carte affichée), et la capture prouve qu'on est en raid.
- Les noms de cartes inconnus vus dans les logs sont listés dans le diagnostic des logs (Paramètres).

## Nouveautés (améliorations)

- **Extraction la plus proche** : bandeau en haut de la carte avec son nom, la distance et une flèche (orientée comme sur la carte).
- **Rappel de capture discret** : notification dans l'application (ou bip, ou les deux), avec un délai réglable **par carte** (Réglages).
- **Superposition** (touche G ou bouton) : petite fenêtre toujours au premier plan avec seulement la carte et le bandeau d'extraction.
- **Parcours** (touche P) : ordre de visite conseillé (plus proche voisin) des objectifs de tes quêtes en cours sur la carte, tracé et numéroté.
- **Objets à trouver** : liste dans l'onglet Quêtes, tirée des objectifs des quêtes en cours.
- **Alerte au changement de carte** : « N quêtes en cours sur Douanes ».
- **Statistiques** (onglet Stats) : nombre de raids, durée moyenne, et carte de chaleur des zones visitées par carte.
- **Sauvegarde** (Réglages) : export / import des quêtes, de l'historique et des repères (le fichier importé est validé).
- **Diagnostic de raid** (Réglages) : les dernières lignes de logs liées aux raids, l'état détecté et les cartes non reconnues ; bouton Copier.
- **Raccourcis** : V vue entière, T trajet, O objectifs, E extractions, P parcours, M mesurer, R repère, G superposition, 1 à 5 pour changer d'onglet.
- **Installateur** : `build_exe.bat` (Windows, Python requis une fois) produit `dist\TarkovCompanion\TarkovCompanion.exe`.


