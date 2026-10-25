# 系统功能映射

NS 游戏的存读档、跳过、设置、历史等系统功能，不需要逐条复刻。优先用 Ren'Py 原生实现，只在原生能力不足时才补代码。

但"用原生"不等于"什么都不用做"——原作的系统行为中有一部分会与剧情状态耦合，这些必须在移植时显式处理。

## 一、优先级原则

1. **原生能完全覆盖**：直接使用，不写代码
2. **原生能覆盖但默认行为不同**：配置 config 变量，不改结构
3. **原生能力不足**：写 screen 或函数实现，登记到 catalog.features
4. **原作功能无法实现或已过时**：登记 issue，由用户决定接受差异

每个系统功能在 `catalog.json` 的 `features` 数组中登记状态：`native` / `configured` / `custom` / `unsupported`。

## 二、存读档

### NS 原作行为

`セーブ` / `ロード` 指令打开存档界面，存档槽通常 10-20 个，存在游戏目录。部分作品有"存档预览图"、"存档注释"、"快速存档"。

### Ren'Py 原生能力

原生 save/load 已经覆盖存档槽、缩略图、时间戳。默认 10 个槽位，可配置：

```renpy
define config.save_directory = "MyGame-1.0"
define config.has_autosave = True
define config.autosave_slots = 3
define config.quicksave_slots = 3

# 存档槽数量
define config.save_slots_per_page = 6
```

### 需要显式处理的部分

**1. 存档时机的剧情耦合**

NS 原作可能在特定指令后禁止存档（如演出中、选项前）。检查是否存在：

```text
; 原作示例
if %flag == 1  ; 演出中
    存档无效
```

对应 Ren'Py：

```renpy
label dramatic_scene:
    $ renpy.block_rollback()
    # 需要禁止存档时
    $ _game_menu_screen = None
    ...
    $ _game_menu_screen = "save"
```

**2. 存档内必须包含的变量**

Ren'Py 自动保存所有 `default` 和 `define` 之外的 store 变量。但如果是存在外部文件或多周目信息，需要显式处理：

```renpy
# 存档内（默认行为）
default yuki_favor = 0

# 跨周目（需要 persistent）
default persistent.unlocked_gallery = []

# 不该存档的临时变量
define _temp_counter = 0  # define 不进存档
```

**3. 存读档的验证点**

凡是汇合点，都必须测试"从前驱存档、在汇合点读档"是否正确恢复状态。这是汇合点验证的一部分。

## 三、跳过

### NS 原作行为

按住 Ctrl 或点击特定区域跳过已读文本；部分作品有"全跳过"和"跳到下一个选择"。

### Ren'Py 原生能力

原生支持 Ctrl 跳过，`config.skipping` 控制：

```renpy
define config.allow_skipping = True
define config.skip_delay = 75  # 跳过时每行停留毫秒

# 只跳过已读
default preferences.skip_unseen = False
```

### 需要显式处理的部分

**1. 跳过到选择点的行为**

Ren'Py 跳过默认在选择点停止。若原作行为不同（如跳过也自动选默认项），需要显式实现。多数情况下原生行为更安全，保持即可。

**2. 特殊演出的跳过限制**

有动画、计时等待的段落，跳过可能导致状态错乱：

```renpy
label timing_puzzle:
    $ renpy.block_rollback()
    # 不允许跳过这段
    $ config.allow_skipping = False
    ...
    $ config.allow_skipping = True
```

**3. 首次游玩禁止跳过**

```renpy
# 已读跳过是默认行为，未读跳过需用户主动开启
define config.allow_skipping = True
```

## 四、历史记录

### NS 原作行为

`回想` 或 `バックログ` 打开历史文本，容量通常 100-500 行。

### Ren'Py 原生能力

原生 C 键打开历史，容量可配：

```renpy
define config.history_length = 250
```

### 需要显式处理的部分

**1. 语音回放**

部分作品历史记录中可点击重新播放语音。Ren'Py 原生支持：

```renpy
# 在 say 时关联语音
y "台词" id voice_id
```

需要 `config.history_allow_tags` 等配置确认语音标签在历史中正确显示。

**2. 历史中的变量文本**

如果台词含变量（如"好感度是 [yuki_favor]"），历史记录保存的是展开后的文本还是模板？Ren'Py 默认保存展开后的，通常符合预期。

## 五、设置

### NS 原作行为

音量（BGM/SE/语音分别）、文字速度、窗口透明度、全屏、文字大小。

### Ren'Py 原生能力

原生 preferences screen 已覆盖全部常见设置。默认 `screens.rpy` 中的 preferences 包含：

- Display（窗口/全屏）
- Skip（已读/未读）
- Text Speed
- Auto-Forward Time
- Music / Sound / Voice Volume

### 需要显式处理的部分

**1. 原作的独特设置项**

如"文字框位置"、"立绘亮度"、"效果音开关"等，原生没有对应项。需要：

```renpy
# 自定义设置项存 persistent
default persistent.textbox_position = "bottom"

# 在 preferences screen 中加
vbox:
    label _("文字框位置")
    textbutton _("底部") action SetField(persistent, "textbox_position", "bottom")
    textbutton _("顶部") action SetField(persistent, "textbox_position", "top")
```

并在对应 screen 中读取该值。

**2. 设置的作用范围**

