# -*- coding: utf-8 -*-
"""把 NScripter 剧本里的**剧情标签**整体翻译成 Ren'Py（只调 ns_stage 演出层）。

和 nsassets.py / convert_assets.py 的分工：
  nsassets.py       普查素材，产出 assets_manifest.json（哪个文件、什么 spec、要不要拆蒙版）
  convert_assets.py 按 manifest 转图/转音、生成 port_images.rpy / port_wrappers.rpy
  ns2renpy_story.py 把 0.txt 的剧情行翻成 story/*.rpy（本脚本）

翻译原则（和 references/conventions.md 一致）：
  * 只调演出层 `ns_*`（背景/CG/立绘/黑幕/音频），绝不直接 show/scene —— 否则会踩
    「scene 清立绘」「tag 不同导致两张图叠着」这些坑
  * 每条转换语句前面写 `# src:0.txt:<行号>`，便于回查
  * 翻不了的一律记进覆盖报告，不静默丢

用法：
    python ns2renpy_story.py <游戏目录> <port 目录> --project <工程目录> [--out story]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nsassets import decode_script, split_spec  # noqa: E402
from convert_assets import safe_name  # noqa: E402


# ---------------------------------------------------------------- 结构常量 --
LABEL_RE = re.compile(r"^\*([A-Za-z_]\w*)\s*$")
SAY_RE = re.compile(r"^\[(?P<who>[^\]/]+?)(?:/(?P<vid>[^\]]+))?\](?P<text>.*)$")
IF_RE = re.compile(r"^if\s+(?P<cond>.+?)\s+(?P<cmd>[A-Za-z_]\w*)\s*(?P<rest>.*)$")

# 剧情区出现的指令（其余按文本处理）。顺序不影响匹配，这里只作白名单。
KNOWN_CMDS = set("""
bg _bg ev chr bgchr black black2 music se loop sloop dstop wclose bun if goto gosub
return csel delay wait lsp lsph csp print mpegplay mov add sub inc dec itoa reset
quake texton textoff caption dwave dwaveloop dwavestop chvol saveon saveoff
""".split())

# 源脚本说话人 → port_characters.rpy 里的 Character
SPEAKERS = {
    "塞莉卡": "serika",
    "芹香": "serika_kao",
    "麻由良": "mayura",
    "零": "rei",
    "野田": "noda",
    "芹香？麻由良": "mix",
}

# 源变量名 → port_variables.rpy 里的变量名
VAR_MAP = {
    "kaisoumode": "kaisou_mode",
}

# 图脚本目录 → manifest 里的 dir
DEFAULT_DIRS = {
    "bg": "bg",
    "_bg": "bg",
    "ev": "ev",
    "chr": "chr",
    "bgchr": "bg",
}

# 这些标签虽然在 graph 里是 story，但属于标题/开场流程，Ren'Py 侧由
# port_title.rpy / port_flow.rpy 承担，不生成。
SKIP_LABELS = {"mem34"}

# 原作把 `goto *badend` / `goto *happyend` 当结局走，graph 却把它们归到 system
# （它们在剧情区之前）。这两个要跟着剧情一起生成，否则 jump 到不存在的标签。
EXTRA_LABELS = ["badend", "happyend"]


# ------------------------------------------------------------------ 小工具 --
def py_str(text: str) -> str:
    """Ren'Py 字符串字面量：转义引号/反斜杠，并把 `[` `{` 转成字面量。"""
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    out = out.replace("[", "[[").replace("{", "{{")
    return '"%s"' % out


def unquote(arg: str) -> str:
    a = arg.strip()
    if len(a) >= 2 and a[0] == '"' and a[-1] == '"':
        a = a[1:-1]
    elif a.startswith('"'):
        a = a[1:]
    return a


