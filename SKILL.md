---
name: ns-to-renpy-port
description: 把 NScripter（NScript）引擎的视觉小说系统性移植到 Ren'Py。适用于「NS 游戏转 Ren'Py」「0.txt / nscript.dat 剧本移植」「素材蒙版/动画条转换」「Ren'Py 汉化移植」「把原作功能逐项复刻并验证」这类任务；也适用于只做其中一段（素材普查、演出层、剧情批量翻译、图鉴、打包发布）。输出是可运行、可验证、带覆盖报告的 Ren'Py 工程，而不是一次性的转换脚本。
---

# 全局蓝图驱动的 NS → Ren'Py 重建

## 目标与边界

先理解整个游戏，把理解保存为可检索的蓝图；按剧情结构划分模块，统一公共定义，再分别实现和组装原生 Ren'Py 游戏。

交付可运行的 Ren'Py 工程。原 NS 脚本是剧情、条件、素材和演出行为的依据；无需开发 NS 兼容运行时。保留原文、选项效果、路线关系与可观察行为；实现方式可采用 Ren'Py 原生能力。

## 开始工作

1. 确认可用输入：脚本、资源目录/归档、已有剧情数据、目标 Ren'Py 版本和现有工程。优先利用已提供信息，常规实现选择自行决定。
2. 检查 `port/STATUS.md`。已有项目从记录的下一步继续；新项目按下列阶段开始。
3. 按需读取参考文件：
   - 建蓝图或模块时读 [数据模板](references/blueprint-templates.md)
   - 分配任务时读 [任务提示词](references/rebuild-prompts.md)
   - **写模块代码前读 [功能对照表](references/ns_to_renpy_map.md) 和 [写法规范](references/conventions.md)**
   - **处理素材、立绘蒙版、背景/CG/黑幕切换前读 [素材与演出层契约](references/assets_contract.md)**
   - 划模块时读 [模块粒度指南](references/module_sizing_guide.md)
   - 标汇合点或验证汇合时读 [汇合点验证指南](references/mergepoints_guide.md)
   - 处理存读档/跳过/鉴赏等系统功能时读 [系统功能映射](references/system_features.md)
   - **开工前扫一遍 [实测踩坑清单](references/pitfalls.md)**：那些坑的共同点是 lint 全绿也照样出事

## 工作阶段

| 阶段 | 动作 | 输出 | 转入下一阶段的依据 |
|---|---|---|---|
| 1 全局理解 | 阅读脚本、核对素材、识别剧情及公共功能 | overview、graph、catalog、sources、issues | 全部脚本区间已标记为已读/已解析/未解析/未读；分支、汇合、结局、动态跳转已标明；素材检查状态明确 |
| 2 模块规划 | 按章节、完整事件、主要路线和汇合点分组；统一命名及边界；跑粒度自查 | 模块清单、公共契约、模块任务包、mergepoints | 每个剧情节点有唯一实现归属；每模块通过粒度自查；所有多入边节点已登记为汇合点 |
| 3 公共基础 | 素材普查与转换、实现公共角色、变量、素材、演出层、UI 和被模块调用的功能；自写系统功能 | Ren'Py 公共文件、`port_images.rpy`、`port_wrappers.rpy`、`ns_stage.rpy`、system features | 模块依赖的接口存在且有使用说明；素材普查 `missing=0`；`custom` 状态系统功能已实现 |
| 4 分别实现 | 每次加载公共契约和一个模块包，实现原生剧情 | 各模块 .rpy 及模块完成记录 | 台词、选项、条件、事件、等待原因有对应实现；缺口有具体 issue |
| 5 组装验证 | 合并模块，跑结构检查与汇合点核对，执行 lint 与路线测试 | 完整工程和验证记录 | 静态检查、实际运行、路线覆盖、汇合点状态分别如实报告 |

不要求用户逐阶段批准。数据足够时持续推进；局部问题不阻塞无关模块。

## 1. 全局理解

