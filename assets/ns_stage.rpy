# -*- coding: utf-8 -*-
# =============================================================================
# ns_stage.rpy —— 通用演出层运行时（与具体游戏无关，随工作流分发，勿按作品改）
#
# 为什么要有这一层
# ----------------
# NScripter 的画面模型是分层的：
#     `_bg` / `bg` / `ev`  -> 背景层（背景、事件 CG、黑幕都往这一层换，且顺带清立绘）
#     `ld` / `cl`           -> 立绘层（独立一层；`_bg` 会把这一层清空）
#     `lsp`                 -> 分散精灵（各自独立，只有显式 `csp` 才收）
# 直接照抄成 `scene bg x` 会连带清空立绘（Ren'Py 的 scene 清整层），这就是
# 「换了背景立绘消失」「立绘盖住 CG」这类问题的来源。
#
# 本层用 tag 复刻这个分层，同时复刻 NS 的真实清屏规则：
#     tag "bg"  = 背景层（bg / ev / black / 纯色共用，互相替换）
#     tag "chr" = 立绘层（ld/cl）；**bg/ev/black/color 会清掉它**（NS 的 _bg 就是这样）
#     其余 tag  = lsp 分散精灵（各自独立，只有剧情显式 csp 才收）
#
# 依赖：port_images.rpy 生成的 image 定义与 NS_STAGE 常量（screen / image_root）。
# 缺素材不炸：显示占位图 + 记录到 NS_MISSING + 写 log，验收时能直接查出来。
# =============================================================================

