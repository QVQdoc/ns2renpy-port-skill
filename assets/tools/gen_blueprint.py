"""从 structure.json 生成 ns-port 蓝图的 JSON 部分（sources/graph/mergepoints/modules 计划）。

规则（本脚本自己定的启发式，需在 issues.json 中登记为 needs_verification）：
- 节点 = 每个 `*label`；节点范围 = 从该 label 行到下一个 label 行之前。
- 节点内出现无条件 `goto *X` => jump 边；否则顺次落到下一个 label => fallthrough 边。
- 节点内出现 `csel "文本",*A,"文本",*B` => 每个选项一条 choice 边。
"""
import json
import re
import sys
from collections import OrderedDict

struct_path, out_dir, src_path = sys.argv[1], sys.argv[2], sys.argv[3]
src_id = "src_0"

# 引擎/系统层 label：不是剧情节点，不进模块
SYSTEM_LABELS = {
    "define", "dstop", "setalias", "firstsetting", "execconfig", "exec_vol", "exec_win",
    "done_win", "logo", "lps", "lps_2", "logo_skip", "logo_end", "windowsetting",
    "pretext_lb", "customsel", "cselst", "cselloop", "csel_cfg", "cselend", "text_lb",
    "text_btndef", "tbloop", "text_cfg", "text_end", "wclose", "windowerase", "config",
    "cbtnreload", "cfg_loop", "cfg_reset", "cfg_title", "cfg_exit", "cfg_end", "cfg_end_lb",
    "backlog", "backlog_st", "log_drawpage", "log_drawpage_lp", "log_drawpage_sub",
    "log_drawpage_sub_end", "log_btnlp", "log_voice", "log_btnup", "log_btndown", "log_end",
    "savegame", "loadgame", "saveload", "saveload_pagestart", "svbtnloop", "sv_exec",
    "sv_exec_save", "sv_exec_save_lb", "sv_exec_load", "sv_prev", "sv_next", "sv_end",
    "svbtnload", "svbtnload_sub", "bg", "black2", "black", "ev", "chr", "bgchr", "se",
    "music", "start", "title", "title_restart", "title_btndef", "titleloop", "t_1", "t_2",
    "t_3", "t_4", "t_5", "happyend", "badend", "sloop", "loop", "loopfade", "sloopfade",
    "musicmode", "musloop", "mus_p", "mus_play", "mus_stop", "mus_end", "cgm_end", "cgm_prev",
    "cgm_next", "cgm_getname", "cgm_exec", "cgm_exec_end", "cgmode", "cgmode_pagestart",
    "cgmode_btnloop", "cgmode_loadpage", "cgmlp1", "cgmlp2", "cgmlp3", "mem_end", "mem_prev",
    "mem_next", "mem_getname", "mem_exec", "memmode", "mem_pagestart", "mem_btnloop",
    "mem_loadpage", "memlp1", "memlp2", "memlp3", "bun", "dld", "dcl",
}
d = json.load(open(struct_path, encoding="utf-8"))
labels = d["labels"]
total = d["total_lines"]

spans = []
for i, lb in enumerate(labels):
    start = lb["line"]
    end = labels[i + 1]["line"] - 1 if i + 1 < len(labels) else total
    spans.append({"name": lb["name"], "start": start, "end": end})
span_by_name = {s["name"]: s for s in spans}

# ---- 读取源脚本行，抽取每个节点的边与选择项 ----
lines = open(src_path, "rb").read().decode("cp936").split("\r\n")

GOTO_RE = re.compile(r"^\s*goto\s+\*(\w+)")
CSEL_RE = re.compile(r'csel\s+"([^"]*)"\s*,\*(\w+)')
nodes, edges = [], []
edge_no = 0
for idx, s in enumerate(spans):
    nxt = spans[idx + 1]["name"] if idx + 1 < len(spans) else None
    body = lines[s["start"] - 1:s["end"]]
    gotos, csels, returns = [], [], 0
    for off, ln in enumerate(body):
        t = ln.strip()
        m = GOTO_RE.match(t)
        if m:
            gotos.append((off, m.group(1)))
        for cm in CSEL_RE.finditer(t):
            csels.append((off, cm.group(1), cm.group(2)))
        if t.startswith("return"):
            returns += 1
    has_fallthrough = bool(nxt) and returns == 0 and not gotos
    text_lines = sum(1 for ln in body if ln.strip() and not ln.strip().startswith(("*", ";"))
                     and not re.match(r"^[A-Za-z_]\w*\b", ln.strip()))
    nodes.append(OrderedDict([
        ("id", s["name"]),
        ("module", None),  # 阶段2 分配
        ("kind", "system" if s["name"] in SYSTEM_LABELS else "story"),
        ("source", {"file": src_id, "lines": [s["start"], s["end"]]}),
        ("text_lines", text_lines),
    ]))
    if has_fallthrough:
        edge_no += 1
        edges.append(OrderedDict([
            ("id", "e%03d" % edge_no), ("from", s["name"]), ("to", nxt),
            ("kind", "fallthrough"), ("text", None),
            ("condition", None), ("display_condition", None), ("effects", []),
        ]))
    for (off, target) in gotos:
        edge_no += 1
        edges.append(OrderedDict([
            ("id", "e%03d" % edge_no), ("from", s["name"]), ("to", target),
            ("kind", "jump"), ("text", None),
            ("condition", None), ("display_condition", None), ("effects", []),
        ]))
    for (off, label_text, target) in csels:
        edge_no += 1
        edges.append(OrderedDict([
            ("id", "e%03d" % edge_no), ("from", s["name"]), ("to", target),
            ("kind", "choice"), ("text", label_text),
            ("condition", OrderedDict([("raw_ns", None), ("normalized", None),
                                       ("variables_used", []), ("certainty", "fully_resolved")])),
            ("display_condition", None), ("effects", []),
            ("source_line", s["start"] + off),
        ]))

json.dump(OrderedDict([("version", "2"), ("nodes", nodes), ("edges", edges)]),
          open(out_dir + "/graph.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- sources.json ----
sources = OrderedDict([
    ("version", "2"),
    ("encoding", "utf-8"),
    ("files", [OrderedDict([
        ("id", src_id),
        ("path", "source/0.txt"),
        ("encoding", "cp936"),
        ("encoding_note", "原始档案为 GBK（cp936），非 SKILL 默认假设的 cp932；见 issues.json ISSUE-001"),
        ("total_lines", total),
        ("read_ranges", [[1, 1530], [1529, 1690]]),
        ("parsed_ranges", [[1, 1690]]),
        ("unparsed_ranges", [[1531, 5468]]),
        ("unread_ranges", [[1691, 30056]]),
        ("dynamic_behaviors", []),
    ])]),
])
json.dump(sources, open(out_dir + "/sources.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- 模块计划（阶段2）----
CHAPTERS = [("p1", 1529), ("p2", 2655), ("p3", 5469), ("p4", 7974), ("p5", 9966),
            ("p6", 11302), ("p7", 14101), ("p8", 16764), ("p9", 17435), ("p10", 19181),
            ("p11", 21192), ("p12", 22851)]
print("nodes=%d edges=%d" % (len(nodes), len(edges)))
print("story nodes=%d system nodes=%d" % (sum(1 for n in nodes if n["kind"] == "story"),
                                         sum(1 for n in nodes if n["kind"] == "system")))
for s in spans:
    print("%-18s %6d-%6d  %5d 行" % (s["name"], s["start"], s["end"], s["end"] - s["start"] + 1))
