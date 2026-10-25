# -*- coding: utf-8 -*-
"""用 Pillow 复刻 ns_stage 的两三种帧，用来目视核对分层与槽位（不是游戏截图）。"""
import os
import sys

from PIL import Image

GAME = sys.argv[1] if len(sys.argv) > 1 else "project/game"
OUT = sys.argv[2] if len(sys.argv) > 2 else "_proof_stage.png"
W, H = 800, 600


def load(kind, name):
    return Image.open(os.path.join(GAME, "images", "ns", kind, name + ".png")).convert("RGBA")


def frame(bg, chars):
    canvas = load("bg", bg)
    for slot, name in chars:
        im = load("chr", name)
        im = im.resize((int(im.width), int(im.height)), Image.LANCZOS)
        if slot == "l":
            x = 0
        elif slot == "r":
            x = W - im.width
        else:
            x = (W - im.width) // 2
        canvas.alpha_composite(im, (x, 0))
    return canvas


frames = [
    ("c", frame("street_c", [("c", "m01_a")])),
    ("l+r", frame("class", [("l", "m01_a"), ("r", "m02_a")])),
    ("bg 换、立绘保留", frame("room", [("c", "m01_a")])),
    ("CG 覆盖（tag bg）", frame("street_b", [("c", "m01_a")])),
]

sheet = Image.new("RGB", (W * 2, H * 2), (20, 20, 20))
for i, (label, im) in enumerate(frames):
    sheet.paste(im.convert("RGB"), ((i % 2) * W, (i // 2) * H))
    print(f"{label}: {im.size}")
sheet.save(OUT)
print("saved", OUT)
