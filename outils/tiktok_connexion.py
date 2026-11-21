"""Connecte le projet à TON compte TikTok (une seule fois, par toi, dans ton navigateur).

Avant : crée une app sur https://developers.tiktok.com, ajoute le produit « Content Posting API »
(scope video.publish), enregistre une adresse de redirection, puis copie
config/tiktok.exemple.json en config/tiktok.json et remplis-le.

Usage : python -I outils/tiktok_connexion.py
  1. le script affiche un lien : ouvre-le, connecte-toi à TikTok et autorise ;
  2. TikTok te renvoie vers ton adresse de redirection avec ?code=... dans la barre d'adresse ;
  3. copie l'adresse complète et colle-la ici : le jeton est enregistré dans config/tiktok_token.json.
Le mot de passe TikTok ne passe jamais par ce script ni par Claude : tu le tapes toi-même sur tiktok.com.
"""
import json, secrets, time, urllib.parse, urllib.request, urllib.error
from pathlib import Path

CONFIG = Path(__file__).resolve().parent.parent / "config"


def main():
    chemin = CONFIG / "tiktok.json"
    if not chemin.exists():
        raise SystemExit("Copie config/tiktok.exemple.json en config/tiktok.json et remplis-le d'abord.")
    cfg = json.loads(chemin.read_text(encoding="utf-8"))
    etat = secrets.token_urlsafe(12)
    lien = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode({
        "client_key": cfg["client_key"], "scope": "user.info.basic,video.publish",
        "response_type": "code", "redirect_uri": cfg["redirect_uri"], "state": etat})
    print("1) Ouvre ce lien et autorise l'application :\n\n" + lien + "\n")
    retour = input("2) Colle ici l'adresse complète où TikTok t'a renvoyé : ").strip()
    q = urllib.parse.parse_qs(urllib.parse.urlparse(retour).query)
    if q.get("state", [None])[0] != etat:
        raise SystemExit("Le paramètre state ne correspond pas : recommence.")
    if "code" not in q:
        raise SystemExit(f"Pas de code dans l'adresse (erreur : {q.get('error_description', q.get('error'))}).")
    corps = urllib.parse.urlencode({
        "client_key": cfg["client_key"], "client_secret": cfg["client_secret"], "code": q["code"][0],
        "grant_type": "authorization_code", "redirect_uri": cfg["redirect_uri"]}).encode()
    req = urllib.request.Request("https://open.tiktokapis.com/v2/oauth/token/", data=corps, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        rep = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Refusé : {e.read().decode()}")
    if "access_token" not in rep:
        raise SystemExit(f"Réponse inattendue : {rep}")
    (CONFIG / "tiktok_token.json").write_text(json.dumps({
        "access_token": rep["access_token"], "refresh_token": rep["refresh_token"],
        "expire_a": time.time() + int(rep["expires_in"]), "open_id": rep.get("open_id")}, indent=1), encoding="utf-8")
    print("Connecté. Jeton enregistré dans config/tiktok_token.json (ne le partage jamais).")


if __name__ == "__main__":
    main()
