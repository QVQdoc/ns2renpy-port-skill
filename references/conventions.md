# 移植代码写法规范

目的只有一个：**任何一行 Ren'Py 代码，都能反查到它在 NS 原作里的出处，并且能被机器检查。**

分模块移植最大的维护成本不在第一次写完，而在半年后有人回来改一处演出时，不知道这段代码对应原作哪一段、是不是有人故意改的。规范就是用低成本换掉这个成本。

配套：[功能对照表](ns_to_renpy_map.md)（决定怎么写）、`scripts/nsport_lint.py`（检查有没有照做）。

## 一、总原则

1. **每条转换来的语句带来源注释**，可反查原作。
2. **公共定义只有一处**，模块里不重复定义角色/变量/素材/screen。
3. **位置、过渡、速度用语义名**，不写裸数字。
4. **偏差必须显式**：做不到或不去做的，写 issue，不静默近似。
5. **能被 grep 检查**：规则尽量写成固定模式。

## 二、文件组织

```text
game/
  ns_stage.rpy            演出层运行时（从工作流拷入，勿改）
  ns_gallery.rpy          图鉴运行时（CG/回想，从工作流拷入，勿改）
  ns_volume.rpy           音量桥接（原作 0-6 档 → mixer，从工作流拷入，勿改）
  port_i18n.rpy           界面中文化覆盖层（从工作流 assets/ns_i18n_cn.rpy 拷入，勿改）
  port_characters.rpy     角色定义（define Character）
  port_variables.rpy      共享变量（default，含 persistent）
  port_images.rpy         素材定义（image，由 convert_assets.py 生成）
  port_wrappers.rpy       原作 defsub 包装层（由 convert_assets.py 生成）
  port_transforms.rpy     位置/移动 transform
  port_transitions.rpy    过渡效果映射
  port_screens.rpy        screen 与自写功能
  port_functions.rpy      公共函数
  gallery.json            图鉴数据（由 nsgallery.py 生成）
  images/ns/<目录>/       转换后的素材（由 convert_assets.py 生成）
  audio/<目录>/           拷贝的音频（bgm/se/voice）
  story/
    common_01.rpy         剧情模块（只写剧情）
    yuki_01.rpy
```

硬规则：

- `port_*.rpy` 归公共负责人；剧情任务**不得修改**。
- `port_images.rpy` / `port_wrappers.rpy` / `gallery.json` / `images/ns/` 是**生成物**，要改就改 manifest 或重跑对应脚本，不许手改。
- `ns_stage.rpy` / `ns_gallery.rpy` / `ns_volume.rpy` / `port_i18n.rpy` 是**通用件**（工作流 `assets/` 下），整个拷进来用；要改就改工作流里的原件再同步，别在工程里分叉。
- 音量只许有一个控制点：`ns_volume.rpy` 把原作档位写进 mixer；**不要**再写通道级音量（`renpy.music.set_volume`），那会把设置界面的滑条压成「调了没用」。
- `story/*.rpy` 归各模块负责人；里面**不得**出现 `default` / `define` / `screen` / `image`。
- 文件名与模块 ID 一致。

## 三、来源注释（核心）

### 格式

```renpy
# src:<源文件>:<起始行>[-<结束行>]
```

例：

```renpy
label school_choice:
    # src:0.txt:150-170

    $ ns_w_bg("school")                      # src:0.txt:150
    $ ns_w_chr("yuki_smile")                 # src:0.txt:151

    yuki "今天要一起回去吗？"                 # src:0.txt:152
```

### 规则

| 规则 | 说明 |
|---|---|
| 每段连续转换块开头写一条块级注释 | 覆盖后面若干条语句 |
| 单条语句可再写行尾注释 | 精确到行 |
| 一条语句在 `src:` 前 5 行内没有块注释 | 视为**未登记来源**，lint 报 NS004 |
| 玩家可见文本必须能追到具体行号 | 台词是最需要反查的部分 |
| 不对应任何原作语句（纯技术代码） | 标 `# src:none` 并说明原因 |

```renpy
# src:none —— Ren'Py 侧新增的初始化，原作无对应
$ renpy.block_rollback()
```

### 为什么值得写

- 复查：改一句台词，能立刻打开原脚本对应行确认。
- 覆盖率：`src:` 注释数量 vs `events.json` 事件数，就是实现覆盖率的粗估。
- 交接：新会话不必重读原始脚本，按注释反查即可。

## 四、label 结构

### 模块入口

```renpy
# ==== 模块 common_01 · 共同线第一章 ====
# 契约版本: 2.0
# 蓝图版本: 2
# 入口: 新游戏开始
# 出口: jump yuki_walk / jump common_evening
label common_01:
    # src:0.txt:1-170
    ...
```

