# -*- coding: utf-8 -*-
"""把标题画面按 port_title.rpy 的坐标合成一张预览，用来确认按钮 alpha 抠得对。

不启动 Ren'Py：直接按屏幕定义贴图，坐标与 port_title.rpy 的 xpos/ypos 一致。
"""
import os
import sys

from PIL import Image

GAME = sys.argv[1] if len(sys.argv) > 1 else "project/game"
OUT = sys.argv[2] if len(sys.argv) > 2 else "_title_proof.png"
NS = os.path.join(GAME, "images", "ns", "top")

BTN_Y = [240, 294, 348, 402, 456]

bg = Image.open(os.path.join(NS, "topbg.png")).convert("RGB")
canvas = bg.copy()
for i, y in enumerate(BTN_Y, start=1):
    for state, name in (("c0", "idle"), ("c1", "hover")):
        pass
idle = [Image.open(os.path.join(NS, "top%02d_c0.png" % i)).convert("RGBA") for i in range(1, 6)]
hover = [Image.open(os.path.join(NS, "top%02d_c1.png" % i)).convert("RGBA") for i in range(1, 6)]

for i, y in enumerate(BTN_Y):
    canvas.paste(idle[i], (260, y), idle[i])
canvas.save(OUT.replace(".png", "_idle.png"))

# 第二张：第 3 个按钮处于指针态
canvas2 = bg.copy()
for i, y in enumerate(BTN_Y):
    img = hover[i] if i == 2 else idle[i]
    canvas2.paste(img, (260, y), img)
canvas2.save(OUT.replace(".png", "_hover.png"))
print("saved", OUT.replace(".png", "_idle.png"), OUT.replace(".png", "_hover.png"))
