# TODO 修复配方

每条配方结构：**症状 → 原理 → 配方 → 验证**。
配方里的代码可直接粘进 `.rpy`，但要按你的变量名/路径改。

---

## 1. `textgosub`（文本总钩子）

**症状**：转换器报 `textgosub 是文本总钩子，必须人工改写`。
**原理**：NS 每次显示文本前都会 `gosub` 到这个 label，常见用途是打字音、名字框、
逐字特效、把文本写进自定义日志。Ren'Py 没有等价物，但有三个替身。

**配方 A：只做文本过滤（最简单）**

```renpy
init python:
    def ns_text_filter(s):
        return s          # 在这里做全局替换/后缀
    config.say_menu_text_filter = ns_text_filter
```

**配方 B：每句触发一段演出（最接近原意）**

```renpy
init python:
    def ns_say_callback(event, interact=True, **kwargs):
        if event == "begin":
            renpy.sound.play("audio/type.ogg")
    config.all_character_callbacks = [ns_say_callback]
```

**配方 C：完全自绘文本层**（作品有独特文本框/逐字动画时）
重写 `screen say(who, what)`，保留 `id "what"`，否则存档回滚会失效。

**验证**：随便跳三段剧情，确认钩子每句都触发一次，且快进时不会叠音。

---

## 2. `for ... next`（循环）

**症状**：`for %2=0 to 3` / `next` 变成 TODO。
**原理**：Ren'Py 的脚本层没有循环语句；`python:` 块里能 `for`，但块内不能放 say。

**配方**：改写成 label 循环（把 `%0` 当计数器）。

```renpy
    $ n0 = 0
label loop_1:
    if n0 > 3:
        jump loop_1_end
    # ... 原来的循环体 ...
    $ n0 += 1
    jump loop_1
label loop_1_end:
```

循环体里有 `goto` 跳出时，把目标改成 `loop_1_end` 之后的 label。

**验证**：计数器在退出时等于上界+1；嵌套循环用不同 label 前缀。

---

## 3. `trap` / `lr_trap` / `trap2`（点击即跳转）

**症状**：整段剧情靠"点任意位置继续/触发分支"，转换后卡住。
**原理**：NS 把点击当成可捕获的事件；Ren'Py 用 screen 返回值表达。

```renpy
screen ns_clickwait(seconds=0):
    # 全屏热区
    button:
        xysize (config.screen_width, config.screen_height)
        background None
        action Return("click")
    if seconds:
        timer seconds action Return("timeout")

label ch1_wait:
    call screen ns_clickwait(10.0)
    if _return == "click":
        jump ch1_clicked
    jump ch1_timeout
```

`lr_trap` 区分左右键：热区加 `mousebutton`，或用两个 `key "mouseup_1"` / `"mouseup_3"`。

**验证**：连点不会跳过整段；超时分支能走到。

---

## 4. `selnum`（选择支 + 记录序号）

**症状**：选择后要把"选了第几项"存进变量。
**配方**：

```renpy
    menu:
        "名乗る":
            $ n3 = 0
            jump tell
        "黙っている":
            $ n3 = 1
            jump silent
```

需要"选了才显示后续差异"时，用 `if n3 == 0:` 分支，不要复制整段剧情。

**验证**：两个分支都点一遍，`n3` 的值与预期一致。

---

## 5. `btndef` / `btn` / `btnwait` / `spbtn`（图片按钮）

**症状**：标题画面、存读档按钮、CG 鉴赏全部变成 TODO。
**原理**：这是 NS 的整套 UI 框架，Ren'Py 用 screen language 重写，不是"转换"。

```renpy
screen ns_title_buttons():
    imagebutton:
        idle  "images/btn_start_idle.png"
        hover "images/btn_start_hover.png"
        xpos 260 ypos 300
        action Return("start")
    imagebutton:
        idle  "images/btn_load_idle.png"
        hover "images/btn_load_hover.png"
        xpos 260 ypos 340
        action ShowMenu("load")

label title:
    call screen ns_title_buttons()
    if _return == "start":
        jump start
```

按钮位置直接抄 NS 的 `btn` 坐标（记得乘 `--scale`）。
`btnwait` 的"等待+返回值"就是 `call screen` + `_return`。

**验证**：每个按钮位置与截图对齐；`ShowMenu` 类动作不破坏存档。

---

## 6. `monocro` / `nega`（单色 / 负片）

```renpy
    # 单色（去饱和）
    show ns_bg_room at Transform(matrixcolor=SaturationMatrix(0.0))
    # 恢复
    show ns_bg_room at Transform(matrixcolor=SaturationMatrix(1.0))
```

负片没有现成类：用自定义 4×4 矩阵，或直接把素材预渲染成反色版本再切换。
矩阵写法必须在目标 Ren'Py 版本上实测，别照抄博客。

