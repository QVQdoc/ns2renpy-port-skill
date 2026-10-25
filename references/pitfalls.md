# 实测踩坑清单

> 来自一次完整移植（30,056 行脚本 / 411 条素材 / 81 个标签 / 10 轮全量走线）。
> 每条都是「症状 → 根因 → 解法」，按层分组；新坑按同样格式补在对应小节，并在 `SKILL.md` 的「补坑流程」里登记。

拿一整部作品（28,457 行脚本 / 411 条素材引用 → 586 个 PNG + 6,152 个音频 / 81 个剧情标签 / 10 轮全量走线）跑完之后回填的。共同点是：**两条 lint 全绿、素材也"转出来了"，游戏里照样错**。开工前扫一遍，比事后 debug 便宜。

### 四条通用判据

1. **lint 全绿只说明书写得规范**，不代表运行期对：缺素材、通道注册、归一名对不上都会静默通过。
2. **文件转出来 ≠ 语义转对了**：蒙版、键色、动画条、分割格，四件事都要落到像素或帧序列才算 inspected。
3. **脚本 spec 优先于像素探测**：作者写的 `:…;` 是他对素材的断言；像素只在没有 spec 时用来兜底。
4. **同一件事只许有一个实现**：素材转换、演出层、音频通道、名字归一化，任何一项在每个工程手搓一份，就一定会分叉出不同的 bug。

### 一、素材层

| 症状 | 根因 | 解法 |
|---|---|---|
| 立绘带着绿幕方块，右边还多出半幅黑色人形 | `:a;` 是双宽图「图＋遮罩」，被当普通图转 PNG | 拆 alpha，方向用普查的 `mask_orient`（本作 `dark-opaque`）：`alpha = 255 - 遮罩亮度` |
| 标题按钮发虚、绿底反而留着 | `:a/2,0,3;` 是「每格一对 `[图｜罩]`」，先整图拆蒙版再切格 → alpha 错位半格 | **先按 `cols` 切格、再逐格拆蒙版**（`convert_image` 的 `if mask and cols > 1` 分支） |
| 24x10、60x15 这类小图标没抠透明 | 守卫 `宽 >= 2*16*cols` 把小图整批跳过 | 放宽到 `8*cols`，同时要求 `宽 % (2*cols) == 0` |
| 按钮该实心的透明、该透明的实心 | 方向判不出时默认按 `light-opaque` 处理 | `_pick_orient()` 拿键色区域跟两个候选比差；`mask_note` 记「脚本没写 `:a;`，按脚本处理」 |
| 10 帧动画条被拆成 5 对「图＋罩」 | 像素看着像蒙版对，脚本写的是 `:c/10,40,1;` | spec 优先：有 spec 就按 spec，无 spec 才探像素 |
| 开场 LOGO 没有动画，只有一张静图 | 多格素材只留了落定帧 | `strips_of()` 判「格数 > 1 **且** 第 2 参数 > 0」→ 生成 `<名>_anim`/`_loop` + `NS_STRIPS`，剧情里 `ns_strip()` 播 |
| 素材名对不上：运行期一片灰块，lint 却 0 error | `01`→`n01`、`m02_E`→`m02_e` 的归一化只做在生成端 | 三处共用同一规则：生成端 `safe_name()`、运行端 `ns_safe()`、静态端 lint `NS016` |
| 真彩背景图被抠穿 | 键色占比接近 0，说明那是画面用色不是透明色 | `key_min_ratio=0.10` 以下不抠，并在转换报告里写明「判为画面用色」 |

### 二、演出层

| 症状 | 根因 | 解法 |
|---|---|---|
| 换背景后上一张立绘还挂着；黑幕后人物没消失 | 把 `_bg` 当成「只换背景」 | NS 的 `_bg` **会清 `ld` 立绘**（原作靠它写换景）：`ns_bg`/`ns_ev`/`ns_black`/`ns_color` 默认 `clear_chr=True`，「换景带人」用 `ns_bgchr`；`lsp` 精灵不跟清 |
| 拉黑幕时下面还压着旧背景 | `ev`、`black` 各用了自己的 tag | 背景·CG·黑幕·纯色统一 `tag="bg"`，互相替换 |
| 第一次播 SE 直接抛 `Can't register channel outside of init phase.` | 运行期调 `renpy.music.register_channel` | `init -5` 预注册 `ns1..ns32`，运行期 `ns_channel()` 只查表 |
| `loop "serbg001"` 静音，日志说找不到文件 | 只在 `audio/se/` 里找 | `ns_audio_path()` 按通道在 voice/se/bgm 依次探测，全无才登记 `NS_MISSING` |
| 过渡被叠加成两倍时长 | `ns_bgchr` 里先 `ns_chr(dur)` 又 `ns_apply(dur)` | 各层先 `dur=0` 只排演出，最后一次 `ns_apply(dur)` |
| 设置界面的音量滑条「调了没用」，BGM 还盖住语音 | 全局音量被 `renpy.music.set_volume()` 写成通道级（次级）音量，与滑条的 mixer 音量相乘；换算用 `档/6`（33%）而非原作的 `档*12/100`（2 档=24%）；且只在开新游戏时写 | 全局音量只写 mixer（`preferences.set_volume`），只在第一次运行写；`after_load` 把通道级音量清回 1.0；`chvol` 才用通道音量。母带要实测（本作 BGM 比语音热 4~8 dB） |
| 手写 `ns_strip("sys","01")` 显示灰块 | 归一化只在生成端做了 | `ns_safe()` 运行期兜底 + `NS016` 静态对账 |

