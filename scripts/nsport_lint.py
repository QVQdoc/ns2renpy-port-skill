#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nsport_lint.py —— 检查 NS -> Ren'Py 移植工程是否遵守 conventions.md

用法:
    python nsport_lint.py <game_dir> [--json report.json] [--disable CODE,CODE]
                          [--strict] [--list-codes]

退出码:
    0  没有问题（--strict 下 warning 也算问题）
    1  发现 error（或 --strict 下发现 warning）
    2  用法错误 / 目录不存在

检查项只做"能否被机械判定"的部分；语义正确性仍需按 conventions.md
第十三节的人工清单复查。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter

# ---------------------------------------------------------------- 正则

SRC_RE = re.compile(r"#\s*src\s*:\s*([^\s:]+)\s*:\s*(\d+)(?:\s*-\s*(\d+))?|#\s*src\s*:\s*none\b")
ISSUE_RE = re.compile(r"#\s*(ISSUE-\d{3,})\b")
TODO_RE = re.compile(r"#\s*TODO\b")
LABEL_RE = re.compile(r"^label\s+([A-Za-z_][\w.]*)")
DEF_RE = re.compile(r"^(default|define)\s+([A-Za-z_][\w.]*)")
SCREEN_RE = re.compile(r"^screen\s+([A-Za-z_]\w*)")
SHOW_RE = re.compile(r"^(show|scene)\b")
HIDE_RE = re.compile(r"^hide\b")
CONV_RE = re.compile(r"^(show|scene|hide|menu|play|stop|jump|call|voice)\b")
PLAY_MUSIC_RE = re.compile(r"^play\s+music\b")
POS_RE = re.compile(r"\b(?:xpos|ypos|xalign|yalign|xoffset|yoffset)\b\s*[-+]?\d")
POS_PAIR_RE = re.compile(r"\bpos\b\s*\(?\s*[-+]?\d")
# 旧转换器把素材命名成 ns_bg_xxx / ns_ev_xxx 这类 image 名，出现即为误用旧产物。
# 注意别匹配到演出层运行时函数（ns_bg / ns_chr_clear / ns_ev 都合法），所以只在
# 「image 声明」和「引号里的素材名」这两种上下文里判。
OLD_NS_NAME_RE = re.compile(r"^(?:image\s+)?[\"']?(ns_(?:bg|ev|chr|cg)_\w+)[\"']?")
IMAGE_NS_RE = re.compile(r"^image\s+(ns_(?:bg|ev|chr|cg)_\w+)")
# 旧流程「每作手写一份 port_stage.rpy」的出口，迁移到 ns_* 后不应再出现
LEGACY_STAGE_RE = re.compile(r"\b(?:port_bg|port_bgchr|port_chr|port_ev|port_black|"
                             r"port_music|port_se|port_hide_all)\s*\(")
# 剧情里手拼素材路径 = 绕过素材层契约，路径一改全线崩
RAW_ASSET_RE = re.compile(r"[\"'](?:images|audio)/")
# 引用了 images/ 下非 images/ns/ 的图：基本都是一次性脚本的手搓产物（没有 alpha）
MANUAL_IMAGE_RE = re.compile(r"[\"']images/(?!ns/)(?!ns[\"'])(?P<path>[^\"']+)[\"']")
DISSOLVE_RE = re.compile(r"\bwith\s+(?:Dissolve|dissolve)\b")
HARD_PAUSE_RE = re.compile(r"renpy\.pause\([^)]*hard\s*=\s*True")
HARD_REASON_RE = re.compile(r"理由|必须硬|硬等|原作要求|不能点击跳过|不能靠玩家")

# Ren'Py 自带的框架文件，不属于「移植代码」，默认不检查（否则模板里的示例
# say 行会刷出上百条缺 src: 的 warning，把真正的问题淹掉）。
FRAMEWORK_FILES = {
    "screens.rpy", "gui.rpy", "guisupport.rpy", "options.rpy", "testcases.rpy",
    "gallery.rpy", "debug.rpy",
}

