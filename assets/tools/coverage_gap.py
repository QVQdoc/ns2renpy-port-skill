"""对比本作实际使用的 NScripter 命令 与 ns-port 映射表覆盖情况。

用法: python coverage_gap.py <structure.json> <ns_to_renpy_map.md>
"""
import json
import re
import sys

struct, mapfile = sys.argv[1], sys.argv[2]
d = json.load(open(struct, encoding="utf-8"))
cmds = d["commands"]
text = open(mapfile, encoding="utf-8").read()

covered = {m.group(1).lower() for m in re.finditer(r"^\|\s*`?([A-Za-z_0-9]+)", text, re.M)}
defsubs = {"bgchr", "se", "ev", "chr", "music", "black", "black2", "loop", "sloop",
           "dld", "dcl", "bun", "dstop", "wclose", "_bg"}

std = [k for k in cmds if k not in defsubs]
missing = [(k, cmds[k]) for k in std if k.lower() not in covered]
hit = [(k, cmds[k]) for k in std if k.lower() in covered]

print("映射表里列出的命令: %d 个" % len(covered))
print("本作实际使用(不含 defsub 包装): %d 种" % len(std))
print("其中映射表覆盖: %d 种" % len(hit))
print("未覆盖: %d 种" % len(missing))
print()
print("未覆盖命令（按出现次数）:")
for k, v in sorted(missing, key=lambda kv: -kv[1]):
    print("  %-14s %5d" % (k, v))
print()
print("已覆盖命令（按出现次数）:")
for k, v in sorted(hit, key=lambda kv: -kv[1]):
    print("  %-14s %5d" % (k, v))
