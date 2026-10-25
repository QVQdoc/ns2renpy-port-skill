#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns2renpy.py — NScripter 脚本 → Ren'Py 脚本 转译器（原型 0.9）

用法:
    python ns2renpy.py 输入.txt|nscript.dat -o 输出目录 [选项]

选项:
    -o, --out DIR        输出目录（自动建 game/ 子目录），默认 out
    --assets DIR         资源根目录，用于自动识别图片/音频路径（默认取输入文件所在目录）
    --image-dir NAME     图片子目录名，默认 images
    --audio-dir NAME     音频子目录名，默认 audio
    --max-lines N        一次 say 最多合并几行 NS 文本，默认 4
    --infer-speaker      用 ld 加载的立绘名推断说话人（启发式，默认关）
    --keep-indent        保留文本行前导空格（默认剥掉）
    --xor-key N          强制指定 nscript.dat 的 XOR 常量（十进制或 0x84 形式）
    --selftest           跑内置自检后退出（不读文件）

设计原则:
    1. 宁可留 TODO，也不静默丢语义 —— 每条无法 1:1 映射的指令都会写成
       "# TODO[NS行N]" 并在 report.txt 里汇总。
    2. 文本/指令/标签/注释 四类行按 NS 的解析规则切分（行首 token 命中命令表
       即为命令，否则为文本）。
    3. NS 的 "装载(bg/ld) → 绘制(print) → 等待点击" 被拍平成 "立即显示 + with"，
       观感等价，差异见 README。
"""

import argparse
import os
import re
import sys
from collections import Counter, OrderedDict

VERSION = "0.9"

ENCODINGS = ["utf-8-sig", "utf-8", "cp932", "gbk", "big5"]

# ---------------------------------------------------------------- 命令表
# 行首 token 命中此表 => 命令；否则 => 台词文本。
# 表必须尽量全，漏一个就会把命令当台词打出来。
COMMANDS = set("""
game reset definereset end
setwindow setwindow2 textoff texton windoweffect erasetextwindow
defaultfont textclear locate puttext br textspeed rubyon rubyoff
clickstr linepage clickvoice autoclick click
setcursor abssetcursor mousecursor
transmode underline bgalia humanz windowback bg ld cl tal print
lsp lsph csp vsp spstr msp amsp cell blt ofscpy repaint
effect effectblank effectcut quake quakex quakey monocro nega
bar barclear prnum prnumclear
cdfadeout mp3fadeout play playonce playstop wave waveloop wavestop
mp3 mp3loop mp3save dsound dwave dwaveloop dwavestop dwaveload
dwaveplay dwaveplayloop stop
avi mpegplay
selectcolor selectvoice select selgosub selnum
goto skip gosub return jumpf jumpb
trap lr_trap trap2 lr_trap2
btndef btn btnwait btnwait2 spbtn getbtntimer btntime exbtn exbtn_d
delay wait resettimer waittimer gettimer spwait
stralias numalias intlimit dim mov mov3 mov4 mov5 mov6 mov7 mov8 mov9 mov10
movl add sub inc dec mul div mod rnd rnd2 itoa atoi
if notif cmp fchk lchk for next break
rmenu menusetwindow savename menuselectcolor menuselectvoice
rlookback roff rmode
lookbackbutton lookbackcolor lookbackvoice lookbackflush
kidokuskip mode_wave_demo skipoff
filelog globalon labellog
savenumber savegame loadgame savefileexist saveon saveoff
mesbox inputstr input clickpos systemcall
automode automode_time defvoicevol defsevol defmp3vol
mode_saya mode_ext mode800
soundpressplgin spi arc nsa nsadir
versionstr caption
date time savetime getversion getreg getini
killmenu defaultspeed menu_full menu_window menu_click_def menu_click_page
csel cselbtn getcselnum cselgoto textbtnwait selectbtnwait texec getcursorpos
textgosub defsub getparam pretextgosub
""".split())

DEFINE_NOISE = set("""
savename savenumber versionstr defaultfont nsa nsadir arc mode800
kidokuskip globalon filelog transmode underline humanz windowback bgalia
mp3fadeout cdfadeout defsevol defmp3vol defvoicevol effectblank textspeed
autoclick clickstr clickvoice linepage lookbackflush lookbackbutton
lookbackcolor rmenu menusetwindow menuselectcolor menuselectvoice
mode_saya mode_ext soundpressplgin spi intlimit defsub pretextgosub
rubyon rubyoff defaultspeed selectcolor selectvoice
""".split())


# ---------------------------------------------------------------- 小工具
def sanitize(s):
    """把任意 NS 标识符/文件名转成合法的 Ren'Py 标识符片段。"""
    s = s.strip()
    s = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", s)
    s = re.sub(r"[^0-9A-Za-z_]+", "_", s)
    s = s.strip("_")
    if not s:
        s = "x"
    if s[0].isdigit():
        s = "x_" + s
    return s.lower()