# say 行判定用的保留字
RESERVED = {
    "label", "jump", "call", "return", "menu", "if", "elif", "else", "while",
    "for", "python", "init", "screen", "define", "default", "image",
    "transform", "style", "show", "scene", "hide", "play", "stop", "voice",
    "queue", "with", "nvl", "window", "pause", "translate", "layeredimage",
    "camera", "testcase", "text", "bar", "use", "add", "button", "frame",
    "grid", "vbox", "hbox", "fixed", "key", "timer", "imagemap",
    "imagebutton", "textbutton", "viewport", "side", "onlayer", "at",
    "behind", "as", "zorder", "expression", "contains", "old", "new",
    "on", "style_group", "modal", "tag",
}

CODES = {
    "NS001": ("warning", "show/scene 行内出现裸数字坐标，应改用 port_transforms.rpy 的语义 transform"),
    "NS002": ("error", "使用了 // 运算符；NS 的 div 是截断，必须写 int(a / b)"),
    "NS003": ("warning", "出现旧转换器的 image 命名 ns_bg_*/ns_ev_*/ns_chr_*，素材应走 nsassets+convert_assets 产出的 kind 名"),
    "NS004": ("warning", "转换语句缺少 src: 来源注释"),
    "NS005": ("error", "story 模块内出现 default/define，公共定义应只在 port_*.rpy"),
    "NS006": ("warning", "play music 未显式写 loop/noloop"),
    "NS007": ("error", "story 模块内定义了 screen，自写功能应唯一在 port_screens.rpy"),
    "NS008": ("info", "使用了 hard=True 的暂停，需要按原作意图说明理由"),
    "NS009": ("warning", "剧情里硬编码 with dissolve，应使用 port_transitions.rpy 的语义名"),
    "NS010": ("error", "选项文本为空字符串，NS 中 \"\" 是隐藏项，应转成条件"),
    "NS011": ("warning", "出现裸 TODO，应改成 # ISSUE-xxx : 说明"),
    "NS012": ("error", "story 里直接 show/scene/hide 操作画面，必须调 ns_stage.rpy 的演出层"
                      "（scene 会连带清掉立绘）"),
    "NS013": ("error", "调用了旧 per-game 舞台 API（port_bg/port_chr/...），应改调 ns_* 或 ns_w_*"),
    "NS014": ("warning", "剧情里直接写 images//audio/ 路径，绕过了素材层契约"),
    "NS015": ("warning", "引用了 images/ 下非 images/ns/ 的图片，多为一次性脚本的手搓产物"
                        "（多半没有 alpha），应改走 convert_assets.py 生成的 images/ns/"),
    "NS016": ("warning", "ns_sprite/ns_strip 引用的素材名在 port_images.rpy 里找不到"
                        "（运行期会显示占位图；lint 与 Ren'Py lint 都查不出）"),
}

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


# ---------------------------------------------------------------- 工具

def strip_comment(line):
    """去掉行内注释（不处理字符串里的 #，够用）。"""
    idx = line.find("#")
    if idx < 0:
        return line
    # 粗略判断：引号内的 # 不算注释
    prefix = line[:idx]
    if prefix.count('"') % 2 == 1 or prefix.count("'") % 2 == 1:
        return line
    return prefix


def find_bare_double_slash(line):
    """返回不在引号内的 '//' 首次位置，找不到返回 -1。

    避免把台词/路径里的 http:// 当成整除运算符。
    """
    idx = 0
    in_dq = in_sq = False
    while idx < len(line) - 1:
        ch = line[idx]
        if ch == '"' and not in_sq:
            in_dq = not in_dq
        elif ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == "\\" and (in_dq or in_sq):
            idx += 2
            continue
        elif ch == "/" and line[idx + 1] == "/" and not in_dq and not in_sq:
            return idx
        idx += 1
    return -1


def is_say(stripped):
    if not stripped:
        return False
    # 文档串 / 定义行出现在 init python 里，不是台词（包装层生成代码尤其多）
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return False
    if re.match(r"^(def|class|from|import|return|elif|else)\b", stripped):
        return False
    if stripped.startswith('"'):
        return True
    m = re.match(r"^([A-Za-z_][\w.]*)\s+(.*)$", stripped)
    if not m:
        return False
    head, rest = m.group(1), m.group(2)
    if head in RESERVED:
        return False
    return '"' in rest


def normalize_rel(path, root):
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = path
    return rel.replace(os.sep, "/")


def is_story_module(rel_path):
    parts = rel_path.lower().split("/")
    return "story" in parts


# ---------------------------------------------------------------- 检查