def split_args(rest: str) -> list:
    """按逗号切参数（引号内的逗号不切）。"""
    args, cur, in_q = [], "", False
    for ch in rest:
        if ch == '"':
            in_q = not in_q
            cur += ch
        elif ch == "," and not in_q:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip() or args:
        args.append(cur.strip())
    return [a for a in args if a != ""]


def asset_ref(arg: str, default_dir: str) -> tuple:
    """`":a/2,0,3;chr\\m01_a.bmp"` → ("chr", "m01_a")。spec 丢掉（已烘进 PNG）。"""
    raw = unquote(arg)
    spec, path = split_spec(raw) if raw.startswith(":") else ("", raw)
    p = path.replace("\\", "/").strip()
    if "/" in p:
        d, n = p.split("/", 1)
    else:
        d, n = default_dir, p
    n = os.path.splitext(n)[0]
    if not n:
        # `chr ""` / `loop ""` 这类空参数不是文件名：`*chr` 体里 `if $w0=""` 走的是
        # `cl c`（清空槽位），`*loop` 体里走的是淡出停止。不能交给 safe_name ——
        # 它给空串的兜底是 "x"，会变成去找 `chr\x.bmp`、`voice\x.ogg`。
        return (d or default_dir), ""
    return (d or default_dir), safe_name(n)


def cond_to_py(cond: str) -> str:
    """`%kaisoumode=1` → `store.kaisou_mode == 1`。"""
    c = cond.strip()

    def _var(m):
        name = m.group(1)
        return "store." + VAR_MAP.get(name, name)

    c = re.sub(r"%([A-Za-z_]\w*)", _var, c)
    c = c.replace("&&", " and ")
    c = re.sub(r"(?<![=!<>])=(?!=)", "==", c)
    c = re.sub(r"(?<!&)&(?!&)", " and ", c)
    c = c.replace("||", " or ")
    c = c.replace("|", " or ")
    c = re.sub(r"\bmod\b", "%", c)
    return c


def num(arg: str, default=0):
    a = unquote(arg).strip()
    try:
        return int(a)
    except ValueError:
        return default


# ------------------------------------------------------------ 翻译核心状态 --
class Ctx:
    def __init__(self):
        self.lines = []          # 输出行（不含缩进，稍后统一缩进）
        self.rec = {
            "say": 0, "narration": 0, "cmd": 0, "note": 0,
            "unmapped": [], "notes": [], "dead": [], "missing_voice": [],
            "voice": 0, "menu": 0, "npcs": [],
        }
        self.npc_name = None
        self.terminal = False     # 已生成 jump/return/menu/reset
        self.skip_rest = None     # csel 之后的死行


def emit(ctx: Ctx, indent: int, code: str):
    ctx.lines.append("    " * indent + code)


def emit_src(ctx: Ctx, indent: int, script: str, lineno: int):
    ctx.lines.append("    " * indent + "# src:%s:%d" % (script, lineno))


# ---------------------------------------------------------------- 语句翻译 --
def tr_say(ctx, indent, who, vid, text, script, lineno):
    name = SPEAKERS.get(who)
    body = text.strip()
    emit_src(ctx, indent, script, lineno)
    if vid and vid in ctx.voices:
        emit(ctx, indent, 'voice "%s"' % vid)
        ctx.rec["voice"] += 1
    elif vid:
        ctx.rec["missing_voice"].append({"line": lineno, "vid": vid, "who": who})
    if name:
        emit(ctx, indent, '%s %s' % (name, py_str(body)))
    else:
        if ctx.npc_name != who:
            emit(ctx, indent, '$ npc_name = %s' % py_str(who))
            ctx.npc_name = who
            ctx.rec["npcs"].append(who)
        emit(ctx, indent, "npc %s" % py_str(body))
    ctx.rec["say"] += 1


