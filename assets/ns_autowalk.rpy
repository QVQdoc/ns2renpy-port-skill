# -*- coding: utf-8 -*-
## 全量自动走线探针（ns_autowalk.rpy）—— 拷进 game/ 用，测完必须删除。
##
## 干什么：headless 下把整条剧情自动跑一遍，把「lint 查不出的运行期错误」逼出来
## ——缺素材、演出层抛异常、menu 目标写错、跳转成环、死循环。
##
## 怎么跑：配合 scripts/nswalk.py（它会写 plan、启动游戏、收日志、按菜单路径做 DFS）。
##
## 机制（这几条都是踩过坑才定下来的，改之前先读）：
##   * 强制 skip：`preferences.skip_unseen` / `config.skipping = "fast"`。fast skip 下
##     每句台词几乎不耗帧，所以**不能靠 periodic callback 统计覆盖**（帧太少），
##     要在 `renpy.exports.say` 上挂钩。
##   * 菜单：`Menu.execute` 调的是 `renpy.exports.menu(items, set_expr, args, kwargs,
##     item_arguments)`，**不是** `renpy.display_menu`；patch 后者完全不生效，游戏会
##     停在第一个选项上。这里 patch 前者，按 plan 返回选项下标。
##   * 主菜单：靠环境变量 `RENPY_SKIP_MAIN_MENU=1` 跳过（Ren'Py 自己支持的开关），
##     不要自己 patch main_menu。
##   * 结局：原作 `reset` → `renpy.full_restart`，patch 成写日志 + `renpy.quit()`。
##   * 过场动画：`renpy.movie_cutscene` 打桩，不然 headless 下会真开视频窗口。

init 999 python:
    import os
    import time

    _NW_LOG = os.path.join(config.basedir, "_ns_walk_log.txt")
    _NW_START = time.time()
    _NW_SEEN = set()
    _NW_LINES = set()
    _NW_LABELS = set()
    _NW_STATE = [""]
    _NW_LAST_MOVE = [time.time()]
    _NW_LAST_PROG = [0.0]
    _NW_MENUS = [0]
    _NW_OPTIONS = []
    _NW_SAYS = [0]
    _NW_TIMEOUT = 900
    _NW_STALL = 30

    ## 本次运行要选的「第几个菜单选第几项」，从 _ns_walk_plan.txt 读。
    _NW_PLAN = []
    try:
        _plan_path = os.path.join(config.basedir, "_ns_walk_plan.txt")
        if os.path.exists(_plan_path):
            with open(_plan_path, encoding="utf-8") as f:
                _NW_PLAN = [int(x) for x in f.read().split() if x.strip().lstrip("-").isdigit()]
    except Exception:
        _NW_PLAN = []

    def _nw_log(msg):
        try:
            with open(_NW_LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass

    def _nw_finish(why):
        _nw_log(
            "FINISH %s elapsed=%.1fs files=%d says=%d menus=%d at=%s"
            % (why, time.time() - _NW_START, len(_NW_SEEN), _NW_SAYS[0], _NW_MENUS[0], _NW_STATE[0])
        )
        _nw_log("PLAN " + ",".join(str(x) for x in _NW_PLAN))
        _nw_log("OPTIONS " + ",".join(str(x) for x in _NW_OPTIONS))
        _nw_log("FILES " + ",".join(sorted(_NW_SEEN)))
        _nw_log("LINES " + ",".join(sorted(_NW_LINES)))
        _nw_log("LABELS " + ",".join(sorted(_NW_LABELS)))
        try:
            missing = list(store.NS_MISSING)
        except Exception:
            missing = []
        _nw_log("MISSING %d %s" % (len(missing), ",".join(sorted(missing))))
        renpy.quit()

    ## 标签覆盖：`config.label_callbacks` 在每次进入 label 时回调。
    ## 光看 say 行会漏掉「只有 reset / 只有 jump」的标签（结局、纯跳转的别名标签）。
    def _nw_label(label, abnormal=None):
        _NW_LABELS.add(label)

    config.label_callbacks.append(_nw_label)

    ## 台词/文件/行覆盖：挂在 say 上（fast skip 下 tick 打不到几帧）。
    _nw_orig_say = renpy.exports.say

    def _nw_say(who, what, *a, **kw):
        _NW_SAYS[0] += 1
        try:
            fn, ln = renpy.get_filename_line()
            if fn:
                base = os.path.basename(fn)
                _NW_SEEN.add(base)
                _NW_LINES.add("%s:%d" % (base, ln))
        except Exception:
            pass
        return _nw_orig_say(who, what, *a, **kw)

    renpy.exports.say = _nw_say

    ## 过场动画不真播
    try:
        renpy.movie_cutscene = lambda *a, **k: None
    except Exception:
        pass

    ## 菜单：按 plan 选，顺便记下每个菜单有几个可用项（驱动据此扩分支）
    _nw_orig_menu = renpy.exports.menu

    def _nw_menu(items, set_expr=None, args=None, kwargs=None, item_arguments=None):
        avail = []
        try:
            set_obj = renpy.python.py_eval(set_expr) if set_expr else None
        except Exception:
            set_obj = None
        for item in items:
            label, condition, value = item[0], item[1], item[2]
            if value is None:
                continue
            try:
                if condition and not renpy.python.py_eval(condition):
                    continue
            except Exception:
                pass
            avail.append((label, value))
        if not avail:
            return _nw_orig_menu(items, set_expr, args, kwargs, item_arguments)
        idx = _NW_MENUS[0]
        _NW_MENUS[0] += 1
        _NW_OPTIONS.append(len(avail))
        want = _NW_PLAN[idx] if idx < len(_NW_PLAN) else 0
        if want >= len(avail):
            want = len(avail) - 1
        label, value = avail[want]
        _nw_log("MENU %d n=%d pick=%d %s" % (idx, len(avail), want, label))
        if set_obj is not None:
            try:
                if hasattr(set_obj, "add"):
                    set_obj.add(label)
                else:
                    set_obj.append(label)
            except Exception:
                pass
        return value

    renpy.exports.menu = _nw_menu

    ## 结局：原作 reset（→ renpy.full_restart）
    def _nw_restart(*a, **k):
        _nw_finish("ending")

    renpy.full_restart = _nw_restart

    def _nw_tick():
        try:
            preferences.skip_unseen = True
            preferences.skip_after_choices = True
            config.skipping = "fast"
        except Exception:
            pass
        try:
            fn, ln = renpy.get_filename_line()
        except Exception:
            fn, ln = None, 0
        if fn:
            cur = "%s:%s" % (os.path.basename(fn), ln)
            if cur != _NW_STATE[0]:
                _NW_STATE[0] = cur
                _NW_LAST_MOVE[0] = time.time()
                _NW_SEEN.add(os.path.basename(fn))
        elif renpy.get_screen("main_menu"):
            _nw_finish("main_menu")
        now = time.time()
        if now - _NW_LAST_PROG[0] > 10:
            _NW_LAST_PROG[0] = now
            _nw_log(
                "PROGRESS %.0fs files=%d says=%d menus=%d at=%s"
                % (now - _NW_START, len(_NW_SEEN), _NW_SAYS[0], _NW_MENUS[0], _NW_STATE[0])
            )
        if now - _NW_LAST_MOVE[0] > _NW_STALL:
            _nw_finish("stall")
        if now - _NW_START > _NW_TIMEOUT:
            _nw_finish("timeout")

    config.periodic_callbacks.append(_nw_tick)
    _nw_log("START")
