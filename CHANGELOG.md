# CHANGELOG

## 1.0.0

首个公开版本。整理自一次完整规模的 NScripter → Ren'Py 移植实战。

**流程**
- 五阶段主线（全局理解 / 模块规划 / 公共基础 / 分别实现 / 组装验证）+ 打包发布
- 覆盖状态四层登记、动态行为结构化登记、汇合点登记与验证
- 六类「症状 → 根因 → 解法」踩坑清单（30+ 条，全部来自实战）

**工具**
- `nsassets.py`：素材普查（变量路径、spec 语法、defsub 包装层、像素级蒙版判定）
- `convert_assets.py`：拆蒙版 / 抠键色 / 切分割 / 动画条 / 包装层翻译 → `port_images.rpy` + `port_wrappers.rpy`
- `ns2renpy_story.py`：整部剧情批量移植 + 覆盖报告
- `nsgallery.py`：CG / 回想图鉴数据（坐标与解锁条件从脚本抽取，不手抄）
- `ns_movies.py`：过场转 VP8（VP9 会让 `movie_cutscene` 永久阻塞）
- `nswalk.py` + `ns_autowalk.rpy`：菜单分支全量走线
- `nsport_lint.py`：规范检查（NS001–NS016，含来源注释覆盖率）
- `nsstage_migrate.py`：旧工程舞台 API 迁移

**运行时通用件**
- `ns_stage.rpy`：分层演出层（背景/CG/黑幕共用 tag 并清立绘、槽位、音频通道预注册、缺失素材占位）
- `ns_volume.rpy`：音量单控制点（原作 0-6 档 → mixer，读档清通道级上限）
- `ns_gallery.rpy`：图鉴运行时
- `ns_i18n_cn.rpy`：界面中文化（83 条 strings）

**验证**
- 双轨验收：`nsport_lint` + Ren'Py lint + 运行期冒烟 + 全量走线 + 证据图
- 打包：SDK `launcher distribute`，含存档根不可写、`Ren'Py Data` 目录、预置签名密钥等实战解法
