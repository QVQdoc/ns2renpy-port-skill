# 汇合点验证指南

汇合点是模块化移植最容易出错的地方：每条前驱路线单独实现都是正确的，拼接起来却会带来不兼容的画面、音乐或变量状态。本指南把汇合点从"组装时才发现"的问题，变成"规划时就登记、组装时逐条核对"的清单。

## 一、什么是汇合点

以下三种情况都必须登记为汇合点：

| 类型 | 定义 | 例子 |
|---|---|---|
| `sequence_merge` | 多条剧情路线汇聚到同一节点继续 | 雪线和玲线都通向"毕业典礼" |
| `call_return` | 多个模块 call 同一个共享段，返回后继续 | 多个章节都调用"角色介绍过场" |
| `loop_entry` | 循环重新进入某节点，状态带上一轮残留 | 时间循环、可重复的日常事件 |

判定方法：在 `graph.json` 中，任何入边数量 ≥ 2 的节点，都必须出现在 `mergepoints.json` 里。入边为 1 的节点不需要登记。

注意区分：入边数量多 ≠ 汇合点。如果多条入边来自同一个模块内部的相邻分支，且都在同一模块内处理，可以只在模块内说明，不必登记到全局清单。判断标准是**是否跨越模块边界**。

## 二、登记时机

汇合点清单在**阶段 2（模块规划）**建立，不在阶段 5。原因：

- 划分模块时需要知道哪些节点会被多个模块指向，这些节点往往应该独立成模块或明确归属
- 前驱与汇合模块的任务包都要写清"进入/离开时应该是什么状态"
- 等到组装时才发现，往往要回改多个模块

## 三、mergepoints.json 结构

```json
{
  "version": "1",
  "mergepoints": [
    {
      "id": "mp_common_evening",
      "label": "common_evening",
      "module": "common_02",
      "kind": "sequence_merge",
      "incoming_edges": ["e_after_yuki_walk", "e_after_rei_study", "e_school_alone"],
      "predecessors": [
        {
          "from_node": "yuki_walk",
          "from_module": "yuki_01",
          "expected_state": {
            "bg": "park",
            "music": "theme_yuki",
            "characters_shown": ["yuki"],
            "variables": {"yuki_favor": ">=50"}
          },
          "exit_type": "jump",
          "source": {"file": "src_0", "lines": [320, 322]}
        },
        {
          "from_node": "rei_study",
          "from_module": "rei_01",
          "expected_state": {
            "bg": "library",
            "music": "theme_rei",
            "characters_shown": ["rei"],
            "variables": {"rei_route": "==1"}
          },
          "exit_type": "jump",
          "source": {"file": "src_0", "lines": [480, 482]}
        },
        {
          "from_node": "school_alone",
          "from_module": "common_01",
          "expected_state": {
            "bg": "school",
            "music": "bgm_daily",
            "characters_shown": [],
            "variables": {}
          },
          "exit_type": "jump",
          "source": {"file": "src_0", "lines": [170, 172]}
        }
      ],
      "conflict_resolution": {
        "bg": "each_predecessor_keeps_own_bg",
        "music": "fade_to_common_theme",
        "characters_shown": "hide_all_before_entry",
        "variables": "no_reset"
      },
      "semantic_note": "三条路线进入后的第一句台词都是'傍晚了'，但背景应保持各自路线的场景",
      "verification": {
        "status": "unverified",
        "checked_predecessors": [],
        "failed_predecessors": [],
        "runtime_evidence": null,
        "notes": null
      }
    }
  ]
}
```

### 关键字段说明

**predecessors[].expected_state**
该前驱离开时**应该**带来的状态。不是"进入汇合点后应该是什么"，而是"前驱把它留在什么状态"。

**exit_type**
`jump` / `call` / `fall_through`。call 返回型汇合点的状态继承规则与 jump 不同：call 返回后调用方的变量上下文仍在。

**conflict_resolution**
状态冲突的处理策略。常用取值：

| 策略 | 含义 | 何时使用 |
|---|---|---|
| `each_predecessor_keeps_own_bg` | 各前驱保留自己的背景，汇合点不重置 | 原作本来就是各路线背景不同 |
| `reset_to_<具体值>` | 统一重置为固定状态 | 原作在此处明确切到新场景 |
| `fade_to_<音乐>` | 音乐交叉淡入到统一主题 | 保留连续性又不冲突 |
| `hide_all_before_entry` | 进入前清空所有立绘 | 避免上一路线的角色残留 |
| `no_reset` | 完全继承前驱状态 | 汇合点开头紧接着前驱的演出 |

**semantic_note**
写下这个汇合点在原作中的语义。很多"冲突"其实是原作设定，这一条能防止后续修复者把设计当成 bug 修掉。

**verification**
`status` 取值与含义：

