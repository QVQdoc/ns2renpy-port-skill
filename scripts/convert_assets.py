#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""convert_assets.py —— 按 assets_manifest.json 把原作素材转成 Ren'Py 工程资产。

它解决的问题（全部是「昨天那版随手写的转换脚本」踩过的坑）
-----------------------------------------------------------
1. **蒙版被当普通图片拷**：`ld c,":a;chr\\s01_a.bmp"` 里的 `:a;` 表示横双倍宽、
   右半是遮罩。直接 BMP→PNG 的结果是立绘带着一块纯色地板、还露出半张遮罩。
   这里按像素判定与 spec 双路证据拆图：alpha = 255 - 遮罩灰度（或反向，按实测）。
2. **键色没抠**：`:left_right_arrow:#00ff00/2,0,3;` 指定透明键色；没指定的按
   NScripter 默认黑键，并且只在「纯色占比够大」时才当键色（避免把背景图抠穿）。
3. **目录写死**：目录来自 manifest（即脚本里真实出现过的路径），不是手写列表。
4. **变量拼接路径漏转**：manifest 已按字面目录枚举出全部实物文件。
5. **spec 几何没实现**：分割图（`:c/2,0,3;`）按横 N 格裁开，逐格出图。
6. **素材名不合法**：`ev/01.bmp` 会生成 `image ev 01`，Ren'Py 直接语法错。
   这里统一清洗成合法标识符（数字开头前面补 `n`）。

产出
----
- `<project>/game/images/ns/...`  转换后的 PNG（带 alpha）
- `<project>/game/audio/...`      BGM / SE / 语音
- `<project>/game/port_images.rpy`   image 定义 + `NS_STAGE` 常量（自动生成）
- `<project>/game/port_wrappers.rpy` defsub 包装层 → `ns_w_*()` 函数（自动生成）
- `<project>/port/assets_convert_report.md`  转换报告（缺失/跳过/降级说明）

用法
----
    python convert_assets.py <游戏目录> <工程 game 目录> \
        --manifest port/assets_manifest.json [--image-root images/ns] \
        [--audio bgm,se,voice] [--mask-mode auto] [--force]

`--mask-mode`: auto（默认，按 manifest 的 orient；orient 判不出时用「键色区=透明区」现场判）
`--audio`:    逗号分隔的目录名，none 表示不拷音频
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import sys
import time
from typing import Optional

try:
    from PIL import Image, ImageChops, ImageFilter, ImageOps
except Exception:  # pragma: no cover
    print("[error] 需要 Pillow: pip install pillow", file=sys.stderr)
    raise SystemExit(2)

SCHEMA = 1
IMAGE_KINDS = {"bg", "chr", "ev", "sys", "image", "var"}


