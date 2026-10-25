"""生成 catalog.json：角色/变量/素材/系统功能。

素材由实际目录枚举得出（status 按是否已核对给出 inspected / referenced_not_inspected）。
"""
import json
import os
import sys
from collections import OrderedDict

game_dir, out = sys.argv[1], sys.argv[2]
W, H = 800, 600

assets = []


def add(kind, src_rel, target_rel, status, conversion=None, extra=None):
    item = OrderedDict([
        ("id", src_rel.split("/")[-1].rsplit(".", 1)[0].replace("\\", "_")),
        ("kind", kind),
        ("source_path", src_rel),
        ("target_path", target_rel),
        ("status", status),
        ("conversion", conversion),
    ])
    if extra:
        item.update(extra)
    assets.append(item)


bmp_conv = {"action": "bmp_to_png", "notes": "Ren'Py 不保证解码 BMP，统一转 PNG 并核对尺寸"}
for name in sorted(os.listdir(os.path.join(game_dir, "bg"))):
    if name.lower().endswith(".bmp"):
        add("background", "bg/" + name, "images/bg/" + name[:-4] + ".png", "needs_conversion", bmp_conv)
for name in sorted(os.listdir(os.path.join(game_dir, "chr"))):
    if name.lower().endswith(".bmp"):
        add("character_sprite", "chr/" + name, "images/chr/" + name[:-4] + ".png", "needs_conversion", bmp_conv,
            {"notes": "立绘为单层不带 alpha，原作直接用 :a 叠在背景上"})
for name in sorted(os.listdir(os.path.join(game_dir, "ev"))):
    if name.lower().endswith(".bmp"):
        add("event_cg", "ev/" + name, "images/ev/" + name[:-4] + ".png", "needs_conversion", bmp_conv)
for name in sorted(os.listdir(os.path.join(game_dir, "se"))):
    if name.lower().endswith(".ogg"):
        add("sound", "se/" + name, "audio/se/" + name, "referenced_not_inspected")
for name in sorted(os.listdir(os.path.join(game_dir, "bgm"))):
    if name.lower().endswith(".ogg"):
        add("music", "bgm/" + name, "audio/bgm/" + name, "referenced_not_inspected")
for name in sorted(os.listdir(os.path.join(game_dir, "movie"))):
    add("movie", "movie/" + name, "movies/" + name, "needs_conversion",
        {"action": "verify_mpeg1", "notes": "Ren'Py 的 movie_cutscene 只保证 MPEG-1 可播"})
add("font", "default.ttf", "game/fonts/default.ttf", "inspected", None,
    {"notes": "纯文件名下实为 Microsoft YaHei（fontTools 读取 name 表），cmap 29075 字，覆盖全部 253 个台词用字"})
add("voice_pool", "voice/", "audio/voice/", "referenced_not_inspected", None,
    {"notes": "6029 个 ogg，按号段整目录映射；语音号在原文里是 [名字/号] 的后半段"})

characters = [
    {"id": "serika", "display_name": "塞莉卡", "ns_alias": "[塞莉卡/…]", "color": "#f7c6e0"},
    {"id": "serika_kao", "display_name": "芹香", "ns_alias": "[芹香/…]", "color": "#cfe3ff"},
    {"id": "mayura", "display_name": "麻由良", "ns_alias": "[麻由良/…]", "color": "#ffe6b0"},
    {"id": "rei", "display_name": "零", "ns_alias": "[零]", "color": "#d8c8ff"},
    {"id": "noda", "display_name": "野田", "ns_alias": "[野田]", "color": "#cfcfcf"},
    {"id": "npc", "display_name": None, "ns_alias": "[其他名字]", "color": "#ffffff"},
]

variables = [
    ("window_mode", "%G0", 0, "save", "0=窗口 1=全屏"),
    ("effect_on", "%G1", 1, "save", "演出效果开关"),
    ("text_speed", "%G2", 3, "save", "文字速度档"),
    ("skip_read", "%G3", 1, "save", "既读跳过"),
    ("bgm_on", "%G4", 1, "save", "BGM 开关"),
    ("voice_on", "%G5", 1, "save", "语音开关"),
    ("se_on", "%G6", 1, "save", "SE 开关"),
    ("auto_speed", "%G7", 2, "save", "自动播放档"),
    ("bgm_vol", "%G8", 2, "save", "BGM 音量 0-6"),
    ("voice_vol", "%G9", 6, "save", "语音音量 0-6"),
    ("se_vol", "%G10", 2, "save", "SE 音量 0-6"),
    ("voice_skip_stop", "%G11", 1, "save", "语音可否跳过"),
    ("window_style", "%G12", 3, "save", "窗口样式 1-6"),
    ("kaisou_mode", "%kaisoumode", 0, "save", "回想模式"),
    ("cur_bgm", "%MNUM", 0, "save", "当前 BGM 号"),
    ("cg_unlock", "savefileexist", "{}", "persistent", "CG/回想解锁表"),
]
variables = [OrderedDict([("id", a), ("source_name", b), ("type", "int" if not isinstance(c, str) else "dict"),
                          ("initial", c), ("scope", d), ("meaning", e)])
             for a, b, c, d, e in variables]

features = [
    ("text_window", "自绘文本窗 + 6 个按钮（backlog/auto/skip/save/load/config/delete）", "native", "port_say", "say 屏与 quick_menu 覆盖"),
    ("choice_ui", "自绘选项（getcselnum/getcselstr/selectbtnwait/cselgoto）", "native", "menu 屏", "9 处分支全部可直译成 menu"),
    ("backlog", "自定义回想（*backlog，含语音重播）", "native", "renpy 内置历史记录", "原作的「点击历史行重播语音」需 voice log 微调"),
    ("save_load", "自绘 4 页×6 格存档 + 截图缩略图", "configured", "gui.file_slot_cols/rows", "改 gui 参数即可，不需要自绘"),
    ("settings", "自绘设置界面（音量档/文字速度/既读/自动/窗口样式 6 种）", "custom", "port_settings.rpy", "音量档为 0-6 的粗档位，需映射成 0-100"),
    ("cg_gallery", "CG 鉴赏（*cgmode，分页 3 列）", "custom", "port_gallery.rpy", "解锁状态改用 persistent"),
    ("music_gallery", "音乐鉴赏（*musicmode）", "custom", "port_gallery.rpy", "13 首 BGM"),
    ("memory_gallery", "回想鉴赏（*memmode，mem0-mem37）", "custom", "port_gallery.rpy", "需要按段落地 label 才能跳转"),
    ("movie", "片头/变身/结局 mpg 动画（mpegplay）", "configured", "renpy.movie_cutscene", "只保证 MPEG-1"),
    ("quit_confirm", "菜单「结束」用的 yesnobox", "native", "renpy.quit / 确认屏", "无需自定义"),
]
features = [OrderedDict([("id", a), ("behavior", b), ("status", c), ("interface", d), ("notes", e)])
            for a, b, c, d, e in features]

catalog = OrderedDict([
    ("version", "1"),
    ("resolution", {"source": [W, H], "target": [1280, 720]}),
    ("characters", characters),
    ("variables", variables),
    ("assets", assets),
    ("features", features),
])
json.dump(catalog, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("assets=%d characters=%d variables=%d features=%d" % (len(assets), len(characters), len(variables), len(features)))
