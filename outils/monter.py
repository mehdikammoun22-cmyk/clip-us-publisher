"""Monte un clip vertical 1080x1920 avec sous-titres incrustés.

Usage :
  python monter.py <video_source> <transcription.json> <debut_s> <fin_s> <sortie.mp4> [--disposition reaction|centre]

Dispositions :
  reaction : facecam en haut (zone FACECAM) + contenu commenté en dessous (zone CONTENU). Pour les vidéos de réaction.
  centre   : recadrage 9:16 au centre de l'image.
Les zones sont données en pixels de la source 1920x1080 (à mesurer pour chaque nouveau créateur).
Produit aussi <sortie>.srt et <sortie>.ass.
"""
import argparse, json, random, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I n'ajoute pas le dossier du script
from journal import noter

FFMPEG = r"C:\Projets\Outils\manim-venv\Scripts\ffmpeg.exe"
FACECAM = (0, 0, 556, 294)       # x, y, largeur, hauteur
CONTENU = (452, 312, 608, 668)  # x, y, largeur, hauteur (haut masqué par la facecam, bas = barre « données analytiques » retirée)
H_HAUT = 570                     # hauteur de la facecam dans le clip (1080 de large) ; doit être paire (yuv420p)
MOTS_PAR_LIGNE = 3