### 出口

每个出口前写一行注释，说明目标与离开状态，便于和 mergepoints.json 对照：

```renpy
    # 出口 e_accept -> yuki_walk | 离开状态: bg=school_gate, music=bgm_daily, yuki_favor+1
    jump yuki_walk
```

### 禁止

- 同一 label 里既有 `jump` 又有 `call` 的出口（返回语义会不一致）。
- 依赖"执行到文件末尾自然结束"来表示结束（Ren'Py 会报错或回退到后续 label），结局必须显式 `return`。

## 五、画面

### 画面只经演出层，不直接 show/scene

`story/*.rpy` 里**不得**出现 `scene` / `show` / `hide`（lint 码 `NS012`）。背景、CG、黑幕、立绘、精灵一律经 `ns_stage`（或原作包装层 `ns_w_*`）调用，理由见 [素材与演出层契约](assets_contract.md) 第 5 节：NS 的分层规则（`_bg` 换背景层并清立绘、`lsp` 精灵要显式 `csp` 才收）只在演出层实现一次，`scene` 是整层清空、语义对不上。

```renpy
# 正确
$ ns_w_bg("street_c")          # 原作有 *bg 包装层，保留 %G1 演出开关
$ ns_w_chr("s01_a")            # 立绘（槽位由包装层决定）
$ ns_chr("c", "s01_a")         # 没有包装层时直接调运行时
$ ns_ev("01")                  # CG
$ ns_black(0)                  # 黑幕

# 禁止
scene bg street_c with dissolve
show chr s01_a at ns_center
hide chr
```

`scene bg xxx` 不只是风格问题：它清整层，而 NS 的分层语义（背景/CG/黑幕共一层、立绘独立、`lsp` 精灵独立）只有演出层实现，绕过去必然出现「该消失的没消失、该留下的被清掉」；`show chr …` 直接显示的是整张素材，绕过了槽位定位与缺失占位。

**`_bg` 会清立绘，这不是演出层的自作主张**：原作脚本就是这么写的——`0.txt:10677` `black`（立绘 `s03_a` 在位）→ `10684` `bg "room"`，芹香已经在自己房里说话了，中间没有任何 `chr ""`。作者用 `bg` 表示"换景、人不在场"，`bgchr` 才表示"换景并带人"。所以别把 `ns_bg` 改回"不动立绘"：那正是「人物在场景切换时没有按脚本消失」。`lsp` 的怪物/UI 精灵相反，不跟着清，要靠原作显式 `csp`。

### 位置只用语义 transform

演出层内部已按槽位处理（`ld l/c/r` → `ns_left/ns_center/ns_right`）。确有需要自己摆位置时：

```renpy
# 正确
$ ns_sprite(3, "badge", 120, 300)     # lsp 3,"badge",120,300

# 禁止：裸坐标
show badge at Transform(xpos=640, ypos=720, xanchor=0.5, yanchor=1.0)
```

- 立绘位置：`ns_left` / `ns_center` / `ns_right`（按实测值定义在 `port_transforms.rpy`）。
- `lsp` 转来的精灵：坐标来自原作时用 `ns_sprite(layer, name, x, y)`；坐标本身是变量的，登记 issue，不要硬凑。

```renpy
# port_transforms.rpy
transform ns_abs(x, y):
    xanchor 0.0
    yanchor 0.0
    xpos x
    ypos y
```

### 过渡效果

过渡由演出层的 `dur` 参数承载（包装层已把 `,10,500` 这类参数换成 `dur`）。需要显式指定时写在调用里：

```renpy
$ ns_bg("park", dur=0.5)      # src:0.txt:320   ; 原 eff=3 实测为慢淡入
```

`port_transitions.rpy` 里放实测出来的 `EFFECT_*` 语义名，供 screen 与特殊演出使用：

```renpy
# port_transitions.rpy
# NS effect 编号 -> Ren'Py 过渡（逐作品实测填写，勿照抄）
define EFFECT_INSTANT     = None
define EFFECT_FAST_DISS   = Dissolve(0.2)
define EFFECT_SLOW_DISS   = Dissolve(0.5)
define EFFECT_BLACKOUT    = Fade(0.3, 0.2, 0.3, color="#000")
```

禁止：

- 在剧情模块里写 `with dissolve` 硬编码（除非已确认所有 eff 都是这一种）。
- 把不确定的 effect 一律当 `Dissolve`——必须登记 issue。

## 六、文本

- 同页多行按 [对照表](ns_to_renpy_map.md) 第三节「一页多行 → 多条 say」的方案处理，**同一项目统一用同一种**。
- 标签必须闭合：`{cps=30}` → `{/cps}`，`{color=#f00}` → `{/color}`。
- 文本里的 `[` `{` 字面量必须转义成 `[[` `{{`。
- 原文里的技术转义（`!d`→`{w=}`）允许改写，**不得改词**。

