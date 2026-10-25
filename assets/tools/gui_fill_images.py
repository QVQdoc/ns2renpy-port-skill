import os, sys
from PIL import Image

src = sys.argv[1] if len(sys.argv) > 1 else "the_question/game/gui"
dst = sys.argv[2] if len(sys.argv) > 2 else "game/gui"
scale = 0.625
made = 0
for root, dirs, files in os.walk(src):
    rel = os.path.relpath(root, src)
    outdir = os.path.join(dst, rel) if rel != "." else dst
    for fn in files:
        if not fn.lower().endswith(".png"):
            continue
        out = os.path.join(outdir, fn)
        if os.path.exists(out):
            continue
        os.makedirs(outdir, exist_ok=True)
        with Image.open(os.path.join(root, fn)) as im:
            w, h = im.size
            nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
            resized = im.resize((nw, nh), Image.LANCZOS)
            resized.save(out)
        made += 1
        print("%s %dx%d -> %dx%d" % (os.path.join(rel, fn), w, h, nw, nh))
print("made", made)