init -20 python:

    import os
    import re

    # 运行期收集：缺失素材 / 缺失音频，验收时用 ns_report_missing() 打印
    NS_MISSING = []

    # NS 素材名 -> Ren'Py image 名的归一化规则，与 convert_assets.safe_name() 必须一致
    _NS_SAFE_RE1 = re.compile(r"[^0-9A-Za-z_]")
    _NS_SAFE_RE2 = re.compile(r"_+")

    def ns_safe(name):
        """把原作素材名归一成 Ren'Py image 名（与 `convert_assets.safe_name()` 同规则）。

        为什么运行时还要再归一一次：转换器生成 image 时已经归一过（`sys\\01.bmp` →
        `sys n01`、`chr\\m02_E.bmp` → `chr m02_e`），但**手写的流程/演出代码**里
        人还是会照原作写 `ns_strip("sys", "01")`。实跑撞到过两次（`chr "m02_E"`、
        `sys 01`），症状都是「素材转好了、屏幕上是灰块」。
        """
        if not name:
            return ""
        s = _NS_SAFE_RE2.sub("_", _NS_SAFE_RE1.sub("_", str(name).lower())).strip("_")
        if not s:
            return "x"
        if not (s[0].isalpha() or s[0] == "_"):
            s = "n" + s
        return s

    def ns_variants(name):
        """同一张图可能被写成原作名或归一化名；给出候选，让调用方依次试。"""
        out = [name]
        parts = name.split(None, 1)
        if len(parts) == 2:
            fixed = "%s %s" % (parts[0], ns_safe(parts[1]))
            if fixed != name:
                out.append(fixed)
        else:
            fixed = ns_safe(name)
            if fixed != name:
                out.append(fixed)
        return out

    # 包装层会直接读写这些原作变量（%G1 演出开关 / %G5 语音开关 / %G10 SE 音量档 /
    # %MNUM 当前 BGM / %SENUM SE 通道轮转 / %w11 局部标志）。这里只保证「不会
    # NameError」；要让它们进存档、绑到设置界面，请在 port_variables.rpy 用 default
    # 定义同名变量，两者不冲突（default 在新游戏开始时才生效）。
    for _ns_var, _ns_val in (("ns_g1", 1), ("ns_g5", 1), ("ns_g10", 6),
                             ("ns_mnum", -1), ("ns_senum", 0), ("ns_w11", 0)):
        if not hasattr(store, _ns_var):
            setattr(store, _ns_var, _ns_val)

    def ns_stage_conf():
        """NS_STAGE 由 port_images.rpy 定义；没生成时给安全默认值。"""
        conf = getattr(store, "NS_STAGE", None)
        if not conf:
            conf = {"screen": (800, 600), "image_root": "images/ns", "kinds": {},
                    "mask_assets": 0, "effect_flag": None}
            store.NS_STAGE = conf
        return conf

    def ns_scale():
        """NS 坐标 -> 当前分辨率。立绘/坐标全部按原作 800x600 记，这里统一换算。"""
        sw, sh = ns_stage_conf()["screen"][:2]
        return min(config.screen_width / float(sw), config.screen_height / float(sh))

    def ns_trans(dur):
        """NS 的 `,時間,速度` 近似成 Ren'Py 过渡；0/None = 瞬时切换。"""
        try:
            d = float(dur or 0)
        except (TypeError, ValueError):
            d = 0.0
        if d <= 0:
            return None
        # alpha=True 让立绘按像素 alpha 淡入，不然矩形边界会闪
        return Dissolve(d, alpha=True)

    def ns_apply(dur):
        t = ns_trans(dur)
        if t is not None:
            renpy.with_statement(t)

    def ns_show(name, at_list=None, tag=None):
        """显示一张已定义的 image；缺定义时退回占位图并留痕。

        `tag` 是**分层**的关键：背景/事件 CG/黑幕必须共用 tag "bg"，否则后一张
        图不会替换前一张（Ren'Py 里 tag 不同 = 两张同时显示，顺序一变就盖错）。

        名字先按原样试，再按 `ns_safe()` 归一化后试 —— 原作写 `chr "m02_E"`、
        磁盘上是 `m02_e.bmp`，手写代码很容易漏掉这一层换算。
        """
        if not name:
            return False
        for cand in ns_variants(name):
            if renpy.has_image(cand):
                renpy.show(cand, at_list=at_list or [], tag=tag)
                return True
        if name not in NS_MISSING:
            NS_MISSING.append(name)
            renpy.log("ns_stage: 缺素材 image %r（检查 convert_assets 是否跑过、image 名是否被手改）" % name)
        renpy.show("nsplaceholder missing", at_list=at_list or [], tag=tag)
        return False

    # ---------------------------------------------------------------- 画面 --
    #
    # 一个容易漏掉的 NS 语义：`_bg`（背景、CG、黑幕都走它）**会清掉立绘**。
    # 原作脚本正是按这个前提写的，证据在脚本里俯拾皆是：
    #   0.txt:1572  `black`（立绘 s02_e 在场）→ 1574 `bgchr "street_c","s02_i"`
    #   0.txt:10677 `black`（立绘 s03_a 在场）→ 10684 `bg "room"`，芹香已在房里说话
    #   0.txt:2509  `ev "32a"`（立绘 s01_b 在场）→ CG 单独占满画面
    # 作者用的词汇表是：`bg` = 换景（人物随之消失）/ `bgchr` = 换景并带人 /
    # `chr` = 只换人 / `chr ""` = 同一景里人物退场。所以背景类的四个入口默认清立绘；
    # 需要「换景但保留立绘」这种非常规写法时，显式传 clear_chr=False。
    #
    # 注意：`lsp` 的自由精灵（怪物、UI）**不**跟着清 —— 原作对这种精灵一律显式
    # `csp N` 收（0.txt:2259 lsp / 2280 csp），这里跟着显式收，不多做。

    def ns_bg(name, dur=0.5, clear_chr=True):
        """背景替换（原 `_bg` / `bg`）。会清立绘（见上），但不清 lsp 精灵。"""
        if clear_chr:
            renpy.hide("chr")
        ns_show("bg %s" % name, at_list=[ns_bg_tf()], tag="bg")
        ns_apply(dur)

    def ns_ev(name, dur=0.5, clear_chr=True):
        """事件 CG（原 `_bg "ev\\xxx.bmp"`）。CG 占背景层，同时清立绘（原作 CG 场景无立绘）。"""
        if clear_chr:
            renpy.hide("chr")
        ns_show("ev %s" % name, at_list=[ns_bg_tf()], tag="bg")
        ns_apply(dur)

    def ns_black(dur=0.5, clear_chr=True):
        """黑幕（原 `_bg black`）。占背景层并清立绘 —— 原作用黑幕收场时人物必退场。"""
        if clear_chr:
            renpy.hide("chr")
        ns_show("nsplaceholder black", at_list=[ns_bg_tf()], tag="bg")
        ns_apply(dur)

    def ns_hide_all(dur=0.0):
        """回到「什么都没有」的状态。清背景层、立绘层和所有 lsp 精灵。"""
        renpy.hide("bg")
        renpy.hide("chr")
        for tag in ("sp%s" % i for i in range(0, 151)):
            renpy.hide(tag)
        ns_apply(dur)

    def ns_chr(slot, name, dur=0.4):
        """立绘（原 `ld {l|c|r}`）。同一 tag 覆盖显示，不会出现两张叠在一起。"""
        ns_show("chr %s" % name, at_list=[ns_slot_tf(slot)])
        ns_apply(dur)

    def ns_chr_clear(slot=None, dur=0.3):
        """清除立绘（原 `cl {l|c|r}`）。slot 只为和生成代码保持同一签名（本引擎只用一个立绘层）。"""
        renpy.hide("chr")
        ns_apply(dur)

    def ns_bgchr(bg, chr_name=None, dur=0.5):
        """背景 + 立绘一步到位（原 `bgchr` 之类的自定义包装层）。

        `_bg` 会清立绘，所以「换景并带一个人」必须用这个入口，而不是分开调
        `ns_bg` + `ns_chr`（那样会先清再显示，白闪一下）。
        """
        ns_bg(bg, dur=0, clear_chr=True)
        if chr_name:
            ns_chr("c", chr_name, dur=0)
        ns_apply(dur)

    def ns_sprite(layer, name, x=0, y=0, dur=0, group=None):
        """分散精灵（原 `lsp n,"file",x,y`），坐标按原作像素。

        `group` 是素材所在目录（`monster\\warm.bmp` → "monster"）：转换器按目录
        注册 image（`image monster warm`），只给文件名是找不到图的。
        """
        tag = "sp%s" % str(layer)
        img = "%s %s" % (group, name) if group else name
        ns_show(img, at_list=[ns_abs(x, y)], tag=tag)
        ns_apply(dur)

    def ns_sprite_hide(layer, dur=0):
        renpy.hide("sp%s" % str(layer))
        ns_apply(dur)

    def ns_strip(group, name, x=0, y=0, loop=False, tag=None):
        """播一条动画条（源 spec `:c/N,<每格毫秒>,<x>;` 的多格素材）。

        动画本身由 `port_images.rpy` 生成：`<目录> <名>_anim` 播一遍停在最后一帧，
        `<目录> <名>_loop` 循环。剧情里**不要**手写一长串 `"xxx_c0" pause 0.04 ...`，
        也不要只 show 单帧（那等于停在第一格，看起来就像「动画没实现」）。

        名字同样先按原样、再按 `ns_safe()` 归一化试（`ns_strip("sys", "01")` 要能
        命中 `sys n01_anim`）。
        """
        suffix = "_loop" if loop else "_anim"
        anim = "%s %s%s" % (group, name, suffix)
        single = "%s %s" % (group, name)
        for base in (anim, single):
            for cand in ns_variants(base):
                if renpy.has_image(cand):
                    renpy.show(cand, at_list=[ns_abs(x, y)], tag=tag)
                    return True
        # 一个都找不到：走 ns_show 的缺素材留痕路径，别静默什么都不显示
        return ns_show(anim, at_list=[ns_abs(x, y)], tag=tag)

    def ns_strip_hide(tag=None):
        renpy.hide(tag or "strip")

    NS_COLOR_NAMES = {
        "white": "#ffffff", "black": "#000000", "red": "#ff0000",
        "green": "#00ff00", "blue": "#0000ff", "yellow": "#ffff00",
        "gray": "#808080", "grey": "#808080", "cyan": "#00ffff",
        "magenta": "#ff00ff",
    }

    def ns_color(name, dur=0.5, clear_chr=True):
        """`_bg white` / `_bg #RRGGBB`：整屏纯色（NS 允许 _bg 直接给颜色名或色值）。

        走的是 `_bg`，所以和背景一样会清立绘（原作 `_bg white` 多用于「白屏转场」，
        人物本来就不该留在上面）。"""
        if not name:
            return
        if clear_chr:
            renpy.hide("chr")
        color = NS_COLOR_NAMES.get(str(name).lower(), str(name))
        if not (color.startswith("#") and len(color) in (4, 7, 9)):
            color = "#000000"
        renpy.show("nsolid", at_list=[ns_bg_tf()], tag="bg", what=Solid(color))
        ns_apply(dur)

    def ns_movie(name, loops=0):
        """`mpegplay "movie\\x.mpg"`：播过场动画后回到原画面。

        优先 .webm（转换阶段用 ns_movies.py 转好），退回 .mpg/.mp4；都没有就留痕
        跳过并 pause 一下，避免整段流程卡死。"""
        for ext in (".webm", ".mp4", ".mpg", ".mpeg", ".avi"):
            path = "movie/%s%s" % (name, ext)
            if renpy.loadable(path):
                renpy.movie_cutscene(path, loops=loops)
                return True
        key = "movie/%s" % name
        if key not in NS_MISSING:
            NS_MISSING.append(key)
            renpy.log("ns_stage: 缺过场动画 %r（跑 ns_movies.py 转换，或从剧情里去掉）" % name)
        # hard=True 的理由：过场动画缺失时不能靠玩家点击跳过（继续点下去会连过好几
        # 句台词），只硬等 0.2 秒留一个可感知的停顿，然后照常继续剧情。
        renpy.pause(0.2, hard=True)
        return False

    # ---------------------------------------------------------------- 音频 --
    # NS 的音频是「通道号 + 起停」模型（`dwave 3,"se\\x.ogg"` / `dwavestop 3`），
    # 通道可以同时开很多条（原作 *dstop 一开就 for 0..150 全停）。Ren'Py 的
    # music/sound/voice 三个固定通道装不下，因此预注册 ns1..ns32（init 里注册，
    # 运行期绝不能再调 register_channel —— Ren'Py 会抛
    # "Can't register channel outside of init phase"）。
    NS_CHANNELS = set(["music", "sound", "voice"])
    NS_CHANNEL_RANGE = list(range(1, 33))

    def ns_audio_file(sub, name, report=True):
        base = os.path.join(config.gamedir, "audio", sub, name)
        for ext in (".ogg", ".wav", ".mp3", ".opus", ".flac"):
            if os.path.exists(base + ext):
                return "audio/%s/%s%s" % (sub, name, ext)
        if report and "audio/%s/%s" % (sub, name) not in NS_MISSING:
            NS_MISSING.append("audio/%s/%s" % (sub, name))
        return None

    def ns_audio_path(name, ch=None):
        """按通道决定去哪个目录找文件。

        NS 的 `dwaveloop 18,"voice\\x.ogg"` 走语音通道，`dwave 19,"se\\x.ogg"` 走
        SE 通道，但通道号本身不携带目录信息 —— 同名文件在 se/ 和 voice/ 都可能存在。
        先按约定顺序（18→voice、19→se，其余 se→voice→bgm）找，找到就用，全都没有
        才登记缺失。不这样分流的话，`loop "serbg001"` 会去 audio/se/ 找语音文件，
        必然缺失（实测：语音循环整段静音，只在 log 里留下 missing）。

        探测期间 `report=False`：多目录试错时前几轮必然 miss，若每次都登记，
        报告里会出现一堆「其实找到了」的假缺失（实测 `dwaveloop 26,"voice\\maybg201.ogg"`
        在 se 里不存在、voice 里有，却把 audio/se/maybg201 记成缺失）。
        """
        chan = ns_channel(ch) if ch is not None else ""
        if chan == "voice":
            subs = ("voice", "se", "bgm")
        elif chan == "sound":
            subs = ("se", "voice", "bgm")
        else:
            subs = ("se", "voice", "bgm")
        for sub in subs:
            path = ns_audio_file(sub, name, report=False)
            if path:
                return path
        if "audio/%s/%s" % (subs[0], name) not in NS_MISSING:
            NS_MISSING.append("audio/%s/%s" % (subs[0], name))
        return None

    def ns_channel(ch):
        """NS 通道号 → Ren'Py 通道名。18=语音、19=SE（原作约定），1..32 用预注册的
        ns<号>，超出范围退回 sound 并登记一次（绝不在这里注册通道：运行期注册会直接崩）。"""
        raw = str(ch if ch is not None else "").strip()
        if not raw:
            return "sound"
        expr = re.sub(r"%(\w+)", lambda m: str(getattr(store, "ns_%s" % m.group(1).lower(), 0)), raw)
        if not expr.isdigit():
            try:
                expr = str(renpy.python.py_eval(expr))
            except Exception:
                expr = raw
        if expr == "18":
            return "voice"
        if expr == "19":
            return "sound"
        if expr.isdigit() and 1 <= int(expr) <= 32:
            return "ns%d" % int(expr)
        key = "ch:%s" % expr
        if key not in NS_MISSING:
            NS_MISSING.append(key)
        return "sound"

    def ns_bgm(name, loop=True, fade=0.5):
        path = ns_audio_file("bgm", name)
        if path:
            renpy.music.play(path, channel="music", loop=loop, fadein=fade)

    def ns_bgm_stop(fade=1.0):
        renpy.music.stop(channel="music", fadeout=fade)

    def ns_se(name, ch=None, channel=None):
        path = ns_audio_path(name, ch)
        if path:
            renpy.sound.play(path, channel=channel or ns_channel(ch))

    def ns_se_loop(name, ch=None):
        path = ns_audio_path(name, ch)
        if path:
            renpy.sound.play(path, channel=ns_channel(ch), loop=True)

    def ns_se_stop(ch=None, channel=None, fade=0.0):
        renpy.music.stop(channel=channel or ns_channel(ch), fadeout=fade)

    def ns_se_stop_all():
        """停掉所有 SE/语音通道（原作 `for 0 to 150:dwavestop`）。"""
        renpy.music.stop(channel="sound")
        renpy.music.stop(channel="voice")
        for chan in list(NS_CHANNELS):
            if chan.startswith("ns"):
                renpy.music.stop(channel=chan)

    def ns_setvol(ch, vol):
        """`chvol ch,vol`，NS 音量是 0-100。"""
        try:
            v = max(0.0, min(1.0, float(vol) / 100.0))
        except (TypeError, ValueError):
            return
        renpy.music.set_volume(v, channel=ns_channel(ch))

    def ns_voice(name):
        path = ns_audio_file("voice", name)
        if path:
            renpy.sound.play(path, channel="voice")

    def ns_voice_loop(name):
        path = ns_audio_file("voice", name)
        if path:
            renpy.sound.play(path, channel="voice", loop=True)

    def ns_voice_stop(fade=0.0):
        renpy.music.stop(channel="voice", fadeout=fade)

    # ---------------------------------------------------------------- 诊断 --
    def ns_report_missing():
        """验收用：打印本次运行缺失的素材/音频。"""
        if not NS_MISSING:
            return "无缺失素材"
        renpy.log("ns_stage 缺失 %d 项: %s" % (len(NS_MISSING), ", ".join(NS_MISSING)))
        return "缺失 %d 项，见 log.txt" % len(NS_MISSING)