## 七、音频

```renpy
play music "audio/bgm_daily.ogg" loop fadein 0.5    # src:0.txt:153
stop music fadeout 1.0                              # src:0.txt:310
play sound "audio/se_door.ogg"                      # src:0.txt:155
```

- BGM 一律 `music` channel；音效一律 `sound` channel。不混用。
- `loop` / `noloop` 必须显式写，不靠默认（lint 报警 NS006）。
- 语音用 `voice` 语句，不塞进 `sound`。

## 八、变量

- 所有 `default` / `define` 只在 `port_variables.rpy` / `port_characters.rpy` 里出现。
- 剧情模块里只做赋值，不声明。
- 变量名用语义名；`source_name` 映射留在 catalog，代码里不出现 `n10` 这种原始名。
- 整除一律 `int(a / b)`，禁止 `//`（NS 是截断，Python `//` 对负数向下取整，见 lint NS002）。

```renpy
$ yuki_favor += 1                       # src:0.txt:160
$ ratio = int(hit / total)              # src:0.txt:410  ; 原作 div，截断
```

## 九、screen 与自写功能

- `screen` 只定义在 `port_screens.rpy`；剧情模块只能用 `call screen`。
- 解锁类副作用走统一 API：`$ port_unlock_cg("cg_yuki_01")`，不直接改 `persistent`。
- 详见 [系统功能映射](system_features.md)。

## 十、issue 标记

代码里存在已知缺口的位置，就在该处标记，保证 grep 能找全：

```renpy
# ISSUE-007 : 原作此处 eff=5，实际效果未确认，暂用 Dissolve
$ ns_bg("rooftop", dur=0.3)              # src:0.txt:512
```

- 标记格式固定 `# ISSUE-<三位数> : <一句话>`。
- 同一 issue 出现在多个文件时，编号一致，`issues.json` 里汇总。
- 不允许裸 `# TODO`（lint 报 NS011）。

## 十一、禁止清单

| 禁止 | 理由 | lint |
|---|---|---|
| `show/scene` 行内裸数字坐标 | 无法统一调整、无法 grep | NS001 |
| `$ a = b // c` | NS `div` 是截断，`//` 是向下取整 | NS002 |
| `ns_bg_xxx` 之类旧转换器命名 | 误用旧 mapping 产物 | NS003 |
| 转换语句缺 `src:` 注释 | 无法反查原作 | NS004 |
| `story/*.rpy` 里出现 `default`/`define` | 公共定义重复 | NS005 |
| `play music` 不写 loop/noloop | 行为依赖默认值 | NS006 |
| `story/*.rpy` 里定义 `screen` | 自写功能应唯一 | NS007 |
| 裸 `# TODO` | 缺口不可追踪 | NS011 |
| `story/*.rpy` 里直接 `scene`/`show`/`hide` | 绕过演出层，会清掉立绘层 / 丢失槽位定位 | NS012 |
| 调旧 per-game 舞台 API（`port_bg`/`port_chr`/`port_ev`/…） | 每个工程各写一份，语义不一致 | NS013 |
| `story/*.rpy` 里写 `"images/…"`/`"audio/…"` 裸路径 | 绕过素材层，改名即坏 | NS014 |
| 引用 `images/` 下非 `images/ns/` 的图 | 多为一次性脚本手搓，没有 alpha（立绘带绿幕、按钮绿底外露） | NS015 |
| `ns_sprite`/`ns_strip` 的素材名在 `port_images.rpy` 里找不到 | 运行期只显示占位图、不报错；Ren'Py lint 也看不出（名字归一化由 lint 一并尝试） | NS016 |
| 未实测的 effect 编号直接 `Dissolve` | 静默丢失演出 | 人工 |

## 十二、机器检查

```bash
# 全量检查（默认跳过 screens/gui 等模板文件）
python scripts/nsport_lint.py project/game

# 连模板文件一起查
python scripts/nsport_lint.py project/game --all-files

# 输出 JSON 供 CI / 汇总
python scripts/nsport_lint.py project/game --json lint_report.json

# 只看某类问题
python scripts/nsport_lint.py project/game --disable NS001,NS005

# 列出所有检查码
python scripts/nsport_lint.py --list-codes
```

检查结果分 `error` / `warning` / `info` 三级。**error 必须清零才可进入组装阶段**；warning 要逐条决定"修"或"记录豁免"。

