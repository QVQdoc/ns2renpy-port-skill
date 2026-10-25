# ns_gallery.rpy
#
# 图鉴层：回想模式 / CG 模式。
#
# NScripter 原作的图鉴页是硬编码的：每页 16 格，每格一行
#
#     if fchk "ev\\01.bmp" lsp 1,":c/2,0,3;sum\\01.bmp",65,56
#     if lchk "*mem35"     lsp 14,":c/2,0,3;sum\\34a1.bmp",235,446
#     lsp 7,":c;sum\\empty.bmp",405,186
#
# 坐标、缩略图、解锁条件全在那一行里，所以这些数字不手抄：由
# `scripts/nsgallery.py` 解析成 `gallery.json`，这里只负责按数据画。
#
# 依赖：
#   * `gallery.json`（放在 game 目录里，nsgallery.py 的产物）
#   * `port_images.rpy` 里的 `image sum <名>_c0` / `image cgm <名>_c0` / `image ev <名>`
#   * 剧情是 `ns2renpy_story.py` 生成的：回想里 `if %kaisoumode=1 return`
#     被译成 `if store.kaisou_mode == 1: return`，所以回放前必须把
#     kaisou_mode 置 1，场景自己会 return 回来。
#
# 用法（在 port_title.rpy 或任何 UI 里）：
#
#     textbutton "CG 鉴赏" action ShowMenu("ns_gallery_cg")
#     textbutton "回想"    action ShowMenu("ns_gallery_mem")
#
# 页面切换、上一页/下一页、退出都在屏内自洽，不需要外部 state。

init -20 python:
    import json as _nsjson

    try:
        NS_GALLERY = _nsjson.load(renpy.file("gallery.json"))
    except Exception:
        NS_GALLERY = {"cg": {"per_page": 16, "pages": []},
                      "mem": {"per_page": 16, "pages": []},
                      "cg_names": {}}

    # 图鉴里点得到的东西：CG 看有没有显示过、回想看标签有没有到过。
    def ns_gal_unlocked(entry):
        """entry: gallery.json 里的一格。返回 True 表示可以点。"""
        kind = entry.get("kind")
        arg = entry.get("arg") or ""
        if kind == "fchk":
            group, _, name = arg.rpartition("/")
            img = "%s %s" % (group or "ev", _ns_safe(name))
            try:
                return renpy.seen_image(img)
            except Exception:
                return False
        if kind == "lchk":
            label = arg.lstrip("*")
            return renpy.seen_label(label)
        return False

    def _ns_safe(name):
        import re as _re
        s = _re.sub(r"[^0-9A-Za-z_]", "_", name.lower())
        s = _re.sub(r"_+", "_", s).strip("_")
        if not s:
            return "x"
        if not _re.match(r"[A-Za-z_]", s):
            s = "n" + s
        return s

    def ns_img(name):
        """按 image 名取 displayable。

        注意不能用 `Image("cgm cgm_prev_c0")`：Image() 把字符串当**文件名**，
        名字里带空格就报 "Couldn't find file 'cgm cgm_prev_c0'"（实测踩过）。
        图像名要用 ImageReference(tuple(...))。
        """
        return renpy.display.image.ImageReference(tuple(name.split()))

    def ns_gal_pages(kind):
        return NS_GALLERY.get(kind, {}).get("pages", [])

    def ns_gal_bg(kind, page):
        """原作每页各有一张背景：cgm/cgmode_bgN（CG）、cgm/mmode_bgN（回想）。
        背景图里本身就画着 "Page N/3"，所以拿到对应页那张时不需要再叠文字。"""
        name = ns_gal_bg_name(kind, page)
        if renpy.has_image(name):
            return name
        fallback = ns_gal_bg_name(kind, 0)
        if renpy.has_image(fallback):
            return fallback
        return None

    def ns_gal_bg_name(kind, page):
        prefix = "cgmode_bg" if kind == "cg" else "mmode_bg"
        return "cgm %s%d" % (prefix, page + 1)

    def ns_gal_replay_cg(names):
        """CG 模式点开一张：names 是这一格包含的文件名列表（原作可左右翻）。"""
        if not names:
            return
        _ns_gal_show_cg(names, 0)

    def _ns_gal_show_cg(names, idx):
        renpy.show_screen("ns_cg_viewer", names=names, idx=idx)

    # —— 翻页状态放在 store 里，不用屏幕变量 ——
    #
    # 这个屏幕是被 `use ns_gallery("cg")` 嵌进 port_cg / port_mem 里的。
    # 屏幕变量（SetScreenVariable）在这种嵌套里写进去读不到：`default page = 0`
    # 还挂在被 use 的那层 scope 上，每次父屏重算都会回到 0，表现就是
    # 「点上一页/下一页什么都没发生」。用 store 字典 + Function 就没有这层歧义。
    def ns_gal_page(kind):
        return store.ns_gal_page_index.get(kind, 0)

    def ns_gal_turn(kind, delta):
        pages = ns_gal_pages(kind)
        n = max(1, len(pages))
        store.ns_gal_page_index[kind] = (ns_gal_page(kind) + delta) % n
        renpy.restart_interaction()

    def ns_gal_reset(kind):
        store.ns_gal_page_index[kind] = 0

    def ns_replay_mem(label):
        """回想模式点开一段：原作是 gosub *memN，场景里靠 kaisoumode 自己 return。"""
        store.kaisou_mode = 1
        try:
            renpy.call_in_new_context(label)
        finally:
            store.kaisou_mode = 0