def tr_cmd(ctx, indent, cmd, rest, script, lineno):
    """翻译一条指令。返回是否已产出终端语句。"""
    args = split_args(rest)

    if cmd in ("bg", "_bg"):
        if not args:
            ctx.rec["unmapped"].append({"line": lineno, "cmd": cmd, "why": "无参数"})
            return
        quoted = args[0].strip().startswith('"')
        raw = unquote(args[0])
        if not quoted:
            # `_bg white` / `_bg white,10,800` / `_bg #FFFF88,1` —— NS 允许整屏纯色。
            # 注意只有**不带引号**的才算颜色：`bg "street_c"` 是图名，不是颜色。
            emit_src(ctx, indent, script, lineno)
            emit(ctx, indent, "$ ns_color(%s)" % py_str(raw))
            ctx.rec["cmd"] += 1
            return
        d, n = asset_ref(args[0], "bg")
        if not n:
            emit_src(ctx, indent, script, lineno)
            emit(ctx, indent, "# bg 空参数：原作会去找 `bg\\.bmp`（不存在），等于不换背景")
            ctx.rec["note"] += 1
            ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": "空参数"})
            return
        emit_src(ctx, indent, script, lineno)
        if d == "ev":
            emit(ctx, indent, "$ ns_w_ev(%s)" % py_str(n))
        else:
            emit(ctx, indent, "$ ns_w_bg(%s)" % py_str(n))
        ctx.rec["cmd"] += 1
        return

    if cmd in ("ev", "chr"):
        d, n = asset_ref(args[0] if args else '""', "ev" if cmd == "ev" else "chr")
        if not n and cmd == "ev":
            emit_src(ctx, indent, script, lineno)
            emit(ctx, indent, "# ev 空参数：原作会去找 `ev\\.bmp`（不存在），等于不换 CG")
            ctx.rec["note"] += 1
            ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": "空参数"})
            return
        # chr 的空参数是有意义的：`*chr` 体里 `if $w0=""` → `cl c` 清空中央槽位，
        # 必须原样传给 ns_w_chr("")，由包装层决定是「收立绘」还是「换立绘」。
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_w_%s(%s)" % (cmd, py_str(n)))
        ctx.rec["cmd"] += 1
        return

    if cmd == "bgchr":
        b = asset_ref(args[0] if args else '""', "bg")[1]
        c = asset_ref(args[1] if len(args) > 1 else '""', "chr")[1]
        if not b or not c:
            emit_src(ctx, indent, script, lineno)
            emit(ctx, indent, "# bgchr 有空参数：原作会去找不存在的文件，等于什么都不做")
            ctx.rec["note"] += 1
            ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": "空参数"})
            return
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_w_bgchr(%s, %s)" % (py_str(b), py_str(c)))
        ctx.rec["cmd"] += 1
        return

    if cmd == "music":
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_w_music(%d)" % num(args[0] if args else "0"))
        ctx.rec["cmd"] += 1
        return

    if cmd in ("se", "loop", "sloop"):
        n = asset_ref(args[0] if args else '""', "se")[1] if args else ""
        if not n and cmd == "se":
            emit_src(ctx, indent, script, lineno)
            emit(ctx, indent, "# se 空参数：原作会去找 `se\\.ogg`（不存在），等于不发声")
            ctx.rec["note"] += 1
            ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": "空参数"})
            return
        # loop/sloop 的空参数也有意义：`*loop` 体里 `if $w0="" goto *loopfade` → 淡出停止。
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_w_%s(%s)" % (cmd, py_str(n)))
        ctx.rec["cmd"] += 1
        return

    if cmd in ("black", "black2", "dstop", "wclose", "bun"):
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_w_%s()" % cmd)
        ctx.rec["cmd"] += 1
        return

    if cmd in ("delay", "wait"):
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "pause %.3f" % (num(args[0] if args else "0") / 1000.0))
        ctx.rec["cmd"] += 1
        return

    if cmd in ("lsp", "lsph"):
        layer = num(args[0]) if args else 0
        d, n = asset_ref(args[1] if len(args) > 1 else '""', "monster")
        if not n:
            emit_src(ctx, indent, script, lineno)
            emit(ctx, indent, "# lsp 空参数：原作会去找不存在的图，等于什么都不显示")
            ctx.rec["note"] += 1
            ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": "空参数"})
            return
        x = num(args[2]) if len(args) > 2 else 0
        y = num(args[3]) if len(args) > 3 else 0
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, '$ ns_sprite(%d, %s, %d, %d, dur=0.4, group=%s)'
             % (layer, py_str(n), x, y, py_str(d)))
        ctx.rec["cmd"] += 1
        return

    if cmd == "csp":
        layer = num(args[0]) if args else -1
        if layer in (166, -1):
            emit_src(ctx, indent, script, lineno)
            emit(ctx, indent, "# csp %d：文本窗口/全清，Ren'Py 由 UI 层承担" % layer)
            ctx.rec["note"] += 1
            ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": "文本窗口 (csp %d)" % layer})
            return
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_sprite_hide(%d)" % layer)
        ctx.rec["cmd"] += 1
        return

    if cmd == "print":
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "# print %s：等点击/淡入时长，Ren'Py 由对话与 ns_sprite 的 dur 承担"
             % " ".join(args))
        ctx.rec["note"] += 1
        ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": "print %s" % " ".join(args)})
        return

    if cmd == "mpegplay":
        n = asset_ref(args[0] if args else '""', "movie")[1]
        loops = num(args[1]) if len(args) > 1 else 0
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_movie(%s, loops=%d)" % (py_str(n), loops))
        ctx.rec["cmd"] += 1
        return

    if cmd in ("dwave", "dwaveloop"):
        ch = cond_to_py(args[0]) if args else "None"
        n = asset_ref(args[1] if len(args) > 1 else '""', "se")[1]
        emit_src(ctx, indent, script, lineno)
        if cmd == "dwave":
            emit(ctx, indent, "$ ns_se(%s, ch=%s)" % (py_str(n), ch))
        else:
            emit(ctx, indent, "$ ns_se_loop(%s, ch=%s)" % (py_str(n), ch))
        ctx.rec["cmd"] += 1
        return

    if cmd == "dwavestop":
        ch = cond_to_py(args[0]) if args else "None"
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ ns_se_stop(%s)" % ch)
        ctx.rec["cmd"] += 1
        return

    if cmd == "goto":
        target = unquote(args[0] if args else "").lstrip("*")
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "jump %s" % target)
        ctx.terminal = True
        ctx.rec["cmd"] += 1
        return

    if cmd == "gosub":
        target = unquote(args[0] if args else "").lstrip("*")
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "call %s" % target)
        ctx.rec["cmd"] += 1
        return

    if cmd == "return":
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "return")
        ctx.terminal = True
        ctx.rec["cmd"] += 1
        return

    if cmd == "reset":
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "$ renpy.full_restart()")
        ctx.terminal = True
        ctx.rec["cmd"] += 1
        return

    if cmd == "csel":
        # csel "文案",*目标,"文案2",*目标2 → menu: 两个选项
        pairs = []
        i = 0
        while i + 1 < len(args):
            pairs.append((unquote(args[i]), unquote(args[i + 1]).lstrip("*")))
            i += 2
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "menu:")
        for text, target in pairs:
            emit(ctx, indent + 1, "%s:" % py_str(text))
            emit(ctx, indent + 2, "jump %s" % target)
        ctx.terminal = True
        ctx.skip_rest = "csel 之后的 `●` 行是原作者的选项去向注释，原作也不会执行"
        ctx.rec["menu"] += 1
        ctx.rec["cmd"] += 1
        return

    if cmd in ("texton", "textoff", "caption", "quake", "saveon", "saveoff", "chvol"):
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "# %s %s：窗口/存档/音量由配置与 UI 层承担" % (cmd, rest.strip()))
        ctx.rec["note"] += 1
        ctx.rec["notes"].append({"line": lineno, "cmd": cmd, "why": rest.strip()[:40]})
        return

    ctx.rec["unmapped"].append({"line": lineno, "cmd": cmd, "why": rest.strip()[:60]})


