"""story 侧的静态资源与来源校验。

用法: python qa_assets.py <project/game> <source/0.txt 行数>

检查项:
  1. voice "xxxxx" 引用的语音文件是否真的在 game/audio/voice/ 里；
  2. 剧本里出现的素材名（bg/chr/ev 由 $ port_* 调用传入）是否有对应 PNG；
  3. 每条 # src:0.txt:<行> 是否落在源文件行数范围内；
  4. 台词中是否有替换符 U+FFFD、控制字符或未闭合的全角括号。
"""
import io
import os
import re
import sys

game = sys.argv[1]
src_lines = int(sys.argv[2])
story = os.path.join(game, "story")

voice_dir = os.path.join(game, "audio", "voice")
have_voice = set(os.path.splitext(f)[0] for f in os.listdir(voice_dir)) if os.path.isdir(voice_dir) else set()

img_root = os.path.join(game, "images")
have_img = set()
for sub in ("bg", "chr", "ev"):
    d = os.path.join(img_root, sub)
    if os.path.isdir(d):
        for f in os.listdir(d):
            have_img.add(os.path.splitext(f)[0])

missing_voice, missing_img, bad_src, bad_char = [], [], [], []
n_voice = n_img = n_src = n_say = 0

for name in sorted(os.listdir(story)):
    if not name.endswith(".rpy"):
        continue
    path = os.path.join(story, name)
    for ln_no, raw in enumerate(io.open(path, encoding="utf-8-sig").read().split("\n"), 1):
        line = raw.strip()

        for m in re.finditer(r'^\s*voice\s+"([^"]+)"', line):
            n_voice += 1
            if m.group(1) not in have_voice:
                missing_voice.append((name, ln_no, m.group(1)))

        for m in re.finditer(r'\$ port_(?:bg|bgchr|chr|ev)\("([^"]+)"', line):
            n_img += 1
            for token in m.group(1).split("|"):
                if token and token not in have_img:
                    missing_img.append((name, ln_no, token))
        for m in re.finditer(r'^\s*(?:scene|show)\s+(?:bg|chr|ev)\s+(\S+)', line):
            n_img += 1
            if m.group(1) not in have_img:
                missing_img.append((name, ln_no, m.group(1)))

        m = re.match(r'^#\s*src:0\.txt:(\d+)(?:-(\d+))?', line)
        if m:
            n_src += 1
            a = int(m.group(1))
            b = int(m.group(2) or a)
            if not (1 <= a <= b <= src_lines):
                bad_src.append((name, ln_no, line))

        if "\ufffd" in raw or re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", raw):
            bad_char.append((name, ln_no, "替换符或控制字符"))
        if raw.count("「") != raw.count("」"):
            bad_char.append((name, ln_no, "「」不配对"))
        if raw.count('"') % 2 == 1 and not line.startswith("#"):
            bad_char.append((name, ln_no, "双引号数为奇数"))
        if re.match(r'^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s+)?"', line):
            n_say += 1

print("台词 %d 条 / voice %d 条 / 素材引用 %d 处 / src 注释 %d 条" % (n_say, n_voice, n_img, n_src))
print("语音文件目录 %d 个，图片 %d 个" % (len(have_voice), len(have_img)))
for label, items in (("缺语音", missing_voice), ("缺图片", missing_img), ("src 越界", bad_src), ("文本异常", bad_char)):
    if items:
        print()
        print("%s（%d）:" % (label, len(items)))
        for it in items[:15]:
            print("  %s:%d %s" % it)
    else:
        print("%s: 无" % label)

bad = len(missing_voice) + len(missing_img) + len(bad_src) + len(bad_char)
print()
print("结论：%s" % ("全部通过" if bad == 0 else "发现 %d 处问题" % bad))
sys.exit(1 if bad else 0)
