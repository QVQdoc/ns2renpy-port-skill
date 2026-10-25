# 素材与演出层契约（assets_contract）

本文件规定「素材怎么进 Ren'Py、演出怎么落到画面上」。它解决的是两类反复出问题的移植：

1. **素材层每作手搓**：把 `GROUPS = [("bg"), ("chr"), ("ev")]` 写死在一次性脚本里，换个游戏就重写一遍；路径、spec、蒙版处理全靠当时那一次 AI 的临场判断，无法复用也无法核对。
2. **把 NS 的分层模型照抄成 `scene` / `show`**：`scene bg street` 会把立绘一起清掉；立绘图（带 `:a;` 蒙版、1166×600 双半幅）被当成普通 PNG 直接显示，人物带着绿幕方块和遮罩半幅。

对应的三个脚本 + 一个运行时：

| 文件 | 作用 | 谁维护 |
|---|---|---|
| `scripts/nsassets.py` | 素材普查：脚本里的引用 → `assets_manifest.json` + `assets_report.md` | 工作流（通用） |
| `scripts/convert_assets.py` | 按 manifest 转图、拆蒙版、抠键色、切分割、生成 `port_images.rpy` / `port_wrappers.rpy` | 工作流（通用） |
| `assets/ns_stage.rpy` | 演出层运行时（`ns_bg` / `ns_chr` / `ns_ev` / `ns_black` / `ns_se` …） | 工作流（通用） |
| `scripts/nsstage_migrate.py` | 把旧流程的 per-game 舞台 API 调用改写成 `ns_*` | 工作流（通用） |

**禁止**在具体工程里重写上面任何一个。工程里只允许出现「数据」（manifest、由脚本生成的 `port_images.rpy`）和「桥接」（`port_variables.rpy` 里的默认值、设置界面同步）。

---

## 1. 标准顺序

```bash
cd <任务目录>
python <workflow>/scripts/nsassets.py "<原作目录>" --script 0.txt \
       --out port/assets_manifest.json --report port/assets_report.md
python <workflow>/scripts/convert_assets.py "<原作目录>" <工程>/game \
       --manifest port/assets_manifest.json
python <workflow>/scripts/nsstage_migrate.py <工程>/game --apply    # 只对旧工程需要
python <workflow>/scripts/nsport_lint.py <工程>/game --json port/lint_report.json
```

`nsassets.py` 的输出是**唯一事实来源**：转换器不自己猜目录、不自己猜文件名，全部按 manifest 走。普查报告里 `missing=0` 才能进阶段 3。

---

## 2. NS 素材引用的语法（必须先看懂，否则查不出问题）

NScripter 脚本里的素材引用形如：

```
_bg "bg\"+$w0+".bmp",10,500      ; 背景，变量拼文件名
ld c,":a;chr\"+$w0+".bmp",10,300 ; 立绘，带 :a; 蒙版说明
lsp 0,":c;ev\01.bmp",0,0         ; 分散精灵
```

- **反斜杠是路径分隔符，不是转义符**。`"bg\"+$w0+".bmp"` 里第一个 `"+` 之前是 `bg\`；写成 Python 正则时不能按转义处理，否则整类素材会被漏掉。
- `":...;"` 是 **spec 前缀**，语法 `<flags>/<params>`，`;` 结束，后面才是绝对/相对路径。

### spec 语义

| spec | 含义 | 转换后的处理 |
|---|---|---|
| `:a;` | **蒙版对**：同一张图里「左半 = 图像、右半 = 遮罩」 | 裁左半做图，右半做 alpha |
| `:l;` | 左右翻转 | 水平镜像 |
| `:#RRGGBB;` | 键色（该颜色要透明） | 抠掉该色 |
| `/N,dx,dy;` | 分割：图里横向切 N 格 | 切成 `name_c1…name_cN` |

spec 可以组合：`:a/2,0,3;`（蒙版对 + 分割 2 格）、`:#00FF00/2,0,3;`（键色 + 分割 2 格）、`:a/10,50,0;`。

`/N` 的**第 3 个参数语义未确认**（可能是间距/锚点/帧数），转换器按 `N` 横切并在报告里写明「第 3 参数语义未确认，按横切处理」。验收时若发现切错，按 `# ISSUE-xxx` 记录并在工程里单独处理，不要改转换器的默认行为。

