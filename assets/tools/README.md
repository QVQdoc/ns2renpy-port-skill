# 一次性小工具（按需取用）

这些脚本是在真实移植里长出来的，**不是流程必需**，但每一步都能省很多手工。
绝大多数接受命令行参数（第一个参数通常是 `<工程>/game`），少数几个需要你改一下写死的素材名。

| 文件 | 用途 | 参数 |
| --- | --- | --- |
| `survey_script.py` | 剧本普查：行数 / 标签 / 命令直方图 / 说话人 / 跳转边 → `script_survey.json` | `<0.txt> [--json out.json]` |
| `analyze_structure.py` | 结构统计：label、边、命令、素材、变量 → `structure.json` | `<游戏目录>` |
| `probe_encoding.py` | 猜剧本编码（cp932/gbk/euc-jp/big5 混用时逐行容错） | `<0.txt>` |
| `gen_catalog.py` / `gen_events.py` / `gen_blueprint.py` / `validate_blueprint.py` / `coverage_gap.py` | 阶段 1–2 的蓝图与覆盖产物 | 见各脚本 `--help` |
| `qa_alpha.py` | 素材复核：每个目录的 alpha 分布、尺寸、残余键色像素 | `[game 目录]` |
| `qa_assets.py` / `qa_text_fit.py` | 素材完整性与文本出框检查 | `[game 目录]` |
| `ui_sheet.py` | 各目录抽 6 张贴棋盘格 → 一眼看出哪张没抠干净 | `[game 目录] [输出 png]` |
| `title_proof.py` | 按 title 按钮坐标离线合成预览（验证按钮 alpha） | `[game 目录] [输出 png]` |
| `logo_proof.py` | 按原作 `*logo` 时间轴离线合成 LOGO 滑入/翻转证据图 | `[game 目录] [输出 png]` |
| `make_proof.py` | 按演出层槽位规则合成「立绘 / 换景 / CG」对照图 | `[game 目录] [输出 png]`（**里面的素材名是示例，改成你工程的**） |
| `gui_fill_images.py` | GUI 生成器只给 24 张图，从 `the_question` 按比例补齐缺失的 28 张 | `<sdk>/the_question/game/gui <game>/gui` |
| `gui_button_art.py` | 补出来的存档格主题色不对时，用 Pillow 重画中性九宫格 | `<game>/gui` |
| `gui_marks.py` | 勾选/单选标记尺寸必须等于 `*_button_borders` 左边距，否则压字 | `<game>/gui/button` |
| `bg_semantics.py` | 统计「换背景时立绘在场」的现场，用来判定 `_bg` 的清理语义 | `<0.txt>` |
| `patch_lint.py` | 把 lint 报告按模块切分成待修清单 | `<lint.json>` |
| `speakers.py` | 统计说话人、语音号段与台词行数 | `<0.txt>` |

约定：输出图默认写到当前目录的 `_*.png`，跑完记得删；这些脚本**不该留在交付工程里**。