def tr_line(ctx, indent, line, script, lineno):
    """翻译一行源脚本（可能含多条 `:` 分隔语句）。"""
    stmts = [s.strip() for s in _split(line) if s.strip()]
    if not stmts:
        return
    head = stmts[0]
    m = IF_RE.match(head)
    if m:
        cond = cond_to_py(m.group("cond"))
        inner = [(m.group("cmd"), m.group("rest"))]
        inner += [_split_cmd(s) for s in stmts[1:]]
        emit_src(ctx, indent, script, lineno)
        emit(ctx, indent, "if %s:" % cond)
        saved_term = ctx.terminal
        ctx.terminal = False
        before = len(ctx.lines)
        for cmd, rest in inner:
            tr_cmd(ctx, indent + 1, cmd, rest, script, lineno)
        if len(ctx.lines) == before + 1:      # 条件体什么都没生成
            emit(ctx, indent + 1, "pass")
        ctx.terminal = saved_term
        return

    for stmt in stmts:
        cmd, rest = _split_cmd(stmt)
        tr_cmd(ctx, indent, cmd, rest, script, lineno)
        if ctx.terminal:
            return


def _split(line):
    from nsassets import _split_statements
    return _split_statements(line)


def _split_cmd(stmt):
    parts = stmt.split(None, 1)
    if not parts:
        return "", ""
    return parts[0], (parts[1] if len(parts) > 1 else "")


