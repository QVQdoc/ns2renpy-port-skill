# 蓝图与模块模板

这些是移植项目生成的工作数据，不是新的游戏运行时。结构化数据用于核对和分工，最终直接生成 Ren'Py。
小项目可合并文件，保持信息完整即可；大项目按章节拆 graph/event 数据，并在目录中索引。

## 项目布局

```text
port/
  STATUS.md                 当前进度和下一步
  overview.md               全局故事、路线及功能简述
  sources.json              源文件读取覆盖和原文位置
  graph.json                节点、边、条件及模块归属
  catalog.json              角色、变量、素材和公共功能
  contracts.md              公共接口、版本历史及影响范围
  issues.json               未解决问题与明确决定
  mergepoints.json          汇合点清单与验证状态
  modules/
    common_01/brief.md       自包含任务说明
    common_01/events.json   完整有序事件及来源
    common_01/source.txt    对应原文（或准确的原文索引）
    common_01/result.md     实现及验证结果
  validation.md             lint、启动、路线和演出核对记录
project/game/
  port_characters.rpy
  port_variables.rpy
  port_images.rpy
  port_screens.rpy
  story/common_01.rpy
  story/yuki_01.rpy
```

素材相对路径以 Ren'Py 的 game 目录为基准，例如 `images/bg/classroom.jpg` 对应 `project/game/images/bg/classroom.jpg`。
若已有工程，沿用其目录结构，不覆盖现有 gui/screens 文件。

## 全局概述 overview.md

```text
作品与输入范围：
目标 SDK/分辨率：
故事概要：
主要角色：
共同线与路线：
分支/汇合/结局：
关键变量与跨周目解锁：
共用 UI/特殊交互：
素材与演出约定：
蓝图版本：
详细数据索引：
未确定事项：
```

## 来源登记 sources.json

```json
{
  "version": "2",
  "encoding": "utf-8",
  "files": [{
    "id": "src_0",
    "path": "source/0.txt",
    "encoding": "cp932",
    "total_lines": 500,
    "read_ranges": [[1, 200], [301, 400]],
    "parsed_ranges": [[1, 150], [160, 200], [301, 350]],
    "unparsed_ranges": [[151, 159], [351, 400]],
    "unread_ranges": [[201, 300], [401, 500]],
    "dynamic_behaviors": [
      {
        "lines": [155, 158],
        "type": "dynamic_goto",
        "raw_code": "goto *%50",
        "depends_on_vars": ["n50"],
        "possible_targets": ["yuki_event", "rei_event", "common_evening"],
        "certainty": "needs_runtime_verification",
        "issue_id": "ISSUE-001"
      },
      {
        "lines": [370, 375],
        "type": "implicit_interaction",
        "behavior": "click_area_map",
        "coordinates": {"x": [100, 500], "y": [200, 600]},
        "targets": ["school", "home", "park"],
        "certainty": "fully_resolved"
      }
    ]
  }]
}
```

**四层覆盖状态：**

| 字段 | 含义 |
|---|---|
| `read_ranges` | 已读取的行号区间 |
| `parsed_ranges` | 已成功解析含义的区间（read_ranges 的子集） |
| `unparsed_ranges` | 读过但尚未确定行为的区间 |
| `unread_ranges` | 完全未读的区间 |

**dynamic_behaviors 类型：**

| type | 含义 | 必填字段 |
|---|---|---|
| `dynamic_goto` | 目标为变量或表达式的跳转 | raw_code、depends_on_vars、possible_targets |
| `implicit_interaction` | 点击区域、计时推进等隐式交互 | behavior、trigger、targets |
| `dynamic_asset_path` | 变量拼接的素材路径 | raw_code、depends_on_vars、resolved_values |

行号指统一解码后保留的原始行；源文件变更后更新版本或哈希并重新核对索引。

## 流程图 graph.json

示例数据仅示范结构；实际项目必须包含所引用的全部节点定义。

