# NS → Ren'Py 移植流程（可被 AI 直接调用的 skill）

一套**已验证过完整规模**的 NScripter → Ren'Py 移植方法：先建立剧情与演出的全局蓝图，再用通用脚本把素材、包装层、剧情、图鉴、界面逐层转换，最后用「规范检查 + 引擎检查 + 运行期冒烟 + 全量走线」验收。

不是一次性转换器。产出是**能运行、能验证、带覆盖报告**的 Ren'Py 工程。

> 实战基线：一部 30,056 行、196 个 label、411 条素材、6,030 个语音文件的 NScripter 游戏，全量移植到 81 个剧情 label / 41,947 行 `.rpy`；台词覆盖 14,969/14,969，走线 10 轮分支全覆盖，`nsport_lint` 0 error，Ren'Py lint 无 error，打包 678.9MB 一行命令。详见 [案例](docs/case-study-serika.md)。

## 怎么用

### 作为 AI skill 加载

把整个目录放进所用工具的 skills 目录（例如 `.claude/skills/ns-to-renpy-port/`、`~/.codex/skills/ns-to-renpy-port/`），`SKILL.md` 的 frontmatter 带 `name` / `description`，AI 会在遇到「NS 游戏移植 Ren'Py」「0.txt 剧本翻译」这类任务时自动匹配并读取。

`SKILL.md` 是主流程（1 全局理解 → 2 模块规划 → 3 公共基础 → 4 分别实现 → 5 验证 → 6 打包）；细节都在 `references/`，按需加载：

| 文件 | 什么时候读 |
| --- | --- |
| [references/conventions.md](references/conventions.md) | 写模块代码前：来源注释、文件组织、命名、禁止清单 |
| [references/ns_to_renpy_map.md](references/ns_to_renpy_map.md) | 写转换语句前：NS 命令 → Ren'Py 写法 |
| [references/assets_contract.md](references/assets_contract.md) | 处理素材/立绘/背景切换前：spec 语法、蒙版、键色、动画条、演出层 API |
| [references/module_sizing_guide.md](references/module_sizing_guide.md) | 划模块时 |
| [references/mergepoints_guide.md](references/mergepoints_guide.md) | 标汇合点、验证汇合点时 |
| [references/system_features.md](references/system_features.md) | 存读档/跳过/鉴赏等系统功能 |
| [references/blueprint-templates.md](references/blueprint-templates.md) | 建蓝图、写任务包时 |
| [references/repair-playbook.md](references/repair-playbook.md) | 出错返工时 |
| [references/pitfalls.md](references/pitfalls.md) | **开工前必读**：七类 51 条「症状 → 根因 → 解法」（素材/演出/剧情/验证/环境/界面/打包） |
| [references/packaging.md](references/packaging.md) | 打发布包时 |

### 当脚本工具集用

只想要转换器也可以，每个脚本都是独立 CLI：

```bash
python scripts/nsassets.py     <游戏目录> --script 0.txt          # 素材普查 → assets_manifest.json
python scripts/convert_assets.py <游戏目录> <工程>/game           # 转图拆蒙版 + 生成 port_images.rpy / port_wrappers.rpy
python scripts/ns2renpy_story.py <游戏目录> <工程>/port --project <工程>   # 整部剧情机械移植
python scripts/nsgallery.py    <游戏目录> --port <工程>/port       # CG/回想图鉴数据
python scripts/ns_movies.py    <游戏目录> <工程>/game              # mpg → VP8 webm
python scripts/nsport_lint.py  <工程>/game --json lint.json        # 规范检查
python scripts/nswalk.py       <工程>                             # 全量走线（需先拷 assets/ns_autowalk.rpy）
```

依赖：Python 3.10+、`Pillow`（`pip install -r requirements.txt`）；过场转换需要系统里有 `ffmpeg`/`ffprobe`。

## 目录

```text
SKILL.md                 主流程（AI 读这个）
references/              规范、映射表、素材契约、碎坑清单、打包
scripts/                 通用转换器与检查器（可直接跑）
scripts/legacy/          早期一次性脚本（仅供对照，不要用于新工程）
assets/                  拷进 Ren'Py 工程的运行时通用件
  ns_stage.rpy           演出层（分层、槽位、音频通道、缺失素材占位）
  ns_volume.rpy          音量桥接（原作 0-6 档 → mixer）
  ns_gallery.rpy         图鉴（CG / 回想）
  ns_i18n_cn.rpy         界面中文化
  ns_autowalk.rpy        全量走线探针
  ns_stage_smoke.rpy     运行期冒烟探针
  tools/                 一次性小工具（普查、证据图、GUI 补图等）
docs/
  design-notes.md        设计思路：每一步为什么这么做
  case-study-serika.md   完整案例与验收数字
```

## 五个最容易踩的坑（只看这一节也能少走一半弯路）

1. **素材不是文件到文件**：NS 的 `:a;` 是「左半图 + 右半遮罩」，`:c/2,0,3;` 是「2 格、每格图+罩」，`:#00FF00` 是键色。当普通图直接转 PNG，立绘就是一块绿幕。
2. **`_bg` 会清掉立绘**：背景/CG/黑幕共用一层，换景即清人；换景带人要用 `ns_bgchr`。移植版用 `scene` 会连立绘一起清、用纯 `show bg` 又把上一景留下。
3. **`defsub` 包装层必须按语义翻**：`bg`/`chr`/`music`/`se` 都是包装层，`%G1` 控制瞬时/带过渡。逐条翻译命令而丢掉分支条件，效果全错。
4. **界面模板不能手改尺寸**：1280×720 的 GUI 手改成 800×600，导航会叠在左上、存档第三列出屏；要用 launcher 的 `generate_gui` 重新生成。
5. **lint 全绿 ≠ 运行期正确**：必须再跑运行期冒烟与全量走线（`assets/ns_autowalk.rpy` + `scripts/nswalk.py`），否则立绘不消失、音频通道报错、开场动画卡死这类问题一个都查不出来。

## 许可

MIT，见 [LICENSE](LICENSE)。本仓库只含方法与工具代码，不含任何游戏素材。
