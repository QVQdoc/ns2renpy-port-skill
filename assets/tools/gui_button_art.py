# -*- coding: utf-8 -*-
"""生成 800x600 这套 GUI 缺的 9 宫格素材（中性配色，取自 gui.rpy）。"""
import os
from PIL import Image, ImageDraw

ROOT = sys.argv[1] if len(sys.argv) > 1 else "game/gui"
ACCENT = (0, 184, 195, 255)
ACCENT_DIM = (0, 184, 195, 120)
WHITE = (255, 255, 255, 255)
IDLE = (136, 136, 136, 255)
HOVER = (102, 212, 219, 255)


def rounded(size, fill, outline=None, radius=4, width=1):
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=fill, outline=outline, width=width)
    return im


def save(rel, im):
    path = os.path.join(ROOT, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)
    print("wrote", rel, im.size)


# 普通按钮：常态透明，hover 淡底
save("button/idle_background.png", rounded((48, 48), (0, 0, 0, 0)))
save("button/hover_background.png", rounded((48, 48), (255, 255, 255, 18), (255, 255, 255, 40), radius=6))

# 存档格
save("button/slot_idle_background.png", rounded((48, 48), (0, 0, 0, 110), (255, 255, 255, 28), radius=6))
save("button/slot_hover_background.png", rounded((48, 48), (0, 184, 195, 30), ACCENT_DIM, radius=6))

# 勾选框 / 单选框
def check_mark(selected):
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([2, 2, 29, 29], radius=4, fill=(0, 0, 0, 90), outline=(255, 255, 255, 70))
    if selected:
        d.line([(8, 17), (14, 23), (24, 9)], fill=ACCENT, width=3)
    return im

save("button/check_idle_foreground.png", check_mark(False))
save("button/check_selected_foreground.png", check_mark(True))

def radio_mark(selected):
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([2, 2, 29, 29], fill=(0, 0, 0, 90), outline=(255, 255, 255, 70))
    if selected:
        d.ellipse([10, 10, 21, 21], fill=ACCENT)
    return im

save("button/radio_idle_foreground.png", radio_mark(False))
save("button/radio_selected_foreground.png", radio_mark(True))

# bar（进度条/音量条）：left=已填充，right=未填充
save("bar/left.png", rounded((32, 16), ACCENT, radius=3))
save("bar/right.png", rounded((32, 16), (255, 255, 255, 26), radius=3))
save("bar/top.png", rounded((16, 32), ACCENT, radius=3))
save("bar/bottom.png", rounded((16, 32), (255, 255, 255, 26), radius=3))

# slider
save("slider/horizontal_idle_bar.png", rounded((32, 16), (255, 255, 255, 30), radius=3))
save("slider/horizontal_hover_bar.png", rounded((32, 16), (255, 255, 255, 46), radius=3))
save("slider/horizontal_idle_thumb.png", rounded((16, 16), IDLE, radius=8))
save("slider/horizontal_hover_thumb.png", rounded((16, 16), HOVER, radius=8))
save("slider/vertical_idle_bar.png", rounded((16, 32), (255, 255, 255, 30), radius=3))
save("slider/vertical_hover_bar.png", rounded((16, 32), (255, 255, 255, 46), radius=3))
save("slider/vertical_idle_thumb.png", rounded((16, 16), IDLE, radius=8))
save("slider/vertical_hover_thumb.png", rounded((16, 16), HOVER, radius=8))

# scrollbar
save("scrollbar/horizontal_idle_bar.png", rounded((32, 8), (255, 255, 255, 24), radius=2))
save("scrollbar/horizontal_hover_bar.png", rounded((32, 8), (255, 255, 255, 40), radius=2))
save("scrollbar/horizontal_idle_thumb.png", rounded((8, 8), IDLE, radius=3))
save("scrollbar/horizontal_hover_thumb.png", rounded((8, 8), HOVER, radius=3))
save("scrollbar/vertical_idle_bar.png", rounded((8, 32), (255, 255, 255, 24), radius=2))
save("scrollbar/vertical_hover_bar.png", rounded((8, 32), (255, 255, 255, 40), radius=2))
save("scrollbar/vertical_idle_thumb.png", rounded((8, 8), IDLE, radius=3))
save("scrollbar/vertical_hover_thumb.png", rounded((8, 8), HOVER, radius=3))
print("done")
