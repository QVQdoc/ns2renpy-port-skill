# -*- coding: utf-8 -*-
"""判断「背景/黑幕/CG 切换」在原作里是否会自动清立绘：
统计 bg/ev/black 前后立绘状态的变化模式。"""
import io, json, re, sys
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL = os.path.dirname(os.path.dirname(_HERE))   # assets/tools -> 仓库根
sys.path.insert(0, os.path.join(_SKILL, "scripts"))

import nsassets

SCRIPT = sys.argv[1] if len(sys.argv) > 1 else "0.txt"
lines, enc = nsassets.decode_script(SCRIPT)
graph = json.loads(io.open(r"port\graph.json", encoding="utf-8").read())
nodes = graph["nodes"]
items = nodes.items() if isinstance(nodes, dict) else [(n["id"], n) for n in nodes]
ranges = sorted([(nid, int(n["source"]["lines"][0]), int(n["source"]["lines"][1]))
                 for nid, n in items if n.get("source", {}).get("lines") and int(n["source"]["lines"][0]) >= 1529],
                key=lambda x: x[1])

stmt = []   # (行号, 命令, 参数)
for nid, s, e in ranges:
    for ln in range(s, e + 1):
        for st in nsassets._split_statements(lines[ln - 1]):
            t = st.strip()
            if not t or t.startswith(";") or t.startswith("*") or t.startswith("["):
                continue
            m = re.match(r"^([A-Za-z_]+)\s*(.*)$", t)
            if m:
                stmt.append((ln, m.group(1), m.group(2).strip()))

def is_bg_cmd(c):
    return c in ("bg", "ev", "black", "black2", "bgchr", "mpegplay")

show = None
events = []
for i, (ln, cmd, arg) in enumerate(stmt):
    if cmd == "chr":
        empty = arg in ('""', "") or arg.startswith('""')
        show = None if empty else arg.strip('"')
        continue
    if cmd == "bgchr":
        # bgchr 自带立绘参数
        continue
    if not is_bg_cmd(cmd):
        continue
    had = show is not None
    # 看后面 8 条语句里有没有 chr 调用（非空=重新出现，空=清）
    after = []
    for j in range(i + 1, min(i + 9, len(stmt))):
        if stmt[j][1] == "chr":
            after.append(("empty" if stmt[j][2] in ('""', "") else "show", stmt[j][0]))
    events.append((ln, cmd, had, show, after))

had_n = [e for e in events if e[2]]
print("bg/ev/black 总数:", len(events), " 其中切换时立绘在场的:", len(had_n))
no_chr = [e for e in had_n if not e[4]]
print("  立绘在场且之后 8 条内没有任何 chr 调用:", len(no_chr))
empty_after = [e for e in had_n if any(a[0] == "empty" for a in e[4])]
print("  立绘在场且之后 8 条内有 chr \"\"（显式清）:", len(empty_after))
re_show = [e for e in had_n if any(a[0] == "show" for a in e[4])]
print("  立绘在场且之后 8 条内重新 chr 显示:", len(re_show))
print("\n样例（立绘在场、之后无 chr）:")
for e in no_chr[:8]:
    print("  line %d %s  char=%s after=%s" % (e[0], e[1], e[3], e[4]))
print("\n样例（立绘在场、随后重新 chr）:")
for e in re_show[:8]:
    print("  line %d %s  char=%s after=%s" % (e[0], e[1], e[3], e[4]))
