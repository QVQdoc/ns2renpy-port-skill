# -*- coding: utf-8 -*-
"""按原作 *logo 的时间轴离线合成一张证据图（不启动 Ren'Py）。

源 0.txt:154-195：
  lsp 0,":c;sys\\01.bmp",800,174 → msp 0,-200,0,0 ×4 / waittimer 60 → x = 800→600→400→200→0
  csp 0 + vsp 1,1 → lsph 1,":c/10,40,1;sys\\tlanime.bmp",188,174（10 格 × 40ms）

用法: python logo_proof.py <game 目录> [输出 png]
      python logo_proof.py project\game port\proof_logo.png
"""
import os
import sys

from PIL import Image

GAME = sys.argv[1] if len(sys.argv) > 1 else os.path.join("project", "game")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join("port", "proof_logo.png")
ROOT = os.path.join(GAME, "images", "ns", "sys")
SW, SH = 800, 600

slide = Image.open(os.path.join(ROOT, "n01.png")).convert("RGBA")
flip = [Image.open(os.path.join(ROOT, "tlanime_c%d.png" % i)).convert("RGBA") for i in range(10)]

panels = []
for i, x in enumerate((600, 400, 200, 0)):
    canvas = Image.new("RGBA", (SW, SH), (0, 0, 0, 255))
    canvas.alpha_composite(slide, (x, 174))
    panels.append(("slide x=%d  t=%.2fs" % (x, (i + 2) * 0.06), canvas))
for i in (2, 4, 6, 8, 9):
    canvas = Image.new("RGBA", (SW, SH), (0, 0, 0, 255))
    canvas.alpha_composite(flip[i], (188, 174))
    panels.append(("flip frame %d  t=%.2fs" % (i, 0.30 + 0.04 * i), canvas))

cols = 3
tw = 400
th = int(SH * tw / SW)
rows = (len(panels) + cols - 1) // cols
sheet = Image.new("RGB", (cols * tw, rows * (th + 22)), (18, 18, 18))
for k, (_label, canvas) in enumerate(panels):
    r, c = divmod(k, cols)
    sheet.paste(canvas.convert("RGB").resize((tw, th), Image.LANCZOS), (c * tw, r * (th + 22)))
    print(k, _label)
sheet.save(OUT)
print("saved", OUT, sheet.size)