```json
{
  "version": "2",
  "entry": "school_choice",
  "nodes": [
    {
      "id": "school_choice",
      "module": "common_01",
      "kind": "choice",
      "source": {"file": "src_0", "lines": [150, 170]}
    },
    {
      "id": "yuki_walk",
      "module": "yuki_01",
      "kind": "scene"
    },
    {
      "id": "common_evening",
      "module": "common_02",
      "kind": "scene"
    },
    {
      "id": "game_ending_a",
      "module": "endings",
      "kind": "ending",
      "ending_type": "true_end"
    }
  ],
  "edges": [
    {
      "id": "e_accept",
      "from": "school_choice",
      "to": "yuki_walk",
      "kind": "choice",
      "text": "一起回去",
      "condition": {
        "raw_ns": "%10 >= 50 && %20 == 1",
        "normalized": "yuki_favor >= 50 and yuki_route == 1",
        "variables_used": ["yuki_favor", "yuki_route"],
        "certainty": "fully_resolved"
      },
      "display_condition": null,
      "effects": [
        {"var": "yuki_favor", "op": "add", "value": 1}
      ]
    },
    {
      "id": "e_decline",
      "from": "school_choice",
      "to": "common_evening",
      "kind": "choice",
      "text": "留在学校",
      "condition": null,
      "display_condition": null,
      "effects": []
    },
    {
      "id": "e_dynamic",
      "from": "map_select",
      "to": "DYNAMIC",
      "kind": "interaction",
      "condition": {
        "raw_ns": "goto *%50",
        "normalized": "UNRESOLVED",
        "variables_used": ["n50"],
        "certainty": "needs_verification",
        "possible_targets": ["school", "home", "park"],
        "issue_id": "ISSUE-001"
      },
      "effects": []
    }
  ]
}
```

**条件字段三层：**

| 字段 | 含义 |
|---|---|
| `condition.raw_ns` | 原始 NS 表达式，原样保留 |
| `condition.normalized` | 规范化的 Ren'Py 表达式；无法确定时写 `"UNRESOLVED"` |
| `condition.certainty` | `fully_resolved` / `needs_verification` / `unresolved` |

**其他字段：**

- `variables_used`：依赖的变量列表，用于追踪状态与影响分析
- `possible_targets`：动态跳转可能的目标
- `display_condition`：选项显示条件（与选中后的执行条件分开记录）
- `ending_type`：结局类型（`true_end` / `normal_end` / `bad_end` 等）

边类型可为 sequence、choice、conditional、call、return、interaction。
不要把所有无出边节点自动认定为结局——只有原作明确的结局才标 ending。

## 公共目录 catalog.json

```json
{
  "version": "2",
  "characters": [
    {
      "id": "yuki",
      "display_name": "雪",
      "ns_alias": "$0",
      "color": "#e3f2fd"
    }
  ],
  "variables": [
    {
      "id": "yuki_favor",
      "type": "int",
      "initial": 0,
      "scope": "save",
      "source_name": "%10",
      "meaning": "雪的好感度",
      "modified_by_modules": ["common_01", "yuki_01", "yuki_02"]
    },
    {
      "id": "unlocked_gallery",
      "type": "list",
      "initial": "[]",
      "scope": "persistent",
      "source_name": "?20",
      "meaning": "已解锁 CG 列表"
    }
  ],
  "assets": [
    {
      "id": "bg_school",
      "kind": "background",
      "source_path": "bg/school.jpg",
      "target_path": "images/bg/school.jpg",
      "status": "inspected",
      "resolution": [1280, 720],
      "format": "JPEG",
      "has_alpha": false,
      "conversion": null
    },
    {
      "id": "sprite_yuki_smile",
      "kind": "character_sprite",
      "source_path": "fg/yuki_smile.png",
      "target_path": "images/characters/yuki_smile.png",
      "status": "needs_conversion",
      "resolution": [800, 1200],
      "format": "PNG",
      "has_alpha": true,
      "conversion": {
        "action": "extract_alpha",
        "notes": "NS 使用独立遮罩，需合并到 alpha 通道"
      }
    },
    {
      "id": "bgm_main",
      "kind": "music",
      "source_path": "sound/main.mid",
      "target_path": "audio/bgm_main.ogg",
      "status": "referenced_not_inspected",
      "conversion": {
        "action": "midi_to_ogg",
        "notes": "需要用 soundfont 预渲染"
      }
    }
  ],
  "features": [
    {
      "id": "map_select",
      "behavior": "点击地图区域选择地点",
      "interface": "call screen port_map",
      "returns": "location_id",
      "owner": "shared",
      "status": "custom",
      "implementation_file": "port_screens.rpy",
      "notes": "返回字符串 location_id，需在调用处根据返回值跳转"
    }
  ]
}
```

