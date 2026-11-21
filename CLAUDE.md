# Projet Clipping

Découper des vidéos longues en clips courts verticaux (9:16) avec sous-titres, prêts pour TikTok, Instagram Reels et YouTube Shorts.

## Dossiers

- `sources/` : vidéos longues à traiter (une par fichier, nom parlant).
- `clips/<nom-de-la-source>/` : clips produits, avec pour chacun le `.mp4`, le `.srt` et un `.txt` (titre, légende, hashtags).
- `clips/<nom-de-la-source>/reperage.md` : la liste des moments retenus, avec leurs horodatages.

## Outils

- ffmpeg : `C:\Projets\Outils\manim-venv\Scripts\ffmpeg.exe` (il n'est pas dans le PATH).
- Python des outils de clipping : `C:\Projets\Outils\clipping-venv\Scripts\python.exe` (Python 3.14), avec :
  - faster-whisper pour la transcription (modèle `small`, il tourne en local) ;
  - yt-dlp pour télécharger (à lancer avec `-m yt_dlp --ffmpeg-location C:\Projets\Outils\manim-venv\Scripts`).

## Marché visé : US

Depuis le 17/11/2026, on vise le marché américain : vidéos US, sous-titres et légendes en anglais. Pour lancer toute la chaîne d'un coup : `/clipper` (skill du projet), ou `/clipper <lien>` pour une vidéo précise.

Le relais entre agents passe par les fiches `file_attente/<id>.json` (statut `a_faire` → `pret` → `fait`) :
- `outils/chasseur.py` : surveille les chaînes de `config/createurs_us.json` et classe les vidéos récentes par vues par heure. Il ajoute un bonus si YouTube donne les pics « les plus revus », qui n'existent que sur certaines chaînes. Environ 1 min pour 40 vidéos.
- `outils/preparer.py <id> …` : récupère les sous-titres anglais de YouTube (horodatés au mot, donc pas besoin de Whisper) et télécharge la vidéo. Environ 20 s par vidéo.
- Whisper (`transcrire.py`) ne sert plus que pour les vidéos sans sous-titres (par exemple en français).

## Scripts (dans `outils/`)

- Transcription : `python -I outils/transcrire.py <video> clips/<source>` → `transcription.json` (mots horodatés) + `transcription.txt`. Sur le processeur, c'est lent : environ 3 min de calcul par minute de vidéo (32 min pour 11 min 38). À lancer en arrière-plan.
- Montage : `python -I outils/monter.py <video> clips/<source>/transcription.json <debut_s> <fin_s> clips/<source>/clip_NN.mp4 [--disposition reaction|centre]`.
  - `reaction` : facecam en haut + contenu commenté en dessous. Les zones `FACECAM` et `CONTENU` en tête du script sont mesurées pour la mise en page d'Anyme : à re-mesurer pour chaque nouveau créateur (extraire une image et regarder).
  - `centre` : recadrage 9:16 au centre (créateur plein écran, immobile).
  - `suivi` : le recadrage suit le plus grand visage (OpenCV, en local). C'est le meilleur choix pour les vlogs et les podcasts, mais il peut se tromper de personne dans une foule, donc vérifie les images. Il faut OpenCV 4 (`opencv-python-headless<5`), car la version 5 n'a plus le détecteur.
  - `--jeu auto|anneaux|descente|chute` : écran partagé, avec le clip en haut (1080x960) et un jeu hypnotique en bas (1080x960), sous-titres sur la jonction. Marche avec `centre` et `suivi`. Les jeux sont **nos propres animations** (`outils/jeux.py` → `gameplay/`), donc il n'y a pas de risque de droits, contrairement à des images de Subway Surfers ou de Minecraft. N'utilise jamais d'images de jeux existants. Pour en refaire ou en ajouter : `python -I outils/jeux.py <nom> --duree 180`.
  - Toujours vérifier une image de chaque clip : la mise en page de la source peut changer en cours de vidéo (outro en plein écran, etc.).
- Les agents du projet (`reperage`, `montage`, `legendes`) ne se chargent que dans une session ouverte dans `C:\Projets\Clipping`.

## Droits

Clipper la vidéo d'un autre créateur pour la publier n'est permis que s'il l'autorise (programme de clipping, accord). Sinon, les clips restent des tests. Toujours créditer la source dans la légende.

## Contenu des comptes (skills réseaux)

Pour trouver des idées, faire la veille, planifier la semaine, écrire légendes/bio ou préparer des réponses aux commentaires : skills globaux `reseaux-idees`, `reseaux-veille`, `reseaux-planning`, `reseaux-legendes`, `reseaux-reponses`. La fiche de ce compte est `~/.claude/reseaux/comptes/clipping.md` (celle de Prepadmis : `prepadmis.md`). Claude propose, Mehdi publie ; jamais de commentaires ou messages automatiques sur les comptes des autres.

## Répartition du travail

Chaque étape a son agent. Lance-les dans cet ordre, en leur passant les fichiers de l'étape précédente :

1. `reperage` (Sonnet) : il lit la transcription et choisit les meilleurs passages.
2. `montage` (Haiku) : il découpe, recadre en 9:16 et incruste les sous-titres avec ffmpeg.
3. `legendes` (Sonnet) : il écrit le titre, la légende et les hashtags pour chaque plateforme.
4. `publieur` (Haiku) : il publie sur TikTok les clips terminés des créateurs autorisés (`/publier`). Il lit la légende TikTok dans `clip_NN.txt` (bloc `TIKTOK`) et exige la ligne `Credit:`. Les posts restent privés tant que l'app n'a pas passé l'audit TikTok.

Les agents globaux (`rapide`, `redac`, `batisseur`, `expert`) restent disponibles pour le reste.

## Règles

- Publication : depuis le 20/11/2026, Mehdi a demandé la publication automatique sur son compte TikTok. Elle passe **uniquement** par `outils/publier.py` (API officielle, agent `publieur`, skill `/publier`), jamais par le navigateur, et **uniquement** pour les créateurs `autorise: true`. Instagram et YouTube Shorts restent à la main.
- `clips/demo_perso/` : clip de démo fait avec **notre propre animation** (créateur `@demo_perso`, `autorise: true`, `surveiller: false` dans `config/createurs_us.json`, donc ignoré par le chasseur). Il sert à la vidéo de démo de l'audit TikTok ; ne jamais y mettre de contenu de tiers.
- Mehdi crée lui-même le compte TikTok, l'app développeur et la connexion (`outils/tiktok_connexion.py`) : aucun agent ne saisit de mot de passe.
- Ne pas toucher aux fichiers de `sources/` (pas d'écrasement, pas de suppression).
- Durée d'un clip : entre 20 et 60 secondes, sauf demande contraire.
- Toujours vérifier la sortie (durée, format 1080x1920, son présent) avant de dire qu'un clip est prêt.