素材/演出层相关的三条（`NS012`/`NS013`/`NS014`）是这套规范落地的主要抓手：它们把「素材怎么进来」「演出怎么落地」从口头约定变成机器可查的 error。`NS015` 是配套的 warning，专门盯「又有人贴了一张 `images/xxx.png`」——这类图通常来自一次性转换脚本，最典型的后果就是立绘带绿幕、标题按钮露出绿底。`NS016` 补的是另一类静默失败：`ns_strip("sys","01")` 里的名字在生成件里是 `sys n01`，运行期只会显示占位图，两条 lint 都是 0 error——所以它按 `safe_name` 规则归一化后再对账一次。

## 十三、人工复查清单

lint 查不出语义，组装阶段仍要人工过一遍：

```text
[ ] 每个 label 的入口注释是否声明了契约版本与出口
[ ] 出口注释是否与 mergepoints.json 的 expected_state 一致
[ ] 是否存在未登记来源的玩家可见台词
[ ] effect 编号是否逐条实测，未确认的是否挂了 issue
[ ] 一页多行的处理方案是否全项目统一
[ ] `wait`（硬等）与 `delay`（可跳过）是否按原作意图区分
[ ] 立绘槽位是否正确（ld l/c/r 与画面位置是否对得上）
[ ] 立绘是否有绿幕方块、遮罩半幅、绿边（转换是否拆了蒙版、抠了键色）
[ ] 黑幕/CG 之后立绘是否还在（分层是否按 NS 的 _bg 语义）
[ ] 是否有模块自造了应该公共唯一的 screen
```

## 十四、与既有格式的关系

- 本规范**取代**旧转换器的输出风格（`ns_bg_a`、统一 `Dissolve`、拍平装载）。旧 [mapping.md](mapping.md) 只作为改转换器时的参考。
- 素材与演出的完整契约（普查、spec、生成文件、API 表）见 [assets_contract.md](assets_contract.md)，本文件只写「写代码时必须遵守的部分」。
- 规范不约束内容：台词、条件、事件顺序仍以蓝图和 events.json 为准。

## 十五、批量生成的剧情文件（`story/gen_*.rpy`）

用 `scripts/ns2renpy_story.py` 整部机械移植时，产出按下面的规矩落地：

```
game/story/gen_01_happyend.rpy
game/story/gen_03_p1.rpy
...
```

- 文件名 `gen_<两位序号>_<标签名>.rpy`，**序号由脚本按 graph 顺序分配**，不要手动改名（重跑会按新顺序重排）。
- 文件头三行固定：来源脚本、生成命令、「自动生成·勿手改」。缺了说明是手写的，别和生成物混在一起。
- 生成物**允许**暂时不满足本规范的部分条目（例如一个标签内没有模块头注释块），但以下三条必须满足，否则视为生成器缺陷：
  - 每条转换语句 5 行内有 `# src:0.txt:<行号>`
  - 不出现裸坐标、`//`、旧 `ns_bg_xxx` 命名
  - story 里不出现 `default` / `define` / `screen` / `image`
- **精修流程**：改哪个标签，就把那个文件移到 `port/modules/<模块>/`、从 `story/` 删掉（同时删 `.rpyc`），并在 `mergepoints.json` / STATUS 里登记。留在 `story/` 的一律当作「还是底稿，重跑会被覆盖」。
- 重跑前先 `git status`／比对差异，避免覆盖人工改动；生成器不保留手改内容。

## 十六、全量走线（`scripts/nswalk.py` + `assets/ns_autowalk.rpy`）

语法检查和演出层冒烟都过了，也不代表剧本跑得通。全量走线是把整条剧情按菜单分支真跑一遍。

```powershell
copy <skill>/assets/ns_autowalk.rpy <工程>\game\
python scripts\nswalk.py <工程> --max-runs 30
del <工程>\game\ns_autowalk.rpy
```

- 探针**必须**在测完删掉：它会 patch `renpy.exports.say/menu`、强制 skip，留在工程里会污染正常游玩。
- 判定标准：`missing_assets` 为空、`bad_runs` 为空、`unreached_labels` 只剩确实到不了的（结局另一侧、纯跳转别名标签）。任何一项不满足都要查，不能用「游戏能启动」代替。
- 探针实现细节（改之前先读注释）：patch 的是 `renpy.exports.menu` 而非 `renpy.display_menu`；主菜单用 `RENPY_SKIP_MAIN_MENU=1` 跳过；覆盖统计挂在 `renpy.exports.say` 与 `config.label_callbacks` 上，因为 fast skip 下 periodic callback 几乎不刷新。
- 驱动**不要**用 `stdout=PIPE` 接 `renpy.exe`：它会留一个继承句柄的子进程，管道不关，读端会一直卡住（实测卡死 5 分钟）。重定向到文件再读尾部。