### 三、剧情翻译层

| 症状 | 根因 | 解法 |
|---|---|---|
| `*music` 后半段十几条 `bgm` 分派整段消失，参数变成 `"0:return"` | NS 用 `:` 分隔同一条语句 | `_split_statements()` 只在冒号后紧跟**已知指令词**时拆；`if 条件 return` 不能当成标签结束 |
| 每个标签丢最后一行（菜单 9 个变 8 个） | `graph.json` 的 `source.lines` 是**闭区间** | `begin, finish = s, e`，别写 `e - 1` |
| `bg "street_c"` 被译成纯色 | 用「参数里有没有反斜杠」判断颜色 | 只看**有没有引号**：无引号才是 `white` / `#FFFF88` 这种颜色 |
| `chr ""` 变成 `ns_w_chr("x")`，运行期找 `chr\x.bmp` | `safe_name()` 给空名补了个 `x` | `asset_ref()` 空名返回 `""`；`chr`/`loop`/`sloop` 的空参数原样传（语义是清槽位/淡出停止），`bg/ev/se/bgchr/lsp` 的空参数只写备注 |
| Ren'Py 报 `Unreachable Statements` | `goto`/`return` 之后原作还有行 | 终止后置 `skip_rest`，统计进 `story_coverage.json`（本作 42 行） |
| 生成代码缺 `# src:` → NS004 | fallthrough 补的 `jump` 没带行号 | `translate_label` 记 `last_n` 再补注释 |

### 四、验证层

| 症状 | 根因 | 解法 |
|---|---|---|
| 双 lint 全绿，游戏里还是崩、还是灰块 | lint 只解析语法，不执行演出层 | 冒烟 `ns_stage_smoke.rpy` + 全量走线 `nswalk.py` + lint `NS016`，三件一起上 |
| 走线永远停在第一个选项 | patch 的是 `renpy.display_menu` | `Menu.execute` 调的是 `renpy.exports.menu`（`renpy/ast.py`） |
| 走线驱动挂住好几分钟没有任何输出 | `subprocess.run(stdout=PIPE)`：renpy 留下继承句柄的子进程，管道不关 | 重定向到文件再读 |
| 连续启动偶发 `rc=3221226356`（0xC0000374） | 堆损坏 | 自动重试一次；两次都挂才算 `bad_run` |
| fast skip 下覆盖率几乎为 0 | periodic callback 在跳过时几乎不刷新 | 覆盖统计挂 `renpy.exports.say`；主菜单用 `RENPY_SKIP_MAIN_MENU=1` |
| 探针被打进发行包 / lint 计数莫名其妙变了 | 探针忘了删 | 用完立刻删 `ns_autowalk.rpy`、`ns_stage_smoke.rpy`、各类 `_*check.rpy` |

### 五、环境与工程层

| 症状 | 根因 | 解法 |
|---|---|---|
| `renpy.exe <project> lint` 报 `PermissionError: ...\AppData\Roaming/RenPy/tokens/upgraded.txt` | 子进程写 token 受限（手工 `open(...,"a")` 却能写） | 先 `$env:APPDATA='<工程上级>\_appdata'` 再跑 |
| 开场动画永久卡住：不报错、log 干净、CPU≈0 | `webm` 是 **VP9** 编码 | 必须 VP8；`ns_movies.py --verify` 复核，幂等判断不能只看时间戳 |
| 幂等重跑没修好旧问题 | 跳过判据是「目标比源新」 | 编码/尺寸这类可复核的，先 ffprobe 校验再决定跳过 |
| `Start-Process` 报「已添加项。字典中的关键字:"NO_PROXY"」 | 环境变量大小写重复 | 改用 `Start-Job` 里跑 `& renpy.exe <project> *>&1 > out.txt` |
| 终端里中文全是乱码 | pwsh 控制台按 cp936 解 UTF-8 输出 | 用 read 工具看文件；Python 侧设 `PYTHONIOENCODING=utf-8` |
| 改脚本后读旧档报 `Could not find return label` | Ren'Py 存档绑定脚本位置哈希 | 不是代码 bug，新开档；在报告里说明，别当缺陷追 |
| 用 PowerShell 调 GitHub API 建仓库，描述里中文全变成 `?` | `ConvertTo-Json` 产出 UTF-16 字符串，`Invoke-RestMethod -Body` 按单字节编码发出 | 先 `[Text.Encoding]::UTF8.GetBytes($json)` 再用 `-Body $bytes -ContentType 'application/json; charset=utf-8'`；发完用 API 读回来核对 |
| 无头环境里 `set_mouse_pos` + `queue_event("mousedown_1")` 打不中屏幕按钮，截图前后逐像素相同 | dummy 视频驱动下没有真实指针命中测试 | 点击类交互只能实机验；无头验证改走 `Function(...)`/`renpy.call_in_new_context` 直接调动作，别伪造鼠标 |