- 能放入上下文时整体阅读；超出时按源文件/章节分批阅读，持续合并同一蓝图。
- 保存两层信息：故事摘要帮助理解；精确数据保存台词来源、条件表达式、变量变化、跳转及事件顺序。摘要不能替代精确数据。
- 流程图允许分支、汇合、循环及调用返回；动态目标或隐式交互尚未确定时标记为 unresolved，不能假装图已完整。

### 覆盖状态分四层登记

每个源脚本分别记录：

- `read_ranges`：已读取的行号区间
- `parsed_ranges`：已成功解析含义的区间（是 read_ranges 的子集）
- `unparsed_ranges`：读过但尚未确定行为的区间
- `unread_ranges`：完全未读的区间

已读不等于已解析。只有 parsed 才算真正理解；unparsed 必须挂 issue。

### 动态行为必须结构化登记

以下三类内容最容易在静态分析中漏掉，不能只写在正文里：

| 类型 | 内容 | 必须记录 |
|---|---|---|
| `dynamic_goto` | 目标为变量或表达式的跳转 | 原始代码、依赖变量、可能目标、确定状态 |
| `implicit_interaction` | 点击区域、计时推进、条件触发的隐式交互 | 触发条件、可能目标 |
| `dynamic_asset_path` | 变量拼接的素材路径 | 依赖变量、已确定取值 |

### 条件表达式必须保留三层

任何分支条件都记录 `raw_ns`（原始 NS 表达式原样）、`normalized`（规范化后的可读表达式）、`certainty`（fully_resolved / needs_verification / unresolved）。不能只写"有条件/无条件"。

选项的**显示条件**与**选中后执行的条件判断**必须分别记录。

### 事件必须记录等待原因

节点内保存有序事件：背景、显示/隐藏、表情、移动、音频、等待、台词、选择及状态变化。每个事件包含执行类型、参数、来源位置和 `wait_for`：

```
null | click | timer | music_end | sound_end | animation_end | interaction
```

计时等待带 `duration_ms`，动画等待带 `animation_id`。仅列出"用过哪些素材"不能表达演出时机。

### 素材检查要落到实物

素材分析包括变量拼接路径、归档、遮罩、透明方式、精灵帧和音频声道。状态必须是四选一：

`referenced_not_inspected` / `inspected` / `needs_conversion` / `ready`

仅列出文件名的素材不得标为 inspected。检查后补充分辨率、格式、alpha 通道、转换需求。没有资源时只记录引用并挂 issue，不能声称已检查。

**这一步不许手搓。** 素材普查和转换由两个通用脚本完成，不要在具体工程里现写一份「遍历目录、BMP 转 PNG」的临时脚本：

```bash
python scripts/nsassets.py "<原作目录>" --script 0.txt \
       --out port/assets_manifest.json --report port/assets_report.md
python scripts/convert_assets.py "<原作目录>" <工程>/game \
       --manifest port/assets_manifest.json
```

