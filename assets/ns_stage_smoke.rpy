## 演出层冒烟测试（可选，验证阶段用）
##
## 用法：
##   1) 把本文件临时拷进 <工程>/game/（文件名随意，建议 _ns_stage_smoke.rpy）
##   2) 把下面 SMOKE 段里的 bg / chr / ev / se / bgm 名字换成该作真实存在的素材名
##   3) headless 跑一次：
##        $env:APPDATA = '<工程上级>/_appdata'
##        $env:RENPY_SKIP_SPLASHSCREEN = '1'
##        $env:SDL_AUDIODRIVER = 'dummy'
##        renpy.exe <project>
##      进程会自己退出（renpy.quit()），结果写在 <工程>/game/_ns_smoke_result.txt
##   4) 看有没有 FAIL 行，之后删掉本文件与结果文件
##
## 它验证的是「运行期才暴露的错误」：未注册的音频通道、缺素材没兜住、
## 用了不存在的 Ren'Py API。lint 查不出这些。

init 999 python:
    _ns_smoke = {"done": False}

    def _ns_smoke_run():
        if _ns_smoke["done"]:
            return
        _ns_smoke["done"] = True

        # ---- SMOKE：换成该作真实素材名 ----------------------------------
        BG1, BG2 = "bio_a", "bio_b"
        CHR1, CHR2, CHR3 = "m01_a", "m01_b", "m01_c"
        EV1 = "n01"
        SE1, VOICE1, BGM1 = "mse009", "mse009", "bgm01"
        # -----------------------------------------------------------------

        out = []
        cases = [
            ("ns_bg", lambda: ns_bg(BG1, dur=0)),
            ("ns_bg dur", lambda: ns_bg(BG2, dur=0.5)),
            ("ns_ev", lambda: ns_ev(EV1, dur=0)),
            ("ns_black", lambda: ns_black(0)),
            ("ns_chr", lambda: ns_chr("c", CHR1, dur=0)),
            ("ns_chr left", lambda: ns_chr("l", CHR2, dur=0.2)),
            ("ns_chr right", lambda: ns_chr("r", CHR3, dur=0)),
            ("ns_bgchr", lambda: ns_bgchr(BG1, CHR1, dur=0)),
            ("ns_chr_clear", lambda: ns_chr_clear("c", dur=0)),
            ("ns_sprite", lambda: ns_sprite(1, CHR1, 100, 120)),
            ("ns_hide_all", lambda: ns_hide_all()),
            ("ns_scale", lambda: ns_scale()),
            ("ns_bgm", lambda: ns_bgm(BGM1)),
            ("ns_bgm_stop", lambda: ns_bgm_stop()),
            ("ns_se", lambda: ns_se(SE1, ch=1)),
            ("ns_se_loop", lambda: ns_se_loop(SE1, ch=2)),
            ("ns_se_stop", lambda: ns_se_stop(ch=2)),
            ("ns_se_stop_all", lambda: ns_se_stop_all()),
            ("ns_setvol", lambda: ns_setvol(19, 80)),
            ("ns_voice", lambda: ns_voice(VOICE1)),
            ("ns_voice_loop", lambda: ns_voice_loop(VOICE1)),
            ("ns_voice_stop", lambda: ns_voice_stop()),
            ("ns_report_missing", lambda: ns_report_missing()),
            ("ns_w_bg", lambda: ns_w_bg(BG1)),
            ("ns_w_chr", lambda: ns_w_chr(CHR1)),
            ("ns_w_chr empty", lambda: ns_w_chr("")),
            ("ns_w_bgchr", lambda: ns_w_bgchr(BG2, CHR2)),
            ("ns_w_ev", lambda: ns_w_ev(EV1)),
            ("ns_w_black", lambda: ns_w_black()),
            ("ns_w_black2", lambda: ns_w_black2()),
            ("ns_w_music", lambda: ns_w_music(3)),
            ("ns_w_music 0", lambda: ns_w_music(0)),
            ("ns_w_se", lambda: ns_w_se(SE1)),
            ("ns_w_loop", lambda: ns_w_loop(VOICE1)),
            ("ns_w_sloop", lambda: ns_w_sloop(SE1)),
            ("ns_w_bun", lambda: ns_w_bun()),
            ("ns_w_dcl", lambda: ns_w_dcl()),
            ("ns_w_dld", lambda: ns_w_dld()),
            ("ns_w_wclose", lambda: ns_w_wclose()),
            ("ns_w_dstop", lambda: ns_w_dstop()),
        ]

        for name, fn in cases:
            try:
                fn()
                out.append("OK   %s" % name)
            except Exception as e:
                if "interaction" in str(e):
                    # 周期性回调里跑带过渡的演出会撞「不能在交互中开交互」；
                    # 换新上下文重试，这才是脚本语句里的真实环境
                    try:
                        renpy.invoke_in_new_context(fn)
                        out.append("OK*  %s (new context)" % name)
                    except Exception as e2:
                        out.append("FAIL* %s -> %s: %s" % (name, type(e2).__name__, e2))
                else:
                    out.append("FAIL %s -> %s: %s" % (name, type(e).__name__, e))

        # 缺素材应当回落占位图/静默，而不是抛异常
        try:
            ns_bg("__no_such_bg__", dur=0)
            ns_chr("c", "__no_such_chr__", dur=0)
            ns_se("__no_such_se__", ch=1)
            out.append("OK   missing-asset fallback")
        except Exception as e:
            out.append("FAIL missing-asset fallback -> %s: %s" % (type(e).__name__, e))

        try:
            with open(os.path.join(config.gamedir, "_ns_smoke_result.txt"), "w") as f:
                f.write("\n".join(out) + "\n")
        except Exception as e:
            print("SMOKE write fail: %r" % (e,))
        for line in out:
            print("SMOKE " + line)
        renpy.quit()

    config.periodic_callbacks.append(_ns_smoke_run)