default ns_gal_page_index = {"cg": 0, "mem": 0}


screen ns_gallery(kind):

    $ pages = ns_gal_pages(kind)
    $ npages = max(1, len(pages))
    $ page = ns_gal_page(kind) % npages
    $ entries = pages[page] if pages else []
    $ bgimg = ns_gal_bg(kind, page)

    if bgimg:
        add ns_img(bgimg)

    for e in entries:
        if ns_gal_unlocked(e):
            $ thumbname = "%s %s" % (e["group"], e["thumb"])
            if renpy.has_image(thumbname):
                button:
                    xpos e["x"]
                    ypos e["y"]
                    background None
                    action (Function(ns_gal_replay_cg, NS_GALLERY.get("cg_names", {}).get(str(page * 16 + e["slot"] - 1), [e["arg"].split("/")[-1]]))
                            if kind == "cg" else Function(ns_replay_mem, e["arg"].lstrip("*")))
                    add ns_img(thumbname)

    # 上一页 / 下一页 / 退出：坐标照抄原作 lsp 100/101/102。
    # 用 imagebutton + idle/hover 两张图（原作就转出了 _c0/_c1），点上去有反馈。
    imagebutton:
        xpos 522
        ypos 27
        idle ns_img("cgm cgm_prev_c0")
        hover ns_img("cgm cgm_prev_c1")
        action Function(ns_gal_turn, kind, -1)

    imagebutton:
        xpos 667
        ypos 27
        idle ns_img("cgm cgm_next_c0")
        hover ns_img("cgm cgm_next_c1")
        action Function(ns_gal_turn, kind, 1)

    imagebutton:
        xpos 753
        ypos 44
        idle ns_img("cgm cgm_exit_c0")
        hover ns_img("cgm cgm_exit_c1")
        action Return()

    # 键盘和滚轮也能翻页：鼠标点在 62x15 的小按钮上本来就不容易。
    key "K_LEFT" action Function(ns_gal_turn, kind, -1)
    key "K_RIGHT" action Function(ns_gal_turn, kind, 1)
    key "mousedown_4" action Function(ns_gal_turn, kind, -1)
    key "mousedown_5" action Function(ns_gal_turn, kind, 1)
    key "K_PAGEUP" action Function(ns_gal_turn, kind, -1)
    key "K_PAGEDOWN" action Function(ns_gal_turn, kind, 1)

    # 页码：原作把 "Page N/3" 直接画在每页的背景图里（cgm cgmode_bgN / mmode_bgN），
    # 所以只在背景没换成对应页那张（走 fallback）时才自己补一个，免得和美术叠在一起。
    if bgimg != ns_gal_bg_name(kind, page):
        text ("Page %d/%d" % (page + 1, npages)):
            xpos 40
            ypos 60
            size 14
            color "#e8e8e8"


screen ns_gallery_cg():
    use ns_gallery("cg")


screen ns_gallery_mem():
    use ns_gallery("mem")


screen ns_cg_viewer(names, idx):

    if renpy.has_image("ev %s" % names[idx]):
        add ns_img("ev %s" % names[idx])
    else:
        add Solid("#000000")

    if len(names) > 1:
        text ("%d / %d" % (idx + 1, len(names))):
            xalign 0.5
            yalign 0.98
            size 14
            color "#cfcfcf"

    key "dismiss" action Hide("ns_cg_viewer")
    # 翻图同样走「重新 show 一次」而不是改屏幕变量：ns_cg_viewer 是被
    # renpy.show_screen() 弹出来的独立屏幕，用 Function 重开最稳。
    key "K_LEFT" action (Function(_ns_gal_show_cg, names, (idx - 1) % len(names)) if len(names) > 1 else NullAction())
    key "K_RIGHT" action (Function(_ns_gal_show_cg, names, (idx + 1) % len(names)) if len(names) > 1 else NullAction())

    button:
        xfill True
        yfill True
        action Hide("ns_cg_viewer")
        background None