class Lint(object):
    def __init__(self, disabled):
        self.findings = []
        self.disabled = disabled
        self.files = 0
        self.labels = 0
        self.conv_statements = 0
        self.sourced_statements = 0

    def add(self, code, path, lineno, detail=""):
        if code in self.disabled:
            return
        severity, desc = CODES[code]
        self.findings.append({
            "code": code,
            "severity": severity,
            "file": path,
            "line": lineno,
            "message": desc,
            "detail": detail,
        })

    def check_file(self, abs_path, rel_path):
        self.files += 1
        try:
            with open(abs_path, "r", encoding="utf-8-sig", errors="replace") as fh:
                lines = fh.read().splitlines()
        except OSError as exc:
            self.add("NS004", rel_path, 0, "无法读取: %s" % exc)
            return

        story = is_story_module(rel_path)
        src_lines = set()
        for i, raw in enumerate(lines, 1):
            if SRC_RE.search(raw):
                src_lines.add(i)

        for i, raw in enumerate(lines, 1):
            stripped = strip_comment(raw).strip()
            if not stripped:
                continue

            # 结构类
            m = LABEL_RE.match(stripped)
            if m:
                self.labels += 1

            m = DEF_RE.match(stripped)
            if m and story:
                self.add("NS005", rel_path, i, "%s %s" % (m.group(1), m.group(2)))

            m = SCREEN_RE.match(stripped)
            if m and story:
                self.add("NS007", rel_path, i, "screen %s" % m.group(1))

            # NS001 裸坐标
            if SHOW_RE.match(stripped) and (POS_RE.search(stripped) or POS_PAIR_RE.search(stripped)):
                self.add("NS001", rel_path, i, stripped[:90])

            # NS002 //
            if find_bare_double_slash(stripped) >= 0:
                self.add("NS002", rel_path, i, stripped[:90])

            # NS003 旧转换器 image 命名（只在 image 声明 / 引号素材名里判）
            m = IMAGE_NS_RE.match(stripped)
            if not m:
                m2 = re.match(r"^[\"'](ns_(?:bg|ev|chr|cg)_\w+)", stripped)
                m = m2
            if m:
                self.add("NS003", rel_path, i, m.group(1))

            # NS012 story 里直接操作画面（scene 会连带清立绘，是最常见的翻车点）
            if story and (SHOW_RE.match(stripped) or HIDE_RE.match(stripped)):
                self.add("NS012", rel_path, i, stripped[:90])

            # NS013 旧 per-game 舞台 API（`screen port_music():` 这种声明不算调用）
            if not re.match(r"^(screen|label|def|init)\b", stripped):
                m = LEGACY_STAGE_RE.search(stripped)
                if m:
                    self.add("NS013", rel_path, i, m.group(0) + ")")

            # NS014 剧情里手拼素材路径
            m = RAW_ASSET_RE.search(stripped)
            if m and story:
                self.add("NS014", rel_path, i, stripped[:90])

            # NS015 引用了 images/ 下非 images/ns/ 的图（手搓、多半无 alpha）
            for mm in MANUAL_IMAGE_RE.finditer(stripped):
                if mm.group("path").startswith("ui/"):
                    continue  # 工程自带 UI（logo 等）允许放在 images/ui/
                self.add("NS015", rel_path, i, mm.group(0))

            # NS006 play music 缺 loop 声明
            if PLAY_MUSIC_RE.match(stripped) and "loop" not in stripped:
                self.add("NS006", rel_path, i, stripped[:90])

            # NS009 硬编码 dissolve
            if story and DISSOLVE_RE.search(stripped):
                self.add("NS009", rel_path, i, stripped[:90])

            # NS008 hard pause —— 相邻 4 行内有说明理由的注释就算已交代（规则本意是
            # 「说清楚为什么必须硬等」，不是禁止 hard=True）
            if HARD_PAUSE_RE.search(raw):
                near = "\n".join(lines[max(0, i - 5):i])
                if not HARD_REASON_RE.search(near):
                    self.add("NS008", rel_path, i, "需要注释说明为何必须硬等")

            # NS010 空选项文本
            if stripped == '""' or stripped.startswith('"" '):
                self.add("NS010", rel_path, i, stripped[:60])

            # NS011 裸 TODO
            if TODO_RE.search(raw) and not ISSUE_RE.search(raw):
                self.add("NS011", rel_path, i, raw.strip()[:90])

            # NS004 来源注释覆盖（只查剧情模块：公共层 port_*.rpy 是「定义」不是
            # 「逐句转换」，生成文件已自带 src；在那边刷 warning 只会淹掉真问题）
            if story and (CONV_RE.match(stripped) or is_say(stripped)):
                self.conv_statements += 1
                window = range(max(1, i - 5), i + 1)
                if any(w in src_lines for w in window):
                    self.sourced_statements += 1
                else:
                    self.add("NS004", rel_path, i, stripped[:90])

    def summary(self):
        counts = Counter(f["severity"] for f in self.findings)
        return counts


