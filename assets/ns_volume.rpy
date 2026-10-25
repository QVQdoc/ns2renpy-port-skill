## 音量桥接（通用件，工程直接拷进 game/）
##
## 原作 NS 的音量是「档位 0-6」模型，设置界面自己画；Ren'Py 的对应物是 mixer 音量
## （设置界面那三条滑条控的就是它）。这个文件只做一件事：把原作档位换算成 mixer 音量。
##
## 三条硬规则（都是实测踩出来的，详见 references/assets_contract.md 5.5）：
##   1) 只写 mixer（preferences.set_volume），**不要**再写通道级音量 —— 两者相乘，
##      会把滑条可用范围压成 1/4~1/3，玩家会觉得「调了没用」。
##   2) 换算用 `档*12/100`（原作 *exec_vol 的百分比语义），6 档 = 1.0；不是 `档/6`。
##   3) 只在第一次运行时写（persistent.port_vol_init），之后交给玩家的滑条；
##      读档时把通道级音量清回 1.0，收掉旧版本留下的上限（通道音量会存进存档）。
##
## 需要的工程变量（port_variables.rpy 里用 default 定义，缺省值由 getattr 兜底）：
##   bgm_vol / bgm_on、voice_vol / voice_on、se_vol / se_on  —— 对应 %G8/%G4、%G9/%G5、%G10/%G6

init python:
    def ns_vol_level(level, on=True):
        """NS 音量档 0-6 → 0.0-1.0。

        源 *exec_vol：`bgmvol %G8*12`、`voicevol %G9*12`、`sevol %G10*12`，
        档 6 直接给 100；开关 %G4/%G5/%G6 = 0 时给 0。
        所以 2 档 = 0.24（约 -12 dB），不是 2/6 = 0.333 —— 原作默认 BGM 就压得比语音低。
        """
        if not on:
            return 0.0
        try:
            lv = int(level)
        except (TypeError, ValueError):
            return 1.0
        if lv <= 0:
            return 0.0
        if lv >= 6:
            return 1.0
        return lv * 12 / 100.0

    def port_apply_volume(force=False):
        """把原作档位作为**初值**写进 mixer 音量；返回写进去的三个值（便于验收打日志）。"""
        levels = {
            "music": ns_vol_level(getattr(store, "bgm_vol", 2), getattr(store, "bgm_on", 1)),
            "sfx": ns_vol_level(getattr(store, "se_vol", 2), getattr(store, "se_on", 1)),
            "voice": ns_vol_level(getattr(store, "voice_vol", 6), getattr(store, "voice_on", 1)),
        }
        if not force and getattr(persistent, "port_vol_init", False):
            return levels
        persistent.port_vol_init = True
        for mixer, value in levels.items():
            try:
                renpy.game.preferences.set_volume(mixer, value)
            except Exception:
                try:
                    SetMixer(mixer, value)()
                except Exception:
                    pass
        return levels

    def port_clear_channel_volume():
        """把通道级（次级）音量清回 1.0 —— 旧版本写过的那层，会跟着存档回来。"""
        for name in ["music", "sound", "voice"] + ["ns%d" % i for i in range(1, 33)]:
            try:
                renpy.music.set_volume(1.0, channel=name)
            except Exception:
                pass

    def port_se_stop():
        """停掉所有 SE/语音通道（旧调用点兼容）。"""
        ns_se_stop_all()
