"""Prépare une fiche de la file d'attente pour le repérage et le montage, sans Whisper.

- Récupère les sous-titres anglais de YouTube (manuels sinon automatiques), horodatés au mot,
  et les convertit au même format que transcrire.py : clips/<id>/transcription.json + transcription.txt.
- Télécharge la vidéo (1080p max) dans sources/<id>.mp4 pendant ce temps (en parallèle).
- Passe la fiche file_attente/<id>.json au statut « pret ».

Usage : python -I outils/preparer.py <id> [<id> ...]
"""
import json, re, sys, threading
from pathlib import Path
import yt_dlp

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I n'ajoute pas le dossier du script
from journal import noter

RACINE = Path(__file__).resolve().parent.parent
FFMPEG_DIR = r"C:\Projets\Outils\manim-venv\Scripts"
OPTS = {"quiet": True, "no_warnings": True, "js_runtimes": {"node": {}}}


def hms(s):
    return f"{int(s // 3600):02d}:{int(s % 3600 // 60):02d}:{s % 60:06.3f}"


def json3_vers_transcription(data):
    """Format json3 de YouTube -> liste de segments {start, end, text, words:[{start, end, word}]}."""
    segments = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs or "tStartMs" not in ev:
            continue
        t0, dur = ev["tStartMs"] / 1000, ev.get("dDurationMs", 0) / 1000
        mots = []
        for s in segs:
            # retire les changements de locuteur (>>) et les bruits ([Music], [Applause])
            txt = re.sub(r">>|\[[^\]]*\]", "", s.get("utf8", "").replace("\n", " "))
            if not txt.strip():
                continue
            mots.append({"start": t0 + s.get("tOffsetMs", 0) / 1000, "word": " " + txt.strip()})
        for i, m in enumerate(mots):
            m["end"] = mots[i + 1]["start"] if i + 1 < len(mots) else t0 + dur
        if mots:
            segments.append({"start": mots[0]["start"], "end": mots[-1]["end"],
                             "text": "".join(m["word"] for m in mots).strip(), "words": mots})
    # Les sous-titres auto se chevauchent : on supprime les mots déjà vus (même instant).
    vus, propres = set(), []
    for seg in segments:
        seg["words"] = [w for w in seg["words"] if (round(w["start"], 2), w["word"]) not in vus]
        vus.update((round(w["start"], 2), w["word"]) for w in seg["words"])
        if seg["words"]:
            seg["text"] = "".join(w["word"] for w in seg["words"]).strip()
            propres.append(seg)
    return propres


def sous_titres(vid, dossier):
    url = f"https://www.youtube.com/watch?v={vid}"
    with yt_dlp.YoutubeDL({**OPTS, "skip_download": True}) as y:
        info = y.extract_info(url, download=False)
    manuels = {k: v for k, v in (info.get("subtitles") or {}).items() if k == "en" or k.startswith("en-")}
    autos = info.get("automatic_captions") or {}
    pistes = manuels or {k: autos[k] for k in ("en-orig", "en") if k in autos}
    if not pistes:
        raise SystemExit(f"{vid} : pas de sous-titres anglais")
    langue, formats = next(iter(pistes.items()))
    piste = next(f for f in formats if f.get("ext") == "json3")
    with yt_dlp.YoutubeDL(OPTS) as y:
        data = json.loads(y.urlopen(piste["url"]).read().decode("utf-8"))
    segs = json3_vers_transcription(data)
    (dossier / "transcription.json").write_text(json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
    (dossier / "transcription.txt").write_text(
        "\n".join(f"[{hms(s['start'])} -> {hms(s['end'])}] {s['text']}" for s in segs), encoding="utf-8")
    return f"{len(segs)} segments ({'manuels' if manuels else 'auto'} {langue})"


def video(vid):
    sortie = RACINE / "sources" / f"{vid}.mp4"
    if sortie.exists():
        return
    with yt_dlp.YoutubeDL({**OPTS, "noprogress": True, "ffmpeg_location": FFMPEG_DIR, "merge_output_format": "mp4",
                           "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
                           "outtmpl": str(RACINE / "sources" / f"{vid}.%(ext)s")}) as y:
        y.download([f"https://www.youtube.com/watch?v={vid}"])


def preparer(vid):
    fiche_p = RACINE / "file_attente" / f"{vid}.json"
    fiche = json.loads(fiche_p.read_text(encoding="utf-8")) if fiche_p.exists() else {"id": vid}
    dossier = RACINE / "clips" / vid; dossier.mkdir(parents=True, exist_ok=True)
    noter("preparateur", "debut", vid, f"Sous-titres + téléchargement : {fiche.get('titre', vid)}")
    th = threading.Thread(target=video, args=(vid,)); th.start()
    try:
        resume = sous_titres(vid, dossier)
    except BaseException as e:
        noter("preparateur", "erreur", vid, str(e)[:200]); th.join(); raise
    (dossier / "info.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    th.join()
    fiche["statut"] = "pret"
    fiche_p.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    noter("preparateur", "fin", vid, f"Prête : {resume}")
    print(f"PRET {vid} | {resume} | sources/{vid}.mp4")


if __name__ == "__main__":
    ids = sys.argv[1:]
    with __import__("concurrent.futures").futures.ThreadPoolExecutor(4) as ex:
        list(ex.map(preparer, ids))