# ---------------------------------------------------------------- 位置换算 --
# NS 的 l/c/r 是「按图片宽度贴边/居中、底边贴画面底」。原作 800x600，立绘多为
# 整屏高，因此等价于底部对齐；实测有偏差时只改这里，不要在剧情里写裸坐标。
init python:

    def ns_bg_tf():
        return Transform(anchor=(0, 0), pos=(0, 0), zoom=ns_scale())

    def ns_slot_tf(slot):
        sc = ns_scale()
        slot = (slot or "c").lower()
        if slot == "l":
            return Transform(anchor=(0.0, 0.0), pos=(0, 0), zoom=sc)
        if slot == "r":
            return Transform(anchor=(1.0, 0.0), pos=(1.0, 0), zoom=sc)
        return Transform(anchor=(0.5, 0.0), pos=(0.5, 0), zoom=sc)


transform ns_left:
    anchor (0.0, 0.0)
    pos (0, 0)
    zoom ns_scale()

transform ns_center:
    anchor (0.5, 0.0)
    pos (0.5, 0)
    zoom ns_scale()

transform ns_right:
    anchor (1.0, 0.0)
    pos (1.0, 0)
    zoom ns_scale()


# 原作像素坐标的通用位置（lsp 用）。参数是 NS 坐标，自动换算到当前分辨率。
transform ns_abs(x, y):
    anchor (0.0, 0.0)
    pos (int(x * ns_scale()), int(y * ns_scale()))
    zoom ns_scale()


# NS 通道号在 init 里一次性注册好：Ren'Py 禁止在运行期 register_channel
# （`Can't register channel outside of init phase`），必须在这里全量建出来。
init -5 python:
    for _ns_ch in store.NS_CHANNEL_RANGE:
        _ns_name = "ns%d" % _ns_ch
        renpy.music.register_channel(_ns_name, mixer="sfx", loop=False)
        store.NS_CHANNELS.add(_ns_name)
    del _ns_ch, _ns_name


# 占位图：只有真缺素材时才会出现，看到它就是清单没对上，别当成美术问题
init python:
    renpy.image("nsplaceholder black",
                Solid("#000000", xysize=(config.screen_width, config.screen_height)))
    renpy.image("nsplaceholder missing",
                Fixed(Solid("#3a0000", xysize=(config.screen_width, config.screen_height)),
                      Text("缺少素材\n见 log.txt / NS_MISSING",
                           color="#ff6666", size=48, xalign=0.5, yalign=0.5)))