### 本例实测（`触装天使セリカ`）

| 类别 | spec 分布 | 说明 |
|---|---|---|
| `chr` 57 张 | 全部 `:a;` | 尺寸三档 822×600 / 854×600 / 1166×600，即半宽 411 / 427 / 583；左半角像素 `#00FF00`，右半 `#000000`~`#FFFFFF` |
| `ev` 106 张 | `:c;` | 800×600，无几何影响（`:c;` 只表示「无蒙版、居中」） |
| `bg` 15 张 | `:c;` | 800×600 不透明，键色占比≈0 |
| `sys/config/top` | `:c;` `:a;` `:#00FF00` `/2,0,3` `/10,40,1` | UI 素材两套写法并存 |

**蒙版方向判定不能靠猜**：`nsassets.py` 比较两组的「暗像素占比」与「非键色占比」，两者接近时判 `dark-opaque`（黑=不透明、白=透明），否则 `light-opaque`（白=不透明）。本例 57 张全部 `dark-opaque`、`overlap=0.976`。

---

## 3. manifest 结构（`port/assets_manifest.json`）

```json
{
  "game_root": "...", "scripts": ["0.txt"], "screen": [800, 600],
  "assets": [
    {"id": "chr/s01_a", "kind": "chr", "dir": "chr", "name": "s01_a",
     "spec": ":a;", "spec_raw": ":a;", "mask": true, "flip": false,
     "key": null, "cells": 0, "size": [1166, 600],
     "mask_pair": true, "mask_orient": "dark-opaque", "overlap": 0.976,
     "sources": [{"script": "0.txt", "line": 1535}], "status": "inspected"}
  ],
  "audio": [{"kind": "bgm", "name": "bgm01", "dir": "bgm", "sources": [...]}],
  "wrappers": [{"name": "bg", "params": [{"name": "$w0"}], "ops": [...],
                "body_script": "0.txt", "body_line": 865}]
}
```

- `kind` 决定 Ren'Py 的 image tag：`bg`→`bg`、`chr`→`chr`、`ev`→`ev`、其余按目录名。**tag 是分层的基础**，不要改。
- `status` 四选一，对应 SKILL.md 阶段 1 的素材检查状态。
- `wrappers` 是脚本里的 `defsub` 定义，转换器据此生成包装层。

---

## 4. 转换规则

### 4.1 蒙版对（`:a;`）

```
原图 [L: 图像 583×600][R: 遮罩 583×600]
mask_orient = dark-opaque  →  alpha = 255 - mask亮度（黑=不透明）
mask_orient = light-opaque →  alpha = mask亮度（白=不透明）
```

只取左半为图像，右半丢弃。RGB 在透明区用邻域渗色（`_bleed_rgb`，5 轮 3px）**填满**，否则缩放/位移时采样到透明像素的 RGB 会出现绿边。

### 4.2 键色（`:#RRGGBB`）

采样全图该色像素占比：`< 0.10` 判「画面用色」不抠（本工程的 `config/cnb_01.bmp` 就是这样，强抠会把 UI 抠穿）；否则把差异 < 12 的像素抠成全透明（`difference` 取最亮通道 + 阈值）。

### 4.3 分割（`/N`）

横向等宽切 N 份，输出 `name_c1…name_cN`（转换器实际用 0 基 `_c0`），同时生成 `image <kind> <name>_c0 = ...`。

**顺序有讲究：先切格，再拆蒙版。** `:a/2,0,3;` 这种「带蒙版又带分割」的素材，布局是每格自己
一对 `[图像|遮罩]`：`[图|罩][图|罩]`。若先把整图对半拆，遮罩会横跨两格取，得到的 alpha 整体错位
半格 —— 本作标题按钮就是这样：绿底留下、按钮本体发虚，`top0N_c1.png` 甚至直接就是遮罩本身。
判据：`宽 % (2 × 格数) == 0`，且每格宽度 ≥ 8px。

### 4.4 谁说了算：脚本 spec > 像素探测

像素探测（右半是否近似二值、暗部是否与左半非键色区重合）只用来**补**没有 spec 的素材。
一旦脚本明确写了 spec，就按 spec：