**变量字段：**

| 字段 | 说明 |
|---|---|
| `scope` | `save`（存档内）/ `persistent`（跨周目）/ `local`（标签局部） |
| `source_name` | 原始 NS 变量名（如 `%10`），改名后保留映射 |
| `modified_by_modules` | 所有修改此变量的模块，用于契约升级的影响分析 |

**素材 status 四态：**

| status | 含义 |
|---|---|
| `referenced_not_inspected` | 只在脚本里见过文件名 |
| `inspected` | 已实际检查文件 |
| `needs_conversion` | 已检查且确认需要转换 |
| `ready` | 已转换完成可直接使用 |

**feature status 四态：** `native`（原生覆盖）/ `configured`（配置即可）/ `custom`（需自写）/ `unsupported`（无法实现）。
详见 [系统功能映射](system_features.md)。

公共契约明确屏幕调用参数/返回值、label 名、角色/素材名称、模块文件归属及公共变量修改规则。

## 汇合点清单 mergepoints.json

凡是**跨模块**入边数量 ≥2 的节点，都登记在这里。完整说明见 [汇合点验证指南](mergepoints_guide.md)。

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
      "semantic_note": "三条路线进入后第一句台词都是「傍晚了」，但背景应保持各自路线的场景",
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

**verification.status 四态：**

| status | 含义 | 达到条件 |
|---|---|---|
| `unverified` | 未验证 | 初始状态 |
| `state_checked` | 静态核对 | 读过所有前驱出口代码并比对 expected_state |
| `runtime_tested` | 运行测试 | 实际跑通至少一条前驱路径并观察状态 |
| `validated` | 全部验证 | 所有前驱都实际跑通且状态符合预期 |

只有全部前驱都在 `checked_predecessors` 里，才能标 `validated`。

## 公共契约 contracts.md

````markdown
# 公共契约

## 版本历史

| 版本 | 变更内容 | 受影响模块 | 兼容性 |
|---|---|---|---|
| 2.0 | 增加 yuki_favor_max；port_map 返回值改为字典 | common_01, yuki_01, yuki_02 | 不兼容，需重新实现 |
| 1.1 | 增加 bg_park_night 素材 | yuki_01 | 向后兼容 |
| 1.0 | 初始版本 | 全部 | - |

## 角色定义

所有角色定义在 port_characters.rpy。

```python
define yuki = Character("雪", color="#e3f2fd")
define rei = Character("玲", color="#fff9c4")
```

## 变量定义

所有共享变量定义在 port_variables.rpy。

```python
default yuki_favor = 0        # 雪的好感度，范围 0-100
default yuki_route = 0        # 是否进入雪路线，0=否 1=是
default persistent.unlocked_gallery = []  # 已解锁 CG
```

修改规则：
- yuki_favor：只能由 common_01、yuki_01、yuki_02 修改
- yuki_route：只能由 common_02 一次性设置
- persistent.unlocked_gallery：只能通过 port_unlock_cg() 追加，不直接操作

## 素材定义

所有素材在 port_images.rpy 中定义。

```renpy
image bg school = "images/bg/school.jpg"
image yuki smile = "images/characters/yuki_smile.png"
```

## 公共 Screen

### port_map

签名：

```renpy
screen port_map(available_locations):
    # available_locations: list[str]
```

返回：

```python
{
    "location": str,  # "school" | "home" | "park"
    "time": str       # "day" | "night"
}
```

实现位置：port_screens.rpy

使用示例：

```renpy
$ result = renpy.call_screen("port_map", ["school", "home"])
if result["location"] == "school":
    jump school_visit
```

