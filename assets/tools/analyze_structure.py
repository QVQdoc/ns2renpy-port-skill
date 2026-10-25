"""扫描 NScripter 脚本，输出结构摘要 JSON。

用法: python analyze_structure.py <0.txt> <out.json>
编码固定按 cp936 读取（本作实测为 GBK，见 tools/probe_encoding.py 结果）。
行号为 1-based，与编辑器一致。
"""
import json
import re
import sys
import collections

path, out = sys.argv[1], sys.argv[2]
raw = open(path, "rb").read().decode("cp936")
lines = raw.split("\r\n")
if lines and lines[-1] == "":
    lines.pop()

LABEL_RE = re.compile(r"^\*(\S+)\s*$")
# 命令 = 行首 token（命令与参数间用空格分隔）
CMD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\b")

# 会产生控制流的命令
BRANCH_GOTO = ("goto", "gosub", "cselgoto", "cselgosub", "jump", "jumpf", "jumpb")

ASSET_CMDS = {
    "bg": "background",
    "ld": "sprite",
    "cl": "clear",
    "bgchr": "bgchr_defsub",
    "lsp": "sprite_lsp",
    "csp": "sprite_csp",
    "bmp": "image",
    "play": "music",
    "bgm": "music",
    "se": "sound",
    "voice": "voice",
    "mp3": "music",
    "wave": "sound",
    "setwindow": "window_graphic",
    "effect": "effect",
}

stats = collections.Counter()
labels = []          # 定义
label_index = {}     # name -> 行号
edges_static = collections.Counter()
edges_dynamic = []   # (line, text)
text_lines_per_label = collections.Counter()
assets = collections.defaultdict(set)
current_label = None
menus = []
pending_menu = None
vars_written = collections.Counter()
suspicious = []      # 需要人工判读的行

for no, line in enumerate(lines, start=1):
    s = line.strip()
    if not s:
        stats["blank"] += 1
        if pending_menu is not None:
            pending_menu["end"] = no
            menus.append(pending_menu)
            pending_menu = None
        continue
    if s.startswith(";"):
        stats["comment"] += 1
        continue
    m = LABEL_RE.match(s)
    if m:
        name = m.group(1)
        labels.append({"name": name, "line": no})
        label_index[name] = no
        current_label = name
        stats["label"] += 1
        if pending_menu is not None:
            pending_menu["end"] = no
            menus.append(pending_menu)
            pending_menu = None
        continue
    m = CMD_RE.match(s)
    cmd = m.group(1) if m else None
    if cmd is None:
        # 不是命令也不是标签 => 台词/文本行（NS 里以 \ 或任意文本开头）
        stats["text"] += 1
        if current_label:
            text_lines_per_label[current_label] += 1
        continue
    stats["cmd"] += 1
    stats["cmd:" + cmd] += 1
    lowered = cmd.lower()

    if lowered in ASSET_CMDS:
        am = re.search(r'"([^"]+)"', s)
        if am:
            assets[ASSET_CMDS[lowered]].add(am.group(1))

    if lowered in BRANCH_GOTO or (lowered == "if" and re.search(r"\b(goto|gosub)\b", s)):
        for tm in re.finditer(r"(?:goto|gosub|jump|jumpf|jumpb)\s+\*?(\S+)", s):
            tgt = tm.group(1).rstrip(":")
            if re.match(r"^[\w\u3040-\u9fff]+$", tgt):
                edges_static[(current_label, tgt)] += 1
            else:
                edges_dynamic.append({"line": no, "label": current_label, "text": s[:120]})

    if lowered in ("menu", "select", "csel"):
        pending_menu = {"line": no, "label": current_label, "text": s[:120], "end": None}

    if lowered in ("mov", "add", "sub", "inc", "dec", "mul", "div", "mod", "movstr"):
        vm = re.match(r"^\w+\s+%?(\w+)", s)
        if vm:
            vars_written[vm.group(1)] += 1

    if lowered in ("getparam", "systemcall", "exec_dll", "textgosub", "pretextgosub",
                   "ruby", "html", "getscreenshot", "exbtn", "exbtn_d", "textbtnwait",
                   "btnwait", "caption", "erasetextwindow", "tag", "transmode", "clickstr"):
        stats["special:" + lowered] += 1

if pending_menu is not None:
    pending_menu["end"] = len(lines)
    menus.append(pending_menu)

# 悬空目标（指向不存在的标签）
dangling = sorted({t for (_, t) in edges_static if t not in label_index})

cmd_counts = {k[4:]: v for k, v in stats.items() if k.startswith("cmd:")}
special = {k[8:]: v for k, v in stats.items() if k.startswith("special:")}

result = {
    "file": path,
    "encoding_read_as": "cp936",
    "total_lines": len(lines),
    "bytes": len(open(path, "rb").read()),
    "stats": {k: v for k, v in stats.items() if not k.startswith(("cmd:", "special:"))},
    "commands": dict(sorted(cmd_counts.items(), key=lambda kv: -kv[1])),
    "special": dict(sorted(special.items(), key=lambda kv: -kv[1])),
    "label_count": len(labels),
    "labels": labels,
    "text_lines_total": stats["text"],
    "text_lines_per_label": dict(sorted(text_lines_per_label.items(), key=lambda kv: -kv[1])[:80]),
    "edges_static_count": sum(edges_static.values()),
    "edges_static": [{"from": a, "to": b, "count": c} for (a, b), c in sorted(edges_static.items(), key=lambda kv: -kv[1])],
    "edges_dynamic": edges_dynamic,
    "dangling_targets": dangling,
    "menus": menus,
    "assets": {k: sorted(v) for k, v in assets.items()},
    "asset_counts": {k: len(v) for k, v in assets.items()},
    "vars_written_top": dict(vars_written.most_common(40)),
}
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("lines=%d labels=%d text=%d static_edges=%d dynamic=%d dangling=%d menus=%d" % (
    len(lines), len(labels), stats["text"], sum(edges_static.values()),
    len(edges_dynamic), len(dangling), len(menus)))
print("commands:", dict(sorted(cmd_counts.items(), key=lambda kv: -kv[1])[:25]))
print("assets:", result["asset_counts"])
print("dangling:", dangling[:20])