- `nsassets.py` 从脚本里抽出**所有**素材引用（含变量拼接的路径、`:…;` spec 前缀、`defsub` 包装层），再到磁盘上核对实物尺寸与像素；输出 manifest 与普查报告。判定规则见 [素材与演出层契约](references/assets_contract.md) 第 2–3 节。
- 素材检查状态以普查报告为准：`missing=0`、每条 `chr/ev/bg` 都标了 `mask_pair` / `mask_orient` / `key` / `cells` 才算 `inspected`。
- **蒙版（`:a;`）必须拆**：NS 的立绘图常把「图像 + 遮罩」拼成一张双宽图，直接转 PNG 会得到带绿幕方块、还多出半幅遮罩的立绘。方向不能猜，用普查的 `mask_orient`。
- **带分割的蒙版先切格再拆**：`:a/2,0,3;` 是「每格一对 `[图|罩]`」（标题按钮、小图标常见）。顺序反了 alpha 会错位半格，按钮看着发虚、绿底反而留下。**脚本写了 spec 就按 spec**，像素探测只用于没有 spec 的素材（`sys/tlanime.bmp` 那种 10 帧动画条会被误判成蒙版对）。
- **透明方式必须核对**：键色（`:#RRGGBB`）要查该色在全图的占比，占比过低说明是画面用色而非透明色，强抠会把图抠穿。
- **动画条要生成可播的 image，不能只留一张静态帧**：spec 第 2 参数是每格毫秒（`:c/10,40,1;` = 10 格 × 40ms），转换器会生成 `<名>_anim`（播一遍）/`<名>_loop`（循环），剧情里用 `ns_strip()` 播。早期工程把 `sys/01.bmp` 直接存成 `logo.png`，开场 LOGO 的「滑入 + 翻转」就整段丢了——静图替代不了动画条。
- `convert_assets.py` 负责落地：拆蒙版、抠键色、切分割、RGB 渗色、命名合法化，并生成 `port_images.rpy` 与 `port_wrappers.rpy`。转换结果以 `port/assets_convert_report.md` 为准，跳过项、缺失项、无法翻译项都要逐条登记。

### 演出层统一走 `ns_stage.rpy`

原作的 `_bg` / `black` / `ev` / `ld` / `cl` / `lsp` 对应一套固定的分层语义（背景·CG·黑幕共用一层、立绘独立成层）。把 `assets/ns_stage.rpy` 拷进工程 `game/`，剧情模块只调它：

- 换背景、上 CG、拉黑幕都走同一个 tag `bg`（互相替换），但它们**会清立绘**——NS 的 `_bg` 就是这样，原作也这么写；「换景并带人」用 `ns_bgchr`
- 用 `scene` 换背景会清整层，是「换了背景立绘消失」的病根，写代码时禁止
- 旧工程遗留的 `port_bg/port_chr/port_ev/port_black/port_bgchr` 用 `scripts/nsstage_migrate.py <game 目录> --apply` 批量改写
- 音频通道（`dwave` 的通道号）由演出层在 `init` 阶段预注册（`ns1..ns32`）；Ren'Py 不允许运行期 `register_channel`，第一次播 SE 就崩
- 音量只许有一个控制点：原作档位（`bgmvol` = `档*12` 百分比）写进 **mixer**（`preferences.set_volume`），且只在第一次运行写一次；`chvol` 这类单条音轨的音量才用通道音量。两条都写 → 设置界面的滑条会被压成「调了没用」（见 `assets_contract.md` 5.5）
- 动画条（`.bmp` 的 `/N,<间隔ms>` 分割）走 `ns_strip(目录, 名, x, y, loop)`，不要手写帧序列；`msp`/`vsp`/`csp`/`waittimer` 这类逐帧滑动用 `renpy.pause(..., hard=True)` 逐段复刻，并在注释里写明「必须硬等」的理由
- 素材名在生成时会被归一化（`sys\01.bmp` → `sys n01`），**调用点照原作写也能命中**（`ns_strip("sys","01")` 由 `ns_safe()` 兜底）；但看到灰块/占位图时，先跑一遍运行期探针确认 `NS_MISSING`，别只看 lint

## 2. 模块划分与公共契约

- 以章节、完整事件、较长支线、路线入口和汇合点为边界；小范围 if 留在模块内。模块可以包含多个 NS 标签。
- **按 [模块粒度指南](references/module_sizing_guide.md) 跑自查**：事件条目 ≤300、原文 ≤5000 行、二级选择点 ≤8、入口前驱 ≤5、出口 ≤6。超出只增加模块数，不裁内容。
- 共享段只有一个实现归属，由多个模块跳转或调用，避免复制。调用后需返回时使用 call；顺序转移使用 jump；结局显式结束。短于约 20 条事件的共享段不值得独立成模块。
- 模块包包含全局简述、自己的原文与有序事件、必要公共定义、入口/出口、状态前置条件与变化、对应来源、验收路径。
- 原文过长时按场景继续拆分，用明确顺序和入口/出口连接；不要裁掉台词来满足包大小。
- 入口状态可为多个变体。记录继承的画面、音乐、变量，不强行在每个模块开头重置。
- 用公共契约版本约束角色 ID、变量初始值/作用域、素材 ID、label、screen 及函数接口。**契约必须带版本历史表**，记录每条变更的受影响模块与兼容性。

