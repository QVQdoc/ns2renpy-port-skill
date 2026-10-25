# -*- coding: utf-8 -*-
"""抽查转换后的 PNG（images/ns 下所有子目录）：
是否真有 alpha、全不透明占比、残余键色像素、尺寸分布。"""
import glob
import os
import sys

from PIL import Image

GAME = sys.argv[1] if len(sys.argv) > 1 else "project/game"
ROOT = os.path.join(GAME, "images", "ns")


def green_hit(im, step=2):
    rgb = im.convert("RGB")
    a = im.getchannel("A")
    w, h = im.size
    hit = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            if a.getpixel((x, y)) > 200:
                r, g, b = rgb.getpixel((x, y))
                if g > 240 and r < 20 and b < 20:
                    hit += 1
    return hit


rows = []
for d in sorted(os.listdir(ROOT)):
    p = os.path.join(ROOT, d)
    if not os.path.isdir(p):
        continue
    files = sorted(glob.glob(os.path.join(p, "*.png")))
    if not files:
        continue
    alpha_n = opaque_n = green_n = 0
    sizes = {}
    for f in files:
        with Image.open(f) as im:
            sizes[im.size] = sizes.get(im.size, 0) + 1
            if im.mode != "RGBA" or im.getchannel("A").getextrema()[0] == 255:
                opaque_n += 1
            else:
                alpha_n += 1
            green_n += green_hit(im)
    rows.append((d, len(files), alpha_n, opaque_n, green_n, sizes))

for d, n, a, o, g, sizes in rows:
    st = ", ".join(f"{w}x{h}×{c}" for (w, h), c in sorted(sizes.items())[:4])
    print(f"{d:10s} 张数={n:3d} 有alpha={a:3d} 全不透明={o:3d} 残余纯绿={g:6d} 尺寸[{st}]")

print("\n合计 %d 张" % sum(r[1] for r in rows))
bad = [(d, g) for d, n, a, o, g, s in rows if g > 0]
if bad:
    print("警告：以下目录仍见纯绿像素（可能是键色没抠或遮罩判反）：", bad)
else:
    print("未见残余纯绿像素。")