- 写了 `:a;` → 按蒙版对拆（哪怕像素判据不充分，例如 24x10 的小图标，那是样本太少不是没蒙版）
- 写了 `:c;` / `:#RRGGBB;` → **不拆蒙版**，哪怕像素长得像蒙版对

第二条例子的反例很典型：`sys/tlanime.bmp`（4240x252，`sys/01.bmp` 的动画条）每格 424 宽，
横切两半确实「像」图+遮罩，但它其实是 10 帧动画（`lanime`），按像素判会把每一帧都拆碎。
同理 `sys/wb_*.bmp` 这类 60x15 的小按钮，spec 是 `:a/2,0,3;` 就必须按格拆。

### 4.5 蒙版方向判不出时怎么办

manifest 的 `orient` 可能是 `unknown`（整图不是简单双倍宽时判不出来）。**此时不能当成
light-opaque 处理** —— 那会把按钮抠反：底色留下、本体透明。转换器的做法是：图半若有键色，
就比较「alpha = 255-遮罩」与「alpha = 遮罩」哪一个更符合「键色区 = 透明区」，取更吻合的那个。

### 4.6 命名

`01`、`1a` 这类数字开头的名字在 Ren'Py 里不是合法标识符 → 统一补前缀 `n`（`01` → `n01`）。**改名只发生在 image 名上**，manifest 里的原始 id 保持原样。

### 4.7 音频

只拷 `--audio` 指定的目录（默认 `bgm,se,voice`）到 `game/audio/<目录>/`；已存在且大小相同则跳过。movie 不自动拷（体积大、需要 `renpy.movie_cutscene` 单独处理，见 4.8）。

### 4.8 过场动画：`mpegplay` → webm，**必须 VP8**

`mpegplay "movie\x.mpg",1` 在 Ren'Py 侧对应 `renpy.movie_cutscene("movie/x.webm")`（演出层
`ns_movie(name)`），转换用 `scripts/ns_movies.py <游戏目录> <工程 game 目录>`。

**编码必须是 VP8 + Vorbis。** 实测 Ren'Py 8.5.3（Windows，官方 SDK 自带解码器）播 **VP9**
的 webm 时 `renpy.movie_cutscene()` **永久阻塞**：画面停在黑屏、不抛异常、不超时、`log.txt`
里一行错误都没有，整个游戏看起来就是「卡死在开场动画」，而且 CPU 几乎为 0，很容易误判成
死循环或资源缺失。

所以 `ns_movies.py` 的幂等判据不能只看「目标比源新」——那样一个手工 `ffmpeg` 命令做出的
VP9 文件会被安静跳过。现在的做法是跳过前先 ffprobe 复核：

```
[skip] opening（已存在、编码 vp8，可播）
[redo] opening（已有文件不可播：VP9：Ren'Py 8.5 的 movie_cutscene 会永久阻塞（实测），必须重转 VP8）→ 重转
```

验收清单里加一条只查不转的：

```
python scripts/ns_movies.py <游戏目录> <工程 game 目录> --verify
# [ok  ] opening.webm  vp8  vorbis  71.0s
# 共 5 个 webm，问题 0 个
```

顺带一个排查手法：动画「卡住」时在 `renpy.movie_cutscene()` 前后各写一行文件日志
（`open(os.path.join(config.basedir, "_mprobe.txt"), "a")`），如果只有 before 没有 after，
就是解码器阻塞而不是脚本死循环。

---

### 4.9 动画条（spec 第 2 参数 = 每格毫秒）

`:c/10,40,1;` 这种 spec 的第二个参数是**每格间隔（ms）**，第三个参数语义未确认但不影响转换。
转换器据此判定「动画条」：**格数 > 1 且第 2 参数 > 0**。只看格数会把按钮状态（`:a/2,0,3;`，第 2 参数是 0）误当成动画。

对每个动画条，`port_images.rpy` 除了单帧 `image <目录> <名>_c0…_cN`，还会生成两个可播的 image：

```renpy
image sys tlanime_anim:   # 播一遍，停在最后一帧
    "sys tlanime_c0"
    pause 0.040
    ...
image sys tlanime_loop:   # 循环播放（待机/闪光）
    ...
    repeat
```

并在 `NS_STRIPS` 里登记 `{"cells": 10, "delay": 0.040}`。剧情/流程层用演出层的
`ns_strip(group, name, x, y, loop=False)` 播放，**不要**在 `.rpy` 里手写十几行帧序列，
也不要只 `show` 单帧 —— 后者看起来就是「动画没实现」。