### 汇合点必须在规划阶段登记

凡是**跨模块**的入边数量 ≥2 的节点，在阶段 2 就写入 `mergepoints.json`，包含：每个前驱及其离开时的 bg/music/立绘/变量、状态冲突处理策略、验证状态。按 [汇合点验证指南](references/mergepoints_guide.md) 操作。

不要等组装时才发现汇合点状态不一致——那时回改成本高。

## 3–4. 实现与协作

- 统一角色、变量和素材声明；公共负责人实现通用 screen/函数。剧情负责人只写分配的模块文件。
- 用 Ren'Py 的 scene/show/hide、menu/if、play/voice、ATL、screen 实现相应行为。系统存读档、历史、设置优先采用原生功能；需要自写的功能按 [系统功能映射](references/system_features.md) 提供统一 API，不让剧情模块直接操作 persistent。
- **整部剧情机械移植时用 `scripts/ns2renpy_story.py`**：它按 `graph.json` 的标签区间逐条翻译（台词/旁白/语音号/指令/菜单/跳转/死行），一个标签一个 `story/gen_NN_<标签>.rpy`，并出 `story_coverage.json` 与 `story_convert_report.md`（每条源行去了哪里、缺哪些语音、哪些行按原作本来就不执行）。生成物是**底稿不是终稿**：逐模块复检后再进验收，人工修过的模块移进 `port/modules/` 并从 `story/` 删掉，否则下次重跑会覆盖。规则见 [素材与演出层契约](references/assets_contract.md) 第 6 节与 [写法规范](references/conventions.md) 第 16 节。
- **画面演出只调演出层**：背景走 `ns_bg`/`ns_w_bg`、CG 走 `ns_ev`、黑幕走 `ns_black`、立绘走 `ns_chr`/`ns_chr_clear`、音效走 `ns_se`/`ns_bgm`。剧情模块里不写 `scene`/`show`/`hide`、不拼 `"images/…"` 路径；原作有同名 `defsub` 时优先调 `ns_w_*`（包装层保留了 `%G1` 演出开关等原作逻辑）。细节见 [素材与演出层契约](references/assets_contract.md) 第 5 节。
- **`_bg` 会清立绘，别把背景层做成"只换背景"**：NS 里背景、CG、黑幕、纯色全走 `_bg`，它同时清掉 `ld` 上的立绘；原作正是靠这一点写场景切换（`black` 之后直接 `bg "room"`，人已经不在场）。所以 `ns_bg`/`ns_ev`/`ns_black`/`ns_color` 默认清立绘，「换景并带一个人」用 `ns_bgchr`。反过来把三条都做成不清立绘，就是「人物在场景切换时没按脚本消失」。依据见 [素材与演出层契约](references/assets_contract.md) 5.3 的「分层要点」。
- **每条 NS 语句按 [功能对照表](references/ns_to_renpy_map.md) 判类后再写代码**：
  - A 直接对应：用原生写法，不写自定义代码
  - B 语义近似：用原生 + 调整，差异必须写进 result.md 的已知差异
  - C 需自定义：先查 `catalog.features`，有实现就调统一 API，没有就登记 issue 交公共负责人，**不在本模块里另造一份**
  - 查不到对应条目：不得凭“看起来差不多”套用近似，登记 issue 后先做无关部分
