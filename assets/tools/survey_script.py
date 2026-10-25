# -*- coding: utf-8 -*-
r"""剧本结构普查：标签、跳转关系、命令直方图、文本行统计。

用法：
    python tools\survey_script.py <0.txt> [--json out.json]

只做统计，不改任何文件。用于决定全量移植的模块切分与翻译覆盖面。
"""
import argparse
import collections
import json
import os
import re
import sys

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL = os.path.dirname(os.path.dirname(_HERE))   # assets/tools -> 仓库根
sys.path.insert(0, os.path.join(_SKILL, "scripts"))


from nsassets import decode_script  # noqa: E402

LABEL_RE = re.compile(r"^\*([A-Za-z_][\w]*)")
CMD_RE = re.compile(r"^([a-zA-Z_][\w]*)\b")
SAY_RE = re.compile(r'^(?P<who>[^\s"\\]+)(?:\s+(?P<face>[^\s"]+))?\s+"(?P<text>.*)"\s*$')


def classify(line):
    s = line.strip()
    if not s:
        return "blank", None
    if s.startswith("*"):
        m = LABEL_RE.match(s)
        return ("label", m.group(1)) if m else ("label_odd", s)
    if s.startswith("//"):
        return "comment", None
    if s.startswith(";"):
        return "comment_semi", None
    m = SAY_RE.match(s)
    if m:
        return "say", m.group("who")
    m = CMD_RE.match(s)
    if m:
        return "cmd", m.group(1)
    return "other", s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    lines, enc = decode_script(args.script)
    print("编码: %s" % enc)

    labels = []
    cmds = collections.Counter()
    say_who = collections.Counter()
    other = collections.Counter()
    say_count = 0
    kinds = collections.Counter()

    for i, line in enumerate(lines, 1):
        kind, val = classify(line)
        kinds[kind] += 1
        if kind == "label":
            labels.append({"name": val, "line": i})
        elif kind == "label_odd":
            labels.append({"name": None, "line": i, "raw": val})
        elif kind == "say":
            say_count += 1
            say_who[val] += 1
        elif kind == "cmd":
            cmds[val] += 1
        elif kind in ("other", "label_odd"):
            other[str(val)[:60]] += 1

    # 跳转目标统计
    jumps = collections.Counter()
    for line in lines:
        s = line.strip()
        for pat in (r"goto\s+\*?([A-Za-z_]\w*)", r"jump\s+\*?([A-Za-z_]\w*)", r"jumpf\s+\*?([A-Za-z_]\w*)"):
            m = re.match(r"^(?:if\s+.*?\s+)?" + pat, s)
            if m:
                jumps[m.group(1)] += 1

    print("行数 %d，标签 %d，台词行 %d" % (len(lines), len(labels), say_count))
    print("\n## 命令直方图（前 40）")
    for cmd, n in cmds.most_common(40):
        print("  %-14s %5d" % (cmd, n))
    print("\n## 说话人（前 15）")
    for who, n in say_who.most_common(15):
        print("  %-14s %5d" % (who, n))
    print("\n## 其他行（前 15）")
    for raw, n in other.most_common(15):
        print("  %5d  %s" % (n, raw))
    print("\n## 标签数 %d，跳转目标 %d 个" % (len(labels), len(jumps)))
    print("  重复标签:", [k for k, v in collections.Counter(l["name"] for l in labels if l["name"]).items() if v > 1][:10])
    undefined = [k for k in jumps if k not in {l["name"] for l in labels}]
    print("  跳转目标未定义:", undefined[:10], "共", len(undefined))
    print("\n## 前 20 个标签")
    for l in labels[:20]:
        print("  %5d  *%s" % (l["line"], l["name"]))

    if args.json:
        data = {
            "script": os.path.abspath(args.script),
            "lines": len(lines),
            "say_lines": say_count,
            "labels": labels,
            "commands": dict(cmds),
            "speakers": dict(say_who),
            "jumps": dict(jumps),
            "kinds": dict(kinds),
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("\n写出", args.json)


if __name__ == "__main__":
    main()