**这条最容易犯的错：拿一张静态帧去替代动画条。** 本作开场 LOGO 就是例子：早期一次性脚本
`convert_ui_assets.py` 把 `sys/01.bmp` 直接存成 `logo.png`，于是移植版只剩「落定后的那一帧」，
原作「从右滑入 4 段 + 10 格翻转」全丢。判据：源脚本里同一个素材既有 `lsp/lsph` 又带
`msp`/`vsp`/`csp`/`waittimer` 的组合，就一定是在演，静态图替代不了。

**手写代码里怎么称呼它**：转换器会把素材名归一化成合法 image 名（`sys\01.bmp` → `sys n01`、
`chr\m02_E.bmp` → `chr m02_e`），但**调用点可以照原作写**：`ns_strip` / `ns_show` 内部有
`ns_safe()` 归一化，先按原样试、再按归一化名试（`ns_strip("sys", "01", ...)` 能命中 `sys n01_anim`）。
这是运行期兜底，不是让你故意写错——生成代码里用的仍是归一化名。

## 5. 生成文件契约

### 5.1 `port_images.rpy`（自动生成，勿手改）

```renpy
init -10 python:
    NS_STAGE = {
        "screen": (800, 600),          # 原作画面尺寸，坐标换算基准
        "image_root": "images/ns",
        "kinds": {"bg": 15, "chr": 57, "ev": 106, ...},
        "mask_assets": 91,             # 拆过蒙版的张数，验收用（本作 91/411）
        "effect_flag": "%G1",          # 演出开关变量（见 5.3）
    }
image bg street_c = "images/ns/bg/street_c.png"
image chr s01_a = "images/ns/chr/s01_a.png"
```

`image <kind> <name>` 两段式命名是**分层契约的一部分**：Ren'Py 的 tag 取第一段，所以 `bg`/`ev` 共用背景层、`chr` 独占立绘层。

文件末尾还有动画条段（见 4.9）：`NS_STRIPS` 注册表 + `<名>_anim` / `<名>_loop` 两个 image。它们是生成物，改素材要重跑转换器，不要在工程里手写帧序列。

### 5.2 `port_wrappers.rpy`（自动生成，勿手改）

每个 NS `defsub` 生成一个 `ns_w_<name>(...)`，逐行带 `# src:<脚本>:<行号>`，条件表达式翻成 Python（`%G1`→`store.ns_g1`、`=`→`==`、`&`→`and`）。翻译不了的指令不会静默消失，写进 `assets_convert_report.md` 的「包装层翻译备注」。

包装层用到的原作变量（`ns_g1` 演出开关 / `ns_g5` 语音开关 / `ns_g10` SE 音量档 / `ns_mnum` 当前 BGM / `ns_senum` SE 轮转 / `ns_w11`）由 `ns_stage.rpy` 在 init 时保证存在。要让它们进存档、绑设置界面，在 `port_variables.rpy` 用 `default` 定义同名变量（不要用 `default` 定义两次，那会报 "defined twice"）。

### 5.3 `ns_stage.rpy` 运行时 API