- **按 [写法规范](references/conventions.md) 写代码**，最低要求：
  - 每条转换来的语句在 5 行内有 `# src:<源文件>:<行号>`，纯技术代码标 `# src:none` 并说明理由
  - 位置、过渡、速度用 `port_transforms.rpy` / `port_transitions.rpy` 的语义名，不写裸数字
  - `story/*.rpy` 内不得出现 `default` / `define` / `screen` / `image`
  - `play music` 必须显式 `loop` 或 `noloop`；BGM 只走 music，音效只走 sound
  - 整除用 `int(a / b)`，禁止 `//`
  - 缺口用 `# ISSUE-xxx : 说明` 标记，禁止裸 TODO
- 台词保持原文；允许为等效显示调整技术性转义及文本标签，不改变措辞、选择结果或等待顺序。
- 实现时核对每个事件的 `wait_for`：定时推进不能用默认点击代替，音效等待与动画等待分别处理。
- 并行时按独立模块分工，每个任务带公共契约版本、只读依赖和允许写入路径；多个任务不得同时改公共文件。
- 公共缺口返回主协调者统一处理。任务返回实现位置、入口/出口、状态变化、核对结果和问题 ID。
- 避免覆盖已经人工修过的文件；重做时先读取现状及差异。

## 5. 验证与完成

### 结构检查

核对节点归属、跨模块 label、call/return 配对、重复声明、变量作用域、素材路径是否存在、公共功能调用签名。检查所有选项的显示条件、状态变化和目标。

### 汇合点专项检查

按 `mergepoints.json` 逐条：列出前驱路径 → 实际运行到汇合点 → 记录进场的 bg/music/变量 → 与期望状态比对 → 更新验证状态。

**存在路径不等于条件可达。**未实际走通的前驱必须标为 unverified，不能算通过。汇合点整体状态取所有汇合点的最低值。

### 规范检查（不是语法检查）

实现阶段结束、组装之前跑一次 `python scripts/nsport_lint.py <game 目录> --json lint_report.json`：

- **error 必须清零**才能进入组装阶段
- warning 逐条决定"修"或"登记豁免"，豁免理由写进 `validation.md`
- 来源注释覆盖率（`src:` 注释 / 转换语句数）作为实现完整度的粗估，写进 STATUS

它检查的是**有没有遵守写法规范**（裸坐标、`//`、缺来源注释、story 里定义公共对象等），**不检查 Ren'Py 语法**，不能替代下面的 SDK 验证。

与素材/演出层相关的机器检查：

| 码 | 级别 | 含义 |
|---|---|---|
| `NS012` | error | `story/*.rpy` 里直接出现 `scene` / `show` / `hide`，必须调演出层 |
| `NS013` | error | 调用旧 per-game 舞台 API（`port_bg`/`port_chr`/`port_ev`/`port_black`/`port_bgchr`…），用 `nsstage_migrate.py` 改写；工程缺 `port_images.rpy` / `port_wrappers.rpy` / `ns_stage.rpy` 也报这条 |
| `NS014` | warning | story 里写 `"images/…"` / `"audio/…"` 裸路径，应从演出层或已登记音频 ID 走 |
| `NS015` | warning | 引用 `images/` 下非 `images/ns/` 的图（一次性脚本的手搓产物，多半没有 alpha）；工程自带 UI 放 `images/ui/` 可豁免 |
| `NS016` | warning | `ns_sprite`/`ns_strip` 引用的素材名在 `port_images.rpy` 里找不到（运行期只显示占位图、不报错；归一化名也试过） |

`--all-files` 可把模板文件（`screens.rpy` 等）也纳入扫描；默认跳过它们，避免几百条无关 warning 淹没真问题。

### SDK 验证

使用目标 Ren'Py SDK 的 lint 和实际启动结果验证。自制静态检查仅作辅助，不能替代 Ren'Py 语法解析或运行。

### 运行期冒烟（lint 查不出的那类错）

lint 只解析语法，**不会执行**演出层。`renpy.music.register_channel` 只能在 init 期调用、缺素材有没有兜住、包装层参数传没传对，都只有真跑才暴露（实测踩过：`ns_w_se` 在剧情中途抛 `Can't register channel outside of init phase.`，lint 全程 0 error）。