def is_cmd(line: str) -> bool:
    head = line.split(None, 1)[0] if line.strip() else ""
    return head in KNOWN_CMDS


# ---------------------------------------------------------------- 标签处理 --
def translate_label(ctx, script, lines, name, start, end, fallthrough):
    """把 [start, end) 这一段（0 基索引）翻成一个 label。"""
    out_start = len(ctx.lines)
    ctx.lines.append("label %s:" % name)
    ctx.npc_name = None
    ctx.terminal = False
    ctx.skip_rest = None

    n = 0
    last_n = start + 1
    for idx in range(start, end):
        lineno = idx + 1
        last_n = lineno
        raw = lines[idx]
        stripped = raw.strip()
        if not stripped:
            n += 1
            continue
        if stripped.startswith("*"):
            continue                        # 段内标签（不该有）
        if stripped.startswith(";//") or stripped.startswith(";"):
            n += 1
            continue                        # 注释
        if ctx.terminal and not ctx.skip_rest:
            # jump/return 之后还有非空行 —— 原作里同样执行不到（例：0.txt:23867
            # `goto *happyend` 后面紧跟一行「第一章预告」），记进死行，不生成。
            ctx.skip_rest = "跳转/返回之后的行，原作同样不可达"
        if ctx.skip_rest:
            ctx.rec["dead"].append({"line": lineno, "text": stripped[:80]})
            n += 1
            continue
        st = SAY_RE.match(stripped)
        if st:
            tr_say(ctx, 1, st.group("who").strip(), (st.group("vid") or "").strip(),
                   st.group("text"), script, lineno)
            n += 1
            continue
        if is_cmd(stripped):
            tr_line(ctx, 1, stripped, script, lineno)
            n += 1
            continue
        # 其余都是旁白
        emit_src(ctx, 1, script, lineno)
        emit(ctx, 1, py_str(stripped))
        ctx.rec["narration"] += 1
        n += 1

    if not ctx.terminal:
        emit_src(ctx, 1, script, last_n)
        if fallthrough:
            emit(ctx, 1, "# 原作用 fallthrough 继续到 %s" % fallthrough)
            emit(ctx, 1, "jump %s" % fallthrough)
        else:
            emit(ctx, 1, "return")
    if len(ctx.lines) == out_start + 1:
        emit(ctx, 1, "return")
    return n


