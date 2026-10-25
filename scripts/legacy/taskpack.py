#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""taskpack.py — 把一个 label 切成一份自包含的移植任务包（人工/AI 修复单元）。

用法:
    python taskpack.py --ns 源.txt --rpy out/game/script.rpy --label tell
    python taskpack.py --ns 源.txt --rpy out/game/script.rpy --all --out tasks/

任务包含: NS 原文 / 生成的 Ren'Py / 该标签的 TODO / 出入边跳转 / 资源引用 / 验收清单。
目的: 让修复者在 200 行以内拿到全部上下文，不必读整份脚本。
"""

import argparse
import os
import re
import sys
from collections import OrderedDict

LABEL_RE = re.compile(r'^label\s+([A-Za-z_][\w]*)\s*:')
JUMP_RE = re.compile(r'^(jump|call)\s+([A-Za-z_][\w]*)')
ASSET_RE = re.compile(r'"([^"\n]+\.(?:png|jpg|jpeg|bmp|webp|ogg|mp3|wav|opus))"')


def sanitize(s):
    s = s.strip()
    s = re.sub(r'\.[A-Za-z0-9]{1,5}$', '', s)
    s = re.sub(r'[^0-9A-Za-z_]+', '_', s)
    s = s.strip('_')
    if not s:
        s = 'x'
    if s[0].isdigit():
        s = 'x_' + s
    return s.lower()


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read().splitlines()


def ns_blocks(lines):
    blocks = OrderedDict()
    cur = None
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith('*'):
            cur = s[1:].strip()
            blocks[cur] = [(i, raw)]
        elif cur is not None:
            blocks[cur].append((i, raw))
    return blocks


def rpy_blocks(lines):
    blocks = OrderedDict()
    cur = None
    for i, raw in enumerate(lines, 1):
        m = LABEL_RE.match(raw)
        if m:
            cur = m.group(1)
            blocks[cur] = [(i, raw)]
        elif cur is not None:
            blocks[cur].append((i, raw))
    # 去掉块尾的空行和属于下一个标签的分隔注释
    for k in list(blocks):
        b = blocks[k]
        while len(b) > 1:
            s = b[-1][1].strip()
            if s == '' or s.startswith('# ---- NS'):
                b.pop()
            else:
                break
    return blocks


def make_packet(name, ns_lines, rpy_lines, in_edges, out_edges, todos, assets):
    san = 'start' if name == 'start' else sanitize(name)
    out = []
    out.append('# 任务包: %s  (%s)' % (name, san))
    out.append('')
    out.append('- NS 行范围: %d–%d' % (ns_lines[0][0], ns_lines[-1][0]))
    out.append('- rpy 行范围: %d–%d' % (rpy_lines[0][0], rpy_lines[-1][0]))
    out.append('- TODO: %d 处' % len(todos))
    out.append('')
    out.append('## 0. 入场/出场')
    out.append('')
    out.append('入口: ' + (', '.join(sorted(in_edges)) if in_edges else '（无，可能是入口标签）'))
    out.append('')
    out.append('出口: ' + (', '.join(sorted(out_edges)) if out_edges else '（无）'))
    out.append('')
    out.append('## 1. NS 原文')
    out.append('')
    out.append('```ns')
    for i, raw in ns_lines:
        out.append('%5d | %s' % (i, raw))
    out.append('```')
    out.append('')
    out.append('## 2. 生成的 Ren\'Py')
    out.append('')
    out.append('```renpy')
    for i, raw in rpy_lines:
        out.append('%5d | %s' % (i, raw))
    out.append('```')
    out.append('')
    if todos:
        out.append('## 3. 本标签的 TODO')
        out.append('')
        for i, raw in todos:
            out.append('- `rpy:%d` %s' % (i, raw.strip()))
        out.append('')
        out.append('修复方法查 `references/repair-playbook.md` 对应类别；'
                   '无法修复的写进 WAIVERS.md。')
        out.append('')
    if assets:
        out.append('## 4. 资源引用')
        out.append('')
        for a in sorted(assets):
            out.append('- `%s`' % a)
        out.append('')
    out.append('## 5. 验收')
    out.append('')
    out.append('- [ ] `python scripts/verify.py out/game` 无新增 ERROR')
    out.append('- [ ] 本标签 TODO 清零，或已登记 WAIVERS.md')
    out.append('- [ ] 台词与 NS 原文逐字一致（只允许增删文本标签，不许改写）')
    out.append('- [ ] 本标签内的 jump/call 目标全部存在')
    return '\n'.join(out) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description='生成按 label 切分的移植任务包')
    ap.add_argument('--ns', required=True, help='NS 明文脚本')
    ap.add_argument('--rpy', required=True, help='生成的 script.rpy')
    ap.add_argument('--label', default=None, help='只生成指定标签')
    ap.add_argument('--all', action='store_true', help='生成全部标签')
    ap.add_argument('--out', default=None, help='输出目录（不填则打印）')
    args = ap.parse_args(argv)

    nsb = ns_blocks(read(args.ns))
    rpb = rpy_blocks(read(args.rpy))

    if args.label:
        names = [args.label]
    elif args.all:
        names = [n for n in nsb if n not in ('define',)]
    else:
        ap.print_help()
        return 2

    in_edges = {}
    all_edges = {}
    for san, block in rpb.items():
        outs = set()
        for _, raw in block:
            m = JUMP_RE.match(raw.strip())
            if m:
                outs.add(m.group(2))
                in_edges.setdefault(m.group(2), set()).add(san)
        all_edges[san] = outs

    made = 0
    for name in names:
        san = 'start' if name == 'start' else sanitize(name)
        if name not in nsb:
            print('跳过（NS 中找不到）: %s' % name)
            continue
        if san not in rpb:
            print('跳过（rpy 中找不到 label）: %s -> %s' % (name, san))
            continue
        block = rpb[san]
        todos = [(i, raw) for i, raw in block if raw.strip().startswith('# TODO')]
        assets = set()
        for _, raw in block:
            for m in ASSET_RE.finditer(raw):
                assets.add(m.group(1))
        text = make_packet(name, nsb[name], block,
                           in_edges.get(san, set()), all_edges.get(san, set()),
                           todos, assets)
        if args.out:
            if not os.path.isdir(args.out):
                os.makedirs(args.out)
            path = os.path.join(args.out, '%03d_%s.md' % (made + 1, san))
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
        else:
            print(text)
        made += 1

    if args.out:
        print('已生成 %d 个任务包 -> %s' % (made, args.out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
