# legacy（仅供参考，不要直接用于新工程）

这三个脚本是移植流程**最早**的版本，`SKILL.md` 把它们列为「随附旧工具」：

| 文件 | 当年干什么 | 为什么不再作为主力 |
| --- | --- | --- |
| `ns2renpy.py` | 一次性把 `0.txt` 直接翻成 `script.rpy` | 不认 `defsub` 包装层、不拆立绘蒙版、不区分背景层与立绘层；产物要人肉返工 |
| `taskpack.py` | 给 AI 拆任务包 | 与 `ns2renpy_story.py` + `nswalk.py` 的流程重复 |
| `verify.py` | 粗验产物 | 覆盖不了运行期，已被 `nsport_lint.py` + `ns_autowalk.rpy` + `nswalk.py` 取代 |

留在这里是为了对照「为什么必须重写」，读代码时别把它们当规范。