# ------------------------------------------------------------------ 小工具 --
def hex_rgb(h: str):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def safe_name(name: str) -> str:
    """Ren'Py image 名必须是合法标识符；`01` 这种要补前缀。

    统一转小写：NS 在 Windows 上找文件不分大小写，脚本里写 `chr "m02_E"`、
    磁盘上是 `m02_e.bmp` 是常态；Ren'Py 的 image 名却分大小写，不归一化就会
    出现「素材明明转好了，运行期却报缺图」（实测 2 次）。
    """
    s = re.sub(r"[^0-9A-Za-z_]", "_", name.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return "x"
    if not re.match(r"[A-Za-z_]", s):
        s = "n" + s
    return s


def split_dir_name(path: str):
    p = path.replace("\\", "/")
    if "/" in p:
        d, n = p.split("/", 1)
        return d, n
    return "", p


def root_name(ident: str) -> str:
    return ident.split("/")[0].lower()


# ------------------------------------------------------------- 图像转换核心 --
def _key_mask(img: Image.Image, key: str, tol: int = 12) -> Image.Image:
    """返回 L 模 mask：0=键色处（要透明），255=其它。"""
    solid = Image.new("RGB", img.size, hex_rgb(key))
    diff = ImageChops.difference(img, solid).convert("L")
    # 任一通道差异都算「不是键色」，因此用最亮差值来判
    r, g, b = ImageChops.difference(img, solid).split()
    d = ImageChops.lighter(ImageChops.lighter(r, g), b)
    return d.point(lambda v: 0 if v <= tol else 255)


def _strip_key(img: Image.Image, key: str, tol: int = 12) -> Image.Image:
    """把键色像素变成全透明（保留已有 alpha 的较小值）。"""
    keep = _key_mask(img.convert("RGB"), key, tol)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    a = img.getchannel("A")
    img.putalpha(ImageChops.darker(a, keep))
    return img


def _pick_orient(left: Image.Image, mask: Image.Image, key: Optional[str],
                 tol: int = 12) -> str:
    """蒙版方向未知时用像素判：透明区应该正好是键色区。

    manifest 对「分割后的图片」判不出方向（整图不是简单双倍宽），此时
    orient 会留成 unknown。不能凭「unknown 不是 dark-opaque」就当成
    light-opaque —— 那会把按钮抠反：底色留下、按钮本体透明。
    """
    if not key:
        return "dark-opaque"
    keep = _key_mask(left, key, tol)          # 255=非键色（该不透明）
    cand = {"dark-opaque": ImageOps.invert(mask), "light-opaque": mask}
    best, best_score = "dark-opaque", None
    for name, alpha in cand.items():
        diff = ImageChops.difference(alpha, keep)
        hist = diff.histogram()
        score = sum(i * hist[i] for i in range(256))
        if best_score is None or score < best_score:
            best, best_score = name, score
    return best


def _mask_pair(img: Image.Image, orient: Optional[str],
               key: Optional[str] = None) -> tuple[Image.Image, str]:
    """`:a;` 蒙版合成：裁左半为图像，用右半遮罩做 alpha。返回 (图, 实际方向)。"""
    w, h = img.size
    half = w // 2
    left = img.crop((0, 0, half, h)).convert("RGB")
    mask = img.crop((half, 0, w, h)).convert("L")
    if orient not in ("dark-opaque", "light-opaque"):
        orient = _pick_orient(left, mask, key)
    if orient == "dark-opaque":
        # 遮罩是「黑=不透明」：alpha = 255 - 灰度
        alpha = ImageOps.invert(mask)
    else:
        alpha = mask
    left.putalpha(alpha)
    return left, orient


def _flat_ratio(img: Image.Image, color, step: int = 9) -> float:
    w, h = img.size
    px = img.load()
    total = hit = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            total += 1
            if px[x, y] == color:
                hit += 1
    return (hit / total) if total else 0.0


def _bleed_rgb(img: Image.Image, iterations: int = 5, radius: int = 3) -> Image.Image:
    """把透明区的 RGB 渗成邻近边缘色，消掉缩放时的绿边/黑边。

    为什么必须做：工程分辨率与 800x600 不同时 ns_scale() 会 zoom，Ren'Py 按双线性
    采样，透明像素里残留的键色（绿幕）会被插值进边缘，立绘周围出现一圈绿边。
    纯色背景的立绘在 NS 里看不出来，搬进 Ren'Py 一眼就看见。
    """
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    r, g, b, a = img.split()
    if a.getextrema()[0] != 0:      # 没有透明像素，什么都不用做
        return img
    rgb = Image.merge("RGB", (r, g, b))
    fill = rgb
    for _ in range(iterations):     # 逐步把边缘色向透明区扩散
        fill = Image.composite(rgb, fill.filter(ImageFilter.GaussianBlur(radius)), a)
    return Image.merge("RGBA", (*fill.split(), a))


def convert_image(asset: dict, game_root: str, out_root: str, mask_mode: str = "auto",
                  key_min_ratio: float = 0.10) -> tuple[list[str], list[str]]:
    """转一条素材，返回 (输出相对路径列表, 说明列表)。"""
    notes: list[str] = []
    src = os.path.join(game_root, asset["src"].replace("/", os.sep))
    with Image.open(src) as im0:
        img = im0.convert("RGB")
    size0 = img.size
    specs = asset.get("specs") or []
    spec_info = None
    if specs:
        # 取「信息量最大」的那条 spec（蒙版 > 键色 > 分割）
        def score(s):
            return (("a" in s.split("/")[0]) * 4 + s.count("#") * 2 + s.count("/") * 1)
        spec_info = parse_spec_local(max(specs, key=score))
    mask = bool(asset.get("mask"))
    key = (spec_info or {}).get("key") or asset.get("spec_key")
    cells = (spec_info or {}).get("cells") or asset.get("cells")
    cols = int(cells.get("cols", 1) or 1) if cells else 1
    orient = (mask_mode if mask_mode in ("dark-opaque", "light-opaque")
              else asset.get("orient"))
    if orient not in ("dark-opaque", "light-opaque"):
        orient = None  # 交给 _mask_pair 按像素判（键色区=透明区）

    if mask and (size0[0] % (2 * cols) or size0[0] < 8 * cols):
        notes.append("标为蒙版但宽度不适合按 %d 格对半拆：%s，按键色回退" % (cols, size0))
        mask = False

    def finish(im: Image.Image) -> Image.Image:
        """抠键色 + 渗色，统一成 RGBA。"""
        if key:
            ratio = (_flat_ratio(im.convert("RGB"), hex_rgb(key))
                     if im.size[0] * im.size[1] < 4_000_000 else 1.0)
            if ratio >= key_min_ratio or mask:
                im = _strip_key(im, key)
                notes.append("键色 %s（占比 %.3f）已抠除" % (key, ratio))
            else:
                notes.append("键色 %s 占比仅 %.3f，判为画面用色，未抠除" % (key, ratio))
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        return _bleed_rgb(im) if (mask or key) else im

    d, _n = split_dir_name(asset["id"])
    stem = safe_name(os.path.splitext(asset["id"].split("/")[-1])[0])
    out_dir_rel = os.path.join(out_root, d or "misc")
    outs: list[str] = []

    def save(im: Image.Image, name: str):
        rel = "/".join(p for p in (out_dir_rel.replace(os.sep, "/"), name + ".png"))
        abs_path = os.path.join(GAME_DIR, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        im.save(abs_path, "PNG", optimize=True)
        outs.append(rel)

    if mask and cols > 1:
        # 每格自己就是 [图像|遮罩]，必须先按格切、再逐格拆蒙版。
        # （先在整图上拆会横跨两格取遮罩，得到的 alpha 是错位的，UI 按钮会发虚）
        pair_w = size0[0] // cols
        parts, used = [], orient
        for i in range(cols):
            cell, used = _mask_pair(img.crop((i * pair_w, 0, (i + 1) * pair_w, size0[1])),
                                    orient, key)
            parts.append(cell)
        notes.append("蒙版+分割 %d 格：%s -> 每格 %s，遮罩方向 %s"
                     % (cols, list(size0), list(parts[0].size), used or "自动"))
        for i, p in enumerate(parts):
            save(finish(p), "%s_c%d" % (stem, i))
        return outs, notes

    if mask:
        img, used = _mask_pair(img, orient, key)
        notes.append("蒙版拆分 %s -> %s，遮罩方向 %s"
                     % (list(size0), list(img.size), used or "自动"))
    img = finish(img)

    if cols > 1:
        cw = img.size[0] // cols
        for i in range(cols):
            save(img.crop((i * cw, 0, (i + 1) * cw, img.size[1])), "%s_c%d" % (stem, i))
        notes.append("分割 %d 格（spec 参数 %s，第 3 参数语义未确认，按横切处理）"
                     % (cols, ",".join(cells.get("params", []))))
    else:
        save(img, stem)
    return outs, notes


_SPEC_RE = re.compile(r"^:(?P<flags>[a-z]*)(?P<key>#[0-9A-Fa-f]{6})?(?P<params>[^;]*);$")


def parse_spec_local(spec: str) -> dict:
    m = _SPEC_RE.match(spec or "")
    if not m:
        return {"raw": spec, "mask": False, "key": None, "cells": None}
    flags = m.group("flags") or ""
    raw_params = (m.group("params") or "").lstrip("/")
    params = [p for p in raw_params.split(",") if p.strip() != ""]
    cells = None
    if len(params) >= 2 and params[0].isdigit() and int(params[0]) > 1:
        cells = {"cols": int(params[0]), "params": params}
    return {"raw": spec, "mask": "a" in flags, "flip": "l" in flags,
            "key": (m.group("key") or "").upper() or None, "cells": cells}


# ------------------------------------------------------- 包装层 → Ren'Py ---
def ns_expr_to_py(expr: str, params: dict[str, str]) -> str:
    """把 NS 条件表达式翻译成 Python。

    只覆盖包装层里真实出现的形态：变量比较、`&`/`|`、`mod`/`div`。
    翻译不了的分支不会静默：调用方会把原文写进注释。
    """
    py = expr.strip()
    for src, dst in params.items():
        py = re.sub(re.escape(src) + r"(?![0-9A-Za-z_])", dst, py)
    py = re.sub(r"%([A-Za-z_]\w*)", lambda m: "store.ns_%s" % m.group(1).lower(), py)
    py = re.sub(r"\$([A-Za-z_]\w*)", lambda m: "store.ns_%s" % m.group(1).lower(), py)
    py = py.replace(" mod ", " % ").replace(" div ", " // ")
    py = py.replace("<>", "!=")
    py = re.sub(r"(?<![=!<>])=(?!=)", "==", py)
    py = py.replace("&", " and ").replace("|", " or ")
    py = re.sub(r"\s+", " ", py).strip()
    return py


def arg_to_py(arg: str, params: dict[str, str]) -> str | None:
    """NS 素材参数 → Ren'Py 表达式。

    NS 侧形态（注意反斜杠是路径分隔符，不是转义符）：
        `"bg\\"+$w0+".bmp"`  带变量拼接
        `"se\\"+$w0+".ogg"`  同理
        `"chr\\s01_a.bmp"`   字面文件
    变量拼接只保留「目录 + 变量」，目录决定素材种类，文件名就是参数本身 —— 因此
    直接返回参数名（p0），不要拼成字面量 "w0"（那是把变量名当文件名，必炸）。
    """
    p = (arg or "").replace("\\", "/").replace('"', "").strip()
    if not p:
        return None
    d, _, base = p.rpartition("/")
    base = re.sub(r"\.(bmp|png|jpe?g|webp|ogg|wav|mp3)$", "", base, flags=re.I).strip()
    base = base.strip("+").strip()          # `"+$w0+"` 的拼接号去掉，只剩变量
    if not base:
        return None
    m = re.fullmatch(r"\$([A-Za-z_]\w*)", base)
    if m:
        return params.get("$" + m.group(1))
    m = re.fullmatch(r"([A-Za-z0-9_]*)\$\{?([A-Za-z_]\w*)\}?([A-Za-z0-9_]*)", base)
    if m:   # 前后缀都固定（如 "ev0"+n）意味着文件名是拼出来的，映射不到单张图
        return None
    if "$" in base or "%" in base:
        return None
    if base.lower() in ("black", "white", "#000000", "#ffffff"):
        return None
    return '"%s"' % safe_name(base)


def dur_of(op: dict) -> float | None:
    t, s = op.get("t"), op.get("s")
    try:
        t = int(t); s = int(s)
    except (TypeError, ValueError):
        return None
    if t <= 1:
        return None
    return max(0.05, min(1.5, t * max(s, 100) / 10000.0))


def op_to_py(op: dict, params: dict[str, str]) -> tuple[str | None, str, bool]:
    """一条 NS 指令 → 一行 Ren'Py Python，返回 (代码, 备注, 是否终结)。

    `code is None` 且 `note` 非空 = 这条没自动翻译（会被写进报告，不会静默消失）。
    """
    kind = op.get("op")
    dur = dur_of(op)
    d = "dur=%s" % (("%.2f" % dur).rstrip("0").rstrip(".") if dur else "0")
    raw_arg = (op.get("arg") or "").replace("\\", "/").replace('"', "")
    sub_dir = raw_arg.rpartition("/")[0].strip("+/").lower()
    arg = arg_to_py(op.get("arg", ""), params)

    if kind in ("bg", "ev"):
        if arg is None:
            return "ns_black(%s)" % d, "背景参数非字面/非单一变量，按黑幕处理: %r" % raw_arg, False
        if sub_dir == "ev":
            return "ns_ev(%s, %s)" % (arg, d), "", False
        return "ns_bg(%s, %s)" % (arg, d), "", False
    if kind == "chr":
        slot = op.get("slot", "c")
        if arg is None:
            return 'ns_chr_clear("%s", %s)' % (slot, d), "立绘参数无法翻译，按清除处理: %r" % raw_arg, False
        return 'ns_chr("%s", %s, %s)' % (slot, arg, d), "", False
    if kind == "chr_clear":
        return 'ns_chr_clear("%s", %s)' % (op.get("slot", "c"), d), "", False
    if kind == "bgm":
        return ("ns_bgm(%s)" % arg if arg else "ns_bgm_stop()"), "", False
    if kind == "bgm_stop":
        return "ns_bgm_stop()", "", False
    if kind in ("wave", "wave_stop", "vol"):
        ch_raw = op.get("ch") or ""
        ch = ns_expr_to_py(ch_raw, params) if ("%" in ch_raw or "$" in ch_raw) else repr(ch_raw)
    if kind == "wave":
        if arg is None:
            return None, "音频参数无法翻译: %r" % raw_arg, False
        if op.get("cmd") == "dwaveloop":
            return "ns_se_loop(%s, ch=%s)" % (arg, ch), "", False
        return "ns_se(%s, ch=%s)" % (arg, ch), "", False
    if kind == "wave_stop":
        if "%" in (op.get("ch") or ""):      # 出现在 for 循环里，交给 ns_se_stop_all
            return None, "循环内 dwavestop %s（由 ns_se_stop_all 覆盖）" % op.get("ch"), False
        return "ns_se_stop(ch=%s)" % ch, "", False
    if kind == "vol":
        return "ns_setvol(%s, %s)" % (ch, ns_expr_to_py(op.get("arg", "0"), params)), "", False
    if kind == "print":
        return None, "NS 文本窗/点击等待指令 %s %s（Ren'Py 由 say 与过渡承担）" % (
            op.get("cmd"), op.get("arg") or ""), False
    if kind == "misc":
        t = (op.get("arg") or "").strip()
        if t == "dstop":
            return "ns_se_stop_all()", "", False
        if t == "black":
            return "ns_black(%s)" % d, "", False
        if t == "cl":
            return "ns_chr_clear(%s)" % d, "", False
        return None, "misc 未翻译: %s" % t, False
    if kind == "goto":
        tgt = op.get("target")
        if tgt == "loopfade":
            return "ns_voice_stop()", "goto *loopfade（语音淡出）", True
        if tgt == "sloopfade":
            return "ns_se_stop(fade=1.0)", "goto *sloopfade（SE 淡出）", True
        return 'ns_w_%s()' % tgt, "", True
    if kind == "gosub":
        return 'ns_w_%s()' % op.get("target"), "", False
    if kind == "return":
        return "return", "", True
    if kind == "sprite":
        x, y = op.get("x"), op.get("y")
        if arg and x is not None and y is not None and "$" not in str(x) and "$" not in str(y):
            return ('ns_sprite(%s, %s, %s, %s)' % (op.get("layer", '"0"'), arg, x, y), "", False)
        return None, "sprite 未生成（层/坐标含变量）: %s" % op, False
    if kind == "wait":
        return "renpy.pause(%s / 1000.0)" % (op.get("arg") or "0"), "", False
    if kind == "other":
        text = (op.get("text") or "").strip()
        m = re.match(r"^mov\s+(%\w+)\s*,\s*(.+)$", text)
        if m:
            lhs = re.sub(r"%(\w+)", lambda mm: "store.ns_%s" % mm.group(1).lower(), m.group(1))
            return "%s = %s" % (lhs, ns_expr_to_py(m.group(2), params)), "", False
        m = re.match(r"^inc\s+(%\w+)$", text)
        if m:
            lhs = re.sub(r"%(\w+)", lambda mm: "store.ns_%s" % mm.group(1).lower(), m.group(1))
            return "%s = %s + 1" % (lhs, lhs), "", False
        if text.startswith("for "):
            return "ns_se_stop_all()", "NS 的 for 循环停通道 → ns_se_stop_all(): %s" % text, False
        if text in ("next", "saveoff", "saveon"):
            return None, "跳过: %s" % text, False
        return None, "未翻译: %s" % text, False
    return None, "未处理 op: %s" % op, False


def wrapper_to_py(w: dict) -> tuple[str, list[str]]:
    """把一个 defsub 包装层转成 Ren'Py Python 函数。"""
    notes: list[str] = []
    plist = [p["name"] for p in w.get("params", [])]
    params_map = {p: "p%d" % i for i, p in enumerate(plist)}
    sig = ", ".join("p%d" % i for i in range(len(plist)))
    lines = ['    def ns_w_%s(%s):' % (w["name"], sig)]
    doc = '        """defsub *%s(%s)  src:%s:%s"""' % (
        w["name"], ",".join(plist), w.get("body_script", "?"), w.get("body_line", "?"))
    lines.append(doc)
    body_lines: list[str] = []
    terminated = False
    prev_cond = None
    src = w.get("body_script", "?")
    for op in w.get("ops", []):
        if op["op"] == "params":
            continue
        code, note, stops = op_to_py(op, params_map)
        if note:
            notes.append("*%s: %s" % (w["name"], note))
        if not code:
            continue
        cond = ns_expr_to_py(op["cond"], params_map) if op.get("cond") else None
        tail = "  # src:%s:%s" % (src, op.get("line"))
        if cond:
            # `if 条件 A:return` 与同条件的上一条指令合并成一个块，否则生成两段
            # 一模一样的 if（*chr / *loop 这种写法会刷出一堆重复判断）。
            if code == "return" and prev_cond == cond:
                body_lines.append("            return%s" % tail)
            else:
                body_lines.append("        if %s:  # NS: if %s" % (cond, op["cond"]))
                body_lines.append("            %s%s" % (code, tail))
                if stops and code != "return":
                    body_lines.append("            return")
            # 条件返回只结束当前分支，后续语句照常翻译（*chr / *loop 都是这么写的）
        else:
            body_lines.append("        %s%s" % (code, tail))
            if stops:
                if code != "return":
                    body_lines.append("        return")
                terminated = True
                break
        prev_cond = cond
    if not body_lines:
        body_lines.append("        pass  # 包装层无可翻译操作，见 assets_convert_report.md")
    elif not terminated:
        body_lines.append("        pass")
    return "\n".join(lines + body_lines), notes


# --------------------------------------------------------------- 生成文件 --
IMAGES_HEADER = """# -*- coding: utf-8 -*-
# 自动生成 · 请勿手改 —— 由 scripts/convert_assets.py 依据 assets_manifest.json 产出
# 原作: {game_root}
# 画面: {sw}x{sh}   素材: {assets} 条（蒙版 {mask} / 分割 {cells}）  音频: {audio} 条
# 改了素材就重跑转换脚本，不要在此文件里补 image 定义。
"""


def strips_of(man: dict) -> list[dict]:
    """挑出「动画条」：spec 形如 `:c/N,<间隔ms>,<x>;` 的多格素材。

    判据是**第 2 个参数 > 0**（每格间隔毫秒），不是「格数 > 1」。因为按钮那类
    `:a/2,0,3;` 也是多格，但第 2 参数是 0——那是 [图像|遮罩] 或按钮状态，不是动画。
    """
    out: list[dict] = []
    for a in man.get("assets", []):
        cells = a.get("cells") or {}
        cols = int(cells.get("cols") or 1)
        params = [str(p) for p in (cells.get("params") or [])]
        delay = int(params[1]) if len(params) > 1 and params[1].isdigit() else 0
        if cols > 1 and delay > 0:
            d, _ = split_dir_name(a["id"])
            stem = os.path.splitext(a["id"].split("/")[-1])[0]
            out.append({"dir": d or "misc", "base": stem, "cells": cols,
                        "delay": delay / 1000.0, "id": a["id"]})
    return out


def write_images_rpy(man: dict, entries: list[dict], path: str, image_root: str) -> None:
    out = [IMAGES_HEADER.format(
        game_root=man.get("game_root", "?"), sw=man["screen"][0], sh=man["screen"][1],
        assets=man["stats"]["assets_total"], mask=man["stats"]["mask_assets"],
        cells=man["stats"]["cell_assets"], audio=man["stats"]["audio_total"]), ""]
    kinds: dict[str, int] = {}
    for e in entries:
        kinds[e["dir"]] = kinds.get(e["dir"], 0) + 1
    out.append("init -10 python:")
    out.append("    NS_STAGE = {")
    out.append('        "screen": (%d, %d),' % tuple(man["screen"]))
    out.append('        "image_root": "%s",' % image_root)
    out.append('        "kinds": %s,' % json.dumps(kinds, ensure_ascii=False, sort_keys=True))
    out.append('        "mask_assets": %d,' % man["stats"]["mask_assets"])
    eff = next((w.get("effect_flag") for w in man["wrappers"] if w.get("effect_flag")), None)
    out.append('        "effect_flag": %r,' % eff)
    out.append("    }")
    out.append("")
    last_dir = None
    for e in sorted(entries, key=lambda x: (x["dir"], x["name"])):
        if e["dir"] != last_dir:
            out.append("")
            out.append("# ---- %s" % (e["dir"] or "misc"))
            last_dir = e["dir"]
        out.append('image %s %s = "%s"' % (safe_name(e["dir"] or "misc"), e["name"], e["path"]))
    out.append("")

    # ---- 动画条：多格 + 有帧间隔的素材，直接生成可播的 image
    strips = strips_of(man)
    if strips:
        out.append("# ---- 动画条（源 spec 第 2 参数 = 每格毫秒）")
        out.append("# 剧情里不要再手写 10 行 image 定义，也不要 show 单帧名：")
        out.append("#   show <目录> <名>_anim   → 播一遍停在最后一帧（落地/闪光照）")
        out.append("#   show <目录> <名>_loop   → 循环播（待机动画）")
        out.append("init -9 python:")
        out.append("    NS_STRIPS = {")
        for s in strips:
            out.append('        ("%s", "%s"): {"cells": %d, "delay": %.3f},'
                       % (safe_name(s["dir"]), safe_name(s["base"]), s["cells"], s["delay"]))
        out.append("    }")
        for s in strips:
            d = safe_name(s["dir"])
            base = safe_name(s["base"])
            # 单帧 image（<名>_c0…）已由上面的通用条目定义过，这里只补动画
            for suffix, repeat in (("_anim", False), ("_loop", True)):
                out.append("")
                out.append("image %s %s%s:" % (d, base, suffix))
                for i in range(s["cells"]):
                    out.append('    "%s %s_c%d"' % (d, base, i))
                    out.append("    pause %.3f" % s["delay"])
                if repeat:
                    out.append("    repeat")
        out.append("")
    open(path, "w", encoding="utf-8-sig", newline="\n").write("\n".join(out))


WRAPPERS_HEADER = """# -*- coding: utf-8 -*-
# 自动生成 · 请勿手改 —— 由 scripts/convert_assets.py 依据 defsub 语义表产出
# 每个 ns_w_* 对应原作一个 defsub 包装层；剧情模块调用它们，不要自己拼素材路径。
# 依赖: port_images.rpy（image 定义 + NS_STAGE）、ns_stage.rpy（运行时）
# 未翻译的原作指令见 port/assets_convert_report.md，不要静默放过。
"""


VAR_DEFAULTS = {"ns_mnum": "-1", "ns_senum": "0", "ns_w11": "0",
                "ns_g1": "1", "ns_g5": "1", "ns_g10": "6"}


def write_wrappers_rpy(man: dict, path: str) -> list[str]:
    notes: list[str] = []
    blocks: list[str] = []
    for w in man["wrappers"]:
        code, n = wrapper_to_py(w)
        notes += n
        blocks.append(code)
    used = sorted(set(re.findall(r"store\.(ns_[a-z0-9_]+)", "\n".join(blocks))))
    defaults = []
    if used:
        defaults = ["# 本文件用到的原作变量（%G1 演出开关 / %G5 语音开关 / %G10 SE 音量 0-6 /",
                    "# %MNUM 当前 BGM / %SENUM SE 通道轮转 / %w11 局部标志）:",
                    "# " + ", ".join("%s=%s" % (v, VAR_DEFAULTS.get(v, "0")) for v in used),
                    "# 默认值在 ns_stage.rpy 里保证存在；要让它们进存档并绑到设置界面，",
                    "# 请在 port_variables.rpy 用 default 定义同名变量（不要在 story 里定义）。"]
    text = [WRAPPERS_HEADER, ""] + (defaults + [""] if defaults else []) + ["init -5 python:", ""]
    text.append("\n\n".join(blocks) if blocks else "    pass")
    text.append("")
    aliases = ["", "# ---- 调用别名（剧情里用这些名字）----",
               "# ns_w_bg / ns_w_chr / ns_w_ev / ns_w_bgm ... 命名规则: ns_w_<defsub 名>"]
    open(path, "w", encoding="utf-8-sig", newline="\n").write("\n".join(text + aliases) + "\n")
    return notes


# ------------------------------------------------------------------- 主流程 --
GAME_DIR = ""


def main(argv=None) -> int:
    global GAME_DIR
    ap = argparse.ArgumentParser(description="按 assets_manifest.json 转换素材并生成 port_images/port_wrappers")
    ap.add_argument("game_root")
    ap.add_argument("project_game")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--image-root", default="images/ns")
    ap.add_argument("--audio", default="bgm,se,voice")
    ap.add_argument("--mask-mode", default="auto", choices=["auto", "dark-opaque", "light-opaque"])
    ap.add_argument("--report", default=None)
    ap.add_argument("--stage-template", default=None,
                    help="ns_stage.rpy 模板路径（默认取工作流 ns-port/assets/ns_stage.rpy）")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    game_root = os.path.abspath(args.game_root)
    GAME_DIR = os.path.abspath(args.project_game)
    man = json.load(open(args.manifest, encoding="utf-8"))
    if man.get("schema") != SCHEMA:
        print("[warn] manifest schema=%s，脚本期望 %s" % (man.get("schema"), SCHEMA), file=sys.stderr)
    if not os.path.isdir(GAME_DIR):
        print("[error] 工程 game 目录不存在: %s" % GAME_DIR, file=sys.stderr)
        return 2

    image_root = args.image_root.replace("\\", "/").strip("/")
    entries: list[dict] = []
    skipped: list[str] = []
    notes_all: list[str] = []
    t0 = time.time()

    todo = [a for a in man["assets"] if a.get("kind") in IMAGE_KINDS]
    for i, a in enumerate(todo, 1):
        if not a.get("exists"):
            skipped.append("%s（文件缺失）" % a["id"])
            continue
        try:
            outs, notes = convert_image(a, game_root, image_root, args.mask_mode)
        except Exception as e:
            skipped.append("%s（转换失败 %s: %s）" % (a["id"], type(e).__name__, e))
            continue
        d, _ = split_dir_name(a["id"])
        stem = os.path.splitext(a["id"].split("/")[-1])[0]
        if len(outs) > 1:
            for k, rel in enumerate(outs):
                entries.append({"dir": d or "misc", "name": safe_name("%s_c%d" % (stem, k)), "path": rel})
            notes_all.append("%s: %s" % (a["id"], "; ".join(notes)))
        else:
            entries.append({"dir": d or "misc", "name": safe_name(stem), "path": outs[0]})
            if any(("蒙版" in n) or ("键色" in n) or ("回退" in n) for n in notes):
                notes_all.append("%s: %s" % (a["id"], "; ".join(notes)))
        if i % 50 == 0:
            print("  ... %d/%d" % (i, len(todo)))

    # 音频
    copied_audio = 0
    audio_dirs = [d.strip() for d in (args.audio or "").split(",") if d.strip() and d.strip() != "none"]
    for a in man["audio"]:
        if not a.get("exists"):
            skipped.append("%s（音频缺失）" % a["id"])
            continue
        d, n = split_dir_name(a["id"])
        if audio_dirs and d.lower() not in [x.lower() for x in audio_dirs]:
            continue
        dst = os.path.join(GAME_DIR, "audio", d, n)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        src = os.path.join(game_root, a["id"].replace("/", os.sep))
        if args.force or not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
            shutil.copy2(src, dst)
        copied_audio += 1

    # 生成 rpy
    write_images_rpy(man, entries, os.path.join(GAME_DIR, "port_images.rpy"), image_root)
    gen_notes = write_wrappers_rpy(man, os.path.join(GAME_DIR, "port_wrappers.rpy"))

    # 安装通用演出层运行时（ns_stage.rpy，与作品无关，随工作流分发）
    stage_dst = os.path.join(GAME_DIR, "ns_stage.rpy")
    stage_src = os.path.abspath(args.stage_template or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "ns_stage.rpy"))
    if args.force or not os.path.exists(stage_dst):
        if os.path.exists(stage_src):
            shutil.copy2(stage_src, stage_dst)
            stage_note = "已安装 -> %s" % stage_dst
        else:
            stage_note = "[!] 模板缺失（%s），请手动拷贝 ns_stage.rpy" % stage_src
    else:
        stage_note = "已存在，保持不变（--force 覆盖）"

    # 报告
    report = args.report or os.path.join(os.path.dirname(GAME_DIR), "assets_convert_report.md")
    L = ["# 素材转换报告", "",
         "- 原作目录：`%s`" % game_root,
         "- 工程目录：`%s`" % GAME_DIR,
         "- manifest：`%s`" % os.path.abspath(args.manifest),
         "- 图像条目：%d（image 定义 %d 条），音频拷贝：%d 条，耗时 %.1fs"
         % (len(todo), len(entries), copied_audio, time.time() - t0), ""]
    L += ["## 转换要点", ""]
    for n in notes_all[:80]:
        L.append("- " + n)
    if len(notes_all) > 80:
        L.append("- ……其余 %d 条同类省略（可重跑 --force 查看）" % (len(notes_all) - 80))
    L += ["", "## 跳过 / 缺失", ""] + (["- " + s for s in skipped] or ["- 无"])
    L += ["", "## 包装层翻译备注", ""] + (["- " + n for n in gen_notes] or ["- 无"])
    L += ["", "## 演出层运行时", "", "- ns_stage.rpy：" + stage_note]
    os.makedirs(os.path.dirname(os.path.abspath(report)) or ".", exist_ok=True)
    open(report, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")

    print("[ok] 图像 %d 条 -> %s/%s" % (len(entries), GAME_DIR, image_root))
    print("[ok] port_images.rpy / port_wrappers.rpy 已生成")
    print("[ok] ns_stage.rpy %s" % stage_note)
    print("[ok] 音频 %d 条，跳过 %d 条" % (copied_audio, len(skipped)))
    print("[ok] 报告 -> %s" % report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