# --------------------------------------------------------------------- main --
def main(argv=None):
    ap = argparse.ArgumentParser(description="把 NScripter 剧情标签整体翻译成 Ren'Py")
    ap.add_argument("game_root")
    ap.add_argument("port_dir")
    ap.add_argument("--project", required=True, help="Ren'Py 工程目录（含 game/）")
    ap.add_argument("--script", default="0.txt")
    ap.add_argument("--graph", default="graph.json")
    ap.add_argument("--out", default="story", help="输出目录（相对 game/）")
    ap.add_argument("--coverage", default="story_coverage.json")
    ap.add_argument("--report", default="story_convert_report.md")
    ap.add_argument("--only", default="", help="只翻这些标签（逗号分隔，调试用）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    game_dir = os.path.join(args.project, "game")
    lines, enc = decode_script(os.path.join(args.game_root, args.script))
    graph = json.load(open(os.path.join(args.port_dir, args.graph), encoding="utf-8"))

    nodes = {}
    for n in graph["nodes"]:
        nodes[n["id"]] = n
    fall = {e["from"]: e["to"] for e in graph["edges"] if e["kind"] == "fallthrough"}

    story = []
    for n in graph["nodes"]:
        if n["kind"] != "story" or n["id"] in SKIP_LABELS:
            continue
        story.append((n["source"]["lines"][0], n["id"]))
    for extra in EXTRA_LABELS:
        n = nodes.get(extra)
        if n:
            story.append((n["source"]["lines"][0], extra))
    story.sort()

    if args.only:
        want = set(x.strip() for x in args.only.split(",") if x.strip())
        story = [(ln, nm) for ln, nm in story if nm in want]

    # 语音清单：只有工程里真有的才写 voice 语句
    voice_set = set()
    vdir = os.path.join(game_dir, "audio", "voice")
    if os.path.isdir(vdir):
        for fn in os.listdir(vdir):
            if fn.lower().endswith((".ogg", ".wav", ".mp3")):
                voice_set.add(os.path.splitext(fn)[0])

    ctx = Ctx()
    ctx.voices = voice_set
    per_label = {}
    files = []

    total_src = 0
    for start, name in story:
        node = nodes.get(name)
        if not node:
            continue
        s, e = node["source"]["lines"]      # graph 的 lines 是**闭区间**，e 是最后一行
        begin, finish = s, e                # 0 基索引 s..e-1 ←→ 行号 s+1..e
        start_idx = len(ctx.lines)
        translated = translate_label(
            ctx, args.script, lines, name, begin, finish, fall.get(name))
        per_label[name] = translated
        total_src += translated
        files.append((name, ctx.lines[start_idx:]))
        del ctx.lines[start_idx:]

    header = [
        "# 由 ns2renpy_story.py 从 %s 自动生成，**不要手改**。" % args.script,
        "# 重新生成：python ns2renpy_story.py <游戏目录> <port 目录> --project <工程目录>",
        "# 演出全部经由 ns_stage.rpy（背景/立绘/CG/黑幕/音频），不要在这里写 scene/show。",
        "",
    ]

    out_dir = os.path.join(game_dir, args.out)
    written = []
    if not args.dry_run:
        os.makedirs(out_dir, exist_ok=True)
        for i, (fname, body) in enumerate(files, 1):
            path = os.path.join(out_dir, "gen_%02d_%s.rpy" % (i, fname))
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(header) + "\n".join(body) + "\n")
            written.append(os.path.relpath(path, game_dir))

    cov = {
        "script": args.script,
        "encoding": enc,
        "labels": len(per_label),
        "label_lines": per_label,
        "files": written,
        "totals": {
            "say": ctx.rec["say"], "narration": ctx.rec["narration"],
            "voice": ctx.rec["voice"], "cmd": ctx.rec["cmd"],
            "note": ctx.rec["note"], "menu": ctx.rec["menu"],
            "unmapped": len(ctx.rec["unmapped"]),
            "dead_after_csel": len(ctx.rec["dead"]),
            "missing_voice": len(ctx.rec["missing_voice"]),
        },
        "unmapped": ctx.rec["unmapped"],
        "notes": ctx.rec["notes"],
        "dead_after_csel": ctx.rec["dead"],
        "missing_voice": ctx.rec["missing_voice"][:200],
        "npcs": sorted(set(ctx.rec["npcs"])),
    }
    if not args.dry_run:
        with open(os.path.join(args.port_dir, args.coverage), "w",
                  encoding="utf-8", newline="\n") as f:
            json.dump(cov, f, ensure_ascii=False, indent=1)
        write_report(cov, per_label, os.path.join(args.port_dir, args.report))

    print("标签 %d 个、源行 %d 行" % (len(per_label), total_src))
    print("say %d / 旁白 %d / 语音 %d / 指令 %d / 菜单 %d / 备注 %d / 未翻译 %d / csel 死行 %d"
          % (cov["totals"]["say"], cov["totals"]["narration"], cov["totals"]["voice"],
             cov["totals"]["cmd"], cov["totals"]["menu"], cov["totals"]["note"],
             cov["totals"]["unmapped"], cov["totals"]["dead_after_csel"]))
    print("缺语音 %d 条（前 5：%s）" % (len(ctx.rec["missing_voice"]),
                                   ", ".join(m["vid"] for m in ctx.rec["missing_voice"][:5])))
    print("输出文件 %d 个%s" % (len(written), ("：" + "、".join(written)) if written else "（dry-run）"))
    return 0


