#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""nsassets.py —— NScripter / ONScripter 素材普查：把「脚本里怎么引用素材」变成可执行清单。

为什么需要它
------------
素材层最容易出现的三个错误，全都是「靠猜」造成的：

1. 猜目录名：手写 `GROUPS = [("bg"), ("chr"), ("ev")]`。原作只要多一个 `sys\\`、`sv\\`、
   `log\\`、`musm\\`、`seld\\`，这些素材就永远进不了工程。
2. 猜文件清单：只转「脚本里出现过字面名」的文件，`"chr\\"+$w0+".bmp"` 这种变量拼接
   路径整批漏掉。
3. 猜显示方式：把 `:a;chr\\x.bmp` 当普通图片拷成 PNG。`:a;` 是**蒙版合成**——文件是横
   向双倍宽，右半是遮罩。丢掉 `:a;` 的结果是立绘带着一块纯色地板出场。

本脚本不做任何猜测，只做三件事：
  A. 从脚本里抽出**所有**素材引用（含 `:spec;` 前缀、变量拼接、字号/坐标等参数）；
  B. 变量部分按「字面目录」枚举磁盘真实文件，一个不漏地对上实物；
  C. 把每条引用落成结构化条目：源文件、尺寸、是否蒙版对、键色、目标输出、出现在哪一行。

产出 `assets_manifest.json`（给 convert_assets.py 用）和 `assets_report.md`（给人看，
列异常与待人工收口项）。解析不了的东西一律进报告，**不静默降级**。

用法
----
    python nsassets.py <游戏目录> [--script 0.txt nscript.dat] \
        [--out port/assets_manifest.json] [--report port/assets_report.md] \
        [--screen 800x600] [--root-dirs bg chr ev sys config top musm sv log seld voice]

不指定 --script 时自动找游戏目录下的 .txt/.dat/.nsa/.utf/.ks（排除 readme 等）。
不指定 --out 时打印 JSON 到 stdout。

依赖：Pillow（读尺寸/蒙版方向）；缺失时仍可产出清单，但蒙版方向标记为 unknown。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    from PIL import Image
except Exception:  # pragma: no cover - 允许无 Pillow 环境下跑清单
    Image = None

SCHEMA = 1

