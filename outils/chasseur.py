"""Chasseur de vidéos à clipper (marché US).

Parcourt les dernières vidéos des chaînes de config/createurs_us.json, mesure leur vitesse
(vues par heure depuis la mise en ligne), repère les pics « les plus revus » quand YouTube les donne,
vérifie la présence de sous-titres anglais, puis écrit :
  file_attente/candidats.json   : tous les candidats classés
  file_attente/<id>.json        : une fiche « a_faire » pour chacun des N meilleurs (le relais vers le montage)

Usage : python -I outils/chasseur.py [--jours 7] [--par-chaine 5] [--garder 3] [--duree-min 8]
"""
import argparse, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import yt_dlp

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I n'ajoute pas le dossier du script
from journal import noter

RACINE = Path(__file__).resolve().parent.parent
OPTS = {"quiet": True, "no_warnings": True, "skip_download": True, "js_runtimes": {"node": {}}}


def recents(chaine, n):
    with yt_dlp.YoutubeDL({**OPTS, "extract_flat": True, "playlistend": n}) as y:
        info = y.extract_info(f"https://www.youtube.com/{chaine}/videos", download=False)
    return [e["id"] for e in (info.get("entries") or [])[:n] if e.get("id")]


def pics(heatmap, duree, nb=3, largeur=45):
    """Les nb pics les plus revus, écartés d'au moins `largeur` s, sans le tout début (accroche/intro)."""
    out = []
    for h in sorted(heatmap or [], key=lambda h: -h["value"]):
        c = (h["start_time"] + h["end_time"]) / 2
        if c < 30 or c > duree - 15 or any(abs(c - p["centre"]) < largeur for p in out):
            continue
        out.append({"centre": round(c, 1), "intensite": round(h["value"], 2)})
        if len(out) == nb:
            break
    return out


def detail(vid, createur):
    try:
        with yt_dlp.YoutubeDL(OPTS) as y:
            v = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    except Exception as e:  # première à venir, vidéo privée, etc.
        return {"id": vid, "erreur": str(e)[:120]}
    ts = v.get("timestamp") or v.get("release_timestamp")
    heures = max((time.time() - ts) / 3600, 1) if ts else None
    vues = v.get("view_count") or 0
    subs = set(v.get("subtitles") or {}) | set(v.get("automatic_captions") or {})
    return {
        "id": vid, "url": f"https://www.youtube.com/watch?v={vid}", "titre": v.get("title"),
        "chaine": createur["chaine"], "nom_chaine": v.get("channel"), "autorise": createur.get("autorise", False),
        "disposition": createur.get("disposition", "centre"), "duree": v.get("duration") or 0,
        "vues": vues, "heures_en_ligne": round(heures, 1) if heures else None,
        "vues_par_heure": round(vues / heures) if heures else 0,
        "sous_titres_en": any(s == "en" or s.startswith("en-") for s in subs),
        "pics": pics(v.get("heatmap"), v.get("duration") or 0),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jours", type=float, default=7); p.add_argument("--par-chaine", type=int, default=5)
    p.add_argument("--garder", type=int, default=3); p.add_argument("--duree-min", type=float, default=8)
    a = p.parse_args()
    t0 = time.time()
    createurs = [c for c in json.loads((RACINE / "config" / "createurs_us.json").read_text(encoding="utf-8"))["createurs"]
                 if c.get("surveiller", True)]  # surveiller:false = entrée réservée à nos propres contenus (démo)
    noter("chasseur", "debut", None, f"Parcourt {len(createurs)} chaînes US ({a.jours:g} derniers jours)")

    with ThreadPoolExecutor(8) as ex:
        listes = list(ex.map(lambda c: (c, recents(c["chaine"], a.par_chaine)), createurs))
        taches = [(vid, c) for c, ids in listes for vid in ids]
        fiches = list(ex.map(lambda t: detail(*t), taches))

    ok = [f for f in fiches if "erreur" not in f and f["duree"] >= a.duree_min * 60 and f["sous_titres_en"]
          and f["heures_en_ligne"] is not None and f["heures_en_ligne"] <= a.jours * 24]
    # Score : vitesse de vues, bonus si YouTube montre des pics « les plus revus » (moments viraux déjà identifiés).
    for f in ok:
        f["score"] = round(f["vues_par_heure"] * (1.3 if f["pics"] else 1.0))
    ok.sort(key=lambda f: -f["score"])

    file = RACINE / "file_attente"; file.mkdir(exist_ok=True)
    (file / "candidats.json").write_text(json.dumps(ok, ensure_ascii=False, indent=1), encoding="utf-8")
    deja = {p.stem for p in file.glob("*.json")} | {p.name for p in (RACINE / "clips").glob("*")}
    nouveaux = []
    for f in ok:
        if len(nouveaux) == a.garder:
            break
        if f["id"] in deja:
            continue
        (file / f"{f['id']}.json").write_text(json.dumps({**f, "statut": "a_faire"}, ensure_ascii=False, indent=1), encoding="utf-8")
        nouveaux.append(f)

    print(f"{len(fiches)} vidéos analysées, {len(ok)} candidates, en {time.time() - t0:.0f} s")
    for f in nouveaux:
        noter("chasseur", "info", f["id"], f"Repérée : {f['nom_chaine']} — {f['titre']} ({f['vues_par_heure']:,} vues/h)".replace(",", " "))
    noter("chasseur", "fin", None, f"{len(fiches)} vidéos analysées, {len(nouveaux)} nouvelle(s) en file d'attente")
    for f in nouveaux:
        print(f"A_FAIRE {f['id']} | {f['vues_par_heure']} vues/h | pics={len(f['pics'])} | "
              f"{'AUTORISÉ' if f['autorise'] else 'test'} | {f['nom_chaine']} | {f['titre']}")


if __name__ == "__main__":
    main()
