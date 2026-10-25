"""按 Ren'Py 实际排版规则，静态估算 story/*.rpy 的台词在文本框里占几行。

用法:
  python qa_text_fit.py <game 目录> [--width 612] [--lines 4] [--size 24] [--font fonts/default.ttf]

做法:
  1. 用与游戏相同的字体（project/game/fonts/default.ttf = Microsoft YaHei）按 text_size
     量每个字的宽度；
  2. 按 gui.dialogue_width 做贪心折行（Ren'Py 在 gui.language = "unicode" 时按
     UAX#14 折行，CJK 可任意断，ASCII 按词断，这里用「标点不出现在行首」的简化规则近似）；
  3. 超过 --lines 行就报错（Ren'Py 的文本不会滚动，超出文本框高度会被裁掉）。

注意: 这是静态估算，字体渲染、字距、kerning 与运行时还有偏差，最终以实机为准。
"""
import io
import os
import re
import sys

from PIL import ImageFont

args = sys.argv[1:]
game = args[0]
def opt(name, default):
    if name in args:
        return args[args.index(name) + 1]
    return default

width = float(opt("--width", 612))
max_lines = int(opt("--lines", 4))
size = int(opt("--size", 24))
font_path = opt("--font", os.path.join(game, "fonts", "default.ttf"))

font = ImageFont.truetype(font_path, size)
ascent, descent = font.getmetrics()
line_h = ascent + descent
usable = int(width)
print("字体: %s  %dpx  ascent=%d descent=%d 单行高=%d" % (os.path.basename(font_path), size, ascent, descent, line_h))
print("文本框可用宽度: %d px，最多 %d 行（可用高度约 %d px）" % (usable, max_lines, line_h * max_lines))
print()

NO_LINE_START = "、。，．」』）】！？：；゛゜ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ…ー～"
NO_LINE_END = "「『（【"

_cache = {}


def cw(ch):
    if ch not in _cache:
        _cache[ch] = font.getlength(ch)
    return _cache[ch]


def wrap(text, usable_width):
    """贪心折行，返回行文本列表。"""
    lines = []
    cur = ""
    cur_w = 0.0
    for ch in text:
        w = cw(ch)
        if cur_w + w <= usable_width or not cur:
            cur += ch
            cur_w += w
            continue
        # 需要换行：避头尾处理
        if ch in NO_LINE_START and cur:
            cur += ch
            cur_w += w
            continue
        if cur and cur[-1] in NO_LINE_END:
            cur = cur[:-1]
            cur_w -= cw(cur[-1]) if cur else 0
        lines.append(cur)
        cur, cur_w = ch, w
    if cur:
        lines.append(cur)
    return lines


say_re = re.compile(r'^\s*(?:voice\s+"[^"]*"\s*)?(?:[A-Za-z_][A-Za-z0-9_]*\s+)?"((?:[^"\\]|\\.)*)"\s*(?:id\s+\S+)?\s*$')
story_dir = os.path.join(game, "story")
files = [os.path.join(story_dir, f) for f in sorted(os.listdir(story_dir)) if f.endswith(".rpy")] if os.path.isdir(story_dir) else []

total = 0
worst = []
hist = {}
for f in files:
    for ln_no, raw in enumerate(io.open(f, encoding="utf-8-sig").read().split("\n"), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("$"):
            continue
        if re.match(r'^(?:menu|label|jump|call|scene|show|hide|play|stop|with|if|elif|else|return|python|screen|image|define|default)\b', stripped):
            continue
        m = say_re.match(stripped)
        if not m:
            continue
        text = m.group(1)
        if not text:
            continue
        total += 1
        lines = wrap(text, usable)
        n = len(lines)
        hist[n] = hist.get(n, 0) + 1
        if n > max_lines:
            worst.append((n, ln_no, os.path.basename(f), text[:40]))

print("统计台词 %d 条；行数分布: %s" % (total, dict(sorted(hist.items()))))
print()
if worst:
    print("超出 %d 行的台词 %d 条（会被文本框裁掉）:" % (max_lines, len(worst)))
    for n, ln_no, name, text in sorted(worst, reverse=True)[:20]:
        print("  %d 行  %s:%d  %s…" % (n, name, ln_no, text))
    sys.exit(1)
print("结论：全部台词都在 %d 行以内，没有超框风险。" % max_lines)