Ren'Py 的 preferences 默认全局持久。若原作设置是"每存档独立"，需要改成存档内变量并自行管理。

## 六、其他常见系统功能

| 原作功能 | Ren'Py 方案 | 需要自写 |
|---|---|---|
| 文字速度 | preferences 原生 | 否 |
| 自动播放 | preferences 原生 | 否 |
| CG 鉴赏 | 需自写 gallery screen + persistent 解锁记录 | 是 |
| 音乐鉴赏 | 需自写 music room screen | 是 |
| 场景回想 | 需自写 replay screen 或使用 `renpy.call_replay` | 是 |
| 地图选择 | 需自写 screen + imagemap | 是 |
| 文字输入 | `renpy.input()` | 否 |
| 存档注释 | 原生支持 `save_name` | 否 |
| 快速存读档 | 原生 F5/F9 | 否 |
| 立绘鉴赏 | 需自写 screen | 是 |
| 多周目继承 | persistent 变量 | 部分 |
| 成就/奖杯 | 需自写，或对接平台 SDK | 是 |

## 七、需要自写的功能：统一契约

凡是需要自写的系统功能，都必须在 `catalog.json` 的 `features` 中登记完整契约：

```json
{
  "id": "cg_gallery",
  "behavior": "CG 鉴赏，显示已解锁 CG，点击放大",
  "interface": "call screen cg_gallery",
  "returns": "None（或 'back' 表示退出）",
  "owner": "shared",
  "status": "custom",
  "implementation_file": "port_screens.rpy",
  "depends_on": ["persistent.unlocked_gallery"],
  "unlock_api": "port_unlock_cg(cg_id)",
  "notes": "所有剧情模块通过 port_unlock_cg() 解锁，不直接改 persistent"
}
```

关键点：**提供统一 API，不让剧情模块直接操作 persistent**。否则解锁逻辑散落在各模块，后续加功能（如解锁提示音）要改几十处。

### CG 解锁的推荐实现

```renpy
# port_screens.rpy

init python:
    def port_unlock_cg(cg_id):
        """剧情模块调用此函数解锁 CG，不要直接改 persistent"""
        if cg_id not in persistent.unlocked_gallery:
            persistent.unlocked_gallery.append(cg_id)
            renpy.save_persistent()
            if persistent.cg_unlock_notify:
                renpy.notify("CG 已解锁")

screen cg_gallery():
    tag menu
    use game_menu(_("CG 鉴赏"), scroll="viewport"):
        grid 3 4:
            spacing 10
            for cg in ALL_CG_LIST:
                if cg.id in persistent.unlocked_gallery:
                    imagebutton:
                        idle cg.thumb
                        action Show("cg_viewer", cg=cg)
                else:
                    add "images/ui/cg_locked.png"
```

剧情模块只用一行：

```renpy
$ port_unlock_cg("cg_yuki_01")
```

## 八、系统功能与汇合点的交互

系统功能会与剧情状态交互，组装验证时必须覆盖：

```text
[ ] 在每个汇合点存档，读档后背景/音乐/立绘状态正确恢复
[ ] 在有计时等待的段落存读档，计时器正确恢复或重置
[ ] 在选项处存档，读档后选项正确显示且条件判断使用正确的变量值
[ ] 跳过一段含 show/hide 的演出后，立绘状态正确
[ ] 从历史记录回看含语音的台词，语音标签正确
[ ] 跨周目解锁的内容在新周目可见
[ ] 自定义设置项修改后重启游戏仍保持
```

## 九、常见陷阱

### 1. 用 define 定义需要存档的变量

```renpy
define yuki_favor = 0    # 错误：不进存档
default yuki_favor = 0   # 正确
```

### 2. persistent 变量未显式保存

修改 persistent 后需要 `renpy.save_persistent()`，否则退出时可能丢失（Ren'Py 通常会自动保存，但强制存档点更安全）。

### 3. 自写 screen 未加 `tag menu`

```renpy
screen cg_gallery():
    tag menu    # 缺少这行会导致游戏菜单下方堆叠残留
```

### 4. 跳过时执行了不该执行的状态修改

```renpy
label bad_example:
    $ yuki_favor += 1    # 跳过时也会执行——通常是对的
    $ renpy.pause(2.0)   # 跳过时这行也会过，但计时被打断
```

需要"只在非跳过时执行"的逻辑：

```renpy
if not config.skipping:
    $ renpy.pause(2.0)
```

### 5. 存档里的绝对路径

素材路径必须是相对 `game/` 的相对路径，绝对路径在别的机器上读档会崩。

## 十、登记清单

阶段 1（全局理解）时，把原作的所有系统功能列出并登记状态：

```json
{
  "features": [
    {"id": "save_load", "status": "native"},
    {"id": "skip", "status": "native"},
    {"id": "history", "status": "native"},
    {"id": "settings", "status": "configured", "notes": "增加文字框透明度项"},
    {"id": "cg_gallery", "status": "custom", "owner": "shared"},
    {"id": "music_room", "status": "custom", "owner": "shared"},
    {"id": "map_select", "status": "custom", "owner": "shared"},
    {"id": "trophy", "status": "unsupported", "issue_id": "ISSUE-010"}
  ]
}
```

阶段 3（公共基础）时，`custom` 状态的项必须先实现，否则依赖它们的剧情模块无法完成。