## 公共函数

### calculate_route()

签名：

```python
def calculate_route():
    """根据当前好感度判定进入哪条路线"""
    return str  # "yuki" | "rei" | "common"
```

实现位置：port_functions.rpy

## Label 命名规则

- 模块入口：module_id（如 common_01）
- 子场景：module_id_scene_name（如 yuki_01_confession）
- 结局：ending_<type>（如 ending_true）
````

## 模块 brief.md

```text
模块 ID / 名称：common_01 / 共同线第一章
蓝图版本 / 公共契约版本：2 / 2.0
全局故事简述：（参考 overview.md）
本模块剧情目的：介绍主角和两位女主角，展示日常校园生活，玩家选择是否与雪一起回家

负责节点：intro_morning, classroom_talk, school_choice

只读依赖（准确路径及必要条目）：
- port/catalog.json: characters.yuki, characters.rei
- port/contracts.md v2.0: yuki、rei 角色定义

允许写入的文件：
- project/game/story/common_01.rpy
  （须遵守 references/conventions.md：src 来源注释、语义 transform、禁止裸坐标）

入口 label：common_01

入口前置条件：无（游戏开始）

入口画面/音频状态：
  Variant 1（新游戏开始）:
    bg: 黑屏
    music: null
    variables: 所有变量为初始值

完整剧情及演出数据：modules/common_01/events.json
原文：modules/common_01/source.txt（对应 src_0 lines 1-170）

需要共享变量（直接给出条目，不要让实现者去翻 catalog）：
- yuki_favor (int, initial=0)：本模块可增加 0-2 点
- game_day (int, initial=1)：本模块结束时设为 2

需要素材：
- bg_school (images/bg/school.jpg, ready)
- bg_classroom (images/bg/classroom.jpg, ready)
- yuki_smile (images/characters/yuki_smile.png, needs_conversion)
- bgm_daily (audio/bgm_daily.ogg, ready)

需要公共功能：无

出口：
- 出口1：jump yuki_walk（条件：选择「一起回去」）
    离开状态：bg=school_gate, music=bgm_daily, yuki_favor+=1
- 出口2：jump common_evening（条件：选择「留在学校」）
    离开状态：bg=school, music=bgm_daily, yuki_favor 不变

本模块结局：无

待解决问题：无

验收场景：
1. 正常路径：新游戏 → intro → 选择「一起回去」→ 正确跳转到 yuki_walk
2. 条件分支：新游戏 → intro → 选择「留在学校」→ 正确跳转到 common_evening
3. 状态检查：两个出口的 yuki_favor、bg、music 符合预期
4. 关键演出：教室对话时立绘正确显示与隐藏，背景音乐循环播放
```

任务包应给出本模块实际需要的角色/变量/素材定义，或精确条目索引；不要让实现者为了查一个 ID 重新读整个目录。

## 模块事件 events.json

```json
{
  "module": "common_01",
  "contract_version": "2.0",
  "nodes": [
    {
      "id": "school_choice",
      "label": "school_choice",
      "events": [
        {
          "id": "ev_001",
          "type": "background",
          "asset": "bg_school",
          "transition": "dissolve",
          "source": {"file": "src_0", "lines": [150, 150]},
          "wait_for": null
        },
        {
          "id": "ev_002",
          "type": "show_character",
          "asset": "yuki_smile",
          "position": "center",
          "transition": "dissolve",
          "source": {"file": "src_0", "lines": [151, 151]},
          "wait_for": null
        },
        {
          "id": "ev_003",
          "type": "dialogue",
          "speaker": "yuki",
          "text": "今天要一起回去吗？",
          "source": {"file": "src_0", "lines": [152, 152]},
          "wait_for": "click"
        },
        {
          "id": "ev_004",
          "type": "wait",
          "wait_for": "timer",
          "duration_ms": 800,
          "animation_id": null,
          "source": {"file": "src_0", "lines": [153, 153]}
        },
        {
          "id": "ev_005",
          "type": "sound",
          "asset": "se_door",
          "wait_for": "sound_end",
          "source": {"file": "src_0", "lines": [153, 153]}
        },
        {
          "id": "ev_006",
          "type": "choice",
          "edges": ["e_accept", "e_decline"],
          "source": {"file": "src_0", "lines": [154, 154]},
          "wait_for": null
        }
      ]
    }
  ]
}
```