def split_args(s):
    """按半角逗号切参数，双引号内的逗号不切。"""
    parts = []
    cur = []
    inq = False
    for ch in s:
        if ch == '"':
            inq = not inq
            cur.append(ch)
        elif ch == "," and not inq:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def score_text(t):
    """给候选解码结果打分，用于自动猜编码 / XOR 常量。"""
    if not t:
        return -1e9
    sample = t[:8000]
    good = sum(1 for c in sample if c.isprintable() or c in "\n\t")
    sc = 100.0 * good / float(len(sample))
    sc += 80.0 * t.count("*define")
    sc += 40.0 * t.count("*start")
    sc += 40.0 * t.count("\ngame")
    sc -= 200.0 * t.count("\ufffd")
    return sc


def decode_script(raw, forced_key=None):
    """返回 (text, xor_key, encoding)。0 表示没有 XOR。"""
    keys = [forced_key] if forced_key is not None else [0x84, 0x00]
    best = None
    for key in keys:
        data = raw if key == 0 else bytes(b ^ key for b in raw)
        for enc in ENCODINGS:
            try:
                t = data.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
            sc = score_text(t)
            if best is None or sc > best[0]:
                best = (sc, t, key, enc)
    if best is None:
        data = raw if forced_key in (0, None) else bytes(b ^ forced_key for b in raw)
        best = (-1e9, data.decode("cp932", "replace"),
                forced_key if forced_key else 0, "cp932(replace)")
    return best[1], best[2], best[3]