IMG_EXT = {".bmp", ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif"}
AUD_EXT = {".ogg", ".wav", ".mp3", ".opus", ".m4a", ".flac"}
SCRIPT_EXT = {".txt", ".dat", ".nsa", ".ns2", ".utf", ".ks", ".scn"}

# 顶层目录名 -> 素材类别。只用于给条目分类和给 convert 选转换策略，
# 分类失败不影响转换（未知目录按 image 处理并进报告）。
DIR_KIND = {
    "bg": "bg", "back": "bg", "background": "bg",
    "chr": "chr", "char": "chr", "tati": "chr", "sprite": "chr", " figure": "chr",
    "ev": "ev", "cg": "ev", "event": "ev",
    "sys": "sys", "system": "sys", "btn": "sys", "button": "sys",
    "config": "sys", "conf": "sys", "top": "sys", "title": "sys",
    "musm": "sys", "sv": "sys", "save": "sys", "load": "sys", "log": "sys",
    "savedata": "var", "seld": "sys",
    "voice": "voice", "se": "se", "bgm": "bgm", "sound": "se", "music": "bgm",
}

# ---------------------------------------------------------------- 脚本解码 --
_TRY_ENC = ("utf-8-sig", "cp932", "gbk", "euc_jp", "big5")


def decode_script(path: str) -> tuple[list[str], str]:
    """解码脚本，返回 (lines, 编码说明)。

    汉化工程常见混合编码：命令与结构是 SJIS，被替换的台词是 GBK/UTF-8。
    整文件严格解码必然失败，因此按行容错，尽量不丢结构信息。
    """
    raw = open(path, "rb").read()
    for enc in _TRY_ENC:
        try:
            return raw.decode(enc).splitlines(), enc
        except UnicodeDecodeError:
            continue
    out = []
    for chunk in raw.split(b"\n"):
        for enc in _TRY_ENC:
            try:
                out.append(chunk.decode(enc))
                break
            except UnicodeDecodeError:
                continue
        else:
            out.append(chunk.decode("latin-1", errors="replace"))
    return out, "mixed(line-wise)"


# ------------------------------------------------------------ 字符串表达式 --
# 注意：NScripter 的字符串里反斜杠是**路径分隔符，不是转义符**。
# `"bg\"+$w0+".bmp"` 表示 字符串 `bg\` + 变量 + `.bmp`，因此匹配时 `\` 只能当普通字符。
_SEG = r'"[^"]*"|\'[^\']*\'|\$[A-Za-z_]\w*|\d+%[A-Za-z_]\w*'
_CONCAT_RE = re.compile(r"(?:%s)(?:\s*\+\s*(?:%s))*" % (_SEG, _SEG))
_LITERAL_RE = re.compile(r'"([^"]*)"|\'([^\']*)\'')


def string_exprs(line: str) -> list[str]:
    """把 NS 的字符串拼接表达式抽出来，变量位置用 {var} 占位。

    `"chr\\"+$w0+".bmp"`            -> `chr\\\\{$w0}.bmp`
    `"bg\\"+$w0+".bmp",10,500`      -> `bg\\\\{$w0}.bmp`
    `":a;chr\\"+$w0+".bmp"`         -> `:a;chr\\\\{$w0}.bmp`
    `"#000000"`                     -> `#000000`
    """
    out = []
    for m in _CONCAT_RE.finditer(line):
        text = m.group(0)
        # 纯数字/纯 %var 的表达式不是路径，跳过
        if not any(q in text for q in ('"', "'")):
            continue
        buf = []
        pos = 0
        for lit in _LITERAL_RE.finditer(text):
            gap = text[pos:lit.start()]
            buf.append(gap)
            buf.append(lit.group(1) if lit.group(1) is not None else lit.group(2))
            pos = lit.end()
        buf.append(text[pos:])
        s = "".join(buf)
        # "..." 之外的 $var / %var -> {var}
        s = re.sub(r"\$([A-Za-z_]\w*)", lambda m: "{%s}" % m.group(1),
                   re.sub(r"%([A-Za-z_]\w*)", lambda m: "{%s}" % m.group(1), s))
        out.append(s)
    return out


def split_spec(expr: str):
    """拆出 `:spec;` 前缀，返回 (spec, path)。

    NScripter 精灵规格语法（出现在图片参数字符串开头）：
        :a;            蒙版合成（横双倍宽，右半为遮罩）
        :a/2,0,3;      蒙版 + 分割
        :c;            单元/单元格标记（不改几何）
        :c/2,0,3;      横向分割成 2 格
        :#00ff00/2,0,3; 指定透明键色 + 分割
        :s/25,25,0,0;#AAAA55#FFFFFF   文字精灵（后半是文字参数，不是文件）
        :l;            左右翻转
    """
    if not expr.startswith(":"):
        return "", expr
    end = expr.find(";")
    if end < 0:
        return expr, ""
    return expr[:end + 1], expr[end + 1:]


_SPEC_RE = re.compile(r"^:(?P<flags>[a-z]*)(?P<key>#[0-9A-Fa-f]{6})?(?P<params>[^;]*);$")


def parse_spec(spec: str) -> dict:
    """把 `:a/2,0,3;` 解析成结构。解析不了原样保留并在 flags_raw 暴露。"""
    info = {"raw": spec, "mask": False, "key": None, "flip": False,
            "cells": None, "params": [], "known": True}
    if not spec:
        return info
    m = _SPEC_RE.match(spec)
    if not m:
        info["known"] = False
        return info
    flags = m.group("flags") or ""
    info["mask"] = "a" in flags            # 蒙版合成
    info["flip"] = "l" in flags
    info["key"] = (m.group("key") or "").upper() or None
    raw_params = (m.group("params") or "").lstrip("/")
    params = [p.strip() for p in raw_params.split(",") if p.strip() != ""]
    info["params"] = params
    info["flags"] = flags
    letters = "".join(ch for ch in flags if ch not in "atlcsmb")
    if letters:
        info["known"] = False
    if len(params) >= 2 and params[0].isdigit():
        cols = int(params[0])
        if cols > 1:
            info["cells"] = {"cols": cols, "params": params}
    # 规范化：十六进制统一大写，去掉多余空格，便于按 spec 归组统计
    canon = ":" + flags + (info["key"] or "")
    if params:
        canon += "/" + ",".join(params)
    info["raw"] = canon + ";"
    return info


# --------------------------------------------------------------- 路径解析 --
def norm_path(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def has_var(p: str) -> bool:
    return "{" in p


def expand_pattern(game_root: str, pattern: str) -> tuple[list[str], str]:
    """把含 {var} 的模式按字面目录展开成磁盘真实文件列表。

    `chr\\{$w0}.bmp` -> chr/ 下所有 .bmp
    `bg\\{$w0}.bmp`  -> bg/ 下所有 .bmp
    """
    p = norm_path(pattern)
    if not has_var(p):
        return [p], ""
    idx = p.find("{")
    lit = p[:idx]
    cut = lit.rfind("/")
    dir_lit = lit[:cut] if cut >= 0 else ""
    ext = os.path.splitext(p)[1].lower()
    base = os.path.join(game_root, dir_lit.replace("/", os.sep)) if dir_lit else game_root
    if not os.path.isdir(base):
        return [], "目录不存在: %s" % dir_lit
    found = []
    for name in sorted(os.listdir(base)):
        if ext and not name.lower().endswith(ext):
            continue
        found.append((os.path.join(dir_lit, name) if dir_lit else name).replace(os.sep, "/"))
    return found, ""


# ------------------------------------------------------------ 素材实物核对 --
def probe_image(path: str, cols: int = 1) -> dict:
    """读尺寸、判蒙版对与键色。判据全部来自像素，不来自命名约定。

    `cols` 来自 spec 的分割格数：`[图像|遮罩] x N` 这种布局整体宽度不是简单
    双倍宽，必须拿第一格（2 个半格）去判，否则会误判成「不是蒙版对」。
    """
    info = {"size": None, "mask_pair": False, "half": None, "key": None,
            "key_ratio": None, "orient": "unknown"}
    if not os.path.exists(path):
        return info
    if Image is None:
        return info
    try:
        with Image.open(path) as im:
            rgb = im.convert("RGB")
    except Exception as e:  # 损坏文件也要留痕
        info["error"] = "%s: %s" % (type(e).__name__, e)
        return info
    w, h = rgb.size
    info["size"] = [w, h]
    cols = max(1, int(cols or 1))
    cell_w = w // cols
    if cell_w % 2 == 0 and cell_w >= 8:
        info["half"] = [cell_w // 2, h]
        info["pair_size"] = [cell_w, h]
        info.update(_judge_mask_pair(rgb.crop((0, 0, cell_w, h))))
        info["pair_size"] = [cell_w, h]
    if not info["mask_pair"]:
        px = rgb.getpixel((1, 1))
        info["key"] = "#%02X%02X%02X" % px
        info["key_ratio"] = _flat_ratio(rgb, px)
    return info


def _flat_ratio(rgb, color, step=7) -> float:
    w, h = rgb.size
    data = rgb.load()
    total = hit = 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            total += 1
            if data[x, y] == color:
                hit += 1
    return round(hit / total, 4) if total else None


def _judge_mask_pair(rgb) -> dict:
    """判定「横双倍宽 = 左图 + 右蒙版」，并定出蒙版方向。

    判据：右半必须是近似二值（大量 <64 与 >224），且其暗部形状与左半「非键色」区域
    高度重合。重合度高 -> 黑=不透明（alpha = 255-灰）；否则白=不透明。
    """
    w, h = rgb.size
    half = w // 2
    left = rgb.crop((0, 0, half, h))
    right = rgb.crop((half, 0, w, h)).convert("L")
    key = left.getpixel((1, 1))
    step = max(1, min(half // 64, h // 64, 6))
    lp, rp = left.load(), right.load()
    total = dark = white = both = 0
    dark_and_filled = filled = 0
    for y in range(0, h, step):
        for x in range(0, half, step):
            v = rp[x, y]
            total += 1
            is_dark = v < 64
            is_white = v > 224
            dark += is_dark
            white += is_white
            filled_px = lp[x, y] != key
            if filled_px:
                filled += 1
                if is_dark:
                    dark_and_filled += 1
    if not total:
        return {"mask_pair": False}
    binary = (dark + white) / total > 0.9
    overlap = (dark_and_filled / filled) if filled else 0.0
    is_pair = bool(binary and filled and overlap > 0.5)
    orient = "dark-opaque" if (is_pair and overlap > 0.65) else ("light-opaque" if is_pair else "unknown")
    return {"mask_pair": is_pair, "orient": orient,
            "mask_binary": round((dark + white) / total, 3),
            "overlap": round(overlap, 3),
            "key": "#%02X%02X%02X" % key}


# ------------------------------------------------------------- defsub 语义 --
_CMD_PATTERNS = [
    ("bg", re.compile(r"^_bg\s+(?P<arg>[^,]+?)(?:,(?P<t>\d+)(?:,(?P<s>\d+))?)?\s*$")),
    ("chr", re.compile(r"^ld\s+(?P<slot>[lcr])\s*,\s*(?P<arg>.+?)(?:,(?P<t>\d+)(?:,(?P<s>\d+))?)?\s*$")),
    ("chr_clear", re.compile(r"^cl\s+(?P<slot>[lcr])(?:\s*,\s*(?P<t>\d+))?(?:\s*,\s*(?P<s>\d+))?\s*$")),
    ("ex", re.compile(r"^(?P<arg>ex\d*)\s*,?(?P<t>\d+)?(?:,(?P<s>\d+))?\s*$")),
    ("sprite", re.compile(r"^(?P<cmd>lsp|lsph)\s+(?P<layer>[^,]+),\s*(?P<arg>.+?)(?:,(?P<x>[^,]+),(?P<y>[^,]+))?\s*$")),
    ("bgm", re.compile(r"^bgm\s+(?P<arg>.+?)\s*$")),
    ("bgm_stop", re.compile(r"^bgmstop\s*$")),
    ("wave", re.compile(r"^(?P<cmd>dwave|dwaveloop)\s+(?P<ch>[^,]+),\s*(?P<arg>.+?)\s*$")),
    ("wave_stop", re.compile(r"^(?P<cmd>dwavestop)\s+(?P<ch>[^,]+)\s*$")),
    ("vol", re.compile(r"^chvol\s+(?P<ch>[^,]+),\s*(?P<arg>.+?)\s*$")),
    ("wait", re.compile(r"^(?P<cmd>wait|delay|waitfor)\s+(?P<arg>.+?)\s*$")),
    ("print", re.compile(r"^(?P<cmd>print|csp|texton|textoff)\s*(?P<arg>.*?)\s*$")),
    ("misc", re.compile(r"^(?P<arg>dstop|black|cl|white|bg)\s*$")),
]


_STMT_WORDS = ("return", "goto", "gosub", "mov", "inc", "add", "dec", "bgm", "bgmstop",
               "dwavestop", "dwave", "dwaveloop", "chvol", "wait", "delay", "print",
               "csp", "texton", "textoff", "saveoff", "saveon", "_bg", "ld", "cl",
               "lsp", "lsph", "black", "dstop", "ex", "click", "next")


def _split_statements(s: str) -> list[str]:
    """NScripter 用 `:` 分隔同行的多条语句（`chvol 19,0:return`）。

    但 `:` 也出现在字符串里的 spec（`":a;chr\\x.bmp"`）和文件路径里，所以只在
    「冒号后面紧跟一个已知指令词」时才当分隔符。拆错会把参数切碎，宁可少拆。
    """
    out, start, q = [], 0, False
    for idx, ch in enumerate(s):
        if ch == '"':
            q = not q
        elif ch == ":" and not q:
            rest = s[idx + 1:].strip()
            head = rest.split()[0] if rest else ""
            if head in _STMT_WORDS or head.startswith("*"):
                out.append(s[start:idx].strip())
                start = idx + 1
    out.append(s[start:].strip())
    return [x for x in out if x]


def parse_wrapper_body(lines: list[str], start: int) -> tuple[list[dict], int]:
    """解析一个 `*name` 标签体（到 return / 下一个标签为止）。

    三条容易踩错的规则（吃过亏，别再简化）：
    - `:` 是语句分隔符，一行可能有多条（`chvol 19,0:return`）→ 逐条拆开；
    - `if 条件 return` 是**条件返回**，不能当成标签结束，否则后面的 body 全丢
      （*music 整段 bgm 分派就是这样被吞掉的）；
    - 只有无条件 `return` 才结束解析。
    """
    ops: list[dict] = []
    i = start
    n = len(lines)
    while i < n:
        s = lines[i].rstrip().strip()
        if i > start and re.match(r"^\*[A-Za-z_]\w*$", s):
            break
        i += 1
        if not s or s.startswith(";"):
            continue
        cond = None
        m_if = re.match(r"^if\s+(?P<cond>.+?)\s+(?P<rest>(?:_bg|ld|cl|lsp|lsph|bgm|bgmstop|dwave|dwaveloop|dwavestop|chvol|gosub|goto|mov|inc|print|csp|textoff|delay|wait|return|black|dstop)\b.*)$", s)
        if m_if:
            cond = m_if.group("cond").strip()
            s = m_if.group("rest").strip()

        terminated = False
        for stmt in _split_statements(s):
            if stmt.startswith("return"):
                ops.append({"op": "return", "cond": cond, "line": i})
                if cond is None:      # 无条件返回 = 标签结束
                    terminated = True
                continue
            if stmt.startswith("getparam"):
                ops.append({"op": "params", "args": stmt[len("getparam"):].strip(),
                            "cond": cond, "line": i})
                continue
            m_goto = re.match(r"^goto\s+\*(\w+)\s*$", stmt)
            if m_goto:
                ops.append({"op": "goto", "target": m_goto.group(1), "cond": cond, "line": i})
                continue
            m_gosub = re.match(r"^gosub\s+\*(\w+)\s*$", stmt)
            if m_gosub:
                ops.append({"op": "gosub", "target": m_gosub.group(1), "cond": cond, "line": i})
                continue
            matched = False
            for name, rx in _CMD_PATTERNS:
                m = rx.match(stmt)
                if not m:
                    continue
                op = {"op": name, "cond": cond, "line": i}
                for k, v in m.groupdict().items():
                    if v is not None:
                        op[k] = v.strip() if isinstance(v, str) else v
                if "arg" in op:
                    arg = op["arg"].strip().strip('"').rstrip(":").strip()
                    spec, path = split_spec(arg)
                    if spec:
                        op["spec"] = spec
                    op["arg"] = path.strip() or arg
                ops.append(op)
                matched = True
                break
            if not matched:
                ops.append({"op": "other", "text": stmt, "cond": cond, "line": i})
        if terminated:
            break
    return ops, i


# ------------------------------------------------------------------- 主流程 --
def collect_scripts(game_root: str, explicit: list[str]) -> list[str]:
    if explicit:
        out = []
        for s in explicit:
            p = s if os.path.isabs(s) else os.path.join(game_root, s)
            if os.path.isfile(p):
                out.append(p)
            else:
                print("[warn] 脚本不存在: %s" % p, file=sys.stderr)
        return out
    found = []
    for dirpath, _dirnames, filenames in os.walk(game_root):
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext in SCRIPT_EXT and not re.search(r"(readme|manual|修正|update|log|report)", fn, re.I):
                found.append(os.path.join(dirpath, fn))
        if len(found) > 200:
            break
    return sorted(found)


def analyse(game_root: str, scripts: list[str], screen: tuple[int, int]) -> dict:
    assets: dict[str, dict] = {}
    audio: dict[str, dict] = {}
    wrappers: dict[str, dict] = {}
    errors: list[str] = []
    unknown_specs: list[dict] = []
    script_infos = []

    for path in scripts:
        lines, enc = decode_script(path)
        rel = os.path.relpath(path, game_root).replace(os.sep, "/")
        script_infos.append({"path": rel, "lines": len(lines), "encoding": enc})
        # defsub 声明
        for i, line in enumerate(lines, 1):
            m = re.match(r"^\s*defsub\s+(\w+)", line)
            if m:
                wrappers.setdefault(m.group(1), {"name": m.group(1), "decl_script": rel,
                                                 "decl_line": i, "ops": [], "params": []})
        # 各标签体
        for i, line in enumerate(lines, 1):
            m = re.match(r"^(\*[A-Za-z_]\w*)\s*$", line.strip())
            if not m:
                continue
            name = m.group(1)[1:]
            ops, _end = parse_wrapper_body(lines, i)
            if name in wrappers:
                wrappers[name]["body_script"] = rel
                wrappers[name]["body_line"] = i
                wrappers[name]["ops"] = ops
                params = []
                for op in ops:
                    if op["op"] == "params":
                        for p in op["args"].replace(" ", "").split(","):
                            if not p:
                                continue
                            params.append({"name": p, "type": "num" if p.startswith("%") else "str"})
                wrappers[name]["params"] = params
        # 素材引用
        for i, line in enumerate(lines, 1):
            s = line.strip()
            if not s or s.startswith(";"):
                continue
            cmd = s.split(None, 1)[0].lstrip("$") if s.split() else ""
            for expr in string_exprs(line):
                spec, body = split_spec(expr)
                body = body.replace("\\\\", "\\")
                if not body:
                    continue
                low = body.lower()
                ext = os.path.splitext(low)[1]
                looks_audio = ext in AUD_EXT
                looks_image = ext in IMG_EXT or (spec and not ext)
                is_black = low in ("black", "white", "#000000", "#ffffff")
                has_dir = "\\" in body or "/" in body
                if is_black or not (looks_audio or (looks_image and (has_dir or not has_var(body)))):
                    continue
                if looks_audio:
                    paths, err = expand_pattern(game_root, body)
                    for p in paths:
                        key = norm_path(p)
                        entry = audio.setdefault(key, {"id": key, "src": key,
                                                       "exists": os.path.exists(os.path.join(game_root, key.replace("/", os.sep))),
                                                       "refs": []})
                        entry["refs"].append({"script": rel, "line": i, "cmd": cmd})
                    if err:
                        errors.append("音频目录: %s (%s:%d)" % (err, rel, i))
                    continue
                paths, err = expand_pattern(game_root, body)
                if err:
                    errors.append("图片目录: %s (%s:%d)" % (err, rel, i))
                    continue
                for p in paths:
                    ident = norm_path(p)
                    e = assets.setdefault(ident, {"id": ident, "src": ident, "specs": [], "refs": []})
                    canon = parse_spec(spec)["raw"] if spec else ""
                    if canon and canon not in e["specs"]:
                        e["specs"].append(canon)
                    e["refs"].append({"script": rel, "line": i, "cmd": cmd})
                if spec and not parse_spec(spec)["known"]:
                    unknown_specs.append({"spec": spec, "script": rel, "line": i})

    # 实物核对
    for ident, e in assets.items():
        src = e["src"]
        abs_src = os.path.join(game_root, src.replace("/", os.sep))
        e["exists"] = os.path.exists(abs_src)
        e["kind"] = DIR_KIND.get(src.split("/")[0].lower(), "image")
        e["name"] = os.path.splitext(src.split("/")[-1])[0]
        e["dir"] = src.split("/")[0] if "/" in src else ""
        masks = [s for s in e["specs"] if parse_spec(s)["mask"]]
        keys = [parse_spec(s)["key"] for s in e["specs"] if parse_spec(s)["key"]]
        cells = [parse_spec(s)["cells"] for s in e["specs"] if parse_spec(s)["cells"]]
        e["spec_key"] = keys[0] if keys else None
        e["cells"] = cells[0] if cells else None
        cols = int((e["cells"] or {}).get("cols", 1) or 1) if e["cells"] else 1
        probe = probe_image(abs_src, cols) if e["exists"] else {}
        e.update(probe)
        e["mask_spec"] = bool(masks)
        if masks:
            e["mask"] = True
        elif e["specs"]:
            # 脚本已经明确写了 spec 但没标 `:a;`（例如 `:c;` / `:#RRGGBB;`），
            # 就按脚本走。像素「看起来像蒙版对」不能翻案：动画条 `:c/10,40,1;`
            # 每格 424 宽，横切两半也像「图+遮罩」，按像素判会把每一帧拆碎。
            e["mask"] = False
            if probe.get("mask_pair"):
                e["mask_note"] = "像素像「图+遮罩」，但脚本给的是 %s（无 :a;），按脚本处理" \
                                 % "/".join(e["specs"])
        else:
            e["mask"] = bool(probe.get("mask_pair"))
        if masks and not probe.get("mask_pair") and probe.get("size"):
            e["mask_note"] = "脚本标了 :a; 但像素判据不充分（小图/非二值），仍按 :a; 拆半幅处理"
        e["out"] = None  # convert_assets.py 填

    for ident, e in audio.items():
        e["kind"] = DIR_KIND.get(ident.split("/")[0].lower(), "audio")

    stats = {
        "assets_total": len(assets),
        "assets_missing": sum(1 for e in assets.values() if not e["exists"]),
        "mask_assets": sum(1 for e in assets.values() if e.get("mask")),
        "cell_assets": sum(1 for e in assets.values() if e.get("cells")),
        "audio_total": len(audio),
        "audio_missing": sum(1 for e in audio.values() if not e["exists"]),
        "by_kind": {},
        "by_spec": {},
    }
    for e in assets.values():
        stats["by_kind"][e["kind"]] = stats["by_kind"].get(e["kind"], 0) + 1
        for s in e["specs"]:
            stats["by_spec"][s] = stats["by_spec"].get(s, 0) + 1

    # 效果开关变量：同一个包装层里成对出现 `,10,N` 与 `,1`
    for w in wrappers.values():
        flag = _detect_effect_flag(w.get("ops", []))
        if flag:
            w["effect_flag"] = flag

    return {
        "schema": SCHEMA,
        "generated_by": "nsassets.py",
        "game_root": os.path.abspath(game_root),
        "screen": list(screen),
        "scripts": script_infos,
        "assets": sorted(assets.values(), key=lambda e: e["id"]),
        "audio": sorted(audio.values(), key=lambda e: e["id"]),
        "wrappers": sorted(wrappers.values(), key=lambda w: w["name"]),
        "unknown_specs": unknown_specs,
        "errors": errors,
        "stats": stats,
    }


def _detect_effect_flag(ops: list[dict]) -> str | None:
    """找「有特效 / 无特效」这一对条件，返回控制变量名（如 %G1）。"""
    pairs: dict[str, dict[str, str]] = {}
    for op in ops:
        cond = op.get("cond") or ""
        if op.get("op") not in ("bg", "chr", "sprite"):
            continue
        var = re.match(r"^(%\w+)\s*(=|<|>|!|&)", cond)
        if not var:
            continue
        timed = str(op.get("t", "")) not in ("", "0", "1")
        pairs.setdefault(var.group(1), {})["timed" if timed else "plain"] = cond
    for var, d in pairs.items():
        if len(d) == 2:
            return var
    return None


# ------------------------------------------------------------------ 报告 ---
def write_report(man: dict, path: str) -> None:
    st = man["stats"]
    L = ["# 素材普查报告", "",
         "- 引擎目录：`%s`" % man["game_root"],
         "- 画面尺寸：%dx%d" % tuple(man["screen"]),
         "- 脚本：%s" % ", ".join("`%s`(%d 行, %s)" % (s["path"], s["lines"], s["encoding"])
                                 for s in man["scripts"]),
         "- 素材条目 %d 条，缺失 %d 条；音频 %d 条，缺失 %d 条"
         % (st["assets_total"], st["assets_missing"], st["audio_total"], st["audio_missing"]),
         "- 蒙版合成 %d 条，分割图 %d 条" % (st["mask_assets"], st["cell_assets"]),
         ""]
    L += ["## 按目录分类", "", "| 类别 | 数量 |", "|---|---|"]
    for k, v in sorted(st["by_kind"].items()):
        L.append("| %s | %d |" % (k, v))
    L += ["", "## 出现过的 sprite spec", "", "| spec | 次数 | 语义 |", "|---|---|---|"]
    for s, c in sorted(st["by_spec"].items(), key=lambda kv: -kv[1]):
        p = parse_spec(s)
        sem = []
        if p["mask"]:
            sem.append("蒙版(横双倍宽,右半遮罩)")
        if p["key"]:
            sem.append("键色 %s" % p["key"])
        if p["cells"]:
            sem.append("分割 %s" % ",".join(p["params"]))
        if p["flip"]:
            sem.append("左右翻转")
        if not sem:
            sem.append("无几何影响")
        L.append("| `%s` | %d | %s |" % (s, c, "；".join(sem)))

    L += ["", "## 包装层（defsub）语义", "",
          "剧情里调用的是这些包装，不是裸命令；Ren'Py 侧必须按同一语义实现。", ""]
    for w in man["wrappers"]:
        params = ",".join(p["name"] for p in w.get("params", []))
        L.append("### `%s(%s)`  %s:%s" % (w["name"], params, w.get("decl_script", "?"), w.get("decl_line", "?")))
        L.append("")
        L.append("| 行 | 条件 | 操作 |")
        L.append("|---|---|---|")
        for op in w.get("ops", []):
            desc = op.get("op", "")
            for k in ("slot", "arg", "t", "s", "cmd", "layer", "x", "y", "target", "text", "ch"):
                if k in op:
                    desc += " %s=%s" % (k, op[k])
            if op.get("spec"):
                desc += " spec=%s" % op["spec"]
            L.append("| %s | %s | %s |" % (op.get("line", ""), op.get("cond") or "", desc.replace("|", "\\|")))
        if w.get("effect_flag"):
            L.append("")
            L.append("> 特效开关变量：`%s`（有特效走长过渡，否定走即时）" % w["effect_flag"])
        L.append("")

    problems = []
    for e in man["assets"]:
        if not e["exists"]:
            problems.append("缺失素材 `%s`（引用 %d 处）" % (e["id"], len(e["refs"])))
        elif e.get("mask") and not e.get("mask_pair"):
            problems.append("`%s` 标记为蒙版但像素不像双倍宽：%s" % (e["id"], e.get("mask_note", "")))
        elif e.get("mask_pair") and not e.get("mask_spec"):
            problems.append("`%s` 是双倍宽蒙版对，但脚本没给 `:a;`（可能由包装层统一加，需人工确认）" % e["id"])
    L += ["## 待人工收口", ""] + (["- " + p for p in problems] or ["- 无"])
    if man["unknown_specs"]:
        L += ["", "### 未识别的 spec", ""]
        for u in man["unknown_specs"]:
            L.append("- `%s` @ %s:%d" % (u["spec"], u["script"], u["line"]))
    if man["errors"]:
        L += ["", "### 解析告警", ""] + ["- " + e for e in man["errors"]]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NScripter 素材普查（生成 assets_manifest.json + 报告）")
    ap.add_argument("game_root")
    ap.add_argument("--script", nargs="*", default=None, help="脚本路径（相对游戏目录）")
    ap.add_argument("--out", default=None, help="输出 manifest json（相对当前目录或绝对路径）")
    ap.add_argument("--report", default=None, help="输出 markdown 报告")
    ap.add_argument("--screen", default="800x600")
    args = ap.parse_args(argv)

    game_root = os.path.abspath(args.game_root)
    if not os.path.isdir(game_root):
        print("[error] 游戏目录不存在: %s" % game_root, file=sys.stderr)
        return 2
    m = re.match(r"^(\d+)\s*[xX*]\s*(\d+)$", args.screen)
    screen = (int(m.group(1)), int(m.group(2))) if m else (800, 600)

    scripts = collect_scripts(game_root, args.script or [])
    if not scripts:
        print("[error] 没找到脚本，请用 --script 指定", file=sys.stderr)
        return 2
    man = analyse(game_root, scripts, screen)

    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)) or ".", exist_ok=True)
        write_report(man, args.report)
        print("[ok] 报告 -> %s" % args.report)
    text = json.dumps(man, ensure_ascii=False, indent=1)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
        open(args.out, "w", encoding="utf-8", newline="\n").write(text + "\n")
        print("[ok] manifest -> %s" % args.out)
    else:
        print(text)

    st = man["stats"]
    print("[stats] assets=%d missing=%d mask=%d cells=%d audio=%d images=%d wrappers=%d"
          % (st["assets_total"], st["assets_missing"], st["mask_assets"], st["cell_assets"],
             st["audio_total"], sum(1 for e in man["assets"] if e["kind"] in ("bg", "chr", "ev")),
             len(man["wrappers"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