| 函数 | 对应 NS | Ren'Py 实现 |
|---|---|---|
| `ns_bg(name, dur)` | `_bg "bg\x.bmp"` | `show bg x`（tag `bg`）+ 过渡，**并清立绘** |
| `ns_ev(name, dur)` | `_bg "ev\x.bmp"` | `show ev x`（**tag `bg`**），**并清立绘** |
| `ns_black(dur)` | `_bg black` | 全屏黑 Solid，**tag `bg`**，**并清立绘** |
| `ns_chr(slot, name, dur)` | `ld c,":a;chr\x.bmp"` | `show chr x` + `ns_slot_tf(slot)` |
| `ns_chr_clear(slot, dur)` | `cl c` | `hide chr` |
| `ns_sprite(layer, name, x, y)` | `lsp n,"file",x,y` | 独立 tag `spN` + `ns_abs(x,y)` |
| `ns_strip(group, name, x, y, loop=False)` | `lsph n,":c/10,40,1;file",x,y` | 播 `port_images.rpy` 生成的 `<名>_anim` / `<名>_loop`（见 4.9） |
| `ns_hide_all(dur)` | — | 清 `bg` / `chr` / 所有 `spN` |
| `ns_bgm(name)` / `ns_bgm_stop()` | `bgm "bgm\bgmNN.ogg"` / `bgmstop` | music 通道 |
| `ns_se(name, ch)` / `ns_se_loop` / `ns_se_stop` / `ns_se_stop_all` | `dwave ch,"se\x.ogg"` / `dwavestop` | 通道号 → 通道名查表；1–32 用 **init 时预注册**的 `ns<ch>`，18=voice、19=sound，越界退回 sound |
| `ns_setvol(ch, vol)` | `chvol ch,vol` | 0-100 → 0-1 |
| `ns_voice(name)` / `ns_voice_stop()` | 语音通道 | voice 通道 |
| `ns_scale()` | — | 原作尺寸 → 当前分辨率比例 |
| `ns_abs(x, y)` | — | 原作像素坐标 transform |
| `ns_report_missing()` | — | 打印本次运行缺失的素材/音频 |
| `ns_safe(name)` / `ns_variants(name)` | — | 素材名归一化（`01` → `n01`、`M02_E` → `m02_e`）；`ns_show`/`ns_strip` 内部自动用，手写代码照原作名写也能命中 |

**分层要点**：`bg` / `ev` / `black` 全部共用 tag `bg`，互相替换；`chr` 独立。用 `scene` 会清整层，这正是「换了背景立绘消失」的病根。

**但反过来也有坑：`_bg` 会清立绘。** NS 的 `_bg`（背景、CG、黑幕、纯色都走它）不是"只换背景"，它同时清掉 `ld` 上的立绘。原作就是按这个前提写的：

- `0.txt:1572` `black`（立绘 `s02_e` 在位）→ `1574` `bgchr "street_c","s02_i"`
- `0.txt:10677` `black`（立绘 `s03_a` 在位）→ `10684` `bg "room"`，芹香已经在房里说话
- `0.txt:2509` `ev "32a"`（立绘 `s01_b` 在位）→ CG 单独占满画面

作者用的词汇表是：`bg` = 换景（人物随之消失）/ `bgchr` = 换景并带人 / `chr` = 只换人 / `chr ""` = 同一景里人物退场。所以 `ns_bg` / `ns_ev` / `ns_black` / `ns_color` 默认 `clear_chr=True`；很反常的「换景但保留立绘」才传 `clear_chr=False`。`lsp` 的自由精灵（怪物、UI）**不**跟着清——原作对这些一律显式 `csp N`（`0.txt:2259` lsp / `2280` csp）。

**音频通道必须是 init 预注册**：`renpy.music.register_channel()` 在运行期调用会抛 `Can't register channel outside of init phase`（实测：第一次播 SE 就崩在 `ns_se`）。演出层在 `init -5` 把 `ns1..ns32` 建好，运行期 `ns_channel()` 只做查表。

**lint 过了不等于跑得起来**：上面这条崩溃发生时 `nsport_lint` 与 Ren'Py lint 都是 0 error。把 `assets/ns_stage_smoke.rpy` 拷进 `game/`、改掉 SMOKE 段素材名、headless 跑一次，能在进正式路线测试前把这类运行期错误一次性打出来。

### 5.4 剧情模块只能调这些

```renpy
$ ns_w_bg("street_c")           # 原作有 *bg 包装层时，优先调包装层（保留 %G1 分支）
$ ns_w_chr("s01_a")
$ ns_w_music(6)
$ ns_chr("c", "s01_a")          # 没有对应包装层时才直接调运行时
$ ns_ev("01")
```

禁止：

- `scene` / `show` / `hide` 直接操作画面（NS012）
- 调旧 per-game 舞台 API `port_bg/port_chr/port_ev/port_black/port_bgchr/port_music/port_se/port_hide_all`（NS013，用 `nsstage_migrate.py` 改写）
- 在 story 里写 `"images/..."` / `"audio/..."` 裸路径（NS014）

### 5.5 音量：只许有一个控制点（mixer）

NS 的音量是「档位 0-6」模型：`*exec_vol` 里 `bgmvol %G8*12`、`voicevol %G9*12`、`sevol %G10*12`，档 6 直接给 100，开关 `%G4/%G5/%G6=0` 时给 0。**换算成 0-1 就是 `档*12/100`，不是 `档/6`**（2 档 = 24%，不是 33%）。

