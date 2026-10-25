# -*- coding: utf-8 -*-
"""把原作的过场动画转成 Ren'Py 能放的 webm（VP8 + Vorbis）。

NScripter 的 `mpegplay "movie\\x.mpg"` 在 Ren'Py 里没有直接对应：MPEG-1 走 libav
能放但不保证带声音、体积巨大，所以转换阶段统一转成 webm。

**必须用 VP8，不能用 VP9。** 实测 Ren'Py 8.5.3（Windows，官方 SDK 自带解码器）播
VP9/Vorbis 的 webm 时 `renpy.movie_cutscene()` 会**永久阻塞**——画面停在黑屏，不报错、
不超时、`log.txt` 里一行都没有，游戏看起来就是「卡在开场动画」。同一个源转 VP8 后
71 秒正常播放并返回。所以本脚本固定 `-c:v libvpx`（VP8），并在跳过已有文件前用
ffprobe 复核编码——否则一个手工 ffmpeg 命令做出的 VP9 文件会因为「比源文件新」被
安静地跳过，然后卡死整个开场。

用法：
    python ns_movies.py <游戏目录> <工程 game 目录> [--only opening,ending]
                        [--profile low|normal|high] [--dry-run]
    python ns_movies.py <游戏目录> <工程 game 目录> --verify

幂等：目标 webm 已存在、比源文件新、**且编码复核为 vp8** 才跳过。
`--profile` 三档画质（low/normal/high）对应 crf 18/12/8。
`--verify` 只检查 `<game 目录>/movie/*.webm` 的编码是否可播，不转任何东西（可进 CI / 验收清单）。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

VIDEO_EXTS = (".mpg", ".mpeg", ".m1v", ".avi", ".wmv", ".mp4", ".mkv")

PROFILES = {
    "low": ("-crf", "18", "-b:v", "900k", "-q:a", "3"),
    "normal": ("-crf", "12", "-b:v", "2M", "-q:a", "4"),
    "high": ("-crf", "8", "-b:v", "4M", "-q:a", "6"),
}

# Ren'Py 8.5 实测可播：vp8 / theora + vorbis / opus。vp9 会卡死。
OK_VIDEO = ("vp8", "theora")
OK_AUDIO = ("vorbis", "opus", "mp3", "aac", "pcm_s16le")


def find_sources(game_root):
    out = []
    for dirpath, _dirnames, filenames in os.walk(game_root):
        # 不往已生成工程里钻
        if os.sep + "project" in dirpath or os.sep + "task" in dirpath:
            continue
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in VIDEO_EXTS:
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def find_tool(name, ffmpeg_path=None):
    hit = shutil.which(name)
    if hit:
        return hit
    if ffmpeg_path:
        cand = os.path.join(os.path.dirname(ffmpeg_path), name + (".exe" if os.name == "nt" else ""))
        if os.path.exists(cand):
            return cand
    return None


def probe(path, ffprobe):
    """返回 {'video': ..., 'audio': ..., 'duration': ...}；失败返回 None。"""
    if not ffprobe:
        return None
    cmd = [ffprobe, "-v", "error", "-print_format", "json",
           "-show_streams", "-show_format", path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError:
        return None
    info = {"video": "", "audio": "", "duration": 0.0, "playable": False, "why": ""}
    for stream in data.get("streams", []):
        kind = stream.get("codec_type")
        if kind == "video" and not info["video"]:
            info["video"] = stream.get("codec_name", "")
        elif kind == "audio" and not info["audio"]:
            info["audio"] = stream.get("codec_name", "")
    try:
        info["duration"] = float(data.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        pass
    if info["video"] in OK_VIDEO:
        info["playable"] = True
    elif info["video"] == "vp9":
        info["why"] = "VP9：Ren'Py 8.5 的 movie_cutscene 会永久阻塞（实测），必须重转 VP8"
    elif not info["video"]:
        info["why"] = "没有视频流"
    else:
        info["why"] = "编码 %s 不保证可播，请用 VP8" % info["video"]
    if info["audio"] and info["audio"] not in OK_AUDIO:
        info["why"] = (info["why"] + "；" if info["why"] else "") + "音频 %s 不保证可播" % info["audio"]
    return info


def verify(game_dir, ffmpeg_path):
    movie_dir = os.path.join(os.path.abspath(game_dir), "movie")
    ffprobe = find_tool("ffprobe", ffmpeg_path)
    if not os.path.isdir(movie_dir):
        print("没有 %s 目录，跳过检查" % movie_dir)
        return 0
    if not ffprobe:
        print("找不到 ffprobe，无法复核编码（ffmpeg 同目录一般就有）")
        return 2
    bad = 0
    files = sorted(f for f in os.listdir(movie_dir) if f.lower().endswith(".webm"))
    for fn in files:
        info = probe(os.path.join(movie_dir, fn), ffprobe)
        if info is None:
            print("[ ?? ] %-18s ffprobe 读不出，人工核一下" % fn)
            bad += 1
            continue
        tag = "ok  " if info["playable"] and not info["why"] else "BAD "
        print("[%s] %-18s %-6s %-8s %5.1fs %s"
              % (tag, fn, info["video"] or "?", info["audio"] or "无音轨",
                 info["duration"], info["why"]))
        if not info["playable"] or info["why"]:
            bad += 1
    print("\n共 %d 个 webm，问题 %d 个" % (len(files), bad))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game_root")
    ap.add_argument("game_dir")
    ap.add_argument("--only", default="")
    ap.add_argument("--profile", default="normal", choices=sorted(PROFILES))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true",
                    help="只检查 game/movie/*.webm 的编码是否可播，不转换")
    ap.add_argument("--keep-existing", action="store_true",
                    help="即使已有文件的编码不对也不重转（仅调试用）")
    args = ap.parse_args()

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("找不到 ffmpeg，先把 ffmpeg 放进 PATH 再跑")
        return 2

    if args.verify:
        return verify(args.game_dir, ffmpeg)

    ffprobe = find_tool("ffprobe", ffmpeg)
    srcs = find_sources(os.path.abspath(args.game_root))
    only = set(x.strip() for x in args.only.split(",") if x.strip())
    out_dir = os.path.join(os.path.abspath(args.game_dir), "movie")
    os.makedirs(out_dir, exist_ok=True)

    stats = {"total": 0, "skipped": 0, "ok": 0, "failed": 0}
    total_bytes_in = total_bytes_out = 0

    for src in srcs:
        stem = os.path.splitext(os.path.basename(src))[0]
        if only and stem not in only:
            continue
        stats["total"] += 1
        dst = os.path.join(out_dir, stem + ".webm")
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            info = probe(dst, ffprobe) if ffprobe else None
            if info is None:
                stats["skipped"] += 1
                print("[skip] %s（目标已存在且更新；没 ffprobe，无法复核编码）" % stem)
                continue
            if info["playable"] and not info["why"]:
                stats["skipped"] += 1
                print("[skip] %s（已存在、编码 %s，可播）" % (stem, info["video"]))
                continue
            if args.keep_existing:
                stats["skipped"] += 1
                print("[skip] %s（--keep-existing，但编码有问题：%s）" % (stem, info["why"]))
                continue
            print("[redo] %s（已有文件不可播：%s）→ 重转" % (stem, info["why"]))
        if args.dry_run:
            print("[dry ] %s -> %s" % (src, dst))
            continue
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", src,
               "-c:v", "libvpx", "-deadline", "good", "-cpu-used", "2",
               "-c:a", "libvorbis"] + list(PROFILES[args.profile]) + [dst]
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            stats["failed"] += 1
            print("[fail] %s -> %s" % (stem, (proc.stderr or "").strip().splitlines()[-1:] or "?"))
            continue
        stats["ok"] += 1
        total_bytes_in += os.path.getsize(src)
        total_bytes_out += os.path.getsize(dst)
        note = ""
        info = probe(dst, ffprobe) if ffprobe else None
        if info is not None:
            note = "编码 %s/%s" % (info["video"], info["audio"] or "无音轨")
            if not info["playable"]:
                note += " ← 仍然不可播，检查 ffmpeg 参数"
        print("[ok  ] %-16s %6.1fMB -> %5.1fMB  %.0fs  %s"
              % (stem, os.path.getsize(src) / 1e6, os.path.getsize(dst) / 1e6,
                 time.time() - t0, note))

    print("\n合计 %(total)d 个：转好 %(ok)d、跳过 %(skipped)d、失败 %(failed)d" % stats)
    if stats["ok"]:
        print("体积 %.1fMB -> %.1fMB" % (total_bytes_in / 1e6, total_bytes_out / 1e6))
    return 1 if stats["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
