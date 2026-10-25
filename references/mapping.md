# NS → Ren'Py 映射与偏差

转换器的行为契约。改转换器之前先读这里，改完同步这里。

## 0. 行分类规则（解析契约）

NS 逐行解析，**行首第一个 token 命中命令表即为命令，否则就是台词**。

| 行形态 | 判定 | 转换结果 |
|---|---|---|
| `*name` | 标签 | `label name:` |
| `*define` … `game` | 定义区 | 只记录（窗口/效果/别名/数组），不产码 |
| `;` 开头 | 注释 | 丢弃 |
| `cmd arg,arg` | 命令 | 见下表 |
| 其它一切 | 台词 | say 语句 |

推论：**台词行首不能是命令名**。撞上了原文就是错的，转换后不会再触发，
但要在 `WAIVERS.md` 里记一笔（说明原版这句本来就会被吃掉）。

## 1. 控制流

| NS | Ren'Py | 备注 |
|---|---|---|
| `goto *a` | `jump a` | 不返回 |
| `gosub *a` / `return` | `call a` / `return` | 会返回 |
| `if <cond> <cmd>` | `if <cond>:` + 子命令 | 行内式展开成块 |
| `if A && B <cmd>` | `if a and b:` | |
| `notif <cond> <cmd>` | `if not (...):` | |
| `if fchk "x"` | `if renpy.seen_image("x")` | 近似 |
| `if lchk *a` | `if renpy.seen_label("a")` | 近似 |
| `select "t",*a,"t2",*b` | `menu:` + 分支 | `""` 隐藏项被跳过并注释 |
| `selgosub` | `menu:` + `call` | |
| `end` | `return` | 回主菜单 |
| `reset` | `jump start` | |
| `for`/`next`、`trap`、`selnum`、`skip`、`jumpf/jumpb` | TODO | 见 repair-playbook |

## 2. 画面

| NS | Ren'Py |
|---|---|
| `bg "a.jpg",<eff>` | `show ns_bg_a zorder -100` (+ `with`) |
| `bg #rrggbb,1` / `bg black,1` | `show expression Solid("#rrggbb") as nsbg_solid...` |
| `ld {l,c,r},"y.png",<eff>` | `show ns_c_y at ns_center` |
| `cl {l,c,r}` | `hide ns_c_...` |
| `lsp n,"s.png",x,y[,alpha]` | `show ns_spn_s at Transform(xpos=x, ypos=y, xanchor=0, yanchor=0)` |
| `csp n` / `vsp n` | `hide` / `show`（同一 tag） |
| `msp n,x,y` | 对已显示 tag 重新 `show ... at Transform(...)` |
| `print` / `textclear` | 注释（Ren'Py 自动合成） |
| `quake` / `quakex` / `quakey` | `with hpunch` / `with hpunch` / `with vpunch` |
| `monocro`、`nega`、`tal`、`amsp`、`blt` | TODO |

坐标约定：`l/c/r` 用 `xalign 0.0/0.5/1.0 + yalign 1.0`（近似）；
精灵用**绝对左上角** `xpos/ypos + xanchor=0 + yanchor=0`（精确）。

## 3. 变量

| NS | Ren'Py |
|---|---|
| `%n` | `n<n>`，`default n<n> = 0` |
| `$n` | `s<n>`，`default s<n> = ""` |
| `?n` / `dim %n,10` | `a<n> = [0] * 10` |
| `numalias 好感度,10` | 别名表 → `n10` |
| `mov %0,24` / `mov $0,"雪"` | `$ n0 = 24` / `$ s0 = "雪"` |
| `add/sub/mul/mod` | `+= -= *= %=` |
| `div` | `$ n0 = int(n0 / n1)`（截断，对齐 NS） |
| `inc` / `dec` | `+= 1` / `-= 1` |
| `itoa` / `atoi` | `str()` / `int(float(...))` |
| `rnd %0,100` | `renpy.random.randint(0, 99)` |

## 4. 文本符号

| NS 文本内 | Ren'Py |
|---|---|
| `@` | `{w}`（点击后接着写，不清屏） |
| `\` | 断句（本页结束，成为下一条 say） |
| `!d500` / `!w500` | `{w=0.50}` |
| `!s30` | `{cps=30}`（自动闭合） |
| `#ff0000` | `{color=#ff0000}`（自动闭合） |
| `%0` / `$0` | `[n0]` / `[s0]` |
| `_`（单独成行） | 丢弃（点击去抖） |
| `/`（行末） / `` ` ``（行首） | 丢弃 |
| 字面 `[ ] { }` | `[[ ]] {{ }}` |

## 5. 音频

| NS | Ren'Py |
|---|---|
| `mp3loop` / `mp3` | `play music ...` / `play music ... noloop` |
| `wave` / `waveloop` | `play sound` / `play sound ... loop` |
| `wavestop` / `stop` | `stop sound` / `stop music` + `stop sound` |
| `wait` / `delay` | `$ renpy.pause(ms/1000.0)` |
| `play "*.mid"` | TODO（先预渲染成 OGG/WAV） |

## 6. 已知偏差

| 偏差 | 原因 | 影响 | 可修 |
|---|---|---|---|
| 装载/绘制拍平 | NS 先 `bg ...,0` 装、再 `print` 画 | 只影响"多图同帧切换"的演出 | 手工加 `with` |
| 过渡统一 `Dissolve` | 效果编号非 1:1 | 特殊演出丢失 | playbook §11 |
| 立绘锚点近似 | NS 受 `underline` 影响 | 可能偏几十像素 | 改 transform |
| `div` 截断 | Python `//` 向下取整 | 负数差 1 | 保持 `int(a/b)` |
| `rnd` 区间 | NS 文档未明确 | 骰子差 1 | 实测校准 |
| `fchk` 近似 | 查的是 image 名不是 tag | 已读分支可能错 | 改显式布尔 |
| say 合并 | 一页最多 16 行，Ren'Py 放不下 | 多出点击 | 调 `--max-lines` |
| 折行 | 23 列硬折 vs 容器软折 | 断点不同 | playbook §14 |

## 7. 判定优先级（转换器内部）

1. 编码：对每种编码解码后打分（`*define`/`*start`/`\ngame` 命中，`\ufffd` 扣分）。
2. XOR：候选 `0x84` 与 `0x00`（明文）各解码一次，取高分。
3. 命令/台词：查 `COMMANDS` 表，命中即命令。
4. 未命中命令表但形似命令（全小写英文 + 空格 + 参数）→ 仍按台词处理，
   写进 `WAIVERS.md` 复核（避免误伤英文台词）。