Ren'Py 有两条互不相干的音量：

| 机制 | API | 谁在改 | 作用 |
|---|---|---|---|
| mixer 音量 | `preferences.set_volume("music"/"sfx"/"voice", v)`，设置界面的滑条就是它 | 玩家 | 和通道音量**相乘** |
| 通道音量（次级） | `renpy.music.set_volume(v, channel=...)` / `Channel.set_volume()` | 脚本 | 再乘一层，**且写进存档** |

**两条都写就一定会出「滑条没用」**：实测旧实现把 BGM 的通道音量压到 0.33，滑条从 100% 拉到 50% 只听到 0.33→0.17，而且老档把这个上限带回来。正确做法：

- 全局音量（原作 `bgmvol`/`voicevol`/`sevol`）→ 只写 mixer，而且**只在第一次运行时写**（`persistent.port_vol_init`），之后完全交给玩家滑条，别每次新游戏都覆盖。
- 读档时把通道级（次级）音量清回 1.0（`renpy.music.set_volume(1.0, channel=...)`），收掉旧档残留。
- 这套东西已经做成通用件 `assets/ns_volume.rpy`：拷进 `game/` 改名 `ns_volume.rpy` 即可，**不要**在每个工程手写一份（要调就调 `port_apply_volume()`，别改里面的算式）。
- `chvol <通道>,<音量>` 这类**单条音轨**的音量才用通道音量（`ns_setvol`），它本来就是次级语义。
- 母带电平要实测：本作 `bgm01` mean −12.6 dB / `bgm05` −9.7 dB，语音 mean −16.5 dB —— BGM 比语音热 4～8 dB，按原作 24% 压下去才平衡；照 `档/6` 写成 33% 听起来还是 BGM 盖人。

---

## 6. 剧情批量翻译（`scripts/ns2renpy_story.py`）

整部剧情要「先跑通再精修」时用它。它读 `port/graph.json` 的标签区间，逐行翻成 Ren'Py，一个标签一个 `game/story/gen_NN_<标签>.rpy`，并出 `port/story_coverage.json` 与 `port/story_convert_report.md`。

**它只做机械翻译，不判断演出意图。**生成物是底稿：模块负责人逐段复检（尤其立绘槽位、过渡、音量分支），改好的模块移进 `port/modules/` 并从 `story/` 删掉，否则下次重跑覆盖。

### 6.1 语法决策（全部是实测踩出来的）

| 源写法 | 生成 | 为什么 |
|---|---|---|
| `bg "street_c"` / `_bg "bg\x.bmp",10,500` | `$ ns_w_bg("street_c")` | 带引号 = 文件；**不要**用「有没有 `\` / `.bmp`」判是否是颜色 |
| `_bg white` / `_bg #FFFF88` | `$ ns_color("white")` / `ns_color("#FFFF88")` | 无引号才是纯色 |
| `bg ""` / `chr ""` | `bg` 生成注释备注；`chr` 原样传 `""` | `*chr` 体里 `if $w0=""` 是**清槽位**，语义不能丢（曾有 86 处被 `safe_name` 兜底成 `"x"`） |
| `_bg "ev\x.bmp"` | `ns_w_ev("x")` | 按子目录分派，不靠命令名猜 |
| `lsp 200,":c;monster\warm.bmp",100,100` | `ns_sprite(200, "warm", 100, 100, group="monster")` | 显示名是 `<目录> <名>`，层号是 tag |
| `if %kaisoumode=1 music 2` | `if store.kaisou_mode == 1:` + 缩进翻译 | 条件与命令在同一行是常态；同行 `:cmd2` 也归入 if 体 |
| `goto *x` / `gosub *x` | `jump x` / `call x` | 标签名不带上 `*` |
| `csel "A",*x,"B",*y` | `menu:` 两项各 `jump` | Ren'Py 原生菜单 |
| 标签区间末尾 | 按 graph 的 fallthrough 补 `jump`，没有则 `return` | 原文靠「顺序往下掉」串场，不补就会直接结束 |

### 6.2 三条硬约束

