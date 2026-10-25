"""校验 port/ 下所有蓝图 JSON 是否可解析，并做最小 schema 检查。

用法: python validate_blueprint.py <port 目录>

为什么需要这个脚本：SKILL.md 要求蓝图用 JSON 落地，但 ns-port 自带的
nsport_lint.py 完全不看蓝图，写坏一个引号（比如 description 里出现裸双引号）
不会有任何提示，后续阶段读到的就是坏数据。本次实测就踩到了 issues.json 第 41 行。
"""
import io
import json
import os
import sys

port = sys.argv[1]
REQUIRED = {
    "sources.json": ["version", "files"],
    "graph.json": ["nodes", "edges"],
    "catalog.json": ["assets", "characters", "variables", "features"],
    "issues.json": ["issues"],
    "mergepoints.json": ["mergepoints"],
}

bad = 0
for name, keys in sorted(REQUIRED.items()):
    path = os.path.join(port, name)
    if not os.path.exists(path):
        print("[缺失] %s" % name)
        bad += 1
        continue
    raw = io.open(path, encoding="utf-8-sig").read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        line = raw.split("\n")[exc.lineno - 1] if exc.lineno else ""
        print("[坏 JSON] %s: 第 %d 行第 %d 列 %s" % (name, exc.lineno, exc.colno, exc.msg))
        print("          %s" % line.strip()[:120])
        bad += 1
        continue
    missing = [k for k in keys if k not in data]
    if missing:
        print("[缺字段] %s: %s" % (name, ", ".join(missing)))
        bad += 1
    else:
        counts = ", ".join("%s=%d" % (k, len(data[k])) if isinstance(data[k], list) else "%s=ok" % k for k in keys)
        print("[OK] %-16s %s" % (name, counts))

# 每个模块目录都要有 brief.md / events.json / source.txt / result.md
mod_root = os.path.join(port, "modules")
if os.path.isdir(mod_root):
    for mod in sorted(os.listdir(mod_root)):
        d = os.path.join(mod_root, mod)
        if not os.path.isdir(d):
            continue
        lack = [f for f in ("brief.md", "events.json", "source.txt", "result.md") if not os.path.exists(os.path.join(d, f))]
        status = "完整" if not lack else "缺 " + ",".join(lack)
        print("[模块] %-12s %s" % (mod, status))

print()
print("结论：%s" % ("蓝图结构完整、JSON 全部可解析" if bad == 0 else "发现 %d 处问题" % bad))
sys.exit(1 if bad else 0)
