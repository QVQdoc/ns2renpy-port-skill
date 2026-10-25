# 打包发布

> 目标：一条命令把工程变成「收包人双击就能玩」的发布包。

Ren'Py 的发布包**自带引擎和 Python 运行时**，收包人不需要装 Ren'Py、也不需要装 Python。一条命令（在 SDK 根目录执行，`launcher` 是 SDK 自带的工程）：

```bash
renpy.exe launcher distribute <工程目录> --package pc
# 输出：<工程目录的上一级>/<build.name>-<config.version>-dists/<...>-pc.zip
# 想指定位置加 --destination <目录>
```

`--package` 取值：`pc`（Windows + Linux 一个包）、`win`、`linux`、`mac`、`market`（Android/Play）、`steam`。**mac 包必须在 macOS 上打**——Windows 上跑 `--package pc` 出来的 zip 里没有 `.app`（实测：`lib/` 只有 `py3-windows-x86_64` 和 `py3-linux-x86_64`）。

### 打包前必须做的三件事

1. **`options.rpy` 里把开发期产物排除掉**，否则会打进玩家那边（实测第一版把 `walk_report.json`、`assets_convert_report.md`、`traceback.txt` 一起打了进去）：

```renpy
init python:
    build.classify('game/saves/**', None)    # 测试档、别人的档
    build.classify('game/cache/**', None)    # bytecode 缓存，换机器后可能与 rpyc 不同步
    build.classify('*.txt', None)            # 根目录散落的 log / lint 输出
    build.classify('*.log', None)
    build.classify('*.md', None)             # 开发报告（pattern 只匹配工程根，不会误伤 game/ 里的文件）
    build.classify('*.json', None)
```

2. **名字和版本**：`define build.name = "serika"`（ASCII、无空格，决定 exe/文件夹名）、`define config.version = "1.0"`、`define config.name = _("中文标题")`（窗口标题与安装后显示名）、`define config.save_directory`（存档目录名，换版本时别改，否则老档读不到）。

3. **跑一遍双 lint + 走线**再打包：包里是编译后的 `.rpyc`，玩家那边看不到 traceback 细节。

### 体积与分发

- 素材已经压过（PNG/OGG/WebM），zip 基本不再缩小：本作 `game/` 656MB（voice 420MB 占大头）→ 679MB 的 zip，属于正常。
- 免安装绿色版就是整个 `<name>-pc/` 目录，拷走即用；解压后双击 `<build.name>.exe`。
- **Windows SmartScreen 一定拦**（exe 未签名），让收包人「更多信息 → 仍要运行」，或者用代码签名证书；这不是打包出错。
- 存档在 `%APPDATA%\RenPy\<config.save_directory>`，不是游戏目录，所以升级版本不丢档。

### 两个只在别人机器上才会遇到的坑

- **`%APPDATA%\RenPy\tokens\upgraded.txt` 打不开**：双击 exe 弹一个 traceback 的 txt，内容是 `PermissionError: [Errno 13] Permission denied`，位置 `renpy/savetoken.py:260 with open(upgraded_txt, "a")`。这一条不是"权限坏了"的偶发问题，而是**存档根目录不可写**，`tokens` 与存档共用同一个根（`savetoken.py:301 token_dir = renpy.__main__.path_to_saves(gamedir, "tokens")`）。三种解法，按侵入性从低到高：
  1. 包根放一个空文件夹 **`Ren'Py Data`**（零点击，推荐给最终用户）：`renpy.py:176-187` 会从 `config.renpy_base` 逐级向上找这个名字的目录，找到就把存档根换过去。实测把 `Ren'Py Data\` 放进 `serika-1.0-pc\` 后，双击 `serika.exe` 即在 `<包>\Ren'Py Data\` 下生成 `serika-ns-port-1.0\` 与 `tokens\`，不再碰 `%APPDATA%`。
  2. 发一个启动 bat，设 `RENPY_PATH_TO_SAVES=%~dp0saves`（`renpy.py:173-174`）：存档落到 `<包>\saves\`，适合想保留"标准安装"行为、只在受限机器上用的场合。
  3. 让用户修 `%APPDATA%\RenPy` 的权限（删掉重建 `tokens\`，或用可写的 `APPDATA` 启动）。
  建包时顺手放 1 或 2，比事后解释便宜。
- **包里的 `game/cache/` 不用手动删**：打包器会自己生成 `cache/bytecode-312.rpyb` 和 `cache/build_info.json`（实测包里就这三个条目），这是玩家端免编译用的；你排除的是开发期的 `py3analysis.rpyb` / `screens.rpyb` / `shaders.txt`。
- **打包命令本身也会被这个坑绊倒**：`launcher distribute` 自己就是 Ren'Py 进程，`%APPDATA%` 不可写时直接 exit 1 且没有明显报错。构建前先 `$env:APPDATA='<可写目录>'`。

### 冒烟验证（headless）

```powershell
$env:APPDATA='<可写目录>'; $env:SDL_AUDIODRIVER='dummy'; $env:RENPY_SKIP_SPLASHSCREEN='1'; $env:RENPY_SKIP_MAIN_MENU='1'
Start-Process .\serika.exe
# 看 log.txt 里出现 "Initializing gl2 renderer" + "Screen sizes: virtual=(800, 600)" 即起得来
```

### 允许玩家之间分享存档（预置签名密钥）

Ren'Py 会给每个存档签名，用的密钥在存档根下的 `tokens/security_keys.txt`（`renpy/savetoken.py` 的 `create_token()`：`ecdsa.SigningKey.generate(curve=NIST256p)`，写成一行 `signing-key <私钥DER> <公钥DER>`）。首次启动时**每台机器各自生成一把**，于是别人的存档拿过来读会弹：

> This save was created on a different device. Maliciously constructed save files can harm your computer. Do you trust this save's creator?

玩家两边都点「信任」也能过，但很烦。要让存档**开箱即共享**，就在包里预置一份固定密钥：

1. 随便找一台机器首次跑一次游戏（或跑一次 `renpy.exe <project> lint`，指向一个可写的 `RENPY_PATH_TO_SAVES`），让它生成 `tokens/security_keys.txt`；
2. 把这份文件放进工程的 `Ren'Py Data/tokens/security_keys.txt`（随包发布），内容只有一行 `signing-key ...`；
3. 重打包。玩家端 `init_tokens()` 读到 `signing_keys` 非空就不再生成新密钥，所有包共用同一把。

验证：解压新包直接运行，比对 `Ren'Py Data/tokens/security_keys.txt` 的 SHA256 与源文件一致、行数仍为 1（文件头会多出 `upgraded.txt`，那是另一回事）。

代价：私钥随包公开，任何人可以伪造这个游戏的存档签名。对同人/汉化发布通常可接受；要是把存档签名当防作弊手段，就别预置。

附带好处：存档跟着 `Ren'Py Data/` 走，玩家把整个游戏目录拷到另一台机器，存档一起过去。