把 `assets/ns_stage_smoke.rpy` 临时拷进 `game/`，改掉 SMOKE 段的素材名，headless 跑一次，看 `_ns_smoke_result.txt` 有没有 FAIL，用完删掉：

```powershell
$env:APPDATA = '<工程上级>\_appdata'
$env:RENPY_SKIP_SPLASHSCREEN = '1'; $env:SDL_AUDIODRIVER = 'dummy'
renpy.exe <project>
```

它把演出层 40 个公开入口逐条实打一遍（含缺素材回落），过渡类调用会自动换新上下文重试。

### 全量走线（分支全覆盖）

冒烟只打演出层接口；**整条剧情跑不跑得通，要按菜单分支把每条路径都走一遍**。lint 和冒烟都查不出「菜单目标写错」「跳转成环」「某段立绘换不回来」这类问题。

```powershell
copy <skill>/assets/ns_autowalk.rpy <工程>/game/
python scripts\nswalk.py <工程> --max-runs 30
del <工程>\game\ns_autowalk.rpy
```

它做的事：写 plan → headless 启动 → 探针自动 skip、按 plan 选菜单 → 收 `_ns_walk_log.txt` → 发现「某个菜单还有没试过的项」就换路径再跑（DFS）→ 汇总 `walk_report.json`。

看三个字段：

- `missing_assets`：应为空。不为空就是素材普查或转换漏了，别用「运行没崩」当通过。
- `bad_runs`：`stall` / `timeout` / 启动崩溃 / 掉回主菜单，都要逐条查。
- `unreached_story_files`：应只剩「结局另一侧」这类确实到不了的模块；大片没走到说明分支没被探索到或跳转写错。

两条实现细节是踩坑换来的，改探针前先看注释：探针 patch 的是 `renpy.exports.menu`（**不是** `renpy.display_menu`——`Menu.execute` 调的是前者，patch 后者完全无效，游戏会停在第一个选项），主菜单用 Ren'Py 自己的 `RENPY_SKIP_MAIN_MENU=1` 跳过（别自己去 patch `main_menu`）。

### 过场动画编码复核

走线探针会把 `renpy.movie_cutscene` 打桩跳过，所以**动画播不出来它查不到**。动画必须单独复核编码——VP9 的 webm 会让 `movie_cutscene` 永久卡死且不报错：

```powershell
python scripts\ns_movies.py <游戏目录> <工程 game 目录> --verify
```

全部 `vp8` 才算过；有问题的用同一脚本重转（它会先 ffprobe 复核，不会因为「文件更新」而跳过坏编码）。

### 界面层：模板要用生成器，不要手改尺寸

Ren'Py 的 GUI 模板（`gui.rpy` / `screens.rpy` / `gui/` 图）是 **1280x720** 的一套，靠 `gui.scale()` 缩放。把 `gui.init(800, 600)` 改成目标分辨率、再自己补一个 `def scale(n): return int(n)`，等于把 1280 的尺寸原样塞进 800——**导航项全叠在左上、存档第 3 列跑出屏幕**。正确做法是用 launcher 的生成器按目标分辨率重新生成：

```powershell
$env:APPDATA='<工程上级>\_appdata'
renpy.exe <sdk>\launcher generate_gui <工程目录> --width 800 --height 600 `
    --accent '#00b8c3' --template '<sdk>\gui' --start
