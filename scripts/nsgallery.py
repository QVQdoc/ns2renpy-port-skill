#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从 NScripter 脚本里抽出「回想模式 / CG 模式」的图鉴数据。

NScripter 的图鉴页是纯硬编码：每个格子一行

    if fchk "ev\\01.bmp" lsp 1,":c/2,0,3;sum\\01.bmp",65,56
    if lchk "*mem35"     lsp 14,":c/2,0,3;sum\\34a1.bmp",235,446
    lsp 7,":c;sum\\empty.bmp",405,186

`fchk` = 这张 CG 解锁过、`lchk` = 这个标签看过、裸 lsp = 空格子。格子坐标和
缩略图文件名都在这一行里，所以这里不猜任何东西，全部照抄。

产出 ``port/gallery.json``，给 ``assets/ns_gallery.rpy`` 直接读。

用法：

    python nsgallery.py <游戏目录> --port <port 目录> [--script 0.txt]
                        [--out gallery.json] [--report gallery_report.md]
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nsassets  # noqa: E402


# 一页的图鉴行：if fchk/lchk "..." lsp N,"spec;path",x,y   /   lsp N,"spec;path",x,y
LINE_RE = re.compile(
    r'^(?:if\s+(?P<cond>fchk|lchk)\s+"(?P<condarg>[^"]*)"\s+)?'
    r'lsp\s+(?P<slot>\d+)\s*,\s*"(?P<spec>[^"]*)"\s*,\s*(?P<x>\d+)\s*,\s*(?P<y>\d+)'
)

# *cgm_getname 的一条：if %w4= 3 mov $w0,"04a/04b/04c/04d":return
CGNAME_RE = re.compile(r'if\s+%w4\s*=\s*(?P<idx>\d+)\s+mov\s+\$w0\s*,\s*"(?P<names>[^"]*)"')


def safe_name(name):
    """与 convert_assets.py 保持同一套命名（`01` → `n01`，统一小写）。"""
    s = re.sub(r"[^0-9A-Za-z_]", "_", name.lower())
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return "x"
    if not re.match(r"[A-Za-z_]", s):
        s = "n" + s
    return s


def split_asset(spec, params):
    """`:c/2,0,3;sum\\01.bmp` → ("sum", "01", {"cols": 2})"""
    body = spec
    if body.startswith(":"):
        end = body.find(";")
        if end >= 0:
            body = body[end + 1:]
    body = body.replace("\\", "/")
    parts = body.split("/")
    base = parts[-1]
    base = re.sub(r"\.[A-Za-z0-9]+$", "", base)
    group = parts[-2] if len(parts) >= 2 else ""
    cells = None
    if params:
        try:
            cells = int(params[0].lstrip("/"))
        except (ValueError, IndexError):
            cells = None
    return group, base, cells


def parse_spec(spec):
    """拆出 `/N,dx,dy` 这一段的参数列表。"""
    if not spec.startswith(":"):
        return []
    end = spec.find(";")
    head = spec[:end] if end >= 0 else spec
    head = head[1:]
    if "/" not in head:
        return []
    return head.split("/", 1)[1].split(",")


def find_labels(lines):
    """返回 {标签名: (起始行下标, 结束行下标)}，给 loadpage 段落定位。"""
    labels = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("*") and " " not in s and ":" not in s:
            labels.append((s[1:], i))
    spans = {}
    for k, (name, start) in enumerate(labels):
        end = labels[k + 1][1] if k + 1 < len(labels) else len(lines)
        spans[name] = (start, end)
    return spans


def parse_page(lines, spans, prefix):
    """解析 `*<prefix>lp1..` 这些页，返回 [{slot, x, y, thumb, kind, arg}] 列表的列表。"""
    pages = []
    page_no = 1
    while True:
        name = "%slp%d" % (prefix, page_no)
        if name not in spans:
            break
        start, end = spans[name]
        rows = []
        for line in lines[start + 1:end]:
            m = LINE_RE.match(line.strip())
            if not m:
                continue
            cond, condarg = m.group("cond"), m.group("condarg")
            params = parse_spec(m.group("spec"))
            group, base, cells = split_asset(m.group("spec"), params)
            thumb = safe_name(base)
            if cells and cells > 1:
                thumb += "_c0"       # 双格蒙版对：前半是图
            rows.append({
                "slot": int(m.group("slot")),
                "x": int(m.group("x")),
                "y": int(m.group("y")),
                "group": safe_name(group) if group else "",
                "thumb": thumb,
                "kind": "fchk" if cond == "fchk" else ("lchk" if cond == "lchk" else "empty"),
                "arg": (condarg or "").replace("\\", "/"),
            })
        pages.append(rows)
        page_no += 1
    return pages


