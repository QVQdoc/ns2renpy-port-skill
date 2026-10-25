import sys, io, collections

path = sys.argv[1]
data = open(path, "rb").read()

for enc in ("cp932", "cp936", "utf-8"):
    try:
        text = data.decode(enc)
        status = "ok"
    except UnicodeDecodeError as e:
        text = data.decode(enc, errors="replace")
        status = "err@%d" % e.start
    lines = text.split("\r\n")
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    kana = sum(1 for ch in text if "\u3040" <= ch <= "\u30ff")
    ff = text.count("\ufffd")
    print("== %s  %s  lines=%d  cjk=%d  kana=%d  replacement=%d" % (enc, status, len(lines), cjk, kana, ff))
    for i in (95, 96, 97, 98):
        if i < len(lines):
            print("   %5d| %s" % (i + 1, lines[i][:80]))
    print()

# 找一段对白：连续以非命令、非空行开头的内容
text = data.decode("cp936", errors="replace")
lines = text.split("\r\n")
print("== cp936 抽样：疑似台词行（不以已知命令开头）")
cmds = {"bg", "ld", "cl", "csp", "goto", "gosub", "jump", "return", "if", "mov", "add", "sub",
        "menu", "select", "caption", "print", "text", "*", ";", "\\", "wait", "waittimer",
        "play", "stop", "bgm", "se", "voice", "mp3", "wave", "delay", "reset", "btnwait"}
shown = 0
for i, ln in enumerate(lines):
    s = ln.strip()
    if not s or s.startswith(("*", ";", "if", "mov", "numalias", "global", "str")):
        continue
    head = s.split(" ")[0].split(",")[0]
    if head in cmds:
        continue
    print("   %5d| %s" % (i + 1, ln[:90]))
    shown += 1
    if shown >= 12:
        break
