"""Render the ÇEMBER app icon (1024x1024, opaque, no text) from the in-game logo design.

Mirrors the CSS logo in cember_webapp_src/src/components/MainMenu.tsx: dashed amber
orbit, cyan orbit with amber/cyan satellites, amber→rose→indigo core disc, dark
inner ring and a glowing white center. Drawn at 4x and downsampled for clean edges.

Usage: python3 tools/make_ios_icon.py [output.png]
"""
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "cember-icon-1024.png"
SS = 4                      # supersampling factor
N = 1024 * SS               # working canvas size
C = N / 2                   # center
U = SS                      # 1 output pixel in working units

BG = (3, 9, 25)
AMBER = (251, 191, 36)
AMBER_DOT = (254, 183, 1)
CYAN = (34, 211, 238)
ROSE = (244, 63, 94)
INDIGO = (79, 70, 229)
ORANGE = (255, 140, 50)


def layer():
    return Image.new("RGBA", (N, N), (0, 0, 0, 0))


def circle(draw, r, cx=C, cy=C, **kw):
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), **kw)


def glow(img, radius):
    return img.filter(ImageFilter.GaussianBlur(radius * U))


canvas = Image.new("RGBA", (N, N), BG + (255,))

# Subtle center lift so the dark background isn't flat
yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
dist = np.sqrt((xx - C) ** 2 + (yy - C) ** 2) / (N / 2)
lift = np.clip(1 - dist, 0, 1) ** 2
bg = np.zeros((N, N, 4), np.uint8)
bg[..., 0] = np.clip(BG[0] + 10 * lift, 0, 255)
bg[..., 1] = np.clip(BG[1] + 12 * lift, 0, 255)
bg[..., 2] = np.clip(BG[2] + 26 * lift, 0, 255)
bg[..., 3] = 255
canvas = Image.alpha_composite(canvas, Image.fromarray(bg, "RGBA"))

# Faint dot grid (matches the menu background)
grid = layer()
gd = ImageDraw.Draw(grid)
step = 64 * U
for gx in range(step // 2, N, step):
    for gy in range(step // 2, N, step):
        circle(gd, 2.2 * U, gx, gy, fill=(30, 41, 59, 150))
canvas = Image.alpha_composite(canvas, grid)

# Soft tri-color halo behind the logo
halo = layer()
hd = ImageDraw.Draw(halo)
circle(hd, 300 * U, C - 70 * U, C + 60 * U, fill=CYAN + (55,))
circle(hd, 300 * U, C + 70 * U, C - 60 * U, fill=AMBER + (55,))
circle(hd, 260 * U, C + 40 * U, C + 80 * U, fill=ROSE + (45,))
canvas = Image.alpha_composite(canvas, glow(halo, 90))

# Dashed amber orbit
R_DASH, W_DASH, DASHES = 400 * U, 14 * U, 28
dash = layer()
dd = ImageDraw.Draw(dash)
box = (C - R_DASH, C - R_DASH, C + R_DASH, C + R_DASH)
seg = 360 / DASHES
for i in range(DASHES):
    start = i * seg - 90
    dd.arc(box, start, start + seg * 0.55, fill=AMBER + (190,), width=int(W_DASH))
canvas = Image.alpha_composite(canvas, glow(dash, 6))
canvas = Image.alpha_composite(canvas, dash)

# Cyan orbit
R_ORB = 340 * U
orb = layer()
od = ImageDraw.Draw(orb)
circle(od, R_ORB, outline=CYAN + (150,), width=int(12 * U))
canvas = Image.alpha_composite(canvas, glow(orb, 8))
canvas = Image.alpha_composite(canvas, orb)

# Satellites on the cyan orbit: amber upper-right, cyan lower-left
for angle, color in ((-45, AMBER_DOT), (135, CYAN)):
    a = math.radians(angle)
    sx, sy = C + R_ORB * math.cos(a), C + R_ORB * math.sin(a)
    sat = layer()
    sd = ImageDraw.Draw(sat)
    circle(sd, 46 * U, sx, sy, fill=color + (200,))
    canvas = Image.alpha_composite(canvas, glow(sat, 22))
    sat = layer()
    circle(ImageDraw.Draw(sat), 36 * U, sx, sy, fill=color + (255,))
    canvas = Image.alpha_composite(canvas, sat)

# Core disc: diagonal amber → rose → indigo gradient with an amber glow
R_DISC = 230 * U
disc_glow = layer()
circle(ImageDraw.Draw(disc_glow), R_DISC + 20 * U, fill=(245, 158, 11, 150))
canvas = Image.alpha_composite(canvas, glow(disc_glow, 45))

t = ((xx - (C - R_DISC)) + (yy - (C - R_DISC))) / (4 * R_DISC)   # 0 top-left → 1 bottom-right
t = np.clip(t, 0, 1)[..., None]
stops = np.array([ORANGE, ROSE, INDIGO], np.float32)
grad = np.where(t < 0.5,
                stops[0] + (stops[1] - stops[0]) * (t / 0.5),
                stops[1] + (stops[2] - stops[1]) * ((t - 0.5) / 0.5))
mask = Image.new("L", (N, N), 0)
circle(ImageDraw.Draw(mask), R_DISC, fill=255)
disc = Image.fromarray(np.dstack([grad.astype(np.uint8), np.array(mask)]), "RGBA")
canvas = Image.alpha_composite(canvas, disc)

# Dark inner well with a thin amber rim
R_WELL = 118 * U
well = layer()
wd = ImageDraw.Draw(well)
circle(wd, R_WELL, fill=(11, 15, 25, 215))
circle(wd, R_WELL, outline=(252, 211, 77, 160), width=int(6 * U))
canvas = Image.alpha_composite(canvas, well)

# Glowing white center
core = layer()
circle(ImageDraw.Draw(core), 62 * U, fill=(255, 255, 255, 190))
canvas = Image.alpha_composite(canvas, glow(core, 26))
core = layer()
circle(ImageDraw.Draw(core), 46 * U, fill=(255, 255, 255, 255))
canvas = Image.alpha_composite(canvas, core)

icon = canvas.convert("RGB").resize((1024, 1024), Image.LANCZOS)
icon.save(OUT, optimize=True)
print(f"wrote {OUT} {icon.size} {icon.mode}")