def write_report(cov, per_label, path):
    t = cov["totals"]
    out = []
    out.append("# 剧情翻译覆盖报告\n")
    out.append("源脚本 `%s`（编码 %s）：%d 个剧情标签 → %d 个 .rpy\n"
               % (cov["script"], cov["encoding"], cov["labels"], len(cov["files"])))
    out.append("| 项 | 数量 |\n|---|---|\n")
    rows = [("角色台词", t["say"]), ("旁白", t["narration"]),
            ("带语音台词的语音语句", t["voice"]), ("演出指令（转到 ns_*）", t["cmd"]),
            ("菜单（csel）", t["menu"]), ("备注跳过", t["note"]),
            ("未翻译指令", t["unmapped"]), ("csel 之后的死行", t["dead_after_csel"]),
            ("缺语音文件", t["missing_voice"])]
    for k, v in rows:
        out.append("| %s | %d |\n" % (k, v))
    out.append("\n## 每个标签\n\n| 标签 | 源行数 |\n|---|---|\n")
    for name, n in per_label.items():
        out.append("| `%s` | %d |\n" % (name, n))
    if cov["unmapped"]:
        out.append("\n## 未翻译指令（必须人工看）\n\n| 行 | 指令 | 内容 |\n|---|---|---|\n")
        for u in cov["unmapped"][:200]:
            out.append("| %d | `%s` | %s |\n" % (u["line"], u["cmd"], u["why"]))
    if cov["notes"]:
        out.append("\n## 备注跳过（Ren'Py 侧由别的层承担）\n\n")
        seen = {}
        for n in cov["notes"]:
            seen[n["cmd"]] = seen.get(n["cmd"], 0) + 1
        for k, v in sorted(seen.items()):
            out.append("- `%s` × %d\n" % (k, v))
    if cov["missing_voice"]:
        out.append("\n## 缺语音（工程 audio/voice 里没有）\n\n")
        out.append("- 共 %d 条，前 30：%s\n"
                   % (t["missing_voice"],
                      ", ".join(m["vid"] for m in cov["missing_voice"][:30])))
    if cov["npcs"]:
        out.append("\n## 走 npc 通用角色的说话人\n\n")
        out.append("- %s\n" % "、".join(cov["npcs"]))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))


if __name__ == "__main__":
    sys.exit(main())
