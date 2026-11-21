"""Publie des clips sur TikTok avec l'API officielle (Content Posting API, Direct Post).

Usage (depuis C:\\Projets\\Clipping, avec le Python du projet et -I) :
  python -I outils/publier.py liste                     # clips prêts et ce qui bloque
  python -I outils/publier.py publier <id> [<id> ...]   # simulation : ne poste rien
  python -I outils/publier.py publier <id> --envoyer    # poste vraiment
  python -I outils/publier.py publier --tout --envoyer  # tous les clips publiables
  python -I outils/publier.py statut <publish_id>

Garde-fous (non négociables) :
  - un clip n'est publié que si son créateur a "autorise": true dans config/createurs_us.json ;
  - sans --envoyer, rien n'est posté (simulation) ;
  - un clip déjà publié (file_attente/publies.json) n'est jamais reposté ;
  - la légende doit citer la source (ligne « Credit »).
Configuration : config/tiktok.json (clés de l'app) et config/tiktok_token.json (écrit par tiktok_connexion.py).
"""
import json, re, sys, time, argparse, urllib.request, urllib.error, urllib.parse
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CONFIG = RACINE / "config"
CLIPS = RACINE / "clips"
FILE = RACINE / "file_attente"
PUBLIES = FILE / "publies.json"
API = "https://open.tiktokapis.com"
TAILLE_MAX_UN_BLOC = 64 * 1024 * 1024
TAILLE_BLOC = 32 * 1024 * 1024

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from journal import noter
except Exception:  # le journal est un confort, pas une condition
    def noter(*a, **k):
        pass


def lire_json(chemin, defaut=None):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defaut


def ecrire_json(chemin, donnees):
    Path(chemin).write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")


def http(methode, url, corps=None, entetes=None, brut=None):
    donnees = brut if brut is not None else (json.dumps(corps).encode("utf-8") if corps is not None else None)
    req = urllib.request.Request(url, data=donnees, method=methode, headers=entetes or {})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            texte = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(texte) if texte.strip().startswith("{") else texte), dict(r.headers)
    except urllib.error.HTTPError as e:
        texte = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(texte), dict(e.headers)
        except ValueError:
            return e.code, texte, dict(e.headers)


# ---------- jeton ----------

def jeton_valide():
    cfg = lire_json(CONFIG / "tiktok.json")
    tok = lire_json(CONFIG / "tiktok_token.json")
    if not cfg or not tok:
        raise SystemExit("TikTok n'est pas connecté : remplis config/tiktok.json puis lance outils/tiktok_connexion.py")
    if time.time() > tok.get("expire_a", 0) - 300:
        corps = urllib.parse.urlencode({
            "client_key": cfg["client_key"], "client_secret": cfg["client_secret"],
            "grant_type": "refresh_token", "refresh_token": tok["refresh_token"]}).encode()
        code, rep, _ = http("POST", API + "/v2/oauth/token/", brut=corps,
                            entetes={"Content-Type": "application/x-www-form-urlencoded"})
        if code != 200 or "access_token" not in rep:
            raise SystemExit(f"Renouvellement du jeton refusé ({code}) : {rep}. Relance tiktok_connexion.py.")
        tok = {"access_token": rep["access_token"], "refresh_token": rep["refresh_token"],
               "expire_a": time.time() + int(rep["expires_in"]), "open_id": rep.get("open_id")}
        ecrire_json(CONFIG / "tiktok_token.json", tok)  # le refresh_token change à chaque fois
    return tok["access_token"], cfg


# ---------- clips ----------

def createurs():
    cfg = lire_json(CONFIG / "createurs_us.json", {"createurs": []})
    return {c["chaine"]: c for c in cfg["createurs"]}


def infos_video(vid):
    for p in (CLIPS / vid / "info.json", FILE / f"{vid}.json"):
        d = lire_json(p)
        if d:
            return d
    return None


