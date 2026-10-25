#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify.py — 对 ns2renpy 生成的 .rpy 做静态门禁检查（移植流程的 G2 闸门）。

用法:
    python verify.py out/game [--assets 游戏资源目录] [--strict]

检查项:
    E1  重复 label
    E2  jump / call 目标未定义
    E3  引号未闭合（say / menu 文本行）
    E4  menu: 后没有缩进项
    W1  文本内 { } 或 [ ] 不平衡（Ren'Py 文本标签/插值）
    W2  缩进不是 4 的倍数
    W3  引用的图片/音频在资源目录里找不到
    W4  单行 say 里出现未转义的引号（>2 个）
    I   TODO 数量（信息项，用于确认修复进度）

退出码: 0 通过；1 存在 ERROR（--strict 下 WARNING 也算失败）。
"""

import argparse
import os
import re
import sys

SAY_RE = re.compile(r'^\"|^[A-Za-z_][\w]*\s+\"')
ASSET_RE = re.compile(r'"([^"\n]+\.(?:png|jpg|jpeg|bmp|webp|ogg|mp3|wav|opus|mid|avi))"',
                      re.IGNORECASE)
LABEL_RE = re.compile(r'^label\s+([A-Za-z_][\w]*)\s*:')
JUMP_RE = re.compile(r'^(jump|call)\s+([A-Za-z_][\w]*)')


def strip_escapes(s):
    """把字面量转义（{{ }} [[ ]]）摘掉，避免误判标签平衡。"""
    return s.replace("{{", "").replace("}}", "").replace("[[", "").replace("]]", "")


def count_unescaped(s, ch):
    n = 0
    i = 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        if s[i] == ch:
            n += 1
        i += 1
    return n


def check_file(path, args, errors, warnings, infos, labels, jumps):
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    name = os.path.basename(path)
    pending_menu = None
    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        if not line.strip():
            continue
        s = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if indent % 4 != 0:
            warnings.append((name, i, "W2 缩进不是 4 的倍数"))

        m = LABEL_RE.match(s)
        if m:
            lab = m.group(1)
            if lab in labels:
                errors.append((name, i, "E1 重复 label: %s（首次在 %s:%d）"
                               % (lab, labels[lab][0], labels[lab][1])))
            else:
                labels[lab] = (name, i)
            pending_menu = None
            continue

        m = JUMP_RE.match(s)
        if m:
            jumps.append((name, i, m.group(2), m.group(1)))
            pending_menu = None
            continue

        if s == "menu:":
            pending_menu = (name, i)
            continue

        if pending_menu:
            if indent == 0:
                errors.append((name, i, "E4 menu: 之后没有缩进项"))
            pending_menu = None

        if s.startswith("# TODO"):
            infos.append((name, i, s[:90]))
            continue

        if SAY_RE.match(s):
            q = count_unescaped(s, '"')
            if q % 2 != 0:
                errors.append((name, i, "E3 引号未闭合"))
            elif q > 2:
                warnings.append((name, i, "W4 say 行有未转义的引号（%d 个）" % q))
            body = strip_escapes(s)
            if body.count("{") != body.count("}"):
                warnings.append((name, i, "W1 文本标签 { } 不平衡"))
            if body.count("[") != body.count("]"):
                warnings.append((name, i, "W1 插值 [ ] 不平衡"))

        for m in ASSET_RE.finditer(s):
            p = m.group(1)
            if p.startswith("http") or "seen_image" in s:
                continue
            found = False
            for base in args.search_dirs:
                if os.path.exists(os.path.join(base, p)):
                    found = True
                    break
                if os.path.exists(os.path.join(base, os.path.basename(p))):
                    found = True
                    break
            if not found:
                warnings.append((name, i, "W3 资源缺失: %s" % p))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ren'Py 转译产物静态门禁")
    ap.add_argument("game_dir", help="包含 .rpy 的目录（一般是 out/game）")
    ap.add_argument("--assets", default=None, help="资源根目录（用于 W3 检查）")
    ap.add_argument("--strict", action="store_true", help="WARNING 也算失败")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.game_dir):
        print("目录不存在: %s" % args.game_dir)
        return 2

    project_root = os.path.dirname(os.path.abspath(args.game_dir))
    args.search_dirs = [project_root]
    if args.assets:
        args.search_dirs.append(os.path.abspath(args.assets))

    errors, warnings, infos = [], [], []
    labels, jumps = {}, []
    rpy = [os.path.join(args.game_dir, f) for f in sorted(os.listdir(args.game_dir))
           if f.endswith(".rpy")]
    if not rpy:
        print("没有找到 .rpy 文件: %s" % args.game_dir)
        return 2
    for p in rpy:
        check_file(p, args, errors, warnings, infos, labels, jumps)

    for name, i, target, kind in jumps:
        if target not in labels:
            errors.append((name, i, "E2 %s 目标未定义: %s" % (kind, target)))

    for bucket, tag in ((errors, "ERROR"), (warnings, "WARN"), (infos, "TODO")):
        for name, i, msg in bucket:
            print("%s %s:%d  %s" % (tag, name, i, msg))

    print("-" * 52)
    print("label %d 个 | 跳转 %d 条 | TODO %d 处 | ERROR %d | WARN %d"
          % (len(labels), len(jumps), len(infos), len(errors), len(warnings)))
    if errors:
        print("结果: 不通过（先清 ERROR）")
        return 1
    if warnings and args.strict:
        print("结果: 不通过（--strict 下存在 WARN）")
        return 1
    print("结果: 通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
