# Changelog

## 1.2.1
L'exe est maintenant un fichier unique (plus de dossier `_internal`).
Flèche relative à ton regard (elle tourne quand tu te tournes) ; réglage pour revenir au mode « nord de la carte ».
Suivre un repère : même flèche et même distance (fenêtre principale et mini-fenêtre) que pour une quête.
Détection du raid corrigée d'après de vrais logs Tarkov 1.2.5 : la ligne « TRACE-NetworkGameCreate 6 » (après le début du raid) ne remet plus l'état à « hors raid » ; la fin de raid est détectée via le rechargement du profil et la coupure réseau (network-connection.log) ; dates sans fuseau acceptées ; un raid en cours au lancement du logiciel est repris. Superposition remplacée par une mini-fenêtre séparée (flèche + distance), sans bordure, déplaçable à la souris et toujours au premier plan.

## 1.2.0
Quête suivie avec flèche vers l'objectif ; liste des quêtes dans la superposition ; correctifs d'affichage.

## 1.1.0
Voir RELEASE_NOTES.md.

## 1.0.0
Première version : carte, position via captures d'écran, suivi des quêtes depuis les logs, extractions par camp.