### 六、界面层

| 症状 | 根因 | 解法 |
|---|---|---|
| 存档页导航全叠在左上，第 3 列跑出屏幕 | 1280 模板 + `def scale(n): return int(n)` 恒等缩放 | 用 launcher 的 `generate_gui --width 800 --height 600` 重新生成，删掉手写的 `guisupport.rpy` |
| 一开游戏菜单就 `DynamicImage ... could not find image` | 生成器只给 24 张图，`slot_/bar/slider/scrollbar` 缺 | 从 `sdk\the_question\game\gui` 按比例补图，或自己画中性九宫格 |
| 选项标记（○/☑）压在文字上 | 标记图宽 32px，而 `*_button_borders` 左边距只有 12px | 标记图宽 = 左边距（12–18px），或把 borders 调到标记宽 + 6 |
| 存档格里的缩略图挤爆格子 | 旧档是上一套分辨率存的（缩略图 256x144） | 旧档整体移走另存，别删；只影响老档 |
| 设置页、导航、按钮全是英文 | 直接用了模板英文 | 拷 `assets/ns_i18n_cn.rpy` + `define config.language = "chinese"` |
| 图鉴里报 `Couldn't find file 'cgm cgm_prev_c0'` | `Image("名字 带空格")` 被当文件名 | 用 `ImageReference(tuple(name.split()))` |
| 回想点进去直接回标题 / 跑飞 | 用 `jump` 进 mem 标签（末尾 fallthrough 到下一段） | `kaisou_mode=1` + `renpy.call_in_new_context(label)`，靠场景自己的 `return` 回来 |
| 图鉴的上一页/下一页点了没反应（退出按钮却正常） | 按钮在被 `use` 嵌进去的屏幕里，`SetScreenVariable` 写的是当前屏幕 scope，`default` 又挂在被 use 的那层，父屏一重算就回到 0 | 翻页状态放 store（`default ns_gal_page_index = {...}` + `Function`），别跨 `use` 用屏幕变量；顺手加 `key "K_LEFT"/"K_RIGHT"` 与滚轮 |
| 图鉴页码和美术叠在一起 | 原作把 "Page N/3" 画在每页的背景图里（`cgm cgmode_bgN`） | 只在背景走 fallback 时才自己画页码 |

### 七、打包与发布层

| 症状 | 根因 | 解法 |
|---|---|---|
| 双击 exe 弹一个 traceback 的 txt，游戏起不来：`PermissionError: ...\RenPy\tokens\upgraded.txt` | 存档根目录不可写；`tokens` 与存档**共用同一个根**（`savetoken.py:301`），不是「tokens 这个文件特殊」 | 包根放空目录 `Ren'Py Data`（`renpy.py:176-187` 逐级向上找），或发 `RENPY_PATH_TO_SAVES=%~dp0saves` 的启动 bat；别指望用户去改 `%APPDATA%` 权限 |
| `launcher distribute` 直接 exit 1，没有任何像样的报错 | 打包器本身就是 Ren'Py 进程，撞同一个 `%APPDATA%` 不可写 | 构建前 `$env:APPDATA='<可写目录>'` |
| 包里冒出 `walk_report.json`、`assets_convert_report.md`、`traceback.txt` | 只排除了 `game/saves` 和 `game/cache` | `options.rpy` 的 `init python` 里 `build.classify('*.txt'/'*.log'/'*.md'/'*.json', None)`（这些 pattern 只匹配工程根，不会误伤 `game/` 内部） |
| 想给 Mac 用户发包，Windows 上打出来没有 `.app` | `--package pc` 只含 win + linux 运行时 | mac 包必须在 macOS 上打；`lib/` 里只有 `py3-windows-x86_64`、`py3-linux-x86_64` |
| 手动删了 `game/cache`，但包里又出现了 | 打包器会自己生成 `cache/bytecode-312.rpyb` + `cache/build_info.json`（玩家端免编译） | 不用管；你排除的是开发期的 `py3analysis.rpyb` / `screens.rpyb` / `shaders.txt` |
| 玩家互相给存档，读进来弹「This save was created on a different device」 | 每台机器首次运行各自生成一把签名密钥 | 预置固定 `tokens/security_keys.txt`（生成一次、随包发），玩家端 `init_tokens()` 读到已有密钥就不再生成；代价是私钥公开、可伪造签名 |
| 收包人双击 exe 被 SmartScreen 拦住 | exe 没有代码签名 | 正常现象，让对方「更多信息 → 仍要运行」；要消掉得买证书 |

### 补坑流程

新踩的坑按上面的层补一行，并且尽量同时做三件事：能机器查的补一个 lint 码（`NS0xx`）、能运行期兜底的补进 `ns_stage.rpy`、能写进契约的写进 `references/assets_contract.md`。只写在对话里，下个工程会原样再踩一遍。

打包层的坑没有 lint 可用，就在 `references/packaging.md` 里同步一段「为什么」，免得下个人以为是环境偶发故障。