def legende_tiktok(chemin_txt):
    """Renvoie (credit, titre, legende_tiktok) lus dans clip_NN.txt."""
    texte = Path(chemin_txt).read_text(encoding="utf-8")
    credit = re.search(r"^\s*(?:Cr[ée]dit|Credit)\s*:\s*(.+)$", texte, re.M | re.I)
    titre = re.search(r"^\s*(?:TITRE|TITLE)\s*:\s*(.+)$", texte, re.M | re.I)
    bloc = re.search(r"^\s*TIK\s?TOK\s*:?\s*$\n(.*?)(?=^\s*(?:INSTAGRAM|YOUTUBE)[^\n]*$|\Z)", texte, re.M | re.I | re.S)
    return (credit.group(1).strip() if credit else None,
            titre.group(1).strip() if titre else None,
            bloc.group(1).strip() if bloc else None)


def clips_publiables():
    """Liste de dicts {cle, video, mp4, legende, ok, raison}."""
    deja = lire_json(PUBLIES, {})
    auto = createurs()
    sortie = []
    for dossier in sorted(p for p in CLIPS.iterdir() if p.is_dir()):
        for mp4 in sorted(dossier.glob("clip_*.mp4")):
            cle = f"{dossier.name}/{mp4.stem}"
            raison = None
            info = infos_video(dossier.name)
            credit, titre, legende = (None, None, None)
            txt = mp4.with_name(mp4.stem.removesuffix("_jeu") + ".txt")  # clip_01_jeu partage la légende de clip_01
            if txt.exists():
                credit, titre, legende = legende_tiktok(txt)
            if cle in deja:
                raison = "déjà publié"
            elif not info:
                raison = "vidéo source inconnue (pas d'info.json ni de fiche)"
            elif not auto.get(info.get("chaine"), {}).get("autorise"):
                raison = f"créateur {info.get('chaine')} non autorisé (clip de test)"
            elif not legende:
                raison = "pas de légende TikTok dans le .txt"
            elif not credit:
                raison = "pas de ligne Credit dans le .txt"
            sortie.append({"cle": cle, "video": dossier.name, "mp4": mp4, "legende": legende,
                           "titre": titre, "ok": raison is None, "raison": raison})
    return sortie


# ---------- TikTok ----------

