#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把「每作手写舞台函数」时代的调用点迁到通用舞台层。

背景：旧流程让每个移植工程自己手写一份 port_stage.rpy（port_bg / port_bgchr /
port_chr / port_ev / port_black / port_music / port_se / port_hide_all），
于是同一套语义在不同工程里长得不一样，立绘蒙版、分层关系全靠 AI 复述。
现在这些语义由 ns_stage.rpy（运行时）和 port_wrappers.rpy（原作 defsub 包装）
统一提供，剧情模块只需要调 ns_*。

本脚本只做「命名迁移」，不改参数、不改语义：
    port_bg(x)      -> ns_bg(x)         （有 *bg 包装层时 -> ns_w_bg(x)）
    port_bgchr(b,s) -> ns_bgchr(b,s)
    port_chr(s)     -> ns_chr(s)         （空参 = 清空中央槽位）
    port_ev(x)      -> ns_ev(x)
    port_black()    -> ns_black()
    port_music(n)   -> ns_bgm(n)
    port_se(x)      -> ns_se(x)
    port_hide_all() -> ns_hide_all()

用法：
    python nsstage_migrate.py <game 目录> [--apply] [--json 报告]
不给 --apply 时只打印将发生的改动（dry-run）。

判定规则（不猜）：
* 目标名是否改成 ns_w_<name>，取决于 port_wrappers.rpy 里是否真的生成了
  ns_w_<name>；没有就退回 ns_* 运行时函数。
* 只改「函数调用」位置（名字后紧跟 "("），不碰注释里的说明文字。
"""
from __future__ import print_function

import argparse
import glob
import io
import json
import os
import re
import sys

# 旧手写 API -> 通用运行时 API（包装层存在时前缀改成 ns_w_）
LEGACY = {
    "port_bg": "bg",
    "port_bgchr": "bgchr",
    "port_chr": "chr",
    "port_ev": "ev",
    "port_black": "black",
    "port_music": "music",
    "port_se": "se",
    "port_hide_all": "hide_all",
}

# 这些名字是工程自己的桥接层，不能动
KEEP = {"port_apply_volume", "port_se_stop", "port_apply_window", "port_music_screen"}


def read(path):
    with io.open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def wrapper_names(game_dir):
    """读 port_wrappers.rpy，取实际生成的 ns_w_* 名字。"""
    path = os.path.join(game_dir, "port_wrappers.rpy")
    if not os.path.exists(path):
        return set()
    return set(re.findall(r"^\s*def (ns_w_[A-Za-z_]\w*)\s*\(", read(path), re.M))


def convert_text(text, have_wrappers):
    hits = []

    def target(ns_name):
        if ns_name != "hide_all" and ("ns_w_" + ns_name) in have_wrappers:
            return "ns_w_" + ns_name
        return "ns_" + ns_name

    def repl(m):
        name = m.group(1)
        if name in KEEP:
            return m.group(0)
        ns_name = LEGACY.get(name)
        if not ns_name:
            return m.group(0)
        new = target(ns_name)
        hits.append((name, new))
        return new + "("

    out = re.sub(r"\b(port_[a-z_]+)\s*\(", repl, text)
    return out, hits


def main():
    ap = argparse.ArgumentParser(description="旧 per-game 舞台 API -> 通用 ns_* 舞台层")
    ap.add_argument("game_dir", help="Ren'Py 工程里的 game 目录")
    ap.add_argument("--apply", action="store_true", help="真的写回（默认 dry-run）")
    ap.add_argument("--json", dest="json_out", default=None, help="把改动清单写成 JSON")
    args = ap.parse_args()

    game_dir = os.path.abspath(args.game_dir)
    wrappers = wrapper_names(game_dir)
    files = sorted(glob.glob(os.path.join(game_dir, "story", "*.rpy")) +
                   [os.path.join(game_dir, "script.rpy")])
    totals = {}
    changed = []
    for path in files:
        if not os.path.exists(path):
            continue
        text = read(path)
        new, hits = convert_text(text, wrappers)
        if not hits:
            continue
        for old, dst in hits:
            totals["%s -> %s" % (old, dst)] = totals.get("%s -> %s" % (old, dst), 0) + 1
        rel = os.path.relpath(path, game_dir)
        changed.append({"file": rel, "calls": len(hits),
                        "sample": ["%s -> %s" % (a, b) for a, b in hits[:5]]})
        if args.apply and new != text:
            write(path, new)

    print("包装层 def 数: %d（%s）" % (len(wrappers), ", ".join(sorted(wrappers)[:6]) +
                                     ("..." if len(wrappers) > 6 else "")))
    if not totals:
        print("没有发现旧舞台 API 调用。")
    else:
        for k in sorted(totals):
            print("  %-28s %d 处" % (k, totals[k]))
        print("%s %d 个文件。" % ("已改写" if args.apply else "将改写（dry-run）", len(changed)))
    if args.json_out:
        with io.open(args.json_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"totals": totals, "files": changed}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