def iter_rpy(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "cache", "saves")]
        for name in sorted(filenames):
            if name.endswith(".rpy"):
                yield os.path.join(dirpath, name)


# ---------------------------------------------------------------- 输出

def print_report(lint, root, strict):
    findings = sorted(
        lint.findings,
        key=lambda f: (SEVERITY_ORDER[f["severity"]], f["file"], f["line"]),
    )
    counts = lint.summary()
    coverage = 0.0
    if lint.conv_statements:
        coverage = 100.0 * lint.sourced_statements / lint.conv_statements

    print("nsport_lint 报告")
    print("  扫描目录 : %s" % os.path.abspath(root))
    print("  .rpy 文件: %d   label: %d" % (lint.files, lint.labels))
    print("  来源注释覆盖率: %d/%d (%.1f%%)"
          % (lint.sourced_statements, lint.conv_statements, coverage))
    print("")

    if not findings:
        print("  未发现问题。")
    else:
        current = None
        for f in findings:
            if f["severity"] != current:
                current = f["severity"]
                print("[%s]" % current)
            loc = "%s:%d" % (f["file"], f["line"]) if f["line"] else f["file"]
            detail = ("  <- %s" % f["detail"]) if f["detail"] else ""
            print("  %-6s %-40s %s%s" % (f["code"], loc, f["message"], detail))
        print("")

    print("汇总: %d error, %d warning, %d info"
          % (counts.get("error", 0), counts.get("warning", 0), counts.get("info", 0)))

    if counts.get("error", 0):
        print("结论: 有 error，不得进入组装阶段。")
        return 1
    if strict and counts.get("warning", 0):
        print("结论: --strict 模式下 warning 视为失败。")
        return 1
    print("结论: 无 error。warning 需逐条决定修复或登记豁免。")
    return 0


def check_asset_refs(game_dir, lint):
    """静态对账：`ns_sprite(...)` / `ns_strip(...)` 引用的素材名是否真的存在。

    为什么必须单独查一遍：这两个调用在运行期缺图只会显示占位图 + 记 NS_MISSING，
    **不会报错**，Ren'Py lint 也只看 image 定义、不看运行期命中。实跑撞过
    ISSUE-025：转换器把 `sys\\01.bmp` 归一成 `sys n01`，手写的
    `ns_strip("sys", "01")` 命中不了，开场 LOGO 变成灰块，两边 lint 都是 0 error。

    名字按 `convert_assets.safe_name()` 的规则归一化后再比一次，与运行期
    `ns_stage.ns_safe()` 保持一致；动画条允许回退单帧。
    """
    def safe(name):
        s = re.sub(r"_+", "_", re.sub(r"[^0-9A-Za-z_]", "_", name.lower())).strip("_")
        if not s:
            return "x"
        if not (s[0].isalpha() or s[0] == "_"):
            s = "n" + s
        return s

    def names(name):
        out = [name]
        sn = safe(name)
        if sn != name:
            out.append(sn)
        return out

    images_path = os.path.join(game_dir, "port_images.rpy")
    if not os.path.exists(images_path):
        return  # 缺文件由 NS013 报，这里不重复
    single, strips = set(), set()
    try:
        text = open(images_path, encoding="utf-8").read()
    except OSError:
        return
    for m in re.finditer(r"^image\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*=", text, re.M):
        single.add((m.group(1), m.group(2)))
    for m in re.finditer(r"^image\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)_(?:anim|loop)\s*:", text, re.M):
        strips.add((m.group(1), m.group(2)))

    for abs_path in iter_rpy(game_dir):
        rel = normalize_rel(abs_path, game_dir)
        try:
            src = open(abs_path, encoding="utf-8").read()
        except OSError:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            m = re.search(r'ns_sprite\(\s*\d+\s*,\s*"([^"]*)"[^)]*group="([^"]*)"', line)
            if m:
                name, group = m.group(1), m.group(2)
                if name and not any((group, n) in single for n in names(name)):
                    lint.add("NS016", rel, i,
                             "ns_sprite 引用 %s/%s，port_images.rpy 里没有这张图" % (group, name))
                continue
            m = re.search(r'ns_strip\(\s*"([^"]*)"\s*,\s*"([^"]*)"', line)
            if m:
                group, name = m.group(1), m.group(2)
                if not name:
                    continue
                ok = any(((group, n) in strips or (group, n) in single) for n in names(name))
                if not ok:
                    lint.add("NS016", rel, i,
                             "ns_strip 引用 %s/%s，既没有动画定义也没有单帧图" % (group, name))