def publier_un(clip, jeton, cfg, envoyer):
    mp4 = clip["mp4"]
    taille = mp4.stat().st_size
    titre = (clip["legende"] or "")[:2200]
    entetes = {"Authorization": f"Bearer {jeton}", "Content-Type": "application/json; charset=UTF-8"}

    code, rep, _ = http("POST", API + "/v2/post/publish/creator_info/query/", entetes=entetes, corps={})
    if code != 200 or rep.get("error", {}).get("code") != "ok":
        return False, f"creator_info refusé : {rep}"
    options = rep["data"]["privacy_level_options"]
    visibilite = cfg.get("visibilite", "SELF_ONLY")
    if visibilite not in options:
        return False, f"visibilité {visibilite} indisponible pour ce compte (options : {options})"
    if rep["data"].get("max_video_post_duration_sec") is not None:
        pass  # la durée est contrôlée par TikTok au traitement

    if not envoyer:
        return True, f"SIMULATION ok : {mp4.name} ({taille/1e6:.1f} Mo), visibilité {visibilite}, légende {len(titre)} caractères"

    bloc = taille if taille <= TAILLE_MAX_UN_BLOC else TAILLE_BLOC
    nb = max(1, taille // bloc)
    corps = {"post_info": {"title": titre, "privacy_level": visibilite,
                           "disable_duet": False, "disable_comment": False, "disable_stitch": False,
                           "video_cover_timestamp_ms": 1000},
             "source_info": {"source": "FILE_UPLOAD", "video_size": taille, "chunk_size": bloc, "total_chunk_count": nb}}
    code, rep, _ = http("POST", API + "/v2/post/publish/video/init/", entetes=entetes, corps=corps)
    if code != 200 or rep.get("error", {}).get("code") != "ok":
        return False, f"init refusé ({code}) : {rep}"
    publish_id, url_envoi = rep["data"]["publish_id"], rep["data"]["upload_url"]

    donnees = mp4.read_bytes()
    for i in range(nb):
        debut = i * bloc
        fin = taille if i == nb - 1 else debut + bloc  # le dernier bloc absorbe le reste
        morceau = donnees[debut:fin]
        code, rep, _ = http("PUT", url_envoi, brut=morceau, entetes={
            "Content-Type": "video/mp4", "Content-Length": str(len(morceau)),
            "Content-Range": f"bytes {debut}-{fin - 1}/{taille}"})
        if code not in (200, 201, 206):
            return False, f"envoi du bloc {i + 1}/{nb} refusé ({code}) : {rep}"

    for _ in range(30):  # jusqu'à ~2 min
        time.sleep(4)
        code, rep, _ = http("POST", API + "/v2/post/publish/status/fetch/", entetes=entetes, corps={"publish_id": publish_id})
        etat = rep.get("data", {}).get("status") if isinstance(rep, dict) else None
        if etat == "PUBLISH_COMPLETE":
            return True, f"publié ({visibilite}) publish_id={publish_id}"
        if etat == "FAILED":
            return False, f"échec TikTok : {rep['data'].get('fail_reason')} (publish_id={publish_id})"
    return True, f"envoyé, traitement en cours chez TikTok (publish_id={publish_id}) : vérifier avec « statut »"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("liste")
    p = sp.add_parser("publier")
    p.add_argument("ids", nargs="*", help="id de vidéo (dossier clips/<id>) ou id/clip_NN")
    p.add_argument("--tout", action="store_true")
    p.add_argument("--envoyer", action="store_true", help="poste vraiment (sinon simulation)")
    s = sp.add_parser("statut")
    s.add_argument("publish_id")
    a = ap.parse_args()

    if a.cmd == "liste":
        for c in clips_publiables():
            print(("PRET   " if c["ok"] else "BLOQUE ") + c["cle"] + ("" if c["ok"] else f"  — {c['raison']}"))
        return

    if a.cmd == "statut":
        jeton, _ = jeton_valide()
        _, rep, _ = http("POST", API + "/v2/post/publish/status/fetch/", corps={"publish_id": a.publish_id},
                         entetes={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json; charset=UTF-8"})
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return

    tous = clips_publiables()
    if a.tout:
        choisis = [c for c in tous if c["ok"]]
    else:
        choisis = [c for c in tous if any(c["cle"] == i or c["video"] == i for i in a.ids)]
        manquants = [i for i in a.ids if not any(c["cle"] == i or c["video"] == i for c in tous)]
        for i in manquants:
            print(f"INCONNU {i}")
    for c in choisis:
        if not c["ok"]:
            print(f"REFUSE  {c['cle']} — {c['raison']}")
    choisis = [c for c in choisis if c["ok"]]
    if not choisis:
        print("Rien à publier.")
        return

    jeton, cfg = jeton_valide()
    deja = lire_json(PUBLIES, {})
    for n, c in enumerate(choisis):
        if n:
            time.sleep(12)  # limite de TikTok : 6 créations par minute
        noter("publieur", "debut", c["video"], f"{'Publie' if a.envoyer else 'Simule'} {c['cle']}")
        ok, msg = publier_un(c, jeton, cfg, a.envoyer)
        print(("OK      " if ok else "ECHEC   ") + c["cle"] + " — " + msg)
        noter("publieur", "fin" if ok else "erreur", c["video"], msg[:120])
        if ok and a.envoyer:
            deja[c["cle"]] = {"quand": time.strftime("%Y-%m-%d %H:%M"), "detail": msg}
            ecrire_json(PUBLIES, deja)


if __name__ == "__main__":
    main()