1. **graph 的 `source.lines` 是闭区间**（`mem8 [10127,10511]` 表示 10127..10511 都在标签内）。按半开区间取会每标签丢最后一行——`mem8` 就因此少了一个 `csel`，菜单从 9 个变 8 个。
2. **`jump` / `return` 之后的源行不可达**，原作里同样不可达（如 `0.txt:23867 goto *happyend` 后紧跟「第一章预告」）。生成时丢弃并计入 `csel 死行`，否则 Ren'Py lint 报 Unreachable Statements。
3. **素材名一律走 `safe_name` 归一化（含转小写）**：NS 在 Windows 上找文件不分大小写（脚本写 `chr "m02_E"`、磁盘是 `m02_e.bmp`），Ren'Py 的 image 名分大小写，不归一会「素材转好了但运行期报缺图」。

### 6.3 覆盖报告怎么看

`story_convert_report.md` 逐标签列出：源行区间、`say/旁白/语音/指令/菜单/备注/未翻译/死行` 计数、缺语音 ID、跳过的标签（如 `mem34` 属于标题流程）、按原作本就不执行的死行清单。**`未翻译` 必须为 0**；`缺语音` 逐条对照 `voice/` 目录确认是真缺还是改过名。

---

## 7. 无法自动翻译的部分（必须人工处理并在报告里登记）

| 现象 | 原因 | 处理 |
|---|---|---|
| `goto *loopfade` / `*sloopfade` | 淡出是「mov 音量 → 循环 dwavevol → dwavestop」的手写缓动 | 目前翻成 `ns_voice_stop()` / `ns_se_stop(fade=1.0)`，听感差异登记 issue |
| `print 1` / `csp 166` / `textoff` | 文本窗开关与点击等待，Ren'Py 由 `say` 承担 | 不生成代码；若原作靠它做「先关窗再等一下」，需在模块里补 `pause` |
| `lsp` 坐标含变量 | 坐标在运行时算出 | `ns_sprite` 只接受字面坐标，其余登记 issue |
| 变量拼路径（`"bg\"+%w0`） | 文件名在运行时决定 | 包装层能保留 `p0`；若拼接形态无法归约成单变量，`arg_to_py` 返回 None 并在报告里标注 |
| `/N` 的第 3 参数 | 语义未确认 | 按横切处理，验收时目视核对 |
| `cgm` 等鉴赏类 UI | 布局与解锁逻辑属系统功能 | 见 `system_features.md` |

---

## 8. 验收清单

| 检查 | 期望 |
|---|---|
| `nsassets.py` 统计行 | `missing=0`；`mask` / `cells` / `wrappers` 数量与脚本实际相符 |
| `assets_report.md` | 每条蒙版拆分都写了方向与半宽；跳过/缺失逐条列出 |
| `convert_assets.py` 统计行 | 图像条目数 = manifest 的 image 条目数；音频拷贝数与 `--audio` 目录相符 |
| `nsport_lint.py` | `0 error`；story 里没有 NS012/NS013/NS014；`NS016` 为 0（引用的素材名确实能命中） |
| Ren'Py SDK lint | 无 error；image 总数与定义数一致 |
| `nswalk.py` | `missing_assets` 为空、`bad_runs` 为空、未进入的标签只剩确实到不了的那几个 |
| 目视 | 立绘无绿幕方块、无遮罩半幅、无绿边；换背景不掉立绘；CG 覆盖背景但立绘按原作保留 |

---

## 9. 界面层：GUI 尺寸、中文化、图鉴

原作是 800x600 时，**不要**拿 Ren'Py 的 1280x720 模板改数字。模板靠 `gui.scale()` 缩放，手改 `gui.init(800, 600)` + 补一个恒等的 `scale()` 的后果是：导航项全叠在左上、存档第 3 列跑出屏幕。

### 9.1 用 launcher 生成目标分辨率的 GUI

```powershell
$env:APPDATA='<工程上级>\_appdata'
renpy.exe <sdk>\launcher generate_gui <工程目录> --width 800 --height 600 `
    --accent '#00b8c3' --template '<sdk>\gui' --start
