# 怎么让 AI 用这套流程

`SKILL.md` 是给 AI 读的流程本体；这一页是**人**要用的东西：在哪些场景下说哪句话、要先准备什么、AI 交付什么算合格。

## 准备（一次性）

```text
<skill>/             ← 本仓库（放到 skills 目录里，或任何可读路径）
<ns-game>/           ← 原版游戏目录（含 0.txt、bg/ chr/ ev/ se/ ...）
<port-project>/      ← 目标 Ren'Py 工程目录（可以先空着，Ren'Py SDK 新建一个）
```

Ren'Py SDK 需要装好（8.x），并且能跑 `renpy.exe <project> lint`。

## 四条可直接粘贴的指令

### 1. 从零开始整部移植

> 用 `ns-to-renpy-port` 这套流程，把 `<ns-game>` 移植成 Ren'Py 工程 `<port-project>`。
> 先按流程阶段 1 建立全局理解（overview / graph / catalog / sources / issues），
> 再按阶段 2 划模块并写公共契约，然后阶段 3 用 `scripts/` 里的通用脚本把素材、演出层、
> 界面做出来，阶段 4 逐模块实现，阶段 5 跑双 lint + 运行期冒烟 + 全量走线。
> 开工前先读 `references/pitfalls.md`。每一步都把结果写进 `port/` 下的记录文件，不要只留在对话里。

### 2. 只修素材层（立绘带绿幕 / 蒙版没拆 / 按钮不透明）

> 用 `ns-to-renpy-port` 的素材层流程修 `<port-project>`：
> 先跑 `scripts/nsassets.py` 普查，再跑 `scripts/convert_assets.py` 转图，
> 用 `assets/tools/qa_alpha.py` 复核 alpha 与残余键色，
> 最后用 `assets/tools/*_proof.py` 出证据图。
> 素材名、尺寸、spec 一律以脚本实测为准，不要凭截图猜。

### 3. 只修界面层（存档界面错位 / 设置项英文 / 缺图鉴）

> 用 `ns-to-renpy-port` 的界面层流程修 `<port-project>`：
> GUI 用 launcher 的 `generate_gui` 按目标分辨率重新生成（不要手改尺寸），
> 缺的图用 `assets/tools/gui_fill_images.py` 补，标记图用 `gui_marks.py` 重画，
> 中文化拷 `assets/ns_i18n_cn.rpy` 并设 `config.language = "chinese"`，
> 图鉴用 `scripts/nsgallery.py` + `assets/ns_gallery.rpy`（坐标从脚本抽，不手抄）。

### 4. 续作（换个会话接着干）

> 读 `<port-project>/port/STATUS.md` 和 `port/modules/` 下对应任务包，用 `ns-to-renpy-port` 继续。
> 先核对任务包声明的契约版本与 `contracts.md` 当前版本是否一致，不一致先说明差异再动手。

## 什么算合格交付

AI 说「做完了」时，对照这张表，缺一项就不算完：

| 项 | 判据 |
| --- | --- |
| 静态规范 | `python scripts/nsport_lint.py <project>/game --json lint.json`：**0 error** |
| 引擎检查 | `renpy.exe <project> lint`：无 error |
| 运行期 | 拷 `assets/ns_stage_smoke.rpy` 跑一次，`_ns_smoke_result.txt` 全是 OK |
| 剧情覆盖 | 有覆盖报告（say / 旁白 / 语音 / 指令 / 未翻译 / 跳过原因），未翻译必须为 0 或有 issue |
| 全量走线 | 拷 `assets/ns_autowalk.rpy` + 跑 `scripts/nswalk.py <project>`：`missing_assets=0`、`bad_runs=0` |
| 目视证据 | 至少一张对照图（`_proof_*.png`），证明立绘无绿边、槽位对、UI 不越界 |
| 记录 | `port/` 下 STATUS / issues / validation 三个文件有对应条目 |

## 常见的「AI 糊弄」信号

- 只跑 lint 就说「验证通过」——lint 查不出运行期错误（见 `references/pitfalls.md` 第四类）。
- 素材直接 BMP→PNG 转换——立绘一定带绿幕，看 `references/assets_contract.md` 4.x。
- 用 `scene` 换背景——会把立绘一起清掉，见 `references/conventions.md` 第五节。
- 手改 GUI 的 `gui.init(800, 600)`——1280 模板改成 800 会全线错位，必须重新生成。
- 剧情「看起来翻完了」但没有覆盖报告——一定漏行，`ns2renpy_story.py` 的输出里有对账数字。
