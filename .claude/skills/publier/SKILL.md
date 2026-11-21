---
name: publier
description: Publie sur TikTok les clips prêts et autorisés (API officielle). Utiliser quand Mehdi dit /publier, « publie les clips », « poste sur TikTok », ou à la fin de /clipper pour les créateurs autorisés.
---

# /publier — mise en ligne sur TikTok

Travaille depuis `C:\Projets\Clipping`.

1. Note `chef debut - "Lance /publier"` : `PYTHONIOENCODING=utf-8 /c/Projets/Outils/clipping-venv/Scripts/python -I outils/journal.py chef debut - "<phrase>"`.
2. Lance l'agent `publieur` (Haiku). Il fait `liste`, une simulation, puis la vraie publication seulement si la simulation est ok.
3. Compte rendu à Mehdi : un tableau clip / résultat / raison. Les clips `BLOQUE` pour « non autorisé » sont **normaux** : ce sont des tests. Dis-le en une phrase, sans proposer de contourner.
4. Note `chef fin - "<n> clips publiés"`.

## Prérequis (à faire par Mehdi, une fois)

- Un compte TikTok et une app sur https://developers.tiktok.com avec « Content Posting API » (scope `video.publish`).
- `config/tiktok.json` rempli (modèle : `config/tiktok.exemple.json`), puis `python -I outils/tiktok_connexion.py` lancé par lui.
- Tant que l'app n'a pas passé l'audit TikTok, les posts sont forcés en **privé** (`SELF_ONLY`) : normal.

## Règles

- Jamais de publication d'un créateur avec `autorise: false` dans `config/createurs_us.json`. Ne change pas ce fichier sans demande explicite de Mehdi, et seulement s'il a un accord du créateur.
- Pas d'automatisation du navigateur sur tiktok.com et jamais de mot de passe saisi par un agent.
