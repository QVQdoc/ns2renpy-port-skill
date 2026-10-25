# 案例：一部 30,056 行 NScripter 游戏的全量移植

> 用的就是本仓库这套流程。原作 196 个 label、30,056 行脚本、411 条素材、6,030 个语音文件；
> 一次完整移植产出 81 个剧情 label（41,947 行 `.rpy`）、586 张转换素材、638 个音频文件、5 个过场视频。
> 过程中暴露并修掉的通用缺陷，全部回流进了 `SKILL.md` 与 `references/pitfalls.md`。

## 验收数字

| 项 | 结果 |
| --- | --- |
| 台词覆盖 | 14,969 条（5,960 有语音 + 9,009 旁白），未翻译 0 |
| 全量走线 | 10 轮分支全覆盖，进入标签 94 个，缺素材 0，异常 0 |
| 规范检查 | `nsport_lint` 0 error / 0 warning / 0 info，来源注释 100% |
| 引擎检查 | Ren'Py lint 无 error，591 images / 33 screens / 11 menus |
| 打包 | 一行命令出 678.9MB 发布包，解压双击即玩 |

## 完整报告

# 全量移植测试报告（触装天使セリカ）

测试日期：2026-10-25　工程：`project\`　原作：`<ns-game>`

## 结论

**流程跑通了。**整个游戏 81 个剧情标签、28,457 行源脚本、14,969 句台词全部机械移植完成，Ren'Py lint 与规范 lint 双 0 错误，全量走线 10 次覆盖 100% 台词行、0 缺素材、0 异常退出。

但这轮测试的真正价值不是「跑通了」，而是**跑通之前先炸出了三个只有全量规模才暴露的坑**（见第 5 节）。三个都是通用缺陷，已经修在工具里，不是本工程的特例。

## 1. 规模

| 项 | 数量 | 说明 |
|---|---|---|
| 剧情标签 | 81 | `happyend` / `badend` / `p1`…`p12_2` / `y1`…`y12` / `mem*` |
| 源脚本行 | 28,457 | `0.txt` 共 30,056 行，扣掉系统段与标签声明 |
| 生成代码 | 41,947 行 | `game/story/gen_*.rpy` 81 个文件 |
| 台词 | 14,969 句 | 有脸 5,960 + 旁白 9,009 |
| 语音引用 | 4,852 处 | 缺 1 条（`00345`，原作就没有） |
| 指令翻译 | 3,187 条 | bg/ev/chr/music/se/loop/dstop/lsp/mpegplay… |
| 菜单 | 9 个 | `csel` → `menu:` |
| 图片素材 | 586 个 / 97.0 MB | 含 57 张立绘蒙版、UI 按钮 |
| 音频 | 6,152 个 / 483.8 MB | voice 6,029 + se 110 + bgm 13 |
| 过场 | 5 个 / 44.6 MB | mpg → webm（184.4 MB → 36.6 MB） |

## 2. 可复跑命令

```powershell
cd '<port-project>'
$W = '<skill>/'

# 1) 素材普查 → 转换（幂等）
python $W\scripts\nsassets.py       '<ns-game>' --script 0.txt
python $W\scripts\convert_assets.py '<ns-game>' project\game

# 2) 过场动画
python $W\scripts\ns_movies.py      '<ns-game>' project\game

# 3) 剧情批量翻译（81 个标签）
python $W\scripts\ns2renpy_story.py '<ns-game>' port --project project

# 4) 规范检查 + SDK 检查
python $W\scripts\nsport_lint.py project\game --json port\lint_report.json
$env:APPDATA = '<port-project>\_appdata'
& '<renpy-sdk>\renpy.exe' project lint

