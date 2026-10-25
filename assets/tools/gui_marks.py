# -*- coding: utf-8 -*-
"""按 gui.radio_button_borders / check_button_borders 的左边距(12px)重画选项标记，
尺寸必须等于左边距，否则文字会压在标记上（实测：32px 的标记盖住「窗口」）。

用法: python gui_marks.py <game/gui/button 目录>
"""
import os
import sys

from PIL import Image, ImageDraw

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join("game", "gui", "button")

if OUT in ("-h", "--help"):
    print(__doc__)
    raise SystemExit(0)
S = 12
SS = 8  # 超采样倍数

ACCENT = (0x00, 0xb8, 0xc3, 255)
IDLE = (0x88, 0x88, 0x88, 255)
DIM = (0x88, 0x88, 0x88, 0x7f)
WHITE = (255, 255, 255, 255)


def canvas(size=S * SS):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return im, ImageDraw.Draw(im)


def save(im, name):
    im = im.resize((S, S), Image.LANCZOS)
    p = os.path.join(OUT, name)
    im.save(p)
    print("wrote", p)


def ring(color, width=2, fill=False):
    im, d = canvas()
    w = S * SS
    m = 1 * SS
    if fill:
        d.ellipse([m, m, w - m, w - m], fill=color)
        d.ellipse([w // 2 - SS, w // 2 - SS, w // 2 + SS, w // 2 + SS], fill=(255, 255, 255, 0))
    else:
        d.ellipse([m, m, w - m, w - m], outline=color, width=width * SS)
    return im


def square(color, width=2, check=False, fill=False):
    im, d = canvas()
    w = S * SS
    m = 1 * SS
    r = 2 * SS
    if fill:
        d.rounded_rectangle([m, m, w - m, w - m], radius=r, fill=color)
    else:
        d.rounded_rectangle([m, m, w - m, w - m], radius=r, outline=color, width=width * SS)
    if check:
        d.line([(3 * SS, 6 * SS), (5 * SS, 9 * SS), (9 * SS, 3 * SS)],
               fill=WHITE, width=2 * SS, joint="curve")
    return im


save(ring(IDLE), "radio_idle_foreground.png")
save(ring(ACCENT, fill=True), "radio_selected_foreground.png")
save(ring(DIM), "radio_foreground.png")
save(square(IDLE), "check_idle_foreground.png")
save(square(ACCENT, fill=True, check=True), "check_selected_foreground.png")
save(square(DIM), "check_foreground.png")
