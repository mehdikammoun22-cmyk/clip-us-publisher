"""Génère logo.png (1024x1024) pour l'app TikTok Clip_US Publisher."""
from PIL import Image, ImageDraw, ImageFont
import sys, os

S = 1024
img = Image.new("RGB", (S, S))
px = img.load()
# Dégradé diagonal bleu nuit -> violet
c1, c2 = (58, 36, 120), (58, 36, 120)
for y in range(S):
    for x in range(S):
        t = (x + y) / (2 * S)
        px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

d = ImageDraw.Draw(img)
# Cadre vertical 9:16 (clip)
w, h = 360, 640
x0, y0 = (S - w) // 2, 150
d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=48, outline=(255, 255, 255), width=18)
# Triangle lecture
cx, cy = S // 2, y0 + h // 2
d.polygon([(cx - 55, cy - 80), (cx - 55, cy + 80), (cx + 85, cy)], fill=(255, 255, 255))
# Texte
try:
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 130)
except OSError:
    font = ImageFont.load_default()
txt = "CLIP_US"
bb = d.textbbox((0, 0), txt, font=font)
d.text(((S - (bb[2] - bb[0])) // 2, 830), txt, font=font, fill=(255, 255, 255))

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
img.save(out)
print(out, img.size)
