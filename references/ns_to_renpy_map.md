# NS 功能 → Ren'Py 官方实现 对照表

用途：重建时逐条对照，统一写法，让后期修改和复查有唯一依据。

**本表只收有官方文档依据的条目。**每条 NS 语义来自 NScripter 官方参考手册，每条 Ren'Py 写法来自 Ren'Py 官方文档。查不到官方依据的，标 `需实测` 并挂 issue，不凭经验编。

## 官方资料

| 来源 | 地址 | 用途 |
|---|---|---|
| NScripter Reference（命令逐条） | [weimingtom.github.io/wmthome/nscr](https://weimingtom.github.io/wmthome/nscr/alphabet/alphabet.htm) | NS 命令语义、参数、返回值 |
| ONScripter（Studio O.G.A.） | [ogapee.github.io/www/onscripter.html](https://ogapee.github.io/www/onscripter.html) | ONScripter 分支的差异与扩展 |
| Ren'Py：Labels & Control Flow | [label.html](https://www.renpy.org/doc/html/label.html) | label/jump/call/return |
| Ren'Py：Dialogue | [dialogue.html](https://www.renpy.org/doc/html/dialogue.html) | say、Character、window |
| Ren'Py：In-Game Menus | [menus.html](https://www.renpy.org/doc/html/menus.html) | menu、条件选项 |
| Ren'Py：Displaying Images | [displaying_images.html](https://www.renpy.org/doc/html/displaying_images.html) | image/scene/show/hide/at/with |
| Ren'Py：Transforms / ATL | [transforms.html](https://www.renpy.org/doc/html/transforms.html) · [atl.html](https://www.renpy.org/doc/html/atl.html) | 位置、移动、插值 |
| Ren'Py：Text | [text.html](https://www.renpy.org/doc/html/text.html) | `{w}` `{p}` `{cps}` `{color}` |
| Ren'Py：Audio | [audio.html](https://www.renpy.org/doc/html/audio.html) | play/stop、channel、loop、fadein |
| Ren'Py：Transitions | [transitions.html](https://www.renpy.org/doc/html/transitions.html) | dissolve/fade/pixellate/hpunch |
| Ren'Py：Statement Equivalents | [statement_equivalents.html](https://www.renpy.org/doc/html/statement_equivalents.html) | `renpy.pause(hard=)`、`renpy.jump`、`renpy.call` |
| Ren'Py：Screens | [screens.html](https://www.renpy.org/doc/html/screens.html) | screen、imagebutton、imagemap、bar |
| Ren'Py：Persistent | [persistent.html](https://www.renpy.org/doc/html/persistent.html) | 跨周目数据 |
| Ren'Py：Save/Load/Rollback | [save_load_rollback.html](https://www.renpy.org/doc/html/save_load_rollback.html) | 存档范围、rollback |
| Ren'Py：Gallery / Music Room | [rooms.html](https://www.renpy.org/doc/html/rooms.html) | CG 鉴赏、音乐鉴赏 |

## 三档判定

| 档 | 定义 | 处理 |
|---|---|---|
| **A 官方对应** | Ren'Py 有官方语句/函数，语义等价 | 用原生写法，不写自定义代码 |
| **B 官方近似** | 有官方能力，但默认行为不同 | 用原生 + 参数调整；**差异必须写进 result.md** |
| **C 无对应** | 官方没有等价能力 | 按 [系统功能映射](system_features.md) 写 screen/函数，全局唯一实现 |

判定不了 = 查不到官方依据，挂 issue，不要用"看起来差不多"的近似顶替。

## 一、剧情控制流

| NS | 官方语义 | Ren'Py 官方写法 | 档 | 差异与处理 |
|---|---|---|---|---|
| `*name` | 标签定义 | `label name:` | A | NS 标签可含全角字符，需在 catalog 建 ASCII 映射 |
| `goto *a` | 跳转，不返回 | `jump a` | A | — |
| `gosub *a` | 调用 | `call a` | A | — |
| `return` | 从 gosub 返回 | `return` | A | Ren'Py 顶层 `return` 是回主菜单，见 `end` |
| `end` | 结束游戏 | `return` | B | 若原作是回**标题**而非主菜单，用 `$ renpy.full_restart()`（官方 `renpy.full_restart` 明确写"returning the user to the main menu"） |
| `reset` | 重置 | `jump start` + 显式重置变量 | B | Ren'Py 不自动清存档变量，`start` 里需要重建初始值 |
| `if <cond> <cmd>` | 条件执行 | `if <cond>:` + 缩进块 | A | 行内式展开成块；`&&`/`||` 改 `and`/`or` |
| `notif <cond> <cmd>` | 反条件 | `if not (<cond>):` | A | — |
| `if fchk "x"` | 文件/图片是否已读 | `if renpy.seen_image("x"):` | B | `seen_image` 判的是 image 名，原作语义需核实；若本意是"进过某分支"，改显式布尔 |
| `if lchk *a` | 某标签是否执行过 | `if renpy.seen_label("a"):` | B | 近似；同上 |
| `select` | 选项菜单，选中后跳转 | `menu:` + 分支 | A | **空字符串 `""` 是隐藏项**（官方明载），要转成 `if` 条件而非空选项 |
| `selgosub` | 选项 + 调用 | `menu:` + `call` | A | 同上，`""` 隐藏项同样处理 |
| `selnum` | 数字选择菜单 | `screen` + `bar`/`imagebutton` | C | 官方无数字菜单，需自写 |
| `for` … `next` | 计数循环 | `for i in range(a, b+1):` | B | 循环内多条 say 会逐次点击，原 NS 是连续输出，节奏不同 |
| `jumpf`/`jumpb` | 跳到下/上一个标签 | 无 | C | 用显式 label 重写，不要模拟"相邻标签" |
| `trap` | 跳转分派表 | `python:` dict 分派 | C | 按作品实际用途实现 |

## 二、画面与立绘

> **本节所有「官方写法」列只是语义对照，实际代码必须调演出层**（`ns_bg` / `ns_ev` / `ns_black` / `ns_chr` / `ns_chr_clear` / `ns_sprite`），或原作包装层 `ns_w_*`。故事模块里直接写 `scene` / `show` / `hide` 会被 lint 判 `NS012`。原因：`scene` 与 `show` 单独用都会破坏 NS 的分层（背景·CG·黑幕共一层、立绘独立），见 [素材与演出层契约](assets_contract.md#5-生成文件契约)。

| NS | 官方语义 | Ren'Py 官方写法 | 档 | 差异与处理 |
|---|---|---|---|---|
| `_bg "bg\\x.bmp",<eff>` | 载入背景 + 效果；**同时清掉 `ld` 的立绘** | `show bg x` [+ `with`] | B | **不要用裸 `scene`**（它清整层，连别的东西一起清）。改调 `ns_bg("x", dur)`：换 `bg` 层并清 `chr` 层。若原作是「换景但带一个人」，它一定写的是 `bgchr`，对应 `ns_bgchr(bg, chr)` |
| `bg #rrggbb,1` | 纯色背景 | `scene expression Solid("#rrggbb")` | A | 同样走演出层：`ns_black()` 就是全屏黑；其他纯色用 `ns_bg` + 生成的 Solid 图 |
| `ld {l,c,r},"f",<eff>` | 立绘，左/中/右 | `show <char> at ns_left/ns_center/ns_right` | B | 官方只说"左、右、正中"，**没有给像素锚点**；更关键的是立绘素材常带 `:a;` 蒙版（双宽图），必须先由 `convert_assets.py` 拆出 alpha，否则会显示成绿幕方块 + 遮罩半幅。代码里调 `ns_chr(slot, name, dur)` |
| `cl {l,c,r}` | 清除立绘 | `hide <char>` | A | 调 `ns_chr_clear(slot)`；NS 的 l/c/r 是位置槽，演出层负责映射 |
| `lsp n,"f",x,y[,a]` | 精灵，**x,y 是左上角像素** | `show ... at Transform(xpos=x, ypos=y, xanchor=0, yanchor=0)` | B | 官方明载 lsp 坐标是"upper left pixel"；Ren'Py 默认 anchor 为 0.5。调 `ns_sprite(n, name, x, y)` |
| `lsph` | 同 lsp，初始隐藏；**spec 带 `/N,<间隔ms>` 时是动画条**（`lsph 1,":c/10,40,1;sys\tlanime.bmp",188,174`） | 动画条由 `port_images.rpy` 生成 `<名>_anim`/`<名>_loop`，用 `ns_strip(目录, 名, x, y, loop)` 播 | B | 10 格 × 40ms = 0.4s 的翻转动画。**不要只 show 一帧**：早期工程把 `sys/01.bmp` 存成 `logo.png` 静态图，开场 LOGO 动效就整段丢了。素材名会被归一化（`01` → `n01`），`ns_strip`/`ns_show` 对原作名也认，不用自己转 |
| `csp n` / `vsp n` | 隐藏/显示精灵 | `hide` / `show` | A | 精灵编号 0–49 是槽位，演出层映射成 tag `spN` |
| `msp n,dx,dy[,ms]` | **相对移动**精灵（dx/dy 是增量，ms=0 瞬移） | 逐段 `renpy.pause(ms/1000.0, hard=True)` + 重新 `show ... at` | B | 原作常写成「`msp` ×4 + `waittimer 60`」做逐帧滑入（本作 LOGO 就是 800→0，每段 200px）。这是**必现运动**，要用硬等，否则一点击就停在半路 |
| `print <eff>` | **按效果重绘屏幕** | `with <transition>`，或 `show` 后 `with` | A | ⚠️ 别把它当"输出文字"。官方语义：`0`=只写内存不显示，`1`=瞬时显示，`>1`=调用 `effect` 命令定义的效果。`print 1` 在文本窗关闭后是「等一次点击」，Ren'Py 由 say 承担，转换器会登记而不生成代码 |
| `quake`/`quakex`/`quakey` | 屏幕震动 | `with hpunch` / `with vpunch` | B | 官方只有固定幅度；需要精确震幅用 ATL `offset` |
| `monocro` | 单色化 | `im.MatrixColor(...)` | C | 按原作实际效果实现 |
| `nega` | 负片 | `im.MatrixColor(..., im.matrix.negative())` | C | — |
| `tal`/`amsp`/`blt` | 特殊精灵效果 | ATL 组合 | C | 逐个还原，不套统一近似 |
| `btn`/`spbtn` | 图片按钮 | `imagebutton` | A | — |
| `bar` | 数值条 | `bar` | A | — |

### 素材文件名前的 `:…;` 是 spec，不是文件名```
ld c,":a;chr\s01_a.bmp",10,300
lsp 0,":c;ev\01.bmp",0,0
```

| spec | 含义 | 转换时怎么做 |
|---|---|---|
| `:a;` | **蒙版对**：左半图像、右半遮罩 | 裁左半为图，右半做 alpha（方向由像素实测决定） |
| `:l;` | 左右翻转 | 水平镜像 |
| `:#RRGGBB;` | 键色透明 | 按占比判定后抠除 |
| `/N,dx,dy;` | 横向切 N 格 | 切成 `name_c1…cN` |
| `:c;` | 无蒙版、居中 | 只是元信息，图照原样转 |

手工转素材必然漏掉这一层，所以普查与转换必须走 `nsassets.py` → `convert_assets.py`（见 [assets_contract.md](assets_contract.md)）。

### `defsub` 包装层必须先看清再翻译

原作常把演出包在 `defsub` 里（`*bg`、`*chr`、`*bgchr`、`*black`、`*music`、`*se` 等），每个包装层带着分支条件和参数。直接调底层的后果是丢掉这些分支（例如 `%G1` 演出开关决定 `10,500` 还是 `1` 瞬显）。

`convert_assets.py` 会把每个 `defsub` 翻成 `ns_w_<name>(...)` 并保留条件与参数；剧情模块优先调包装层。翻译不了的部分（`csp 166`/`textoff`/`print 1`/`goto *loopfade`）逐条写进 `assets_convert_report.md`，不要静默丢弃。

### 效果编号：官方就说了"不是固定表"

NScripter 的 `print`/`bg`/`ld` 的 effect 参数，官方定义只有两个固定值：

- `0` — 只写入内存，不显示
- `1` — 瞬时显示
- `>1` — **调用 `effect` 命令自定义的效果**

也就是说，2 以上的编号含义由**每个作品自己的脚本**定义。因此不存在通用的"编号→Ren'Py 过渡"表，必须逐作品实测。做法见 [写法规范 · 过渡效果](conventions.md#过渡效果)。

### 立绘位置校准

官方未定义 l/c/r 的像素位置，所以不能默认 `left/center/right` 就对。步骤：

1. 在目标分辨率下运行原版，量出三档位置的实测坐标；
2. 写入公共 transform 文件：

```renpy
# port_transforms.rpy —— 按实测值填写
transform ns_left:
    xanchor 0.5
    yanchor 1.0
    xpos TARGET_LEFT_X
    ypos TARGET_BASE_Y

transform ns_center:
    xanchor 0.5
    yanchor 1.0
    xpos TARGET_CENTER_X
    ypos TARGET_BASE_Y

transform ns_right:
    xanchor 0.5
    yanchor 1.0
    xpos TARGET_RIGHT_X
    ypos TARGET_BASE_Y
```

3. 剧情模块只写 `at ns_left`，**不写裸坐标**。

## 三、等待与文本

这里是上一版最容易写错的地方。官方语义：

### `wait` 与 `delay` 不是一回事

| NS | 官方语义（原文） | Ren'Py 写法 | 档 |
|---|---|---|---|
| `wait <ms>` | 等指定毫秒，**点击不能跳过**（「クリックで飛ばせません」） | `$ renpy.pause(ms/1000.0, hard=True)` | B |
| `delay <ms>` | 等指定毫秒，**点击可以跳过**（「クリックで飛ばせます」） | `$ renpy.pause(ms/1000.0)` | A |

`!w` 等价于 `wait`，`!d` 等价于 `delay`（官方原文：「特殊表示文字wと同じ」）。

**注意 1**：`hard=True` 官方文档自己写了「In general, using hard pauses is rude」，建议避免。但 NS 的 `wait` 本意就是强制停留。二者冲突时按原作意图选，并把选择记入 result.md——这是允许的设计判断，但不能默默改成可点击。

**注意 2**：该参考手册的中/英译文在 `delay` 是否可点击上与日文原文矛盾（译文写"不能通过点击跳过"）。以日文原文为准，日文与 `wait` 条目的对照逻辑自洽。

### 文本标记

| NS 文本内 | 官方语义 | Ren'Py 写法 | 档 | 差异 |
|---|---|---|---|---|
| `@` | 点击后继续输出，不换页 | `{w}` | B | Ren'Py 的 `{w}` 等点击；一页多行的结构差异见下 |
| `\` | 断句换页 | 拆成两条 `say` | A | — |
| `!d<ms>` | 定时，可点击跳过 | `{w=X.Y}` | A | 语义一致 |
| `!w<ms>` | 定时，不可点击跳过 | `{w=X.Y}` | B | `{w}` 可被点击打断；要硬等需配合 `renpy.pause(hard=True)` 或接受差异并记录 |
| `!s<speed>` | 打字速度 | `{cps=N}` | A | 记得该行内闭合 `{/cps}` |
| `#rrggbb` | 文字颜色 | `{color=#rrggbb}` | A | 闭合 `{/color}` |
| `%n` / `$n` | 插入变量 | `[var_id]` | A | 用 catalog 的语义名，不保留 `n0` |
| `_` 单独成行 | 点击去抖 | 丢弃 | A | — |
| 字面 `[ ] { }` | 需转义 | `[[` `]]` `{{` `}}` | A | 漏转义会被当标签解析 |

### 一页多行 → 多条 say（最大的节奏偏差）

NS 连续输出文字到同一窗口，玩家点击一次推进一页；Ren'Py 一条 say 一次点击。原样逐行转换会让点击数翻数倍。

三个方案，选一个并记录：

| 方案 | 写法 | 何时用 |
|---|---|---|
| 合并（默认） | 同页多行合成一条 say，用 `\n` 换行 | 无逐行演出时 |
| 保序 | 逐行 say | 每行都切表情/语音时 |
| NVL | `nvl` 模式整屏堆字 | 原作本就是整屏文字 |

## 四、音频

| NS | 官方语义 | Ren'Py 官方写法 | 档 | 差异 |
|---|---|---|---|---|
| `mp3loop "f"` | 循环播放 | `play music "f" loop` | A | music channel 单通道，新曲自动顶替 |
| `mp3 "f"` | 单次播放 | `play music "f" noloop` | A | 播完需处理后续 |
| `waveloop "f"` | 循环音效 | `play sound "f" loop` | A | 长 BGM 别放 sound 通道，会与 music 叠加 |
| `wave "f"` | 单次音效 | `play sound "f"` | A | — |
| `wavestop` / `stop` | 停止 | `stop sound` / `stop music` | A | NS 的 `stop` 作用对象需按实测确认 |
| `mp3vol` | 音量 | `$ renpy.music.set_volume(v, channel="music")` | A | — |
| MIDI (`*.mid`) | MIDI 音乐 | 预渲染为 OGG 后 `play music` | C | Ren'Py 不支持 MIDI，必须离线渲染；音色差异需用户确认 |
| 声道/声道分离 | 左右声道 | `renpy.music.set_pan()` / 多 channel | C | 仅在原作真的用到时实现 |

规则：BGM 一律走 `music` channel；播放/停止/循环/淡入淡出分别记录，不要只记"用了哪首曲子"。

### 声道编号：`dwave`/`dwavestop` 的第 1 个参数就是通道

NScripter 的 `dwave n,"se\x.ogg"` 里 `n` 是**混音通道号**，不是"第几个音效"。原作脚本会用 `1+%SENUM`（轮转 5 个通道）、`18`（语音）、`19`（BGM 交叉淡入）这类表达式，`dwavestop n` 也只停对应通道。

演出层的映射是固定的：

| 通道号 | Ren'Py 通道 | 说明 |
|---|---|---|
| 18 | `voice` | 语音，与 `voice` 语句共用 |
| 19 | `sound` | 循环音效 / BGM 淡入用 |
| 1–32 | 预注册 `ns<n>`（init 里建好） | 每通道独立，`ns_se_stop(n)` 只停这路 |
| 其他 n | 退回 `sound` 并登记一次 | 超出预注册范围时降级，宁可打断也不崩 |

**通道只能在 init 里注册。** Ren'Py 的 `renpy.music.register_channel()` 在运行期调用会直接抛
`Exception: Can't register channel outside of init phase` —— 实测踩过：原作 `dwave 1+%SENUM`
在第一次播放音效时就把游戏崩在 `ns_se()` 里。所以演出层把 `ns1..ns32` 一次性注册好，
运行期只做「通道号 → 通道名」的查表，查不到就退回 `sound`。

所以：

- 不要把 `dwave` 一律翻成 `play sound`——那样多路音效会互相顶替。
- `chvol n,vol` → `ns_setvol(n, vol)`（演出层负责 0-100 → 0-1）。
- 包装层 `*loop`/`*sloop`/`*loopfade` 的音量分支（`%G5` 语音开关、`%G10` SE 音量档）由 `ns_w_loop`/`ns_w_sloop` 保留，别绕过。

### 过场动画：`mpegplay` 必须转 VP8

`mpegplay "movie\x.mpg",1` → （`scripts/ns_movies.py` 转 webm）→ `$ ns_movie("x")` → `renpy.movie_cutscene`。

**只能是 VP8 + Vorbis。** Ren'Py 8.5.3（Windows 官方 SDK）播 VP9 的 webm 时 `movie_cutscene()` 永久阻塞：黑屏、无异常、`log.txt` 干净、CPU 接近 0，表现为「卡死在开场动画」。实测同一源转 VP8 后正常播完返回。

因此：不要手工 `ffmpeg` 转 webm（容易带 VP9 默认值）；用 `ns_movies.py`，它会固定 `-c:v libvpx` 并在跳过已有文件前用 ffprobe 复核编码；验收时跑 `ns_movies.py <游戏目录> <工程 game 目录> --verify`，全部 `vp8` 才算过。全量走线探针会打桩 `movie_cutscene`，动画播不出来它查不到。详见 `assets_contract.md` 4.8。

## 五、变量与运算

| NS | 官方语义 | Ren'Py 官方写法 | 档 | 差异 |
|---|---|---|---|---|
| `%n` / `$n` | 数值/字符串变量 | `default <id> = 0` / `""` | A | 建 `source_name` 映射，模块里只用语义名 |
| `?n` / `dim ?n,N` | 数组 | `default <id> = [0]*N` | A | 下标均从 0 起 |
| `numalias 名,N` | 变量别名 | 直接用语义变量名 | A | 别名表写进 catalog |
| `mov/add/sub/mul/mod` | 四则 | `= += -= *= %=` | A | — |
| `div` | **整数除法，小数点以下舍去**（官方「小数点以下切り捨て」） | `$ v = int(a / b)` | B | **不能用 `//`**：Python `//` 对负数是向下取整，NS 是截断，差 1 |
| `inc`/`dec` | 自增自减 | `+= 1` / `-= 1` | A | — |
| `itoa` / `atoi` | 数字↔字符串 | `str()` / `int(float(s))` | B | `atoi` 遇非数字的行为需对齐 |
| `rnd %v,N` | **0 ～ N-1** 的随机整数（官方「０～（二番目のパラメータ－１）」） | `renpy.random.randint(0, N-1)` | A | 端点已确认：**上界 N 取不到**。必须用 `renpy.random` 而非 Python `random`，前者配合 rollback |

## 六、系统功能

| NS | 官方/实际语义 | Ren'Py 官方方案 | 档 |
|---|---|---|---|
| `save` / `load` | 存读档 | 原生 save/load（[save_load_rollback](https://www.renpy.org/doc/html/save_load_rollback.html)） | A |
| `lookback` | 历史回想 | 原生 C 键 + `config.history_length`（[history](https://www.renpy.org/doc/html/history.html)） | A |
| 自动播放 / 跳过 | — | 原生 preferences / `config.allow_skipping` | B |
| 设置界面 | — | 原生 preferences；独有项用 persistent + 自定义 screen | B |
| `systemcall` | 调外部程序 | 无对应 | C |
| CG 鉴赏 | — | `Gallery`（官方 [rooms.html](https://www.renpy.org/doc/html/rooms.html)） | B |
| 音乐鉴赏 | — | `MusicRoom`（同上） | B |
| 场景回想 | — | `renpy.call_replay` / `Replay` action | B |
| 地图选择 | — | `imagemap` / `imagebutton` screen | C |

C/B 类的统一实现要求和陷阱见 [系统功能映射](system_features.md)。

## 七、查表流程

```text
读到一条 NS 语句
  ↓
查本表
  ├─ A → 用原生写法，不写自定义代码
  ├─ B → 用原生 + 调整参数，把差异写进 result.md
  └─ C → 查 catalog.features
  │        ├─ 已有 → 调统一 API
  │        └─ 无   → 登记 issue，交公共负责人，不在本模块另造
  └─ 查不到 → 登记 issue（原文位置 + 官方依据缺失），先做无关部分
  ↓
写代码时按 [写法规范](conventions.md) 加 source 注释
```

## 八、必须标注的偏差

以下差异要么做不到、要么需要用户拍板，一律登记，不要默认忽略：

| 偏差 | 依据 | 处理 |
|---|---|---|
| `wait` 的硬暂停 vs Ren'Py 建议 | `hard=True` 官方建议避免 | 按原作意图选，记录理由 |
| 一页多行 → 多条 say | 结构差异 | 三方案择一记录 |
| 效果编号非通用 | effect 由作品自定义 | 逐作品实测 |
| 立绘锚点 | 官方未定义像素 | 实测校准 |
| `div` 负数是截断 | 官方"舍去" | 用 `int(a/b)` |
| MIDI 音色 | Ren'Py 不支持 MIDI | 离线渲染 + 用户确认 |
| `fchk`/`lchk` 近似 | 判的是 image/label 而非"分支" | 必要时改显式布尔 |
| 硬折行断点 | 23 列 vs 容器软折 | 记录，接受需用户确认 |