**wait_for 取值：**

| 值 | 含义 | 附加字段 |
|---|---|---|
| `null` | 无需等待 | - |
| `click` | 点击推进 | - |
| `timer` | 定时等待 | `duration_ms` |
| `music_end` | 等音乐结束 | - |
| `sound_end` | 等音效结束 | - |
| `animation_end` | 等动画结束 | `animation_id` |
| `interaction` | 等交互完成 | `interaction_id` |

按需增加 show/hide、expression、move、music、sound、voice、assignment、interaction 等事件类型。
嵌入文本的等待、速度、插值和条件文本必须保留；不要通过摘要省略。播放与停止、循环、淡入淡出和声道分别记录。

## 问题登记 issues.json

每项包含 id、source、module、问题描述、影响范围、状态、决定及决定来源。

```json
{
  "version": "1",
  "issues": [
    {
      "id": "ISSUE-001",
      "source": {"file": "src_0", "lines": [155, 158]},
      "modules": ["common_01", "yuki_01"],
      "problem": "动态跳转目标依赖运行时变量 %50，无法静态确定",
      "impact": "可能影响路线连接的正确性",
      "status": "open",
      "decision": null,
      "decided_by": null
    },
    {
      "id": "ISSUE-002",
      "source": {"file": "src_0", "lines": [200, 210]},
      "modules": ["common_02"],
      "problem": "原作使用 MIDI 音乐，目标平台不支持",
      "impact": "需要预渲染为 OGG 或使用替代音乐",
      "status": "resolved",
      "decision": "使用 FluidSynth 将 MIDI 渲染为 OGG",
      "decided_by": "user"
    }
  ]
}
```

状态可为 `open` / `resolved` / `accepted_difference`。
`accepted_difference` 需要用户明确接受，不能由 AI 自行认定。

## STATUS.md

```text
项目：<游戏名称>
最后更新：<YYYY-MM-DD>

## 当前阶段
4 - 分别实现

## 版本
蓝图版本：2
公共契约版本：2.0

## 读取覆盖
- src_0: 已读 1-400/500 行，已解析 1-350 行，未解析 151-159 / 351-400
- src_1: 未读

## 模块进度

| 模块 | 状态 | 备注 |
|---|---|---|
| common_01 | runtime_tested | lint 通过，实际运行正常 |
| yuki_01 | code_review | 代码完成，待 review |
| yuki_02 | implementing | 实现中 |
| rei_01 | spec_ready | 规范已就位，待实现 |
| common_02 | planned | 待规划 |
| endings | blocked:ISSUE-003 | 等待动态跳转问题解决 |

状态定义：
planned / spec_ready / implementing / code_review /
lint_pass / runtime_tested / validated / blocked:<issue_id>

## 汇合点验证

| 汇合点 | 状态 | 备注 |
|---|---|---|
| mp_common_evening | state_checked | 3 前驱中 1 个跑过 |
| mp_birthday | unverified | - |
| mp_final_choice | runtime_tested | 条件可达性未确认 |

## 已完成验证
- lint：common_01 通过
- 启动：项目可启动，主菜单正常
- 路线测试：common_01 → yuki_walk 通过

## 未验证事项
- 汇合点 mp_birthday 全部前驱
- rei 路线条件可达性
- 所有结局实际可达性
- 存读档在汇合点的正确性

## 当前问题
- ISSUE-001：动态跳转（open）
- ISSUE-003：结局触发条件不明确（open）

## 下一步
1. 完成 yuki_02 模块实现
2. 测试 mp_common_evening 剩余 2 个前驱
3. 解决 ISSUE-001 或交用户决定

## 本轮变更及受影响模块
- 公共契约 v1.1 → v2.0
- 受影响：common_01, yuki_01, yuki_02（需 review 变量修改处）
```