def check_assets(game_dir, lint):
    """工程级检查：素材层契约的三件套是否就位。

    这三件事缺一件，都是「每作手搓素材」的病根复发：没有 port_images.rpy 就
    只能手写 image 定义；没有 port_wrappers.rpy 就只能自己拼素材路径；
    没有 ns_stage.rpy 就只能用 scene/show 硬碰分层。
    """
    required = [
        ("port_images.rpy", "素材声明（nsassets/convert_assets 产出）"),
        ("port_wrappers.rpy", "原作 defsub 包装层（convert_assets 产出）"),
        ("ns_stage.rpy", "通用演出层运行时"),
    ]
    for name, why in required:
        if not os.path.exists(os.path.join(game_dir, name)):
            lint.add("NS013", name, 0, "缺少 %s：%s" % (name, why))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="检查 NS -> Ren'Py 移植工程是否符合 conventions.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("game_dir", nargs="?", help="Ren'Py game 目录（含 .rpy）")
    parser.add_argument("--json", metavar="PATH", help="把结果写入 JSON")
    parser.add_argument("--disable", metavar="CODES",
                        help="忽略指定检查码，逗号分隔，如 NS001,NS009")
    parser.add_argument("--strict", action="store_true", help="warning 也视为失败")
    parser.add_argument("--list-codes", action="store_true", help="列出全部检查码后退出")
    parser.add_argument("--all-files", action="store_true",
                        help="连 Ren'Py 框架文件（screens.rpy/gui.rpy/...）一起检查")
    args = parser.parse_args(argv)

    if args.list_codes:
        print("检查码列表:")
        for code in sorted(CODES):
            sev, desc = CODES[code]
            print("  %-6s %-8s %s" % (code, sev, desc))
        return 0

    if not args.game_dir:
        parser.print_help()
        return 2
    if not os.path.isdir(args.game_dir):
        sys.stderr.write("目录不存在: %s\n" % args.game_dir)
        return 2

    disabled = set()
    if args.disable:
        disabled = {c.strip().upper() for c in args.disable.split(",") if c.strip()}
        unknown = disabled - set(CODES)
        if unknown:
            sys.stderr.write("未知检查码: %s\n" % ", ".join(sorted(unknown)))
            return 2

    lint = Lint(disabled)
    for abs_path in iter_rpy(args.game_dir):
        base = os.path.basename(abs_path).lower()
        if not args.all_files and base in FRAMEWORK_FILES:
            continue
        lint.check_file(abs_path, normalize_rel(abs_path, args.game_dir))

    check_assets(args.game_dir, lint)
    check_asset_refs(args.game_dir, lint)

    rc = print_report(lint, args.game_dir, args.strict)

    if args.json:
        counts = lint.summary()
        payload = {
            "root": os.path.abspath(args.game_dir),
            "files": lint.files,
            "labels": lint.labels,
            "converted_statements": lint.conv_statements,
            "sourced_statements": lint.sourced_statements,
            "source_coverage": (100.0 * lint.sourced_statements / lint.conv_statements)
                               if lint.conv_statements else 0.0,
            "counts": {k: counts.get(k, 0) for k in ("error", "warning", "info")},
            "findings": lint.findings,
        }
        try:
            with open(args.json, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
            print("已写入 %s" % args.json)
        except OSError as exc:
            sys.stderr.write("写 JSON 失败: %s\n" % exc)
            return 2

    return rc


if __name__ == "__main__":
    sys.exit(main())