```

生成物里**不该再出现 `gui.scale(`**（生成器已把值算成整数）。另外三件配套：

- 生成器只产出 24 张图，`button/slot_*background`、`bar/*`、`slider/*`、`scrollbar/*` 这类要自己补齐（可从 `sdk\the_question\game\gui` 按比例缩放），否则一开游戏菜单就抛 `DynamicImage ... could not find image`。
- `radio_*_foreground` / `check_*_foreground` 的**宽度必须等于** `gui.radio_button_borders` / `gui.check_button_borders` 的左边距，否则标记压在文字上。
- 换分辨率后旧存档的缩略图尺寸对不上，会挤爆存档格；把旧档移走（别删）再验。

### 界面中文化

Ren'Py 自带界面（存档/读档/设置/历史/帮助/确认框/快捷菜单）里的英文是 `_("...")`，不要去改 `screens.rpy`——下次重新生成会被冲掉。拷 `assets/ns_i18n_cn.rpy` 进 `game/`，在 `options.rpy` 加 `define config.language = "chinese"` 即可。带占位符的条目（`Page {}`）译文里必须保留占位符。

### 图鉴（CG / 回想 / 音乐）

原作的鉴赏页是硬编码坐标 + 缩略图 + 解锁条件，别手抄：

```powershell
python scripts\nsgallery.py <游戏目录> --port port    # → port/gallery.json + gallery_report.md
```

再把 `assets/ns_gallery.rpy` 与 `port/gallery.json` 拷进工程、主菜单按钮 `ShowMenu("ns_gallery_cg")` / `ShowMenu("ns_gallery_mem")`。要点：

- 解锁条件照原作：`fchk "ev\x.bmp"` → `renpy.seen_image("ev nx")`，`lchk "*memN"` → `renpy.seen_label("memN")`。
- 回想回放是「置 `kaisou_mode=1` → `renpy.call_in_new_context(label)` → 场景自己在 `if %kaisoumode=1 return` 处返回」。别用 `jump`，原作 `*mem0` 这类标签末尾会 fallthrough 到下一段。
- 图鉴里的图名要用 `ImageReference(tuple(name.split()))`，**不能用 `Image("cgms cgm_prev_c0")`**：`Image()` 把字符串当文件名，名字带空格就报 `Couldn't find file`。
- 音乐模式按 `bgm` 目录列曲目，跳过缺失文件（本作 `bgm09` 缺）。

### 路线与功能验证

验证普通选项、条件选项、各结局和共享段，以及代表性位置的存读档/回滚。存读档要在汇合点位置测试。未跑过的项目标记未验证。

### 如实报告

未实现内容按稳定 issue ID 记录、关联源位置和受影响模块。用户没有接受的功能差异不能自动算作完成（`accepted_difference` 需用户明确接受）；不使用 TODO 数减豁免数作为验收。

## 续作与上下文

每次暂停或交接更新 `port/STATUS.md`：当前阶段、蓝图/契约版本、读取覆盖、**逐模块状态**、汇合点验证状态、未解决问题和下一步。

模块状态用这些值：

```
planned / spec_ready / implementing / code_review /
lint_pass / runtime_tested / validated / blocked:<issue_id>
```

新会话先读 STATUS、overview 与自己的任务包，按索引读取额外原文；不依赖旧对话记忆。开工前核对任务包声明的契约版本与当前版本是否一致，不一致先确认差异。

最终状态区分：蓝图已建立、代码已组装、lint 已通过、游戏已启动、路线已验证、汇合点已验证。只报告实际达到的状态。

## 两处细节放在 references 里

- 打包发布（distribute 命令、mac 限制、存档根不可写、构建前设 APPDATA）：`references/packaging.md`
- 实测踩坑清单（七类 51 条「症状 → 根因 → 解法」，含四条通用判据与打包发布层）：`references/pitfalls.md`

## 随附文档

- [蓝图与模块模板](references/blueprint-templates.md)：项目结构、蓝图、事件、模块任务、契约和进度模板。
- [任务提示词](references/rebuild-prompts.md)：全局分析、模块规划、模块实现、组装、续作、汇合点修复、契约升级提示词。
- [功能对照表](references/ns_to_renpy_map.md)：每条 NS 功能对应的 Ren'Py 官方实现、官方文档出处、A/B/C 判定、差异处理。
- [写法规范](references/conventions.md)：来源注释、文件组织、命名、位置/过渡/音频写法、禁止清单与人工复查清单。
- [模块粒度指南](references/module_sizing_guide.md)：模块大小上限、拆分信号、好边界特征、自查清单。
- [汇合点验证指南](references/mergepoints_guide.md)：汇合点类型、登记结构、静态与运行验证流程、常见冲突处理。
- [系统功能映射](references/system_features.md)：存读档、跳过、历史、设置、鉴赏等功能的实现策略与陷阱。
- [素材与演出层契约](references/assets_contract.md)：素材普查与转换的通用流程、NS 素材 spec 语法（蒙版对/键色/分割）、manifest 结构、`port_images.rpy` / `port_wrappers.rpy` / `ns_stage.rpy` 的生成契约、剧情模块的调用边界。
- `scripts/nsassets.py`：素材普查。从脚本抽全部引用（含变量路径、spec、`defsub` 包装层）→ 磁盘核对尺寸与像素 → `assets_manifest.json` + `assets_report.md`。
- `scripts/convert_assets.py`：按 manifest 转图（拆蒙版、抠键色、切分割、渗色、命名合法化），生成 `port_images.rpy` 与 `port_wrappers.rpy`，并出转换报告。
- `scripts/nsstage_migrate.py`：把旧工程里手写的 per-game 舞台 API 调用批量改写成演出层 API（默认 dry-run，`--apply` 落盘）。
- `scripts/ns2renpy_story.py`：整部剧情机械移植。按 `graph.json` 的标签区间逐条翻译成 `story/gen_NN_<标签>.rpy`，出覆盖报告；生成物是底稿，人工修过的移进 `port/modules/`。
- `scripts/ns_movies.py`：过场动画转 webm（`mpegplay` 的 `.mpg`），固定 **VP8**（VP9 会让 `movie_cutscene` 永久卡死，见 `references/assets_contract.md` 4.8），跳过前用 ffprobe 复核编码，可 `--dry-run`、`--verify`（只查不转）、`--profile low|normal|high`。
- `scripts/nswalk.py` + `assets/ns_autowalk.rpy`：全量走线。按菜单分支把整条剧情跑一遍，收缺素材、跑不通、没走到的模块。
- `scripts/nsgallery.py`：从脚本里抽图鉴数据（`*cgmlpN` / `*memlpN` 的坐标、缩略图、`fchk`/`lchk` 解锁条件）→ `port/gallery.json` + 报告。坐标不手抄。
- `assets/ns_gallery.rpy`：图鉴运行时（CG / 回想 / CG 查看器）。读 `gallery.json` 画格子，解锁用 `seen_image` / `seen_label`，回想回放走 `kaisou_mode` + `call_in_new_context`。
- `assets/ns_i18n_cn.rpy`：Ren'Py 自带界面的中文化覆盖层（`translate chinese strings`）。通用件，拷进 `game/` 并在 `options.rpy` 设 `config.language = "chinese"`。
- `assets/ns_volume.rpy`：音量桥接（原作 0-6 档 → Ren'Py mixer，只在第一次运行写、读档清通道级上限）。拷进 `game/`，不要手写第二份。
- `assets/ns_stage.rpy`：演出层运行时。分层语义、槽位定位、音频通道、缺失素材占位都在这里，工程直接拷过去用，不要重写。
- `assets/ns_stage_smoke.rpy`：演出层运行期冒烟。拷进 `game/`、改素材名、headless 跑一次，验证 lint 查不出的运行期错误。
- `scripts/nsport_lint.py`：按写法规范做机器检查，输出 error/warning/info 与来源注释覆盖率，支持 `--json`。

## 随附旧工具

`scripts/legacy/ns2renpy.py` 可辅助提取和试译；`scripts/legacy/taskpack.py` 只能按旧标签切片，不能代替本流程的语义模块包；`scripts/legacy/verify.py` 是有限的启发式检查，对 Ren'Py 完整语法存在误报/漏报。旧 mapping 和 repair-playbook 仅供查阅，示例须在目标 SDK 上核实，不作为本流程的强制步骤或验收依据。

`scripts/nsport_lint.py` 不属于旧工具，它是本流程的一部分（规范检查）。