# ---------------------------------------------------------------- 转换器
class Converter(object):
    def __init__(self, opts):
        self.opts = opts
        self.body = []

        self.images = OrderedDict()      # image 名 -> 相对路径
        self.speakers = OrderedDict()    # 变量名 -> 显示名
        self.num_vars = set()
        self.str_vars = set()
        self.arr_vars = OrderedDict()    # 变量号 -> 长度
        self.alias = {}                  # numalias/stralias
        self.effects = {}                # 效果号 -> 秒
        self.todos = []
        self.ref_labels = OrderedDict()  # 目标 -> [行号]
        self.label_defs = {}
        self.labels = set()
        self.cmd_count = Counter()

        self.in_define = False
        self.saw_start = False
        self.text_buf = []
        self.speaker = None
        self.bg_tag = None
        self.layer_tag = {"l": None, "c": None, "r": None}
        self.sprite_tag = {}
        self.caption = None
        self.font_size = None
        self.cols = None
        self.rows = None
        self.assets = {}
        self.textgosub = None
        self.line_no = 0

    # -------------------------------------------------- 资源
    def scan_assets(self, root):
        if not root or not os.path.isdir(root):
            return
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                key = fn.lower()
                if key in self.assets:
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), root)
                self.assets[key] = rel.replace("\\", "/")

    def asset_path(self, filename, default_dir):
        base = os.path.basename(filename)
        hit = self.assets.get(base.lower())
        if hit:
            return hit
        return default_dir + "/" + base

    def image_tag(self, prefix, filename):
        tag = "ns_" + prefix + "_" + sanitize(os.path.basename(filename))
        if tag not in self.images:
            self.images[tag] = self.asset_path(filename, self.opts.image_dir)
        return tag

    # -------------------------------------------------- 输出原语
    def emit(self, text, indent=1):
        self.body.append("    " * indent + text)

    def todo(self, ln, raw, why, indent=1):
        self.todos.append((ln, raw.strip(), why))
        self.emit("# TODO[NS行%d] %s" % (ln, raw.strip()), indent)
        self.emit("#      %s" % why, indent)

    def unquote(self, s):
        s = s.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s

    def scaled(self, val):
        """把 NS 的 640x480 坐标按 --scale 放大（用于 1280x960 等整数倍工程）。"""
        try:
            f = float(val)
        except (TypeError, ValueError):
            return val
        out = f * self.opts.scale
        if abs(out - round(out)) < 1e-6:
            return str(int(round(out)))
        return "%.2f" % out

    # -------------------------------------------------- 变量
    def pref(self, arg):
        """只作为左值/变量引用解析。"""
        a = arg.strip()
        if a.startswith("%"):
            idx = a[1:].strip()
            self.num_vars.add(idx)
            return "n" + idx
        if a.startswith("$"):
            idx = a[1:].strip()
            self.str_vars.add(idx)
            return "s" + idx
        if a.startswith("?"):
            return "a" + a[1:].strip()
        if a in self.alias:
            return self.alias[a]
        return None

    def value(self, arg):
        """右值：变量 / 整数 / 字符串字面量。"""
        a = arg.strip()
        p = self.pref(a)
        if p:
            return p
        if re.match(r"^-?\d+$", a):
            return a
        if len(a) >= 2 and a[0] == '"' and a[-1] == '"':
            return a
        return None

    def label_ref(self, arg):
        nm = arg.strip()
        if nm.startswith("*"):
            nm = nm[1:]
        return sanitize(nm)

    # -------------------------------------------------- 主流程
    def run(self, text):
        for ln, raw in enumerate(text.splitlines(), 1):
            self.line_no = ln
            line = raw.replace("\t", "    ").rstrip()
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(";"):
                continue
            head = line.lstrip()
            if head.startswith("*"):
                self.flush_text()
                name = head[1:].strip()
                if name == "define":
                    self.in_define = True
                    continue
                if name == "start":
                    self.saw_start = True
                self.open_label(name)
                continue
            parts = head.split(None, 1)
            word = parts[0]
            rest = parts[1] if len(parts) > 1 else ""
            if word in COMMANDS:
                self.handle_command(word, rest, raw, ln)
            else:
                self.push_text(line, ln)
        self.flush_text()
        if not self.saw_start:
            self.open_label("start")

    def open_label(self, name):
        self.in_define = False
        san = "start" if name == "start" else sanitize(name)
        if san in self.label_defs:
            self.label_defs[san] += 1
            san = "%s_%d" % (san, self.label_defs[san])
        else:
            self.label_defs[san] = 1
        self.labels.add(san)
        self.emit("", 0)
        self.emit("# ---- NS *%s ----" % name, 0)
        self.emit("label %s:" % san, 0)
        if name == "start":
            self.emit("$ renpy.scene()   # 清空 master 层（对应 NS 的初始画面）")

    # -------------------------------------------------- 文本
    def push_text(self, line, ln):
        if not self.opts.keep_indent:
            line = line.strip()
        self.text_buf.append((line, ln))

    def flush_text(self):
        if not self.text_buf:
            return
        buf = self.text_buf
        self.text_buf = []
        pages = []
        cur = []
        for raw, ln in buf:
            s, brk = self.xform(raw, ln)
            # 纯控制行（如单独一个 _）不产生空行；br 产生的空行要保留
            if s or brk or not raw.strip():
                cur.append(s)
            if brk:
                pages.append(cur)
                cur = []
        if cur:
            pages.append(cur)
        step = max(1, int(self.opts.max_lines))
        for page in pages:
            while page and not page[-1].strip():
                page.pop()
            if not page:
                self.emit("# （翻页等待，本页无文本）")
                continue
            for i in range(0, len(page), step):
                self.emit_say(page[i:i + step])

    def emit_say(self, chunk):
        while chunk and not chunk[-1].strip():
            chunk.pop()
        if not chunk:
            return
        # 注意: Ren'Py 的 say 字符串不能跨物理行，多行必须用 \n 转义
        text = "\\n".join(chunk)
        if not text.strip():
            return
        text = text.replace('"', '\\"')
        if self.speaker:
            self.emit('%s "%s"' % (self.speaker, text))
        else:
            self.emit('"%s"' % text)

    def xform(self, raw, ln):
        """NS 文本行 → Ren'Py 文本。返回 (字符串, 是否页等待)。"""
        out = []
        color_open = False
        cps_open = False
        sole_underscore = (raw.strip() == "_")
        i = 0
        n = len(raw)
        while i < n:
            ch = raw[i]
            if ch == "\\":
                break
            if ch == "@":
                out.append("{w}")
                i += 1
            elif ch == "_" and sole_underscore:
                i += 1
            elif ch == "/" and i == n - 1:
                i += 1
            elif ch == "`" and i == 0:
                i += 1
            elif ch == "!":
                m = re.match(r"!([dws])d?(\d*)", raw[i:])
                if m:
                    kind = m.group(1)
                    num = m.group(2)
                    if num:
                        val = int(num)
                        if kind in ("d", "w"):
                            out.append("{w=%.2f}" % (val / 1000.0))
                        else:
                            if cps_open:
                                out.append("{/cps}")
                            out.append("{cps=%d}" % val)
                            cps_open = True
                    i += m.end()
                else:
                    out.append("!")
                    i += 1
            elif ch == "#":
                m = re.match(r"#([0-9a-fA-F]{6})", raw[i:])
                if m:
                    if color_open:
                        out.append("{/color}")
                    out.append("{color=#%s}" % m.group(1))
                    color_open = True
                    i += m.end()
                else:
                    out.append("#")
                    i += 1
            elif ch == "%":
                m = re.match(r"%(\d+)", raw[i:])
                if m:
                    self.num_vars.add(m.group(1))
                    out.append("[n%s]" % m.group(1))
                    i += m.end()
                else:
                    out.append("%")
                    i += 1
            elif ch == "$":
                m = re.match(r"\$(\d+)", raw[i:])
                if m:
                    self.str_vars.add(m.group(1))
                    out.append("[s%s]" % m.group(1))
                    i += m.end()
                else:
                    out.append("$")
                    i += 1
            elif ch == "[":
                out.append("[[")
                i += 1
            elif ch == "]":
                out.append("]]")
                i += 1
            elif ch == "{":
                out.append("{{")
                i += 1
            elif ch == "}":
                out.append("}}")
                i += 1
            else:
                out.append(ch)
                i += 1
        if cps_open:
            out.append("{/cps}")
        if color_open:
            out.append("{/color}")
        return "".join(out), (i < n)

    # -------------------------------------------------- 命令分发
    def handle_command(self, name, rest, raw, ln):
        self.cmd_count[name] += 1
        if name == "game":
            self.flush_text()
            self.in_define = False
            return
        if name == "br":
            self.text_buf.append(("", ln))
            return
        if self.in_define:
            self.define_cmd(name, rest, raw, ln)
            return
        self.flush_text()
        args = split_args(rest) if rest else []
        self.stmt(name, args, rest, raw, ln, 1)

    def define_cmd(self, name, rest, raw, ln):
        args = split_args(rest) if rest else []
        if name == "caption":
            self.caption = self.unquote(args[0]) if args else ""
        elif name == "setwindow":
            try:
                self.cols = int(args[2])
                self.rows = int(args[3])
                self.font_size = int(args[4])
            except (IndexError, ValueError):
                pass
        elif name == "effect":
            try:
                self.effects[int(args[0])] = int(args[2]) / 1000.0
            except (IndexError, ValueError):
                pass
        elif name == "numalias":
            if len(args) >= 2:
                v = args[1].strip().lstrip("%")
                self.alias[args[0].strip()] = "n" + v
                self.num_vars.add(v)
        elif name == "stralias":
            if len(args) >= 2:
                v = args[1].strip().lstrip("$")
                self.alias[args[0].strip()] = "s" + v
                self.str_vars.add(v)
        elif name == "dim":
            if args:
                v = args[0].strip().lstrip("%?")
                try:
                    sz = int(args[1])
                except (IndexError, ValueError):
                    sz = 10
                self.arr_vars[v] = sz
        elif name == "textgosub":
            if args:
                self.textgosub = args[0].strip().lstrip("*")
                self.todos.append((ln, raw.strip(),
                                   "textgosub 是文本总钩子，必须人工改写成 Ren'Py 的 say 回调"))
        elif name in DEFINE_NOISE:
            pass
        else:
            self.todo(ln, raw, "定义区未处理指令", 0)

    # -------------------------------------------------- 单条命令
    def stmt(self, name, args, rest, raw, ln, indent=1):
        if name in ("if", "notif"):
            self.handle_if(rest, ln, raw, indent, name == "notif")
            return

        if name in ("goto", "gosub"):
            if not args:
                self.todo(ln, raw, "缺少跳转目标", indent)
                return
            t = self.label_ref(args[0])
            self.ref_labels.setdefault(t, []).append(ln)
            self.emit(("jump %s" if name == "goto" else "call %s") % t, indent)
            return

        if name == "return":
            self.emit("return", indent)
            return

        if name == "end":
            self.emit("# NS: end", indent)
            self.emit("return", indent)
            return

        if name == "reset":
            self.ref_labels.setdefault("start", []).append(ln)
            self.emit("jump start   # NS: reset", indent)
            return

        if name in ("mov", "mov3", "mov4", "mov5", "mov6",
                    "mov7", "mov8", "mov9", "mov10"):
            for k in range(0, len(args) - 1, 2):
                dst = self.pref(args[k])
                src = self.value(args[k + 1])
                if dst and src is not None:
                    self.emit("$ %s = %s" % (dst, src), indent)
                else:
                    self.todo(ln, raw, "mov 参数无法识别", indent)
            return

        if name in ("add", "sub", "mul", "div", "mod"):
            if len(args) < 2:
                self.todo(ln, raw, "运算缺参数", indent)
                return
            dst = self.pref(args[0])
            val = self.value(args[1])
            if not dst or val is None:
                self.todo(ln, raw, "运算参数无法识别", indent)
                return
            if name == "div":
                self.emit("$ %s = int(%s / %s)" % (dst, dst, val), indent)
            else:
                op = {"add": "+=", "sub": "-=", "mul": "*=", "mod": "%="}[name]
                self.emit("$ %s %s %s" % (dst, op, val), indent)
            return

        if name in ("inc", "dec"):
            dst = self.pref(args[0]) if args else None
            if not dst:
                self.todo(ln, raw, "inc/dec 参数无法识别", indent)
                return
            self.emit("$ %s %s 1" % (dst, "+=" if name == "inc" else "-="), indent)
            return

        if name == "itoa":
            dst = self.pref(args[0]) if args else None
            src = self.value(args[1]) if len(args) > 1 else None
            if not dst or src is None:
                self.todo(ln, raw, "itoa 参数无法识别", indent)
                return
            self.emit("$ %s = str(%s)" % (dst, src), indent)
            return

        if name == "atoi":
            dst = self.pref(args[0]) if args else None
            src = self.value(args[1]) if len(args) > 1 else None
            if not dst or src is None:
                self.todo(ln, raw, "atoi 参数无法识别", indent)
                return
            self.emit("$ %s = int(float(%s or 0))" % (dst, src), indent)
            return

        if name in ("rnd", "rnd2"):
            dst = self.pref(args[0]) if args else None
            mx = self.value(args[1]) if len(args) > 1 else "100"
            if not dst:
                self.todo(ln, raw, "rnd 参数无法识别", indent)
                return
            self.emit("$ %s = renpy.random.randint(0, max(0, %s - 1))" % (dst, mx), indent)
            return

        if name == "bg":
            self.do_bg(args, ln, raw, indent)
            return

        if name == "ld":
            self.do_ld(args, ln, raw, indent)
            return

        if name == "cl":
            layer = args[0].strip().lower() if args else ""
            if layer in self.layer_tag:
                old = self.layer_tag[layer]
                if old:
                    self.emit("hide %s" % old, indent)
                    self.layer_tag[layer] = None
            else:
                self.todo(ln, raw, "cl 层名无法识别", indent)
            return

        if name in ("lsp", "lsph"):
            self.do_lsp(name, args, ln, raw, indent)
            return

        if name == "csp":
            n = args[0].strip() if args else ""
            old = self.sprite_tag.pop(n, None)
            if old:
                self.emit("hide %s" % old, indent)
            return

        if name == "msp":
            n = args[0].strip() if args else ""
            tag = self.sprite_tag.get(n)
            if not tag:
                self.todo(ln, raw, "msp 找不到已显示的精灵", indent)
                return
            x = self.scaled(self.value(args[1]) if len(args) > 1 else "0")
            y = self.scaled(self.value(args[2]) if len(args) > 2 else "0")
            self.emit("show %s at Transform(xpos=%s, ypos=%s, "
                      "xanchor=0.0, yanchor=0.0)" % (tag, x, y), indent)
            return

        if name == "print":
            self.emit("# NS: print —— Ren'Py 自动合成，无需显式绘制", indent)
            return

        if name == "textclear":
            self.emit("# NS: textclear", indent)
            return

        if name in ("select", "selgosub"):
            self.do_select(name, args, ln, raw, indent)
            return

        if name == "selnum":
            self.todo(ln, raw, "selnum 需要改写成 menu + 变量赋值", indent)
            return

        if name in ("mp3", "mp3loop"):
            if args:
                path = self.asset_path(self.unquote(args[0]), self.opts.audio_dir)
                tail = " noloop" if name == "mp3" else ""
                self.emit('play music "%s"%s' % (path, tail), indent)
            return

        if name in ("wave", "waveloop"):
            if args:
                path = self.asset_path(self.unquote(args[0]), self.opts.audio_dir)
                tail = " loop" if name == "waveloop" else ""
                self.emit('play sound "%s"%s' % (path, tail), indent)
            return

        if name == "wavestop":
            self.emit("stop sound", indent)
            return

        if name == "stop":
            self.emit("stop music", indent)
            self.emit("stop sound", indent)
            return

        if name in ("wait", "delay"):
            ms = self.value(args[0]) if args else "0"
            self.emit("$ renpy.pause(%s / 1000.0)" % ms, indent)
            return

        if name in ("quake", "quakex"):
            self.emit("with hpunch", indent)
            return

        if name == "quakey":
            self.emit("with vpunch", indent)
            return

        if name in ("inputstr", "input"):
            dst = self.pref(args[0]) if args else "s0"
            self.emit('$ %s = renpy.input("")' % dst, indent)
            return

        if name == "savegame":
            if args:
                self.emit('$ renpy.save("ns-%s")' % args[0].strip(), indent)
            return

        if name == "loadgame":
            if args:
                self.emit("$ renpy.load(\"ns-%s\")   # 注意: 一般在主菜单调用"
                          % args[0].strip(), indent)
            return

        if name == "caption":
            if args:
                self.caption = self.unquote(args[0])
            return

        if name == "effect":
            try:
                self.effects[int(args[0])] = int(args[2]) / 1000.0
            except (IndexError, ValueError):
                self.todo(ln, raw, "effect 参数无法识别", indent)
            return

        if name == "setwindow":
            try:
                self.cols = int(args[2])
                self.rows = int(args[3])
                self.font_size = int(args[4])
                self.emit("# NS: setwindow %s  → Ren'Py 由 say 窗口样式控制"
                          % rest, indent)
            except (IndexError, ValueError):
                self.todo(ln, raw, "setwindow 参数无法识别", indent)
            return

        if name in DEFINE_NOISE:
            self.emit("# NS: %s %s（系统层指令，Ren'Py 自带等价功能）"
                      % (name, rest), indent)
            return

        if name in ("for", "next", "break", "skip", "jumpf", "jumpb",
                    "trap", "trap2", "lr_trap", "lr_trap2",
                    "btndef", "btn", "btnwait", "btnwait2", "spbtn",
                    "getbtntimer", "btntime", "exbtn", "exbtn_d",
                    "csel", "cselbtn", "getcselnum", "cselgoto",
                    "textbtnwait", "selectbtnwait", "texec", "getcursorpos",
                    "rmenu", "rlookback", "monocro", "nega", "vsp",
                    "amsp", "blt", "ofscpy", "repaint", "cell", "spstr",
                    "tal", "windoweffect", "erasetextwindow", "transmode",
                    "underline", "humanz", "windowback", "bgalia",
                    "texton", "textoff", "locate", "puttext", "talbar",
                    "bar", "barclear", "prnum", "prnumclear",
                    "for_next", "mesbox", "systemcall", "clickpos",
                    "avi", "mpegplay", "play", "playonce", "playstop",
                    "dwave", "dwaveloop", "dwavestop", "dwaveload",
                    "dwaveplay", "dwaveplayloop", "dsound", "getparam",
                    "defsub", "pretextgosub", "textgosub", "rubyon", "rubyoff",
                    "date", "time", "savetime", "getversion", "getreg", "getini",
                    "savefileexist", "saveon", "saveoff", "savegame2",
                    "automode", "automode_time", "effectcut", "effectblank",
                    "textspeed", "autoclick", "linepage", "clickstr",
                    "clickvoice", "click", "setcursor", "abssetcursor",
                    "mousecursor", "spwait", "resettimer", "waittimer",
                    "gettimer", "intlimit", "movl", "cmp", "fchk", "lchk",
                    "killmenu", "menu_full", "menu_window",
                    "menu_click_def", "menu_click_page", "versionstr",
                    "definereset", "game", "nsa", "arc", "nsadir", "spi",
                    "soundpressplgin", "mode800", "mode_saya", "mode_ext",
                    "savename", "savenumber", "savetime2", "kidokuskip",
                    "skipoff", "filelog", "globalon", "labellog",
                    "roff", "rmode", "defaultspeed", "defaultfont"):
            self.todo(ln, raw, "该指令在 Ren'Py 里没有 1:1 对应，需人工重写", indent)
            return

        self.todo(ln, raw, "未知指令", indent)

    # -------------------------------------------------- 图像
    def transition_for(self, eff):
        try:
            eid = int(str(eff).strip())
        except (ValueError, TypeError):
            return None
        if eid <= 1:
            return None
        tm = self.effects.get(eid, 0.4)
        return "Dissolve(%.2f)" % tm

    def do_bg(self, args, ln, raw, indent):
        if not args:
            self.todo(ln, raw, "bg 缺参数", indent)
            return
        eff = args[1] if len(args) > 1 else "1"
        first = self.unquote(args[0]).strip()
        if first.startswith("#"):
            color = first
            tag = "nsbg_solid" + re.sub(r"[^0-9A-Fa-f]", "", color)
            new_tag = tag
            self.emit('show expression Solid("%s") as %s zorder -100'
                      % (color, tag), indent)
        elif first.lower() in ("black", "white"):
            color = "#000000" if first.lower() == "black" else "#ffffff"
            tag = "nsbg_solid" + color.lstrip("#")
            new_tag = tag
            self.emit('show expression Solid("%s") as %s zorder -100'
                      % (color, tag), indent)
        else:
            new_tag = self.image_tag("bg", first)
            self.emit("show %s zorder -100" % new_tag, indent)
        if self.bg_tag and self.bg_tag != new_tag:
            # 先显示新的再隐藏旧的，避免出现空帧
            self.emit("hide %s" % self.bg_tag, indent)
        self.bg_tag = new_tag
        tr = self.transition_for(eff)
        if tr:
            self.emit("with %s" % tr, indent)

    def do_ld(self, args, ln, raw, indent):
        if len(args) < 2:
            self.todo(ln, raw, "ld 缺参数", indent)
            return
        layer = args[0].strip().lower()
        if layer not in ("l", "c", "r"):
            self.todo(ln, raw, "ld 层名无法识别", indent)
            return
        fn = self.unquote(args[1])
        eff = args[2] if len(args) > 2 else "1"
        tag = self.image_tag(layer, fn)
        pos = {"l": "ns_left", "c": "ns_center", "r": "ns_right"}[layer]
        old = self.layer_tag[layer]
        if old and old != tag:
            self.emit("hide %s" % old, indent)
        self.emit("show %s at %s" % (tag, pos), indent)
        self.layer_tag[layer] = tag
        tr = self.transition_for(eff)
        if tr:
            self.emit("with %s" % tr, indent)
        if self.opts.infer_speaker:
            nm = sanitize(os.path.basename(fn))
            self.speakers[nm] = os.path.splitext(os.path.basename(fn))[0]
            self.speaker = nm

    def do_lsp(self, name, args, ln, raw, indent):
        if len(args) < 2:
            self.todo(ln, raw, "lsp 缺参数", indent)
            return
        n = args[0].strip()
        fn = self.unquote(args[1])
        x = self.scaled(self.value(args[2]) if len(args) > 2 else "0")
        y = self.scaled(self.value(args[3]) if len(args) > 3 else "0")
        alpha = self.value(args[4]) if len(args) > 4 else None
        if alpha is not None:
            # NS 的透明度是 0-255，Ren'Py 的 alpha 是 0.0-1.0
            try:
                if float(alpha) > 1.0:
                    alpha = "%.3f" % (float(alpha) / 255.0)
            except (TypeError, ValueError):
                pass
        tag = self.image_tag("sp" + re.sub(r"[^0-9A-Za-z]", "", n), fn)
        old = self.sprite_tag.get(n)
        if old and old != tag:
            self.emit("hide %s" % old, indent)
        if alpha:
            self.emit("show %s at Transform(xpos=%s, ypos=%s, xanchor=0.0, "
                      "yanchor=0.0, alpha=%s)" % (tag, x, y, alpha), indent)
        else:
            self.emit("show %s at Transform(xpos=%s, ypos=%s, xanchor=0.0, "
                      "yanchor=0.0)" % (tag, x, y), indent)
        self.sprite_tag[n] = tag

    # -------------------------------------------------- 选择支
    def do_select(self, name, args, ln, raw, indent):
        if len(args) < 2:
            self.todo(ln, raw, "select 参数不足", indent)
            return
        self.emit("menu:", indent)
        k = 0
        while k + 1 < len(args) + 1 and k + 1 <= len(args):
            txt = self.unquote(args[k]) if k < len(args) else ""
            tgt = args[k + 1] if k + 1 < len(args) else ""
            k += 2
            if not txt:
                self.emit("# （NS 隐藏项，已跳过）", indent + 1)
                continue
            t = self.label_ref(tgt)
            self.ref_labels.setdefault(t, []).append(ln)
            self.emit('"%s":' % txt.replace('"', '\\"'), indent + 1)
            self.emit(("call %s" if name == "selgosub" else "jump %s") % t,
                      indent + 2)

    # -------------------------------------------------- if / notif
    def handle_if(self, rest, ln, raw, indent, negate):
        toks = rest.split()
        idx = None
        for i, tk in enumerate(toks):
            # fchk / lchk 是条件原语，不是 if 的子命令，跳过
            if i == 0 and tk in ("fchk", "lchk"):
                continue
            if tk in COMMANDS:
                idx = i
                break
        if idx is None:
            self.todo(ln, raw, "if 语句缺少子命令", indent)
            return
        cond_part = " ".join(toks[:idx])
        tail_name = toks[idx]
        tail_raw = " ".join(toks[idx + 1:])
        conds = []
        for piece in re.split(r"&&|&", cond_part):
            piece = piece.strip()
            if not piece:
                continue
            m = re.match(r"^fchk\s+(.+)$", piece)
            if m:
                conds.append("renpy.seen_image(%s)" % m.group(1).strip())
                continue
            m = re.match(r"^(.+?)(==|!=|<>|>=|<=|=|>|<)(.+)$", piece)
            if m:
                lhs = self.value(m.group(1).strip())
                rhs = self.value(m.group(3).strip())
                op = m.group(2)
                op = {"=": "==", "<>": "!="}.get(op, op)
                conds.append("%s %s %s" % (lhs if lhs is not None else "0",
                                           op,
                                           rhs if rhs is not None else "0"))
                continue
            m = re.match(r"^lchk\s+(.+)$", piece)
            if m:
                conds.append("renpy.seen_label(%s)"
                             % self.label_ref(m.group(1)))
                continue
        if not conds:
            self.todo(ln, raw, "if 条件无法解析", indent)
            return
        cond = " and ".join(conds)
        if negate:
            cond = "not (%s)" % cond
        self.emit("if %s:" % cond, indent)
        self.stmt(tail_name, split_args(tail_raw) if tail_raw else [],
                  tail_raw, raw, ln, indent + 1)

    # -------------------------------------------------- 收尾
    def header(self, src, enc, key):
        head = []
        head.append("# -*- coding: utf-8 -*-")
        head.append("# 由 ns2renpy.py %s 生成，请人工复核所有 TODO" % VERSION)
        head.append("# 源文件: %s" % src)
        head.append("# 编码: %s   XOR: %s" % (enc, ("0x%02X" % key) if key else "无"))
        head.append("")
        nums = sorted(self.num_vars, key=lambda x: int(x) if x.isdigit() else 0)
        for v in nums:
            head.append("default n%s = 0" % v)
        strs = sorted(self.str_vars, key=lambda x: int(x) if x.isdigit() else 0)
        for v in strs:
            head.append('default s%s = ""' % v)
        for v, sz in self.arr_vars.items():
            head.append("default a%s = [0] * %d" % (v, sz))
        for var, disp in self.speakers.items():
            head.append('define %s = Character("%s")' % (var, disp))
        head.append("")
        return head

    def unknown(self):
        return [(t, ls) for t, ls in self.ref_labels.items() if t not in self.labels]