def ts_srt(s):
    ms = int(round(s * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


def ts_ass(s):
    cs = int(round(s * 100)); h, cs = divmod(cs, 360000); m, cs = divmod(cs, 6000); sec, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{sec:02d}.{cs:02d}"


def groupes(transcription, debut, fin):
    """Découpe les mots du passage en petits groupes de MOTS_PAR_LIGNE, recalés sur le début du clip."""
    bruts = [w for seg in transcription for w in seg["words"] if w["end"] > debut and w["start"] < fin]
    # Whisper découpe « c'est » en « c » + « 'est » : un morceau sans espace devant se recolle au mot précédent.
    mots = []
    for w in bruts:
        if mots and not w["word"].startswith(" "):
            mots[-1] = {"start": mots[-1]["start"], "end": w["end"], "word": mots[-1]["word"] + w["word"]}
        else:
            mots.append(dict(w))
    out = []
    for i in range(0, len(mots), MOTS_PAR_LIGNE):
        g = mots[i:i + MOTS_PAR_LIGNE]
        texte = " ".join(w["word"].strip() for w in g).replace(" '", "'").strip()
        if texte:
            out.append((max(g[0]["start"], debut) - debut, min(g[-1]["end"], fin) - debut, texte))
    # combler les micro-trous pour éviter le clignotement
    for i in range(len(out) - 1):
        if out[i + 1][0] - out[i][1] < 0.3:
            out[i] = (out[i][0], out[i + 1][0], out[i][2])
    return out


def ecrire_sous_titres(g, base: Path, marge_v, alignement=2):
    base.with_suffix(".srt").write_text(
        "\n".join(f"{i}\n{ts_srt(a)} --> {ts_srt(b)}\n{t}\n" for i, (a, b, t) in enumerate(g, 1)), encoding="utf-8")
    entete = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Clip,Arial Black,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,7,3,{alignement},80,80,{marge_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lignes = [f"Dialogue: 0,{ts_ass(a)},{ts_ass(b)},Clip,,0,0,0,,{t.upper()}" for a, b, t in g]
    ass = base.with_suffix(".ass")
    ass.write_text(entete + "\n".join(lignes) + "\n", encoding="utf-8")
    return ass


def trajectoire_visage(source, debut, fin, dossier_tmp: Path, pas=0.5, larg_analyse=640):
    """Position horizontale (en fraction de la largeur) du plus grand visage, toutes les `pas` secondes.
    Lissée, avec saut net aux changements de plan. Retourne [(t_relatif, centre_x_fraction)]."""
    import cv2, numpy as np
    w, h = larg_analyse, larg_analyse * 9 // 16
    raw = subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-ss", f"{debut:.3f}", "-to", f"{fin:.3f}",
                          "-i", source, "-vf", f"fps={1 / pas},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True, check=True).stdout
    images = np.frombuffer(raw, np.uint8).reshape(-1, h, w)
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    det_profil = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
    xs = []
    for im in images:
        faces = list(det.detectMultiScale(im, 1.1, 6, minSize=(h // 10, h // 10)))
        if not faces:
            faces = list(det_profil.detectMultiScale(im, 1.1, 6, minSize=(h // 10, h // 10)))
        if faces:
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + fw / 2) / w)
        else:
            xs.append(None)
    # trous : on garde la dernière position connue (sinon le centre)
    connu, pleins = 0.5, []
    for x in xs:
        connu = x if x is not None else connu
        pleins.append(connu)
    # lissage exponentiel, sauf saut > 25 % de la largeur (changement de plan) où l'on recale d'un coup
    lisses, cur = [], pleins[0] if pleins else 0.5
    for x in pleins:
        cur = x if abs(x - cur) > 0.25 else cur + 0.35 * (x - cur)
        lisses.append(cur)
    return [(i * pas, x) for i, x in enumerate(lisses)]


def commandes_recadrage(traj, duree, dossier_tmp: Path, fps=30, larg_src=1920, larg_crop=608):
    """Fichier sendcmd qui déplace le recadrage image par image (interpolation linéaire entre les points)."""
    lignes = []
    for k in range(int(duree * fps) + 1):
        t = k / fps
        j = min(int(t / 0.5), len(traj) - 1)
        if j + 1 < len(traj):
            (t0, x0), (t1, x1) = traj[j], traj[j + 1]
            x = x1 if abs(x1 - x0) > 0.25 else x0 + (x1 - x0) * (t - t0) / (t1 - t0)
        else:
            x = traj[j][1]
        px = int(min(max(x * larg_src - larg_crop / 2, 0), larg_src - larg_crop))
        lignes.append(f"{t:.4f} crop@c x {px};")
    f = dossier_tmp / "suivi.cmd"
    f.write_text("\n".join(lignes), encoding="utf-8")
    return f


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source"); p.add_argument("transcription"); p.add_argument("debut", type=float)
    p.add_argument("fin", type=float); p.add_argument("sortie")
    p.add_argument("--disposition", default="reaction", choices=["reaction", "centre", "suivi"])
    p.add_argument("--jeu", default="aucun",
                   help="moitié basse « jeu hypnotique » : aucun | auto (au hasard) | anneaux | descente | chute")
    a = p.parse_args()

    sortie = Path(a.sortie); sortie.parent.mkdir(parents=True, exist_ok=True)
    g = groupes(json.loads(Path(a.transcription).read_text(encoding="utf-8")), a.debut, a.fin)
    duree = a.fin - a.debut
    entree_jeu = []

    if a.jeu != "aucun":
        # Écran partagé : clip en haut (1080x960), jeu en bas (1080x960), sous-titres sur la jonction.
        if a.disposition == "reaction":
            raise SystemExit("--jeu ne marche qu'avec --disposition centre ou suivi")
        dossier_jeux = Path(__file__).resolve().parent.parent / "gameplay"
        jeux = sorted(dossier_jeux.glob("*.mp4"))
        fichier = random.choice(jeux) if a.jeu == "auto" else dossier_jeux / f"{a.jeu}.mp4"
        depart = random.uniform(0, 120)  # départ au hasard dans la boucle de 3 min : jamais deux fois le même passage
        entree_jeu = ["-stream_loop", "-1", "-ss", f"{depart:.2f}", "-i", str(fichier)]
        ass = ecrire_sous_titres(g, sortie, marge_v=0, alignement=5)
        ass_ff = str(ass).replace("\\", "/").replace(":", "\\:")
        if a.disposition == "suivi":
            traj = trajectoire_visage(a.source, a.debut, a.fin, sortie.parent)
            cmd_f = commandes_recadrage(traj, duree, sortie.parent, larg_crop=1215)
            cmd_ff = str(cmd_f).replace("\\", "/").replace(":", "\\:")
            haut = f"[0:v]fps=30,sendcmd=f='{cmd_ff}',crop@c=1215:1080:352:0,scale=1080:960,setsar=1[haut]"
        else:
            haut = "[0:v]fps=30,crop=1215:1080,scale=1080:960,setsar=1[haut]"
        graphe = (f"{haut};[1:v]fps=30,scale=1080:960,setsar=1[bas];"
                  f"[haut][bas]vstack,subtitles='{ass_ff}'[v]")
        print(f"jeu : {fichier.name} (départ {depart:.0f} s)")
    else:
        # Sous-titres sous la facecam (disposition réaction) ou au tiers bas (centre), hors interface TikTok.
        ass = ecrire_sous_titres(g, sortie, marge_v=560 if a.disposition == "reaction" else 520)
        ass_ff = str(ass).replace("\\", "/").replace(":", "\\:")

    if a.jeu != "aucun":
        pass
    elif a.disposition == "reaction":
        fx, fy, fw, fh = FACECAM; cx, cy, cw, ch = CONTENU
        h_bas = 1920 - H_HAUT
        graphe = (f"[0:v]split[a][b];"
                  f"[a]crop={fw}:{fh}:{fx}:{fy},scale=1080:{H_HAUT}[haut];"
                  f"[b]crop={cw}:{ch}:{cx}:{cy},scale=-2:{h_bas},crop=1080:{h_bas}[bas];"
                  f"[haut][bas]vstack,setsar=1,fps=30,subtitles='{ass_ff}'[v]")
    elif a.disposition == "suivi":
        # Recadrage 9:16 qui suit le plus grand visage (vlogs, podcasts filmés à la main).
        traj = trajectoire_visage(a.source, a.debut, a.fin, sortie.parent)
        cmd_f = commandes_recadrage(traj, a.fin - a.debut, sortie.parent)
        cmd_ff = str(cmd_f).replace("\\", "/").replace(":", "\\:")
        graphe = (f"[0:v]fps=30,sendcmd=f='{cmd_ff}',crop@c=608:1080:656:0,scale=1080:1920,setsar=1,"
                  f"subtitles='{ass_ff}'[v]")
    else:
        graphe = f"[0:v]crop=ih*9/16:ih,scale=1080:1920,setsar=1,fps=30,subtitles='{ass_ff}'[v]"

    cmd = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{a.debut:.3f}", "-to", f"{a.fin:.3f}",
           "-i", a.source, *entree_jeu, "-filter_complex", graphe, "-map", "[v]", "-map", "0:a", "-t", f"{duree:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-af", "loudnorm=I=-14:TP=-1.5", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", str(sortie)]
    video = sortie.parent.name
    noter("monteur", "debut", video, f"Monte {sortie.stem} ({duree:.0f} s, {a.disposition}{', jeu ' + a.jeu if a.jeu != 'aucun' else ''})")
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        noter("monteur", "erreur", video, f"{sortie.stem} : ffmpeg a échoué ({e.returncode})"); raise
    noter("monteur", "fin", video, f"{sortie.stem} prêt")
    print(f"OK {sortie} ({a.fin - a.debut:.1f} s, {len(g)} sous-titres)")


if __name__ == "__main__":
    main()