def parse_cg_names(lines, spans):
    """`*cgm_getname`：槽号 → 可用 CG 文件名列表（多张的可以左右翻）。"""
    out = {}
    if "cgm_getname" not in spans:
        return out
    start, end = spans["cgm_getname"]
    for line in lines[start:end]:
        m = CGNAME_RE.search(line)
        if not m:
            continue
        idx = int(m.group("idx"))
        names = [n.strip() for n in m.group("names").split("/") if n.strip()]
        out[idx] = [safe_name(n) for n in names]
    return out


def main():
    ap = argparse.ArgumentParser(description="抽 NScripter 图鉴（回想/CG）数据")
    ap.add_argument("game_root")
    ap.add_argument("--port", default=os.path.join("port"))
    ap.add_argument("--script", default="0.txt")
    ap.add_argument("--out", default="gallery.json")
    ap.add_argument("--report", default="gallery_report.md")
    args = ap.parse_args()

    script_path = os.path.join(args.game_root, args.script)
    if not os.path.exists(script_path):
        sys.exit("找不到脚本：%s" % script_path)

    lines, enc = nsassets.decode_script(script_path)
    spans = find_labels(lines)

    data = {
        "script": os.path.basename(script_path),
        "encoding": enc,
        "cg": {"per_page": 16, "pages": parse_page(lines, spans, "cgm")},
        "mem": {"per_page": 16, "pages": parse_page(lines, spans, "mem")},
        "cg_names": parse_cg_names(lines, spans),
    }

    out_path = os.path.join(args.port, args.out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)

    # 报告
    n_cg = sum(len(p) for p in data["cg"]["pages"])
    n_mem = sum(len(p) for p in data["mem"]["pages"])
    locked_cg = sum(1 for p in data["cg"]["pages"] for r in p if r["kind"] == "empty")
    locked_mem = sum(1 for p in data["mem"]["pages"] for r in p if r["kind"] == "empty")
    print("脚本 %s（%s，%d 行）" % (os.path.basename(script_path), enc, len(lines)))
    print("CG  模式：%d 页 / %d 格（空格子 %d）" % (len(data["cg"]["pages"]), n_cg, locked_cg))
    print("回想模式：%d 页 / %d 格（空格子 %d）" % (len(data["mem"]["pages"]), n_mem, locked_mem))
    print("多图 CG：%d 组" % len(data["cg_names"]))
    print("写出 %s" % out_path)

    rep_path = os.path.join(args.port, args.report)
    with open(rep_path, "w", encoding="utf-8") as f:
        f.write("# 图鉴数据抽取报告\n\n")
        f.write("源脚本：`%s`（%s，%d 行）\n\n" % (os.path.basename(script_path), enc, len(lines)))
        f.write("## CG 模式\n\n")
        for i, page in enumerate(data["cg"]["pages"], 1):
            f.write("\n### 第 %d 页（%d 格）\n\n" % (i, len(page)))
            f.write("| 格 | 坐标 | 缩略图 | 解锁条件 |\n|---|---|---|---|\n")
            for r in page:
                cond = "已看 CG：`%s`" % r["arg"] if r["kind"] == "fchk" else (
                    "已看标签：`%s`" % r["arg"] if r["kind"] == "lchk" else "空格子（永远不可点）")
                f.write("| %d | %d,%d | `%s %s` | %s |\n" % (r["slot"], r["x"], r["y"], r["group"], r["thumb"], cond))
        f.write("\n## 回想模式\n\n")
        for i, page in enumerate(data["mem"]["pages"], 1):
            f.write("\n### 第 %d 页（%d 格）\n\n" % (i, len(page)))
            f.write("| 格 | 坐标 | 缩略图 | 解锁条件 |\n|---|---|---|---|\n")
            for r in page:
                cond = ("已看标签：`%s`" % r["arg"]) if r["kind"] == "lchk" else (
                    "已看 CG：`%s`" % r["arg"] if r["kind"] == "fchk" else "空格子（永远不可点）")
                f.write("| %d | %d,%d | `%s %s` | %s |\n" % (r["slot"], r["x"], r["y"], r["group"], r["thumb"], cond))
        f.write("\n## 多图 CG\n\n| 槽位 | 文件名 |\n|---|---|\n")
        for idx in sorted(data["cg_names"]):
            f.write("| %d | %s |\n" % (idx, ", ".join("`%s`" % n for n in data["cg_names"][idx])))
    print("写出 %s" % rep_path)


if __name__ == "__main__":
    main()
