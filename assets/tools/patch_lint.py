"""给 skill 的 nsport_lint.py 打最小补丁，产出可对比的 patched 版本。

不修改原文件，只在 task 目录里生成 nsport_lint.patched.py，便于 review 后自行覆盖。
用法: python patch_lint.py <原始 nsport_lint.py> <输出路径>
"""
import io
import sys

src_path, out_path = sys.argv[1], sys.argv[2]
s = io.open(src_path, encoding="utf-8").read()
orig = s

reps = []

# ---- 1. 坐标正则兼容 xpos=640 / pos=(a,b) 写法 -------------------------------
reps.append((
    'POS_RE = re.compile(r"\\b(?:xpos|ypos|xalign|yalign|xoffset|yoffset)\\b\\s*[-+]?\\d")\n'
    'POS_PAIR_RE = re.compile(r"\\bpos\\b\\s*\\(?\\s*[-+]?\\d")',
    'POS_RE = re.compile(r"\\b(?:xpos|ypos|xalign|yalign|xoffset|yoffset)\\b\\s*[=:]?\\s*[-+]?\\d")\n'
    'POS_PAIR_RE = re.compile(r"\\b(?:pos|anchor|align)\\b\\s*=?\\s*\\(?\\s*[-+]?\\d")\n'
    '# 空选项（真实写法是 `"":`，不是裸 `""`）\n'
    'EMPTY_CHOICE_RE = re.compile(r\'^""\\s*[:：]?\\s*$\')\n'
    '# play music 的循环标志：按词边界判断，避免文件名里带 loop 被当已声明\n'
    'PLAY_LOOP_RE = re.compile(r"\\b(?:loop|noloop)\\b")',
))

# ---- 2. NS004/覆盖率：只查 story，块级 src 注释覆盖到空行或下一个块注释 -------
reps.append((
    """        for i, raw in enumerate(lines, 1):
            stripped = strip_comment(raw).strip()
            if not stripped:
                continue
""",
    """        # 块级 src 注释 = 整行只有 src 注释
        block_src = set()
        for i, raw in enumerate(lines, 1):
            if SRC_RE.search(raw) and not strip_comment(raw).strip():
                block_src.add(i)

        cur_block = None
        for i, raw in enumerate(lines, 1):
            stripped = strip_comment(raw).strip()

            # NS011 裸 TODO：注释行本身也要查，必须放在 continue 之前
            if TODO_RE.search(raw) and not ISSUE_RE.search(raw):
                self.add("NS011", rel_path, i, raw.strip()[:90])

            if not stripped:
                cur_block = None
                continue

            # 块级 src 从本行开始生效
            if i in block_src:
                cur_block = i
""",
))

# ---- 3. NS001 只在 story 生效 ------------------------------------------------
reps.append((
    "            if SHOW_RE.match(stripped) and (POS_RE.search(stripped) or POS_PAIR_RE.search(stripped)):",
    "            if story and SHOW_RE.match(stripped) and (POS_RE.search(stripped) or POS_PAIR_RE.search(stripped)):",
))

# ---- 4. NS006 用词边界 ------------------------------------------------------
reps.append((
    '            if PLAY_MUSIC_RE.match(stripped) and "loop" not in stripped:',
    "            if PLAY_MUSIC_RE.match(stripped) and not PLAY_LOOP_RE.search(stripped):",
))

# ---- 5. NS010 匹配 `"":` ----------------------------------------------------
reps.append((
    """            if stripped == '\"\"' or stripped.startswith('\"\" '):""",
    "            if EMPTY_CHOICE_RE.match(stripped):",
))

# ---- 6. 删掉旧 NS011 块（已被前置检查取代） ---------------------------------
reps.append((
    """            # NS011 裸 TODO
            if TODO_RE.search(raw) and not ISSUE_RE.search(raw):
                self.add("NS011", rel_path, i, raw.strip()[:90])

""",
    "",
))

# ---- 7. NS004 只统计 story + 接受块级覆盖 -----------------------------------
reps.append((
    """            # NS004 来源注释覆盖
            if CONV_RE.match(stripped) or is_say(stripped):
                self.conv_statements += 1
                window = range(max(1, i - 5), i + 1)
                if any(w in src_lines for w in window):
                    self.sourced_statements += 1
                else:
                    self.add("NS004", rel_path, i, stripped[:90])""",
    """            # NS004 来源注释覆盖：只查 story 模块；块级注释覆盖到空行或下一个块注释
            if story and (CONV_RE.match(stripped) or is_say(stripped)):
                self.conv_statements += 1
                window = range(max(1, i - 5), i + 1)
                if cur_block is not None or any(w in src_lines for w in window):
                    self.sourced_statements += 1
                else:
                    self.add("NS004", rel_path, i, stripped[:90])""",
))

for old, new in reps:
    if old not in s:
        raise SystemExit("补丁锚点未命中:\n" + old[:120])
    s = s.replace(old, new, 1)

assert s != orig
io.open(out_path, "w", encoding="utf-8", newline="\n").write(s)
print("已写出:", out_path)
print("改动点:", len(reps))