# ---------------------------------------------------------------- 自检
TEST_SCRIPT = """
*define
caption "selftest"
effect 10,10,800
game
*start
bg "black",1
ld c,"y.png",1
こんにちは
@
二行目は%0です
\\
mov %0,1
if %0==1 goto *a
「分岐しない」
*a
lsp 0,"n.png",10,20
select "はい",*b,"いいえ",*c
*b
add %0,1
goto *e
*c
sub %0,1
*e
end
"""


def selftest():
    class O(object):
        pass

    o = O()
    o.out = "."
    o.assets = ""
    o.image_dir = "images"
    o.audio_dir = "audio"
    o.max_lines = 4
    o.infer_speaker = False
    o.keep_indent = False
    o.scale = 1.0
    c = Converter(o)
    c.run(TEST_SCRIPT)
    body = "\n".join(c.body)
    checks = [
        ("label start 生成", "label start:" in body),
        ("label a 生成", "label a:" in body),
        ("goto 转 jump", "jump a" in body),
        ("if 转 python 条件", "if n0 == 1:" in body),
        ("@ 转 {w}", "{w}" in body),
        ("%0 转插值", "[n0]" in body),
        ("lsp 绝对定位", "xpos=10, ypos=20" in body),
        ("select 转 menu", "menu:" in body),
        ("add 转增量", "$ n0 += 1" in body),
        ("bg 转 Solid/图片", ("Solid(\"#000000\")" in body) or ("ns_bg" in body)),
    ]
    ok = True
    for label, res in checks:
        print(("PASS  " if res else "FAIL  ") + label)
        if not res:
            ok = False
    if not ok:
        print("\n---- 生成的脚本 ----")
        print(body)
    return 0 if ok else 1