# 5) 全量走线
copy $W\assets\ns_autowalk.rpy project\game\
python $W\scripts\nswalk.py project --max-runs 12
del project\game\ns_autowalk.rpy
```

## 3. 检查结果

| 检查 | 结果 |
|---|---|
| `nsport_lint.py` | **0 error / 0 warning / 0 info**，`.rpy 91 / label 86`，来源注释 19,938/19,938 (100%) |
| Ren'Py SDK lint | **无 error 无 warning**，`14,979 dialogue blocks / 17,548 words / 343,414 characters / 11 menus / 588 images / 28 screens` |
| `qa_alpha.py` | 586 张图，立绘 57 张全带 alpha，残余纯绿 0 |
| `nswalk.py` | 10 次运行，台词行 14,969（= 全部），进入标签 94 / 未进入 **0**，缺素材 **0**，异常 **0** |

走线逐次结果（`project\walk_report.json`）：

| # | 菜单选择序列 | 结束方式 | 台词数 | 菜单数 | 耗时 |
|---|---|---|---|---|---|
| 1 | (默认) | ending | 4,372 | 2 | 4.1s |
| 2 | 1 | ending | 3,494 | 1 | 3.4s |
| 3 | 0 1 | ending | 7,353 | 5 | 6.1s |
| 4 | 0 1 1 | ending | 5,496 | 3 | 4.8s |
| 5 | 0 1 0 1 | ending | 7,148 | 4 | 5.9s |
| 6 | 0 1 0 0 1 | ending | 8,086 | 6 | 6.4s |
| 7 | 0 1 0 0 1 1 | ending | 11,240 | 7 | 9.3s |
| 8 | 0 1 0 0 1 1 1 | ending | 11,535 | 8 | 8.8s |
| 9 | 0 1 0 0 1 1 1 1 | ending | 12,393 | 9 | 9.4s |
| 10 | 0 1 0 0 1 1 1 1 1 | ending | 12,033 | 9 | 9.0s |

每次都以「走到结局 / `reset`」结束，没有卡死、没有掉回主菜单。

## 4. 验证了什么、没验证什么

**验证了**：脚本解析（含 `defsub` 包装层、`:a;` spec、变量拼接路径）→ 素材转换（蒙版拆分、键色、分割、UI 按钮 alpha）→ 演出层调用（分层 tag、槽位、音频通道）→ 剧情翻译（台词/旁白/语音/条件/菜单/跳转/死行）→ 双 lint → 全分支走线，四层全链路无断点。

**没验证（必须人工）**：

| 项 | 原因 |
|---|---|
| 立绘槽位与过渡观感 | 走线是 headless + fast skip，只证明「不报错」，不证明「看着对」。`port\proof_*.png` 只覆盖了静态合成 |
| 音量分支（`%G5` / `%G10`） | 走线忽略音量，只证明不崩 |
| 过场动画 | 探针把 `movie_cutscene` 打桩跳过——**事后证明这条漏得最狠**，见第 7 节 || 系统 UI（存读档、回想、CG 鉴赏、设置） | 原作系统段不移植，Ren'Py 用模板 UI；`mem34`（标题流程）按设计跳过 |
| 文本窗样式、文字速度 | 模板默认值，未对齐原作 |
| 结局演出 | `happyend` / `badend` 只走到 `return`/`reset`，结局后画面未核对 |
| 语音与台词的配对 | 语音号来自脚本字面量，`voice_filename_format` 路径正确，但没逐个听 |

## 5. 这轮炸出来的三个通用缺陷（已修）

1. **素材名大小写**：脚本写 `chr "m02_E"`、磁盘是 `m02_e.bmp`。NS 在 Windows 上不分大小写，Ren'Py 的 image 名分。→ `safe_name()` 统一转小写，参考名与文件名一起归一。表现为「素材明明转好了，运行期报 `chr m02_E` 缺失」。
2. **音频探测的假缺失**：`dwaveloop 26,"voice\maybg201.ogg"` 经 `dwave`/`dwaveloop` 翻译后目录前缀丢失，`ns_audio_path()` 按 se→voice→bgm 试错，前几轮 miss 被逐个记进 `NS_MISSING`，报告里出现 6 条「其实找到了」的缺失。→ 探测阶段 `report=False`，全部试完才登记一次。
3. **`chr ""` 被兜底成 `"x"`**：`*chr` 体里 `if $w0=""` 是**清槽位**，空参数被 `safe_name` 的 `or "x"` 兜底后变成去找 `chr\x.bmp`。影响 86 处 chr、55 处 loop、69 处 sloop。→ 空名直接返回 `""`，`chr`/`loop`/`sloop` 原样透传语义。

另有两个工具层教训（已写进 `SKILL.md` 与 `conventions.md` 第十五、十六节）：

- 探针 patch 的必须是 `renpy.exports.menu`（`Menu.execute` 调它），不是 `renpy.display_menu`——patch 后者时游戏会静悄悄停在第一个菜单上，日志里只有 `START`。
- 驱动不要用 `stdout=PIPE` 接 `renpy.exe`：它会留一个继承句柄的子进程，管道永不关闭，读端卡死（实测 5 分钟无输出）。
- 连续启动偶发 `rc=3221226356`（0xC0000374 heap corruption），连日志都不生成；驱动自动重试一次即可，不要当失败（第 9 次运行就是重试后走完的）。

## 6. 交付物

| 文件 | 内容 |
|---|---|
| `game/story/gen_*.rpy` | 81 个标签的生成代码（底稿） |
| `port/story_coverage.json` | 逐标签、逐行的去向与计数 |
| `port/story_convert_report.md` | 翻译报告（跳过/缺语音/死行） |
| `project/walk_report.json` | 走线原始结果 |
| `port/renpy_lint_full.txt` | SDK lint 全文 |
| `port/lint_report.json` | 规范检查结果 |
| `port/proof_stage.png` / `proof_title_*.png` / `proof_ui_alpha.png` | 目视证据 |

## 7. 补测：开场动画卡死（ISSUE-023）

用户实机报「开头的动画会卡住」。这不是流程之外的小问题，而是**第 4 节「没验证」那一栏的直接后果**——走线探针把 `movie_cutscene` 打桩了，于是「文件存在」被当成了「动画能播」。

| 项 | 结果 |
|---|---|
| 现象 | 启动后永久黑屏；无异常弹窗、`log.txt` 无错误行、进程 CPU≈0（挂死不是慢） |
| 探针定位 | `movie_cutscene()` 前后各写一行文件日志：只有 `before`，71 秒后才有 `after` → 解码器阻塞 |
| 根因 | `movie/opening.webm` 是 **VP9+Vorbis**（上一轮手工 ffmpeg 转的，绕过 `ns_movies.py`）。Ren'Py 8.5.3 官方 SDK 播 VP9 时 `movie_cutscene()` **永不返回** |
| 为什么没被发现 | 旧 `ns_movies.py` 的幂等判据只看「目标比源新」→ 坏编码被安静跳过；探针又把动画打桩 |
| 修复 | 重转为 VP8+Vorbis（92.1MB→15.4MB，71.0s）；`ns_movies.py` 重写：固定 `libvpx`、跳过前 ffprobe 复核编码、`--verify` 只查不转 |
| 复核 | `--verify`：5 个 webm 全 `vp8`，问题 0 个；headless 启动实测 100 秒内 `splashscreen` → `_main_menu`（含 71 秒片头） |
| 沉淀 | `SKILL.md`「过场动画编码复核」、`assets_contract.md` 4.8、`ns_to_renpy_map.md` 四节「`mpegplay` 必须转 VP8」、`设计思路与使用说明.md` 第 11 条「文件更新≠文件能用」 |

## 8. 补测：开场 LOGO 动画（ISSUE-024）

用户接着问「logo.png 这个文件在游戏开头的动画效果怎么没有实现」。核对源脚本后确认：原作 `*logo`（`0.txt:154-195`）是**一段演出**，而移植版只放了一张静态图。

| 项 | 内容 |
|---|---|
| 原作动作 | `lsp 0,":c;sys\01.bmp",800,174` 放到屏幕右侧外 → `msp 0,-200,0,0` ×4 + `waittimer 60`（4 段、每段 200px/60ms）滑到 x=0 → `csp 0` + `vsp 1,1` 换成 `lsph 1,":c/10,40,1;sys\tlanime.bmp",188,174`（10 格、40ms/格翻转）→ 停 2s → 50/50 播 `ser_touchable` / `may_touchable` → 停 2s → 收掉 |
| 移植版原状 | `show port logo` + `Dissolve(0.4)` + `pause 2.5`；`images/ui/logo.png` 是早期一次性脚本 `convert_ui_assets.py` 从 `sys/01.bmp` 复制的落定帧（无 alpha、无帧序列） |
| 为什么没人播 10 帧 | 素材层原先只有「单图」概念：`sys/tlanime.bmp` 的 10 帧确实转成了 `sys tlanime_c0..c9`，但没有任何地方把「多格 + 帧间隔」表达成可播的动画 |
| 根因归类 | 与第一轮的「调用背景不通用 / 立绘蒙版」同源：**素材语义没有被固化成契约**，只能靠人肉在流程里补 |
| 修复（素材层） | `convert_assets.py` 新增 `strips_of()`：判据 = 格数 > 1 **且** spec 第 2 参数（每格毫秒）> 0；`port_images.rpy` 末尾生成 `NS_STRIPS` 表 + `<名>_anim`（播一遍停最后一帧）/ `<名>_loop`（循环）；本作命中 `sys tlanime`（40ms×10）与 `musm mub_a01`（50ms×10） |
| 修复（演出层） | `ns_stage.rpy` 新增 `ns_strip(目录, 名, x, y, loop)`，一句播放，缺动画定义时回退单帧 |
| 修复（流程层） | `port_flow.rpy` 的 `splashscreen` 按原作时间轴重写；`msp` 的 4 段用 `renpy.pause(0.06, hard=True)` 复刻并注明「必须硬等」的理由（NS008 检查也要求这件事） |
| 验证 1（原版对照） | `ffmpeg -f gdigrab -framerate 10 -t 12` 录原版 NS 启动，逐帧确认：滑入约 0.3s、翻转约 0.4s、落定停留约 4s |
| 验证 2（移植侧） | 探针记 `renpy.get_showing_tags("master")`：`sys` 在 0.9–3.5s 在位、5.2s 消失（对应翻转+停留+语音），`splashscreen` 正常进片头 |
| 验证 3（静态证据） | `port\proof_logo.png`（9 格：4 段滑入 + 5 帧翻转） |
| lint | `nsport_lint` 0/0/0；Ren'Py lint 无 error（**591 images**，比上一轮多 3） |
| 清理 | 删 `images/ui/logo.png` 与 `image port logo`；`sys 01` 与它是同一美术，前者才是权威来源 |

---

## 9. 补测：场景切换清立绘（ISSUE-026，2026-10-25）

用户第三次报障：「人物在场景切换时没有按脚本消失」。

**不是漏翻译**：源脚本剧情区 `chr ""` 86 处，生成代码 `ns_w_chr("")` 也是 86 处。

**根因**：NS 的 `_bg`（背景、CG、黑幕、纯色全走它）会连 `ld` 上的立绘一起清掉，而第一版演出层
`ns_bg`/`ns_ev`/`ns_black` 只换背景层。原作脚本一直靠这个前提写场景切换：

| 行 | 代码 | 立绘 | 说明 |
| --- | --- | --- | --- |
| 1572 → 1574 | `black` → `bgchr "street_c","s02_i"` | `s02_e` 在位 | 换景要带人必须 `bgchr` |
| 10677 → 10684 | `black` → `bg "room"` | `s03_a` 在位 | 换到自己房间，芹香直接说话，中间无 `chr ""` |
| 2509 | `ev "32a"` | `s01_b` 在位 | 战斗 CG 单独占满画面 |

`tools\bg_semantics.py` 统计：389 处 `bg`/`ev`/`black` 里 198 处切换时立绘在场，其中 130 处之后
没有任何 `chr`、59 处紧接着重新 `chr`；`chr ""` 全部出现在**没有换景**的场景。

**修复**：`ns_bg`/`ns_ev`/`ns_black`/`ns_color` 默认 `clear_chr=True`，`ns_bgchr` 一次完成「换景+带人」，
`lsp` 精灵不跟随清理（原作显式 `csp`）。

**验证**：运行期探针逐条打 tag（换背景/CG/黑幕之后只剩 `['bg']`，`bgchr` 之后 `['bg','chr']`）；
3 次走线复核无缺素材、无异常；`nsport_lint` 0/0/0；Ren'Py lint 无 error（591 images / 28 screens）。

**附带的保存兼容性问题**：`project\game\port_flow.rpy` 在 13:19 为 LOGO 动画重写过，Ren'Py 的存档
记录的是脚本位置哈希，**改脚本前存下的档无法继续**（表现是 `Could not find return label`）。
这轮排查中看到的 `project\traceback.txt`（13:27）就是这一条，不是代码 bug；新开游戏后正常。

