---
name: clipper
description: Chaîne complète de clipping pour le marché US, sans pause entre les agents. Le chasseur trouve les vidéos qui explosent, puis préparation, repérage, montage et légendes s'enchaînent en parallèle. Utiliser quand Mehdi dit /clipper, « lance la chasse », « trouve des clips » ou « fais des clips de <lien> ».
---

# /clipper — chef d'orchestre

Le relais entre agents se fait par les fiches de `file_attente/<id>.json`, dont le statut avance : `a_faire` → `pret` → `fait`. Tu enchaînes les étapes **sans attendre Mehdi entre deux** et tu lances en parallèle tout ce qui peut l'être. Travaille depuis `C:\Projets\Clipping`.

Python : `/c/Projets/Outils/clipping-venv/Scripts/python -I`, toujours avec `PYTHONIOENCODING=utf-8`.

**Tableau en direct.** Mehdi suit le travail sur le tableau des agents (`outils/tableau.py`, http://localhost:8770). Les scripts (chasseur, preparer, monter) écrivent tout seuls dans le journal. Pour les agents Claude, c'est toi qui notes **juste avant de les lancer** et **dès qu'ils reviennent** :
`$PY outils/journal.py <reperage|legendes|chef> <debut|fin|erreur> <id_video ou -> "<phrase courte>"`
Note aussi `chef debut - "Lance la chaîne /clipper"` au départ et `chef fin - "<n> clips prêts"` à la fin.

## 1. Chasse (agent `chasseur`, Haiku)

- Sans lien : lance l'agent `chasseur` (par défaut `--jours 7 --garder 3`, ou ce que Mehdi demande). Il dépose les fiches et prépare les vidéos (sous-titres et téléchargement).
- Avec un lien YouTube donné par Mehdi : saute la chasse et lance directement `outils/preparer.py <id>`.

## 2. Repérage (agent `reperage`, Sonnet), un par vidéo, tous en même temps

Dès que les vidéos sont `pret`, lance **dans le même message** un agent `reperage` par vidéo, en arrière-plan. Demande 3 clips par vidéo, avec les lignes `CLIP n | debut | fin`.

## 3. Montage et légendes, en parallèle, vidéo par vidéo

Dès qu'un repérage revient (sans attendre les autres) :
- **Montage** : lance toi-même `outils/monter.py` pour chaque clip (une commande Bash qui enchaîne les clips de la vidéo, en arrière-plan). Disposition : celle de `info.json` (`suivi` par défaut). Ajoute toujours `--jeu auto` : écran partagé avec, en bas, un de nos jeux hypnotiques originaux (`gameplay/`), sauf si Mehdi demande « sans jeu ». Les clips d'une même vidéo peuvent se lancer en parallèle (3 commandes avec `&` puis `wait`).
- **Légendes** : lance en même temps un agent `legendes` (Sonnet) sur la vidéo, en anglais américain.

## 4. Vérification (obligatoire)

Pour chaque clip, extrais 2 images (vers 3 s et au milieu) et regarde-les : cadrage correct (visage dans le cadre, pas de bande d'interface), sous-titres lisibles et justes. Corrige (disposition, bornes) et remonte si besoin. Vérifie la durée, le format 1080x1920 et le son avec `ffmpeg -i`.

Passe ensuite la fiche à `"statut": "fait"` et note `chef info <id> "Vidéo terminée et vérifiée"`.

## 5. Compte rendu

Un tableau par vidéo (clip, durée, titre), le dossier des clips, et pour chaque vidéo « AUTORISÉ » ou « test — ne pas publier » selon `autorise` dans `config/createurs_us.json`. Envoie les clips avec SendUserFile.

## Règles

- Ne publie rien toi-même : la mise en ligne TikTok passe par `/publier` (agent `publieur`, `outils/publier.py`), seulement pour les créateurs `autorise: true`. Lance `/publier` à la fin de la chaîne si au moins un clip est « AUTORISÉ » et que TikTok est connecté (`config/tiktok_token.json` existe) ; sinon dis-le en une ligne.
- Ne jamais modifier les fichiers de `sources/` ni `config/createurs_us.json` sans que Mehdi le demande.
- Pour le recadrage `reaction` d'un nouveau créateur, mesure d'abord ses zones (voir CLAUDE.md).
