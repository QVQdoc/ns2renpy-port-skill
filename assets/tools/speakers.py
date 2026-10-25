"""统计台词说话人（[名字/语音ID] 与 [名字] 两种写法）与语音号段。"""
import collections
import json
import re
import sys

src, out = sys.argv[1], sys.argv[2]
lines = open(src, "rb").read().decode("cp936").split("\r\n")

SPK = re.compile(r"^\[([^\]/]+)(?:/([0-9]+))?\]")
names = collections.Counter()
voiced = collections.Counter()
narr = 0
voices = {}
for ln in lines:
    s = ln.strip()
    if not s or s.startswith(("*", ";")):
        continue
    m = SPK.match(s)
    if m:
        name = m.group(1)
        names[name] += 1
        if m.group(2):
            voiced[name] += 1
            voices.setdefault(name, []).append(int(m.group(2)))
    else:
        narr += 1

report = {"narration_lines": narr, "speakers": []}
for name, cnt in names.most_common():
    v = voices.get(name)
    report["speakers"].append({
        "name": name,
        "lines": cnt,
        "voiced_lines": voiced.get(name, 0),
        "voice_id_min": min(v) if v else None,
        "voice_id_max": max(v) if v else None,
    })

json.dump(report, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("叙事行 %d，说话人 %d 种" % (narr, len(names)))
for s in report["speakers"]:
    print("  %-14s 台词 %5d  带语音 %5d  id %s..%s" % (
        s["name"], s["lines"], s["voiced_lines"], s["voice_id_min"], s["voice_id_max"]))
