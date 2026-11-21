"""Génère des vidéos « jeu hypnotique » originales (1080x960, 30 i/s) pour la moitié basse des clips.

Trois jeux, tous dessinés ici (aucune image de jeu existant, donc aucun risque de droits) :
  anneaux  : une balle rebondit dans des anneaux qui tournent et s'échappe par leurs ouvertures
  descente : une voiture dévale une route sans fin dans une vallée
  chute    : une balle tombe à travers des rangées de plots qui s'allument

Usage : python -I outils/jeux.py [anneaux|descente|chute|tous] [--duree 180]
Sortie : C:\\Projets\\Clipping\\gameplay\\<jeu>.mp4 (en boucle dans le montage, avec un départ au hasard)
"""
import argparse, colorsys, math, random, subprocess
from pathlib import Path
import cv2
import numpy as np

FFMPEG = r"C:\Projets\Outils\manim-venv\Scripts\ffmpeg.exe"
W, H, FPS = 1080, 960, 30
SORTIE = Path(__file__).resolve().parent.parent / "gameplay"


def couleur(h, s=0.85, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return (int(b * 255), int(g * 255), int(r * 255))  # BGR


def fond_degrade(haut, bas):
    t = np.linspace(0, 1, H)[:, None, None]
    return (np.array(haut)[None, None, :] * (1 - t) + np.array(bas)[None, None, :] * t).repeat(W, 1).astype(np.uint8)


def encodeur(nom):
    SORTIE.mkdir(exist_ok=True)
    return subprocess.Popen([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(SORTIE / f"{nom}.mp4")],
                            stdin=subprocess.PIPE)


# ---------------------------------------------------------------- anneaux
def anneaux(n_images, rng):
    fond = fond_degrade((40, 12, 18), (70, 20, 10))
    cx, cy, br = W // 2, H // 2, 16
    particules, trace = [], []

    def nouveaux():
        n = 9
        return [{"r": 95 + i * 44, "a": rng.uniform(0, 360), "v": (1 if i % 2 else -1) * rng.uniform(55, 110),
                 "trou": rng.uniform(38, 52), "h": i / n} for i in range(n)]

    rings = nouveaux()
    pos, vel = np.array([cx + 10.0, cy - 20.0]), np.array([180.0, 0.0])
    t_hue = 0.0
    for k in range(n_images):
        dt = 1 / FPS / 4
        for _ in range(4):
            vel[1] += 900 * dt
            pos += vel * dt
            for ring in rings:
                ring["a"] = (ring["a"] + ring["v"] * dt) % 360
            if rings:
                rg = rings[0]
                d = pos - (cx, cy)
                dist = math.hypot(*d)
                if dist + br >= rg["r"]:
                    ang = math.degrees(math.atan2(d[1], d[0])) % 360
                    ecart = (ang - rg["a"] + 180) % 360 - 180
                    if abs(ecart) < rg["trou"] / 2:  # s'échappe par l'ouverture : l'anneau explose
                        for j in range(70):
                            th = math.radians(rng.uniform(0, 360))
                            particules.append([cx + rg["r"] * math.cos(th), cy + rg["r"] * math.sin(th),
                                               math.cos(th) * rng.uniform(100, 400), math.sin(th) * rng.uniform(100, 400),
                                               1.0, rg["h"]])
                        rings.pop(0)
                    else:  # rebond sur l'anneau, avec un petit gain d'énergie pour garder du rythme
                        nrm = d / dist
                        vel -= 2 * np.dot(vel, nrm) * nrm
                        vel *= 1.01
                        vel += nrm * -40
                        pos = (cx, cy) + nrm * (rg["r"] - br - 1)
                        sp = math.hypot(*vel)
                        if sp > 1300:
                            vel *= 1300 / sp
            elif math.hypot(*(pos - (cx, cy))) > 620:  # tous les anneaux franchis : on recommence
                rings = nouveaux()
                pos, vel = np.array([cx + 10.0, cy - 20.0]), np.array([rng.uniform(-200, 200), 0.0])
        t_hue += 0.004
        img = fond.copy()
        for rg in rings:
            a0, tr = rg["a"], rg["trou"]
            cv2.ellipse(img, (cx, cy), (int(rg["r"]), int(rg["r"])), 0, a0 + tr / 2, a0 + 360 - tr / 2,
                        couleur(rg["h"] + t_hue), 9, cv2.LINE_AA)
        trace.append((int(pos[0]), int(pos[1])))
        trace = trace[-18:]
        for i, p in enumerate(trace):
            cv2.circle(img, p, int(br * (i + 1) / len(trace)), couleur(t_hue * 3 + i / 40, 0.6), -1, cv2.LINE_AA)
        cv2.circle(img, trace[-1], br, (255, 255, 255), -1, cv2.LINE_AA)
        for p in particules:
            p[0] += p[2] / FPS; p[1] += p[3] / FPS; p[3] += 500 / FPS; p[4] -= 1 / (FPS * 1.2)
            if p[4] > 0:
                cv2.circle(img, (int(p[0]), int(p[1])), max(1, int(5 * p[4])), couleur(p[5] + t_hue, 0.9, p[4]), -1, cv2.LINE_AA)
        particules[:] = [p for p in particules if p[4] > 0]
        compteur = f"{9 - len(rings)}/9"
        cv2.putText(img, compteur, (40, 80), cv2.FONT_HERSHEY_DUPLEX, 1.8, (255, 255, 255), 3, cv2.LINE_AA)
        yield img


# ---------------------------------------------------------------- descente
def descente(n_images, rng):
    SEG, N_VUS, CAM_H, PROF = 200, 160, 1500, 0.84
    n_seg = 3000
    courbe = np.zeros(n_seg); pente = np.zeros(n_seg)
    i = 0
    while i < n_seg:  # virages et descentes enchaînés au hasard
        lng = rng.randint(60, 160)
        c, p = rng.uniform(-6, 6), rng.uniform(-60, -15)
        for j in range(lng):
            if i + j < n_seg:
                e = math.sin(math.pi * j / lng)
                courbe[i + j], pente[i + j] = c * e, p * (0.4 + 0.6 * e)
        i += lng
    alt = np.cumsum(pente)
    ciel = fond_degrade((235, 160, 90), (200, 220, 255))
    monts = []
    for couche, (teinte, hauteur) in enumerate([((140, 110, 120), 330), ((110, 140, 95), 380), ((70, 120, 60), 430)]):
        xs = np.arange(0, W * 3 + 40, 40)
        ys = hauteur - (np.sin(xs / (180 + couche * 40)) * 60 + np.sin(xs / 67) * 25 + rng.uniform(0, 30))
        monts.append((teinte, np.stack([xs, ys], 1).astype(np.int32)))
    vitesse, z = 2.6 * SEG, 0.0
    decal = 0.0
    for k in range(n_images):
        z = (z + vitesse / FPS) % (SEG * (n_seg - N_VUS - 2))
        base = int(z // SEG)
        decal += courbe[base] * 0.6
        img = ciel.copy()
        for teinte, pts in monts:  # montagnes en parallaxe
            sh = int(-decal * (0.3 + 0.2 * monts.index((teinte, pts)))) % (W * 2)
            p = pts.copy(); p[:, 0] -= sh
            poly = np.concatenate([p, [[p[-1, 0], H], [p[0, 0], H]]])
            cv2.fillPoly(img, [poly], teinte, cv2.LINE_AA)
        cam_y = alt[base] + (alt[base + 1] - alt[base]) * (z % SEG) / SEG + CAM_H
        x, dx = 0.0, 0.0
        proj, max_y = [], H
        for n in range(N_VUS):  # projection pseudo-3D classique, du proche au lointain
            s = base + n
            dz = (n * SEG) - (z % SEG) + 1
            echelle = PROF / (dz / 1000)
            sx = W / 2 + (x - 0) * echelle * 0.5
            sy = H / 2 - (alt[s] - cam_y) * echelle * 0.5 - 40
            sw = 1100 * echelle * 0.5
            proj.append((sx, sy, sw, s))
            dx += courbe[s]; x += dx
        for n in range(N_VUS - 1, 0, -1):
            x1, y1, w1, s = proj[n]; x0, y0, w0, _ = proj[n - 1]
            if y0 <= y1:
                continue
            herbe = (60, 150, 70) if (s // 3) % 2 else (50, 135, 60)
            bord = (230, 230, 240) if (s // 2) % 2 else (40, 40, 210)
            route = (95, 95, 100) if (s // 3) % 2 else (88, 88, 93)
            cv2.fillPoly(img, [np.array([[0, y1], [W, y1], [W, y0], [0, y0]], np.int32)], herbe)
            for (larg, coul) in ((1.15, bord), (1.0, route)):
                q = np.array([[x1 - w1 * larg, y1], [x1 + w1 * larg, y1], [x0 + w0 * larg, y0], [x0 - w0 * larg, y0]], np.int32)
                cv2.fillPoly(img, [q], coul, cv2.LINE_AA)
            if (s // 4) % 2:
                q = np.array([[x1 - w1 * .03, y1], [x1 + w1 * .03, y1], [x0 + w0 * .03, y0], [x0 - w0 * .03, y0]], np.int32)
                cv2.fillPoly(img, [q], (240, 240, 240), cv2.LINE_AA)
        # la voiture (dessin simple, vue arrière), qui penche dans les virages
        incl = int(courbe[base] * 6)
        cx, cy = W // 2 - incl * 3, H - 170
        cv2.ellipse(img, (cx, cy + 75), (190, 26), 0, 0, 360, (30, 30, 30), -1, cv2.LINE_AA)
        corps = np.array([[cx - 170, cy + 60], [cx + 170, cy + 60], [cx + 160, cy - 10], [cx + 110, cy - 20],
                          [cx - 110, cy - 20], [cx - 160, cy - 10]], np.int32)
        cv2.fillPoly(img, [corps], (40, 40, 215), cv2.LINE_AA)
        toit = np.array([[cx - 105, cy - 20], [cx + 105, cy - 20], [cx + 80 + incl, cy - 85], [cx - 80 + incl, cy - 85]], np.int32)
        cv2.fillPoly(img, [toit], (30, 30, 170), cv2.LINE_AA)
        vitre = np.array([[cx - 88, cy - 26], [cx + 88, cy - 26], [cx + 70 + incl, cy - 76], [cx - 70 + incl, cy - 76]], np.int32)
        cv2.fillPoly(img, [vitre], (90, 60, 40), cv2.LINE_AA)
        for sgn in (-1, 1):
            cv2.rectangle(img, (cx + sgn * 150 - 22, cy + 8), (cx + sgn * 150 + 22, cy + 26), (60, 200, 255), -1, cv2.LINE_AA)
            cv2.rectangle(img, (cx + sgn * 130 - 25, cy + 58), (cx + sgn * 130 + 25, cy + 92), (20, 20, 20), -1, cv2.LINE_AA)
        kmh = int(180 + 40 * math.sin(k / 50))
        cv2.putText(img, f"{kmh} km/h", (40, 80), cv2.FONT_HERSHEY_DUPLEX, 1.6, (255, 255, 255), 3, cv2.LINE_AA)
        yield img


# ---------------------------------------------------------------- chute
def chute(n_images, rng):
    fond = fond_degrade((60, 20, 30), (25, 10, 15))
    ESP_Y, ESP_X, R_PLOT, BR = 120, 110, 13, 18
    allumes, trace = {}, []
    pos, vel = np.array([W / 2 + 5.0, 100.0]), np.array([0.0, 0.0])
    cam = 0.0
    for k in range(n_images):
        dt = 1 / FPS / 4
        for _ in range(4):
            vel[1] += 1100 * dt
            vel[0] *= 0.999
            pos += vel * dt
            if pos[0] < BR + 40 or pos[0] > W - BR - 40:  # murs
                vel[0] = -vel[0]; pos[0] = min(max(pos[0], BR + 40), W - BR - 40)
            ligne = int(round(pos[1] / ESP_Y))
            for lg in (ligne - 1, ligne, ligne + 1):
                if lg < 2:
                    continue
                dec = ESP_X / 2 if lg % 2 else 0
                col = int(round((pos[0] - 60 - dec) / ESP_X))
                for c in (col - 1, col, col + 1):
                    px, py = 60 + dec + c * ESP_X, lg * ESP_Y
                    if not (40 < px < W - 40):
                        continue
                    d = pos - (px, py); dist = math.hypot(*d)
                    if dist < R_PLOT + BR:
                        nrm = d / dist
                        vel -= 1.75 * np.dot(vel, nrm) * nrm
                        vel[0] += rng.uniform(-60, 60)
                        pos = np.array([px, py]) + nrm * (R_PLOT + BR + 0.5)
                        allumes[(lg, c)] = 1.0
            sp = math.hypot(*vel)
            if sp > 900:
                vel *= 900 / sp
        cam += (pos[1] - H * 0.4 - cam) * 0.15
        img = fond.copy()
        teinte = (pos[1] / 6000) % 1
        l0 = int(cam // ESP_Y) - 1
        for lg in range(max(l0, 2), l0 + H // ESP_Y + 3):
            dec = ESP_X / 2 if lg % 2 else 0
            for c in range(-1, W // ESP_X + 2):
                px, py = 60 + dec + c * ESP_X, lg * ESP_Y - cam
                if not (40 < px < W - 40):
                    continue
                lum = allumes.get((lg, c), 0)
                coul = couleur(teinte + lg * 0.02, 0.75, 0.7 + 0.3 * lum)
                if lum:
                    cv2.circle(img, (int(px), int(py)), int(R_PLOT + 10 * lum), coul, 2, cv2.LINE_AA)
                cv2.circle(img, (int(px), int(py)), R_PLOT, coul, -1, cv2.LINE_AA)
        for key in list(allumes):
            allumes[key] -= 1 / (FPS * 0.8)
            if allumes[key] <= 0:
                del allumes[key]
        trace.append((pos[0], pos[1]))
        del trace[:-14]
        for i, (tx, ty) in enumerate(trace):
            cv2.circle(img, (int(tx), int(ty - cam)), int(BR * (i + 1) / len(trace)), couleur(teinte + 0.5 + i / 60, 0.6), -1, cv2.LINE_AA)
        cv2.circle(img, (int(pos[0]), int(pos[1] - cam)), BR + 6, couleur(teinte + 0.5, 0.5), -1, cv2.LINE_AA)
        cv2.circle(img, (int(pos[0]), int(pos[1] - cam)), BR, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.putText(img, f"{int(pos[1] / 100)} m", (60, 80), cv2.FONT_HERSHEY_DUPLEX, 1.8, (255, 255, 255), 3, cv2.LINE_AA)
        if pos[1] > 400000:  # remise à zéro très loin (jamais atteinte en pratique)
            pos[1] = 100.0; cam = 0.0
        yield img


JEUX = {"anneaux": anneaux, "descente": descente, "chute": chute}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("jeu", nargs="?", default="tous"); p.add_argument("--duree", type=float, default=180)
    a = p.parse_args()
    for nom in (JEUX if a.jeu == "tous" else [a.jeu]):
        enc = encodeur(nom)
        for img in JEUX[nom](int(a.duree * FPS), random.Random(nom)):
            enc.stdin.write(img.tobytes())
        enc.stdin.close(); enc.wait()
        print(f"OK gameplay/{nom}.mp4")


if __name__ == "__main__":
    main()
