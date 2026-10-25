# -*- coding: utf-8 -*-
"""全量自动走线驱动：按菜单分支把整个剧情跑一遍，收齐运行期错误与覆盖情况。

配套探针是 `assets/ns_autowalk.rpy`，**先把它拷进 `<工程>/game/`**（测完删掉）。

它的做法（见 `references/conventions.md` 第 15 节）：

1. 把「第几个菜单选第几项」写进 `<工程>/_ns_walk_plan.txt`；
2. headless 启动游戏（`RENPY_SKIP_MAIN_MENU=1` + dummy 音频），探针自动 skip、
   按 plan 选菜单、把访问到的文件/台词行/缺素材写进 `<工程>/_ns_walk_log.txt`；
3. 解析日志，发现「第 i 个菜单还有没试过的项」就排一条新路径继续跑（DFS）；
4. 汇总成 `walk_report.json`：覆盖了多少台词行、哪些 story 文件没走到、
   哪些素材缺失、哪几次运行动不了（stall / timeout / 启动崩溃）。

用法：

    python scripts/nswalk.py <工程目录>                  # 全部分支
    python scripts/nswalk.py <工程目录> --max-runs 30
    python scripts/nswalk.py <工程目录> --dry-run        # 只看会跑哪些路径

注意：一次运行 ≈ 启动 5 秒 + 全剧本快进几秒。分支多时用 `--max-runs` 兜底。
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

# renpy.exe 路径：优先命令行 --renpy，其次环境变量 RENPY_EXE，最后按 common 位置猜。
DEFAULT_RENPY = (
    os.environ.get("RENPY_EXE")
    or shutil.which("renpy")
    or r"<Ren'Py SDK>\renpy.exe"
)

RE_FINISH = re.compile(
    r"^FINISH (\w+) elapsed=([\d.]+)s files=(\d+) says=(\d+) menus=(\d+) at=(.*)$"
)

PROBE = "ns_autowalk.rpy"
LOG_NAME = "_ns_walk_log.txt"
PLAN_NAME = "_ns_walk_plan.txt"


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()
    except OSError:
        return []


def run_once(project_dir, renpy, plan, env_base, timeout=900):
    """跑一次游戏，返回解析后的结果。"""
    plan_path = os.path.join(project_dir, PLAN_NAME)
    log_path = os.path.join(project_dir, LOG_NAME)
    try:
        os.remove(log_path)
    except OSError:
        pass
    with open(plan_path, "w", encoding="utf-8") as f:
        f.write(" ".join(str(x) for x in plan) + "\n")

    started = time.time()
    # 不要用 stdout=PIPE：renpy.exe 会留下继承句柄的子进程，管道永不关闭，
    # subprocess.run 会一直卡在读取上（实测卡死 5 分钟）。重定向到文件。
    err_path = os.path.join(project_dir, "_ns_walk_stdout.txt")
    try:
        with open(err_path, "wb") as errf:
            proc = subprocess.run(
                [renpy, project_dir],
                cwd=project_dir,
                env=env_base,
                stdout=errf,
                stderr=subprocess.STDOUT,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return {
            "plan": list(plan), "returncode": None, "wall": round(time.time() - started, 1),
            "why": "hard-timeout", "files": [], "lines": [], "options": [], "menus": 0,
            "says": 0, "missing": [], "at": "", "elapsed": 0.0, "stdout_tail": "",
        }

    res = {
        "plan": list(plan), "returncode": proc.returncode,
        "wall": round(time.time() - started, 1), "why": "no-log",
        "files": [], "lines": [], "options": [], "menus": 0, "says": 0,
        "missing": [], "at": "", "elapsed": 0.0, "stdout_tail": "",
    }
    for line in _read(log_path):
        m = RE_FINISH.match(line)
        if m:
            res.update(
                why=m.group(1), elapsed=float(m.group(2)),
                says=int(m.group(4)), menus=int(m.group(5)), at=m.group(6),
            )
        elif line.startswith("FILES "):
            res["files"] = [x for x in line[6:].split(",") if x]
        elif line.startswith("LINES "):
            res["lines"] = [x for x in line[6:].split(",") if x]
        elif line.startswith("OPTIONS "):
            res["options"] = [int(x) for x in line[8:].split(",") if x]
        elif line.startswith("LABELS "):
            res["labels"] = [x for x in line[7:].split(",") if x]
        elif line.startswith("MISSING "):
            rest = line[8:].split(" ", 1)
            body = rest[1].strip() if len(rest) > 1 else ""
            res["missing"] = [x for x in body.split(",") if x]
    out = []
    try:
        with open(err_path, "rb") as errf:
            out = errf.read().decode("utf-8", "replace").strip().splitlines()
    except OSError:
        pass
    res["stdout_tail"] = "\n".join(out[-6:])
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="按菜单分支全量走线")
    ap.add_argument("project", help="Ren'Py 工程目录（含 game/）")
    ap.add_argument("--renpy", default=DEFAULT_RENPY, help="renpy.exe 路径")
    ap.add_argument("--out", default=None, help="报告路径（默认 <工程>/walk_report.json）")
    ap.add_argument("--max-runs", type=int, default=40)
    ap.add_argument("--delay", type=float, default=1.5, help="两次启动之间的间隔秒数")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    project_dir = os.path.abspath(args.project)
    game_dir = os.path.join(project_dir, "game")
    out_path = args.out or os.path.join(project_dir, "walk_report.json")

    probe = os.path.join(game_dir, PROBE)
    if not os.path.isfile(probe):
        print("缺探针：%s\n把 assets\\ns_autowalk.rpy 拷进 %s 再跑。" % (probe, game_dir))
        return 2

    appdata = os.path.join(os.path.dirname(project_dir), "_appdata")
    os.makedirs(appdata, exist_ok=True)
    env = dict(os.environ)
    env["APPDATA"] = appdata
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    env["RENPY_SKIP_MAIN_MENU"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    queue = [()]
    seen = set()
    results = []
    lines_all = set()
    files_all = set()
    labels_all = set()
    missing_all = {}
    bad_runs = []

    while queue and len(results) < args.max_runs:
        plan = queue.pop(0)
        if plan in seen:
            continue
        seen.add(plan)
        if args.dry_run:
            print("plan:", " ".join(str(x) for x in plan) or "(default)")
            results.append({"plan": list(plan), "options": [2], "why": "dry-run"})
            if len(results) >= 4:
                break
            continue

        print("[run %d] plan=%s" % (len(results) + 1, " ".join(str(x) for x in plan) or "(default)"))
        res = run_once(project_dir, args.renpy, plan, env)
        # 偶发：连续启动时 renpy.exe 在原生初始化阶段崩掉（Windows 返回码 0xC0000374
        # heap corruption），连日志都没有。跟剧本无关，重试一次。
        if res["why"] == "no-log":
            print("    !! 启动异常 rc=%s wall=%ss，2 秒后重试" % (res["returncode"], res["wall"]))
            time.sleep(2.0)
            res = run_once(project_dir, args.renpy, plan, env)
        results.append(res)

        lines_all.update(res["lines"])
        files_all.update(res["files"])
        labels_all.update(res.get("labels", []))
        for m in res["missing"]:
            missing_all[m] = missing_all.get(m, 0) + 1
        print(
            "    why=%s says=%d files=%d menus=%d options=%s at=%s"
            % (res["why"], res["says"], len(res["files"]), len(res["options"]), res["options"], res["at"])
        )
        if res["why"] in ("no-log", "hard-timeout", "stall", "timeout", "main_menu"):
            bad_runs.append({"plan": res["plan"], "why": res["why"], "at": res["at"],
                             "stdout": res["stdout_tail"]})
        time.sleep(args.delay)

        full = list(plan) + [0] * max(0, len(res["options"]) - len(plan))
        for i, n in enumerate(res["options"]):
            cur = full[i]
            if cur + 1 < n:
                nxt = tuple(full[:i] + [cur + 1])
                if nxt not in seen:
                    queue.append(nxt)

    story_dir = os.path.join(game_dir, "story")
    story_files = sorted(f for f in os.listdir(story_dir) if f.endswith(".rpy")) if os.path.isdir(story_dir) else []
    unreached = [f for f in story_files if f not in files_all]

    # 标签覆盖：故事文件里声明了 label 但一次都没进入的
    declared = []
    if os.path.isdir(story_dir):
        for f in story_files:
            try:
                with open(os.path.join(story_dir, f), encoding="utf-8") as fh:
                    for line in fh:
                        if line.startswith("label "):
                            declared.append(line[6:].split(":")[0].strip())
            except OSError:
                pass
    unreached_labels = sorted(set(declared) - labels_all)

    summary = {
        "project": project_dir,
        "runs": len(results),
        "unique_say_lines": len(lines_all),
        "unique_files": len(files_all),
        "labels_entered": len(labels_all),
        "labels_declared": len(set(declared)),
        "unreached_labels": unreached_labels,
        "story_files": len(story_files),
        "unreached_story_files": unreached,
        "missing_assets": missing_all,
        "bad_runs": bad_runs,
        "per_run": results,
    }
    if not args.dry_run:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1)

    print("\n=== 汇总 ===")
    print("运行 %d 次 / 覆盖台词行 %d / 覆盖文件 %d / story 文件 %d（未走到 %d）"
          % (len(results), len(lines_all), len(files_all), len(story_files), len(unreached)))
    print("标签：进入 %d / 声明 %d / 未进入 %d"
          % (len(labels_all), len(set(declared)), len(unreached_labels)))
    if unreached_labels:
        print("   未进入的标签：", ", ".join(unreached_labels[:15]),
              "…" if len(unreached_labels) > 15 else "")
    if missing_all:
        print("缺素材 %d 种：" % len(missing_all))
        for k, v in sorted(missing_all.items()):
            print("   ", k, "（%d 次）" % v)
    else:
        print("缺素材：无")
    if bad_runs:
        print("异常运行 %d 次：" % len(bad_runs))
        for b in bad_runs:
            print("   ", b["why"], "plan=", b["plan"], "at=", b["at"])
    if unreached:
        print("没走到的 story 文件：", ", ".join(unreached[:12]),
              "…" if len(unreached) > 12 else "")
    if not args.dry_run:
        print("报告：", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
