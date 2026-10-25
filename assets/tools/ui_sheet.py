# -*- coding: utf-8 -*-
"""把各目录的 UI 素材抽几张贴到棋盘格上，用来看 alpha 抠得对不对。

棋盘格是判定 alpha 的标准背景：透明处露格子，不透明处盖住格子。
"""
import glob
import os
import sys

from PIL import Image

GAME = sys.argv[1] if len(sys.argv) > 1 else "project/game"
OUT = sys.argv[2] if len(sys.argv) > 2 else "_ui_sheet.png"
ROOT = os.path.join(GAME, "images", "ns")
DIRS = ["config", "sys", "top", "musm", "cgm", "log", "sv", "savedata", "sum"]
PER_DIR = 6


def checker(w, h, s=8):
    im = Image.new("RGB", (w, h), (200, 200, 200))
    px = im.load()
    for y in range(h):
        for x in range(w):
            if ((x // s) + (y // s)) % 2:
                px[x, y] = (160, 160, 160)
    return im


tiles = []
for d in DIRS:
    files = sorted(glob.glob(os.path.join(ROOT, d, "*.png")))
    if not files:
        continue
    step = max(1, len(files) // PER_DIR)
    for f in files[::step][:PER_DIR]:
        with Image.open(f) as im:
            im = im.convert("RGBA")
        scale = 2 if max(im.size) <= 130 else 1
        if scale > 1:
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        tiles.append((d, f, im))

pad = 10
cell_w = max(t[2].width for t in tiles) + pad * 2
cell_h = max(t[2].height for t in tiles) + pad * 2 + 14
cols = 6
rows = (len(tiles) + cols - 1) // cols
sheet = checker(cell_w * cols, cell_h * rows)
from PIL import ImageDraw

dr = ImageDraw.Draw(sheet)
for i, (d, f, im) in enumerate(tiles):
    cx = (i % cols) * cell_w
    cy = (i // cols) * cell_h
    sheet.paste(im, (cx + pad, cy + pad + 14), im)
    dr.text((cx + pad, cy + 2), "%s/%s" % (d, os.path.basename(f)[:-4]), fill=(20, 20, 20))
sheet.save(OUT)
print("saved", OUT, sheet.size, "tiles", len(tiles))
