"""从源脚本行区间生成模块 events.json（ns-port 模板格式）。

用法: python gen_events.py <source/0.txt> <start> <end> <module_id> <out.json>
事件类型映射见 references/blueprint-templates.md 的 events.json 一节。
"""
import json
import re
import sys
from collections import OrderedDict

src, start, end, module, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4], sys.argv[5]
lines = open(src, "rb").read().decode("cp936").split("\r\n")

SPK = re.compile(r"^\[([^\]/]+)(?:/([A-Za-z0-9]+))?\](.*)$")
QUOTE = re.compile(r"^「(.*)」$")
NAME_MAP = {"塞莉卡": "serika", "芹香": "serika_kao", "麻由良": "mayura", "零": "rei", "野田": "noda"}


def asset_id(path):
    return path.replace("/", "_").replace("\\", "_").rsplit(".", 1)[0]


events = []
n = 0


def ev(kind, **kw):
    global n
    n += 1
    item = OrderedDict([("id", "ev_%03d" % n), ("type", kind)])
    item.update(kw)
    events.append(item)


for no in range(start, end + 1):
    raw = lines[no - 1]
    s = raw.strip()
    if not s or s.startswith(";"):
        continue
    src_ref = {"file": "src_0", "lines": [no, no]}

    m = re.match(r'^bgchr\s+"([^"]*)","([^"]*)"', s)
    if m:
        ev("background", asset=asset_id(m.group(1)), transition="dissolve", source=src_ref, wait_for=None)
        ev("show_character", asset=asset_id(m.group(2)), position="center", transition="dissolve",
           source=src_ref, wait_for=None)
        continue
    m = re.match(r'^bg\s+"([^"]*)"', s)
    if m:
        ev("background", asset=asset_id(m.group(1)), transition="dissolve", source=src_ref, wait_for=None)
        continue
    if s == "black":
        ev("hide_all", transition="fade_out", source=src_ref, wait_for=None)
        continue
    m = re.match(r'^chr\s+"([^"]*)"', s)
    if m:
        if m.group(1) == "":
            ev("hide_character", asset=None, source=src_ref, wait_for=None)
        else:
            ev("show_character", asset=m.group(1), position="center", transition="dissolve",
               source=src_ref, wait_for=None)
        continue
    m = re.match(r'^ev\s+"([^"]*)"', s)
    if m:
        ev("background", asset="ev_" + m.group(1), transition="dissolve", source=src_ref, wait_for=None)
        continue
    m = re.match(r"^music\s+(\d+)", s)
    if m:
        num = int(m.group(1))
        ev("music", asset=(None if num == 0 else "bgm%02d" % num), loop=True, source=src_ref, wait_for=None)
        continue
    m = re.match(r'^se\s+"([^"]*)"', s)
    if m:
        ev("sound", asset=m.group(1), wait_for=None, source=src_ref)
        continue
    m = re.match(r'^loop\s+"([^"]*)"', s)
    if m:
        ev("voice_loop", asset=m.group(1), channel="loop", source=src_ref, wait_for=None)
        continue

    m = SPK.match(s)
    if m:
        name, vid, rest = m.group(1), m.group(2), m.group(3)
        q = QUOTE.match(rest)
        text = q.group(1) if q else rest
        ev("dialogue", speaker=NAME_MAP.get(name, name), speaker_raw=name, text=text,
           voice=(vid if vid else None), source=src_ref, wait_for="click")
        continue

    ev("narration", text=s, source=src_ref, wait_for="click")

doc = OrderedDict([
    ("module", module),
    ("contract_version", "1.0"),
    ("source_range", [start, end]),
    ("nodes", [{"id": module, "label": module, "events": events}]),
])
json.dump(doc, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
kinds = {}
for e in events:
    kinds[e["type"]] = kinds.get(e["type"], 0) + 1
print("module=%s events=%d kinds=%s" % (module, len(events), kinds))