# ---------------------------------------------------------------- 入口
def main(argv=None):
    ap = argparse.ArgumentParser(description="NScripter → Ren'Py 转译器")
    ap.add_argument("input", nargs="?", help="nscript.dat / *.txt")
    ap.add_argument("-o", "--out", default="out", help="输出目录")
    ap.add_argument("--assets", default=None, help="资源根目录")
    ap.add_argument("--image-dir", default="images")
    ap.add_argument("--audio-dir", default="audio")
    ap.add_argument("--max-lines", type=int, default=4)
    ap.add_argument("--infer-speaker", action="store_true")
    ap.add_argument("--keep-indent", action="store_true")
    ap.add_argument("--xor-key", default=None)
    ap.add_argument("--scale", type=float, default=1.0,
                    help="坐标/字号整数倍放大，1.0=640x480")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()
    if not args.input:
        ap.print_help()
        return 2

    with open(args.input, "rb") as f:
        raw = f.read()

    key = None
    if args.xor_key:
        key = int(args.xor_key, 0)
    text, used_key, enc = decode_script(raw, key)

    conv = Converter(args)
    root = args.assets if args.assets else os.path.dirname(os.path.abspath(args.input))
    conv.scan_assets(root)
    conv.run(text)

    game_dir = os.path.join(args.out, "game")
    if not os.path.isdir(game_dir):
        os.makedirs(game_dir)

    head = conv.header(os.path.basename(args.input), enc, used_key)
    script_path = os.path.join(game_dir, "script.rpy")
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(head) + "\n")
        f.write("\n".join(conv.body) + "\n")

    img_path = os.path.join(game_dir, "ns_images.rpy")
    with open(img_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 由 ns2renpy.py 生成的图像声明\n\n")
        for tag, path in conv.images.items():
            f.write('image %s = "%s"\n' % (tag, path))

    compat_path = os.path.join(game_dir, "ns_compat.rpy")
    with open(compat_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# 由 ns2renpy.py 生成：分辨率 / 立绘锚点 / 字号\n\n")
        sw = int(round(640 * conv.opts.scale))
        sh = int(round(480 * conv.opts.scale))
        f.write("define config.screen_width = %d\n" % sw)
        f.write("define config.screen_height = %d\n" % sh)
        if conv.caption:
            f.write('define config.name = "%s"\n' % conv.caption.replace('"', '\\"'))
        f.write("\n")
        f.write("transform ns_left:\n    xalign 0.0\n    yalign 1.0\n\n")
        f.write("transform ns_center:\n    xalign 0.5\n    yalign 1.0\n\n")
        f.write("transform ns_right:\n    xalign 1.0\n    yalign 1.0\n\n")
        f.write("style say_dialogue:\n    size %d\n"
                % int(round((conv.font_size or 22) * conv.opts.scale)))

    rep_path = os.path.join(args.out, "report.txt")
    with open(rep_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("ns2renpy %s 转换报告\n" % VERSION)
        f.write("=" * 46 + "\n")
        f.write("源文件 : %s\n" % args.input)
        f.write("编码   : %s   XOR: %s\n" % (enc, ("0x%02X" % used_key) if used_key else "无"))
        f.write("标签数 : %d\n" % len(conv.labels))
        f.write("图片   : %d 个\n" % len(conv.images))
        f.write("TODO   : %d 处\n" % len(conv.todos))
        f.write("窗口   : %s 列 x %s 行, 字号 %s\n"
                % (conv.cols, conv.rows, conv.font_size))
        f.write("\n-- 指令统计(前 25) --\n")
        for name, cnt in conv.cmd_count.most_common(25):
            f.write("  %-16s %d\n" % (name, cnt))
        unk = conv.unknown()
        if unk:
            f.write("\n-- 未定义的跳转目标 --\n")
            for t, ls in unk:
                f.write("  %s  (行 %s)\n" % (t, ",".join(str(x) for x in ls[:8])))
        if conv.todos:
            f.write("\n-- TODO 明细 --\n")
            for ln, raw_txt, why in conv.todos:
                f.write("  [行 %d] %s\n           %s\n" % (ln, raw_txt, why))

    print("已生成:")
    print("  " + script_path)
    print("  " + img_path)
    print("  " + compat_path)
    print("  " + rep_path)
    print("TODO %d 处, 未定义跳转 %d 个" % (len(conv.todos), len(conv.unknown())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