```

- `--template` 指到 **`<sdk>\gui`**（代码会再拼 `\game`）；指到 `\game` 会报 `...\game\game does not appear to be a Ren'Py game`。
- 生成物里**不应再有 `gui.scale(`**：`gui7/code.py` 的 `remove_scale()` 已把值算成整数。
- 生成器只产 24 张图，`button/slot_*background`、`bar/*`、`slider/*`、`scrollbar/*`、`check_*`/`radio_*` 要自己补；缺了会在打开游戏菜单时抛 `DynamicImage ... could not find image`（不是 lint 能查到的）。
- `radio_*_foreground` / `check_*_foreground` 的**宽度必须等于** `gui.radio_button_borders` / `gui.check_button_borders` 的左边距，否则标记压在文字上。
- 换分辨率后，旧存档的缩略图（上一套 `config.thumbnail_width`）会挤爆存档格，把旧档移走另存，不要删。

### 9.2 界面中文化

Ren'Py 自带界面的英文都是 `_("...")`。**不改 `screens.rpy`**（下次重新生成就被冲掉），拷 `assets/ns_i18n_cn.rpy` 进 `game/`，`options.rpy` 里 `define config.language = "chinese"`。带占位符的条目（`Page {}`）译文必须保留 `{}`。

### 9.3 图鉴（`scripts/nsgallery.py` → `gallery.json`）

```powershell
python scripts\nsgallery.py <游戏目录> --port port    # → port/gallery.json + gallery_report.md
```

从脚本里抽三样：格子坐标（原作是 `lsp N,":c/2,0,3;sum\x.bmp",x,y` 的硬坐标）、缩略图名、解锁条件。解锁条件照原作映射：

| 原作 | 数据 | Ren'Py |
|---|---|---|
| `if fchk "ev\01.bmp"` | `kind: "fchk"` | `renpy.seen_image("ev n01")` |
| `if lchk "*mem35"` | `kind: "lchk"` | `renpy.seen_label("mem35")` |

`assets/ns_gallery.rpy` 只负责画：读 `gallery.json`、按数据铺格子、翻页、点赞。四条硬约束：

1. 图名要用 `ImageReference(tuple(name.split()))`。`Image("cgm cgm_prev_c0")` 会把字符串当**文件名**，报 `Couldn't find file`。
2. 回想回放是 `kaisou_mode = 1` → `renpy.call_in_new_context(label)` → 场景自己在 `if %kaisoumode=1 return` 处返回。**不能用 `jump`**：原作 `*mem0` 末尾没有 `return`，会 fallthrough 到 `*mem35`（带 `mpegplay`），用 jump 就回不来了。
3. 多图 CG（原作 `mov $w0,"04a/04b/04c/04d"`）在数据里是数组，查看器要能左右翻。
4. **翻页状态放 store，不要用 `SetScreenVariable`**。图鉴屏是被 `use ns_gallery(kind)` 嵌进 `port_cg` / `port_mem` 里的，屏幕变量写在「当前屏幕」的 scope 上，而 `default page = 0` 挂在被 use 的那一层，父屏一重算就回到 0——表现是「点上一页/下一页毫无反应」，而同屏的 `Return()`（退出）正常，因为退出不需要屏幕状态。做法：`default ns_gal_page_index = {"cg": 0, "mem": 0}` + `Function(ns_gal_turn, kind, ±1)`，动作里改 store 再 `renpy.restart_interaction()`。

另外两条照原作来的细节：

- 「上一页 / 下一页 / EXIT」在原作里是三个 sprite（`lsp 100/101/102`，坐标 522,27 / 667,27 / 753,44），尺寸只有 62x15 和 37x37。**页码 "Page N/3" 是画在每页背景图里的**，所以背景能取到对应页那张时不要再叠自己的页码文字，否则会压住 "CG MODE" 标题。
- 鼠标不好点这么小的按钮，屏里顺手加 `key "K_LEFT"/"K_RIGHT"`、`key "mousedown_4"/"mousedown_5"`（滚轮）；按钮用 `imagebutton` 配 `idle`/`hover` 两张（转换器已经产出了 `_c0`/`_c1`），点上去有反馈。

音乐模式直接按 `audio/bgm/` 列曲目并跳过缺失文件（本作 `bgm09` 就没有），不要用剧本里的 `music N` 编号硬映射。

### 9.4 验收方式

界面层没有 lint 能覆盖的检查，必须**实拍**：`renpy.queue_event("game_menu")` 后 `renpy.screenshot()`，逐个看存档/读档/设置/历史/图鉴。`renpy.show_screen("save")` 单独显示会错位（stock 工程也一样），不能作为布局证据。