| status | 含义 | 达到条件 |
|---|---|---|
| `unverified` | 未验证 | 初始状态 |
| `state_checked` | 静态核对过 | 读过所有前驱出口代码并比对 expected_state |
| `runtime_tested` | 运行测试过 | 实际跑通至少一条前驱路径并观察状态 |
| `validated` | 全部验证 | 所有前驱路径实际跑通且状态符合预期 |

`checked_predecessors` 记录实际跑过的前驱。只有全部前驱都在这个列表里，才能标 `validated`。

## 四、验证流程

### 静态核对（state_checked）

对每个前驱模块：

1. 打开前驱模块的出口实现，确认最后执行的 scene / show / hide / play / stop
2. 确认最后修改的变量值
3. 与 expected_state 比对，不一致则登记 issue

这一步能发现大部分问题，特别是：
- 前驱切换到别的背景但忘了恢复
- 前驱播放了音乐但没有在汇合点处理
- 前驱残留了立绘

### 运行验证（runtime_tested）

对每条前驱路径：

1. 实际运行游戏，走到该前驱
2. 在汇合点入口插入临时日志或断点，记录实际状态：

```renpy
label common_evening:
    $ _mp_debug = {
        "mp": "mp_common_evening",
        "bg": renpy.get_attributes("bg"),
        "music": renpy.music.get_playing("music"),
        "chars": [t for t in ("yuki", "rei") if renpy.showing(t)],
        "yuki_favor": yuki_favor,
    }
    $ print("MP_CHECK", _mp_debug)
```

3. 与 expected_state 比对
4. 把该前驱加入 checked_predecessors

同一段调试代码可以批量插入所有汇合点入口，一次性跑完所有路线收集数据，比逐个人肉检查快。

### 条件可达性验证

这是最容易糊弄过去的一环。"图上有边"不等于"条件满足时能走到"。

对每个汇合点前驱：

1. 取出该前驱路径上所有条件的合取
2. 检查是否存在变量取值组合能让所有条件同时满足
3. 无法静态判断时，实际运行到该路径
4. 确认走不通的，登记 issue 并在 expected_state 里标注 `unreachable`

典型陷阱：
- 条件 `yuki_favor >= 50` 和 `yuki_favor <= 40` 在同一路径上串联，永远不可达
- 某个前驱需要的变量从未被任何模块设置过
- 原作有隐式重置（如每周目开始重置好感度），移植时漏了

## 五、常见冲突与处理

### 1. 背景残留

**现象**：路线 A 结尾是"公园"，汇合点开头原作是"学校"，但移植后从 A 进去看到公园。

**原因**：A 模块以为自己跳走了就不管状态，汇合模块以为自己进来就是学校。

**处理**：汇合模块第一个事件显式 `scene bg school`。如果原作确实保留各路线背景，则在 conflict_resolution 写 `each_predecessor_keeps_own_bg` 并在汇合点用 if 分支处理。

### 2. 音乐叠加

**现象**：进入汇合点后两首 BGM 同时播放。

**原因**：Ren'Py 的 music channel 默认是单通道会替换，但用了多个 channel 或 sound channel 播 BGM 时会叠加。

**处理**：确认所有 BGM 都走 `music` channel；汇合点显式 `play music "..."` 或 `stop music fadeout 1.0`。

### 3. 立绘残留

**现象**：玲线进入的汇合点出现雪的立绘。

**原因**：Ren'Py 的 `show` 是累积的，前驱没有 hide。

**处理**：汇合点入口 `hide yuki` / `hide rei`，或统一用 `scene` 清空。注意 scene 会连背景一起清，需重新 show bg。

### 4. 变量语义冲突

**现象**：同一个变量在不同路线含义不同（如 `%10` 在雪线是"雪好感度"，在玲线是"玲好感度"）。

**原因**：原作复用变量编号。移植时如果不拆分成不同变量，汇合后判断会错。

**处理**：在 catalog 中拆成 `yuki_favor` / `rei_favor` 两个变量，并在映射表记录原编号到两个新变量的对应关系。这类问题必须在阶段 1 发现，不能等到组装。

### 5. call 返回型汇合点

**现象**：共享段 call 返回后，调用方的状态被共享段改坏了。

**原因**：共享段修改了调用方也依赖的变量。

**处理**：共享段的契约中明确"允许修改的变量"白名单；共享段内不自作主张重置背景音乐（除非原作如此）。

## 六、与 STATUS.md 的联动

STATUS.md 的"未验证事项"必须列出所有 `unverified` 和 `state_checked` 的汇合点：

```text
## 未验证事项
汇合点：
- mp_common_evening: state_checked（3 前驱中 1 个跑过）
- mp_birthday: unverified
- mp_final_choice: runtime_tested（2 前驱中 2 个跑过，但条件可达性未确认）
```

组装完成后，汇合点的整体验证状态取所有汇合点的最低值：

- 有任何一个 `unverified` → 整体未验证
- 全部 `runtime_tested` 以上 → 汇合验证通过
- 全部 `validated` → 汇合验证完成

不能因为"大部分汇合点没问题"就标整体通过。