**验证**：切换后立绘/背景都变色；存档读取后颜色状态正确。

---

## 7. `tal` / `vsp` / `amsp`（透明度 / 显隐 / 移动动画）

```renpy
    # tal：只改透明度，不动位置
    show ns_c_yuki at Transform(xalign=0.5, yalign=1.0, alpha=0.5)

    # vsp 0,0 / vsp 0,1：等价于 hide / show 同一个 tag
    hide ns_sp0_name
    show ns_sp0_name at Transform(xpos=100, ypos=60, xanchor=0.0, yanchor=0.0)

    # amsp：带时间的移动，用 ATL
    show ns_sp0_name at Transform(xpos=100, ypos=60, xanchor=0.0, yanchor=0.0):
        linear 0.4 xpos 300 ypos 200
```

`amsp` 的加速度参数用 `ease` / `easein` 近似，逐条调。

**验证**：动画期间点击不会打断到下一条台词（必要时 `$ renpy.pause(0.5, hard=True)`）。

---

## 8. `skip` / `jumpf` / `jumpb`

- `skip N`：跳过 N 行脚本。人工确认这 N 行是什么，然后删掉或注释；
  **不要**机械删，NS 里常用来跳过"已读分支"。
- `jumpf` / `jumpb`：跳到下一个/上一个 `~` 标记。改成显式 label：

```renpy
    jump after_choice      # 原 jumpf
label after_choice:
```

**验证**：分支图（`taskpack` 的出入边）没有环，或环是刻意设计。

---

## 9. `fchk` / `lchk`（图像/标签是否用过）

```renpy
    if renpy.seen_image("ns_c_yuki_normal"):
        jump h_scene_repeat
    if renpy.seen_label("route_a"):
        jump route_a_hint
```

注意：NS 的 `fchk` 参数是**图像 tag**（`ld` 时自动生成），不是文件名；
转换器只能按字面转。若判断不准，改成显式布尔变量最稳：

```renpy
    $ seen_yuki_normal = True     # 在 ld 之后立刻置位
    ...
    if seen_yuki_normal:
```

**验证**：新开档 vs 二周目，两条路径都走一遍。

---

## 10. `textoff` / `texton` / `windoweffect`

用 Ren'Py 的窗口控制，不要手工改 screen 可见性：

```renpy
    window hide          # textoff
    ...
    window show          # texton
    window auto          # 交还给自动管理
```

**验证**：CG 鉴赏、全屏演出段落里没有残留文本框。

---

## 11. `effect` 编号 → Ren'Py 过渡

转换器统一给了 `Dissolve`。按观感替换：

| NS 效果观感 | Ren'Py |
|---|---|
| 淡入淡出 | `Dissolve(t)` |
| 从左/右推入 | `wipeleft` / `wiperight` / `MoveTransition` |
| 马赛克渐显 | `Pixellate(t)` |
| 圆形/自定义形状 | `ImageDissolve("images/mask.png", t)` |
| 闪白/闪黑 | `Fade(t, color="#fff")` |

**验证**：把 `effect` 编号和实际观感列成表，和原作录屏逐条对。

---

## 12. 未定义跳转（`report.txt` 的清单）

处理顺序，别跳步：

1. 查 NS 原文该行**上下文**（前后各 10 行），确认目标是不是拼写错误。
2. 目标在**别的脚本文件**里（NS 支持多文件）→ 把那个文件也转进来，合并后再 verify。
3. 目标确实不存在（原版就是死链/被删）→ 建一个空 label + 注释 `# 原版死链`，
   并在 `WAIVERS.md` 登记。
4. 绝不改成"跳到最近的 label"——会静默改变剧情结构。

---

## 13. 说话人归属（`--infer-speaker` 的校对）

转换器的启发式：**最近一次 `ld` 的立绘名 = 说话人**。它对"立绘常驻"的作品准，
对"多人同框/旁白"的作品错。

修法：维护一张 `speakers.csv`

```csv
ns_line,label,inferred,actual
1234,ch1_a,yuki,旁白
1240,ch1_a,yuki,雪
```

批量改：用 `sed`/脚本把指定行号的 `yuki "..."` 换成 `"..."`（旁白）。
改完必须跑 `verify.py`，确认没有把名字当台词打出来。

---

## 14. 文本折行（23 全角列 × 16 行）

NS 按 `setwindow` 的列数硬折行，Ren'Py 按容器宽度软折行，断点必然不同。

- 只是"看着不一样"：调 `gui.text_size` + 文本框宽度，接受差异。
- 必须逐字复刻：在转换后处理阶段按列宽插 `\n`（全角=1 列，半角=0.5 列），
  并把 Ren'Py 的 `layout "tex"` 关掉，避免二次折行。

**验证**：抽 20 句最长的台词，比对每行断点。
