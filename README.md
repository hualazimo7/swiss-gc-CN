# Swiss 简体中文版 + 游戏内复位（swiss-gc-CN）

<p align="center">
  <a href="https://ifdian.net/a/hualazimo7" title="在爱发电请我喝一杯咖啡">
    <img src="docs/afdian-sponsor.svg" alt="请我喝一杯咖啡 · 爱发电" height="44">
  </a>
  <br>
  <a href="https://ifdian.net/a/hualazimo7"><sub>或点此前往爱发电 →</sub></a>
</p>

> ⚠️ **禁止商业使用 / NON-COMMERCIAL USE ONLY**：本仓库的原创内容仅限非商业用途，禁止出售、预装到售卖的硬件/存储卡、付费代刷、广告变现等。详见 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)。
> 上游 Swiss / GNU Unifont 的 GPL-2.0 材料不受此限制（见 [LICENSE-GPL-2.0.txt](LICENSE-GPL-2.0.txt)）。

[Swiss](https://github.com/emukidid/swiss-gc) 是 GameCube 的全能自制程序加载器。本仓库收录基于上游 **master commit `62a8b9a2`**（2026-11-05，界面显示的 revision 为 **2154**）的**简体中文构建**，以及与之**严格配套**的游戏内复位（IGR / Apploader）文件。

> 这两个东西必须成对使用：`apploader.img` 内嵌了本次编译的汉化 Swiss 本体，换固件不换它（或反过来）都会导致复位后黑屏、反复重启或回到英文原版。

## 包含什么

| 内容 | 说明 |
|---|---|
| `firmware/swiss.dol` | **自解压正式版**，SD 卡 / PicoBoot / CubiBoot / WODE 使用；GCLoader 需打成 ISO（见下） |
| `firmware/swiss-wiiload.dol` | 原始构建，**仅**用于 wiiload 网络推送到已在运行的 Swiss |
| `gcloader/boot.iso` | **GCLoader 专用可引导镜像**，放 SD 卡根目录并保持文件名 `boot.iso` |
| `iso/*.iso` | NTSC-U / NTSC-J / PAL 三个区域镜像，供刻盘或其它 ODE 使用 |
| `ActionReplay/` | Action Replay 用 `AUTOEXEC.DOL` + 同批 `SDLOADER.BIN` |
| `FlippyDrive/` | FlippyDrive 的 `EXTRACT_TO_ROOT.zip` → `boot.dol` |
| `WiikeyFusion/` | `.fzn` 固件 / `.fzn.fw` 恢复固件 / Recovery ISO（WASP Fusion 同用） |
| `Wii/` | Wii Homebrew Channel 用的 `apps/swiss-gc/boot.dol` 离线包 |
| `WODE/` | WODE extcfg 可引导 ISO |
| `MemoryCard/` | 记忆卡存档漏洞用的 `boot.gci` / `xeno.gci` |
| `igr/apploader.img` | 与上述固件同一份源码产出的 IGR 复位镜像 |
| `igr/SDCard_IGR/` + `.zip` | 给无网卡用户的离线包，解压到 SD 卡根目录即可 |
| `Licenses/` | 上游第三方依赖的许可文本 |
| `source/` | 复现汉化所需的翻译表、字模源文件与构建/校验脚本 |
| `tools/` | 构建校验、ISO 生成、各启动方式打包、上传、wiiload、改名工具 |
| `docs/` | IGR 原理、各启动方式说明、汉化实现、游戏名中文化的技术记录 |

## 版本历史与下载（不可变发布）

> 已发布的版本**永久保留**：附件与说明不再覆盖、不再改写，每次改动都发一个新 tag。
> 需要旧版本直接从下表对应 Release 下载即可回滚。规则见
> [docs/RELEASE_POLICY.md](docs/RELEASE_POLICY.md)。

| 版本 | 日期 | 固件 SHA-256 前 8 位 | 主要变化 |
|---|---|---|---|
| [**v2154-zh-r10（Latest）**](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r10) | 2026-11-12 | `45c79728` | 字体重做：矢量字体灰度反锯齿，中文/英文/数字同源（**当前推荐**；固件重编，全部启动方式文件同步更新） |
| [v2154-zh-r9](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r9) | 2026-11-11 | `1106948d` | 中文串里的数字改成与汉字同高的满格点阵 |
| [v2154-zh-r8](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r8) | 2026-11-10 | `26d133f3` | 字库扩到 8887 字，补齐 Big5 常用繁体/日文汉字 |
| [v2154-zh-r7](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r7) | 2026-11-10 | `1ec622cb` | 补齐 ActionReplay / FlippyDrive / WiikeyFusion / Wii / WODE / 记忆卡六种启动方式（固件未变） |
| [v2154-zh-r6](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r6) | 2026-11-10 | `1ec622cb` | 新增 GCLoader 可引导 ISO 与三个区域镜像 |
| [v2154-zh-r5](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r5) | 2026-11-10 | `1ec622cb` | 中文串里的数字改用点阵 |
| [v2154-zh-r4](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r4) | 2026-11-10 | `777243c4` | 修复中文游戏名缺字，字库扩到 6992 字 |
| [v2154-zh-r3](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r3) | 2026-11-09 | `7351321f` | 设置里增加背景图切换（关闭 / 1~9） |
| [v2154-zh-r2](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r2) | 2026-11-09 | `2a52fd27` | 混合字符串内拉丁字形收缩至 0.85 |
| [v2154-zh-r1](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh-r1) | 2026-11-09 | `56711059` | 首发 |
| [v2154-zh](https://github.com/hualazimo7/swiss-gc-CN/releases/tag/v2154-zh) | 2026-11-09 | `1ec622cb` | 最初的 tag，冻结保留以兼容旧链接；内容与 r5 相同 |

⚠️ 升级时 `IPL.dol` 与 `swiss/patches/apploader.img` **必须同时替换成同一版本**，
只换其一会导致游戏内复位异常。

## 快速开始

### 1. 安装固件

把 `firmware/swiss.dol` 复制到 SD 卡根目录：

- **PicoBoot / gekkoboot**：按你的配置改名为 `ipl.dol`（或 `IPL.dol`）
- **CubiBoot / 光驱替代设备**：在菜单里直接选它
- 升级前建议把旧 DOL 改名留一份备份

⚠️ **不要**把 `swiss-wiiload.dol` 放进 SD 卡启动。原始构建链接在 `0x80003100`，会覆盖 IPL 加载器自身，表现为选完文件立刻黑屏。

### 1.1 GCLoader 用户：用 `boot.iso`，不要用 DOL

GCLoader 把 SD 卡上的镜像当一张真实光盘挂给主机，走的是原厂 IPL → apploader → DOL
的启动链，**不能直接加载 `.dol`**。原版 Swiss 的发布包里也因此单独带
`GCLoader/boot.iso`。本包同样提供：

1. 把 [`gcloader/boot.iso`](gcloader/boot.iso) 复制到 GCLoader SD 卡的**根目录**，
   文件名保持 `boot.iso`（GCLoader 固件固定找这个名字）
2. 同卡照常放 `swiss/` 目录（含 `patches/apploader.img`）与游戏镜像
3. 开机自动进入中文 Swiss

镜像里装的就是 `firmware/swiss.dol`（同一次构建的 packed 自解压 DOL），**固件版本与
本 Release 完全一致**。区域镜像、生成原理、自检与验证状态见
[`gcloader/使用说明.md`](gcloader/使用说明.md)；自行换 DOL 重新打包用
`python tools/build_gcloader_iso.py --all`。

> ✅ **GCLoader 真机已验证可用**（2026-11-10 用户实机反馈，r7 固件）：把 `boot.iso` 放在
> GCLoader SD 卡根目录可正常启动进入中文 Swiss。r8 / r9 都只更换了镜像内固件、
> 结构未改，仍建议重测一次。此前镜像已与官方 r2119 `boot.iso`
> 做过结构对照：前 32 KiB 光盘头逐字节相同、boot catalog 与 DOL 的 LBA 一致、
> El Torito platform ID 与校验和一致。Dolphin 对官方盘同样黑屏，属于模拟器
> 不支持该启动路径，不能用 Dolphin 的结果判断镜像好坏。

### 1.2 其它启动方式（Action Replay / FlippyDrive / Wiikey Fusion / Wii / WODE / 记忆卡）

官方 Swiss 发布包按设备分目录提供不同的引导文件，本包也已补齐。**这些目录里装的是
同一份汉化固件**，只是包装成各设备能识别的格式：

| 设备 | 用哪个文件 | 放到哪 |
|---|---|---|
| Action Replay | `ActionReplay/AUTOEXEC.DOL` + `SDLOADER.BIN` | SD 卡根目录，两个都要 |
| FlippyDrive | 解压 `FlippyDrive/EXTRACT_TO_ROOT.zip` → `boot.dol` | FlippyDrive SD 卡根目录 |
| Wiikey / WASP Fusion | `WiikeyFusion/swiss-zh.fzn`（+ `.fzn.fw` / RecoveryISO） | SD 卡根目录，按设备流程刷写 |
| Wii | 解压 `Wii/EXTRACT_TO_ROOT.zip` → `apps/swiss-gc/boot.dol` | Wii 的 SD 卡根目录，从 HBC 启动 |
| WODE | `WODE/swiss-zh(wode_extcfg).iso` | 按 WODE extcfg 流程加载 |
| 记忆卡 | `MemoryCard/boot.gci` / `xeno.gci` | 用 GCMM 等工具写入 GC 记忆卡 |

各文件的细节、刷写风险与真机验证状态见
[`docs/启动方式文件说明.md`](docs/启动方式文件说明.md)。重新打包用
`python tools/build_boot_variants.py`（26 项自检，纯 Python，无需 Wii 工具链）。

### 2. 安装游戏内复位

解压 `igr/SDCard_IGR.zip`，把里面的 `swiss` 文件夹整个合并到 SD 卡根目录，最终路径必须是：

```
SD:\swiss\patches\apploader.img
```

然后在 Swiss 里：**设置 → 游戏全局 → 游戏内复位 → 选「Apploader」**（配置文件中是 `IGRType=Apploader`）。

| 组合键 | 作用 |
|---|---|
| `A + Z + Start` | 退出游戏，回到中文 Swiss 主界面 |
| `R + Z + Start` | 重启当前游戏 |

> `apploader.img` 必须放在**启动该游戏所用设备**的 `/swiss/patches/` 下。从 SD 卡启动就放 SD 卡；从 SMB/FTP 共享启动，就要放到该共享根目录的同样位置。

### 3. 验证

`SHA256SUMS.txt` 列出所有二进制产物的校验值。关键值：

| 文件 | 大小 | SHA-256（前 16 位） |
|---|---:|---|
| `firmware/swiss.dol` | 1,659,648 B | `45c79728df0b0a02` |
| `firmware/swiss-wiiload.dol` | 4,304,000 B | `1402216e9696045a` |
| `igr/apploader.img` | 1,659,424 B | `4426995cfa1a2207` |
| `gcloader/boot.iso` | 1,746,944 B | `79c59d2c4da6de8c` |
| `ActionReplay/SDLOADER.BIN` | 1,659,392 B | `8bd20ba91f11371d` |
| `WiikeyFusion/swiss-zh.fzn` | 1,900,544 B | `2199c645a682c498` |
| `Wii/EXTRACT_TO_ROOT.zip` | 2,138,123 B | `debb6bb45e6fc793` |

全部 19 项二进制产物的完整校验值见 `SHA256SUMS.txt`。

`apploader.img` 的版本标记为 `*swiss_r2154.dol`，与 SD 卡根目录的 `IPL.dol` 内嵌同一份 `executable.xz`。

## 为什么不能用官方 release 的 apploader.img

`apploader.img` 不是通用补丁。上游 `Makefile: build-ipl` 用 `buildtools/dol2ipl.py` 把 `cube/packer/reboot.dol` 展平成内存镜像（入口 `0x81300000`），前面加 32 字节 `ApploaderHeader`；而 `reboot.dol` 链接了 `executable.xz` —— **本次编译的 Swiss 压缩镜像**。按 `A+Z+Start` 复位后，回到的是这个文件里内嵌的那份 Swiss。

拿官方/release 版的同名文件，内嵌的是另一个 commit、未汉化、内存布局不同的 Swiss。详见 [`docs/IGR-技术说明.md`](docs/IGR-技术说明.md)。

本地构建原先一直缺这个文件，还有两个具体原因，本仓库的 `source/build-config/Makefile` 已修：

1. `build-local.bat dev|inc` 只跑 `compile-patches` + `compile`，从不跑 `compile-packer` / `build-ipl`；
2. MSYS2 里没有 `python3`，而 Makefile 原先直接执行 `dol2ipl.py`（shebang 找 `python3`），必然失败。现改为 `PYTHON ?= python3` + `$(PYTHON) …`，并新增精简目标 `apploader`。

## 从源码复现

需要 devkitPro / libogc2（PowerPC 交叉工具链）、MSYS2、7z、Python 3；生成 ISO 另需
`mkisofs`（cdrtools）或 `xorrisofs`（xorriso）。

```bash
# 1) 准备上游源码，并让环境变量指向它
export SWISS_GC_REPO=/path/to/swiss-gc
export SWISS_GC_WORKSPACE=/path/to/workspace       # source/tools/* 的默认基准目录
export DEVKITPPC=/opt/devkitpro/devkitPPC
export MSYS_BASH=/c/msys64/usr/bin/bash.exe

# 2) 应用中文翻译与字模（source/tools/ 下）
py -3 source/tools/apply_translations.py source/translations/*.tsv
py -3 source/tools/gen_font.py --from-source --gb2312-full --big5-common \
    --extra-chars docs/GameCube_中文译名表.md \
    --font "C:/Windows/Fonts/Noto Sans SC Medium (TrueType).otf"
py -3 source/tools/preflight.py

# 3) 编译固件
bash "$SWISS_GC_REPO/build-local.sh" inc

# 4) 【关键】每次编译后重新生成 apploader.img，并做 12 项逐级字节校验
py -3 tools/build_apploader.py --build --repo "$SWISS_GC_REPO"

# 5) 生成 GCLoader / 区域 ISO（需要 mkisofs 或 xorrisofs，附带 20 项自检）
py -3 tools/build_gcloader_iso.py --all

# 6) 生成各启动方式专用文件（Action Replay / FlippyDrive / Wiikey Fusion /
#    Wii / WODE / 记忆卡），26 项自检，纯 Python + 仓库内的引导资产
py -3 tools/build_boot_variants.py
py -3 tools/build_boot_variants.py --verify-only

# 7) 可选：推送到实机并回读比对（需宽带网卡）
py -3 tools/build_apploader.py --upload 192.168.1.2
py -3 tools/wiiload.py 192.168.1.2 firmware/swiss-wiiload.dol
```

`tools/build_apploader.py` 会逐级比对 `swiss.elf → executable.bin → executable.xz → reboot.dol → apploader.img`，并校验 header 的 `entry` / `size` / `rebootSize` / `CRC32` / `date`，全部通过才产出离线包。

**每次重新编译 Swiss 都必须重跑第 4 步。**

## 中文文件名与游戏名中文化

本构建的 FatFs 已启用 UTF-8 长文件名，SD 卡上可以直接用中文文件名。若想把自己的游戏库批量改成中文名，用 `tools/rename_games_cn.py`：

```bash
py -3 tools/rename_games_cn.py --dry-run              # 只校验映射
py -3 tools/rename_games_cn.py --apply --recent       # 执行并同步 recent.ini
py -3 tools/rename_games_cn.py --verify               # 复核
py -3 tools/rename_games_cn.py --rollback             # 一键还原
```

⚠️ Swiss 文件浏览器会持有**当前目录**内所有文件的 FatFs 句柄，导致该目录里任何 `/rename` 返回 `FR_LOCKED(16)`。执行前必须先把 `recent.ini` 的 `Recent_0` 临时指向别的目录并重启 Swiss，让它停在别的目录。完整步骤见 [`docs/游戏名中文化.md`](docs/游戏名中文化.md)。

`docs/GameCube_中文译名表.md` 是一次实机批量改名的 56 条对照记录，`docs/screen-cn.png` 是改名后的实机画面。

### 中文字库覆盖（2026-11-10 两次扩库）

曾收到实机反馈：`忍者神龟3：变异噩梦` 里「噩」显示为空，看起来像 `变异 梦`。
根因不是渲染：旧字库只收 **GB2312 一级 3755 字 + 界面译文用字**（共 3771 字），
而游戏文件名是固件编译之后才由用户改的，「噩 / 飙 / 鑫」这类**二级字**没进字库；
查不到字形时旧代码直接跳过绘制、字宽照算，于是留下一个字宽的空白。

r5 起扩到 **7002 字**（GB2312 全量 6763 ∪ 源码用字 ∪ 译名表 ∪ 异体字 ∪ 数字 ∪ `□`），
查不到的码位统一画 `□`，不再静默留白；图集 14 页 / 896 KB。

**r8 补齐繁体 / 日文常用字**：又收到「斑鸠」的「鸠」不显示的报告。从发布固件二进制
逐字节复核，简体「鸠」U+9E20（GB2312 二级字）在 r5~r7 里码位与位图都完好——
实际是日版原名「斑**鳩**」的「鳩」U+9CE9 不在 GB2312，或反馈者仍在跑 r1~r4 的旧字库。
顺带查出 `EXTRA_VARIANTS` 手工枚举有系统性漏字：Big5 常用区 5401 字里 1885 个未收录
（鳩、無、雙、實、戰、歐、鋼、賽…）。

r8 起生产命令加 `--big5-common`，字库共 **8887 字**：GB2312 全量 6763 ∪ Big5 常用区
5401 ∪ 源码用字 ∪ 译名表 ∪ 手工异体表 ∪ ASCII 0-9 ∪ `□`。两个字符集均 **0 缺失**，
图集 **18 页 / 1152 KB** 常驻（比 r7 +256 KB，DOL +29,984 B）。仍不在库内的码位画 `□`。

**混排数字在 r9 改成与汉字同高**（2026-11-11）：r5~r8 用的是 Unifont 原字形，数字只占
10 行高 / 6 列宽，汉字却是 15 行 / 13 列，看起来小一圈。r9 起 `gen_font.py` 用
`fullsize_digit_bitmaps()` 在同一张 16×16 网格里重绘十个数字：**14 行高、9 列宽、
1px 笔画**，与汉字同网格、同基线；`IPLFontWrite.c` 的字距从 10 调到 12、quad 不再左移，
让数字与汉字中心对齐。直接放大 Unifont 位图会把笔画复制成 2px，骨架细化又会削断
`0` / `7`，所以改用 1px 线段路径重绘；运行时仍是 1:1 纹理映射，**没有 GX 运行时缩放**。
纯英文/数字行（时钟、commit、revision、启动信息）仍用原版 IPL 字体，不受影响。

**r10 换成矢量字体灰度反锯齿**（2026-11-12）：把参考截图放大比对后确认，那种观感来自
**矢量字体在 16px 下做灰度抗锯齿**，而不是更精细的点阵。r10 因此把字库存储从 1bpp 换成
**4bpp 灰度**（每字 128 字节，布局就是 GX I4 的 tiling，运行时直接 memcpy 进图集，
不再逐像素展开），字体源换成 **Noto Sans SC**（SIL OFL，可随包分发）：汉字 Medium 16px
（墨迹正好满格 16×16），拉丁与数字用 Bold 18px（笔画 2px，与汉字等重），
中文/英文/数字**同源、同基线**，数字按字体原生比例宽度排版（新增 `cjkfont_advance[]` 字宽表）。
字符集 8887 → **8972 字**（十个自绘数字换成可打印 ASCII 0x20–0x7E），图集仍 18 页 / 1152 KB，
`cjkfont_bitmaps` 从 284 KB 涨到 1.15 MB，raw DOL 3.36 → 4.30 MB，自解压 DOL 1.06 → 1.59 MB。

渲染侧配套：纹理采样 `GX_NEAR` → `GX_LINEAR`（1:1 时仍落在像素中心不软化，小字缩放才插值）；
删掉 `LATIN_FIT 0.85` 与 `ATLAS_DIGIT_*` 这类补丁分支，统一由 `draw_glyph()` 分发；
UI 调用点按旧 26px IPL 字体写死的 `0.45f` / `0.6f` 在 16px 字库下只剩 7px，因此加了
`LATIN_MIN_SCALE 0.75` / `CJK_MIN_SCALE 1.0` 下限，并导出 `GetEffectiveTextScale()`
让手工算宽度的位置（顶栏温度）与真实绘制一致。

调字库时踩到并修掉的四个坑：**数字浮起 2px**（CJK 字形墨迹比数学基线下沉 1px、数字停在
基线以上 1px，按基线对齐恒差 2px；ASCII 裁切窗口 7→5 抵消）；**`g` 被切成 `σ`**
（18px 降部超出 16 行格子，x-height 重采样 10→9 行、降部压 2 行贴底，只留 1 行会被
0.75 缩放插值抹成横线）；**`[` 被裁成 `厂`**（括号整体压进 16 行）；**顶栏每行文字上方的
破碎点点**（quad 落在半像素：`yofs=7`、`cell_height=26`，0.75 缩放下顶边 = -4.5，
`CJK_BASELINE_NUDGE` 2→4 即 `yofs` 7→9 后消失）。ISO 生成加 `-no-pad`，去掉 mkisofs
默认的 150 扇区（300 KB）尾部填充——否则 1.59 MB 的 DOL 会顶破 Wiikey Fusion 的 1856 KB 上限。

发布前自查 / 自行扩字：

```bash
py -3 source/tools/check_glyphs.py --extra docs/GameCube_中文译名表.md
py -3 source/tools/gen_font.py --from-source --gb2312-full --big5-common \
    --extra-chars docs/GameCube_中文译名表.md \
    --font "C:/Windows/Fonts/Noto Sans SC Medium (TrueType).otf"
```

常用繁体/日文字由 `--big5-common` 覆盖，拉丁与数字随可打印 ASCII 段自动带入；
字体可换成本机任意 Unicode CJK 字体（`--font`），生僻字仍可加进 `gen_font.py` 的
`EXTRA_VARIANTS` 或用 `--extra-chars` 传入。重新生成 `cjkfont.c/.h` 后编译即可：
**记得同时重跑 `build_apploader.py`**，固件与 IGR 镜像必须同次构建；
固件一变，ISO 与全部启动方式文件也要用 `build_boot_variants.py` 重新生成。

## 背景图切换（设置 → 界面设置 2/6 → 背景图）

本构建在设置里加了背景选择，不再只能替换单个文件：

| 取值 | 行为 |
|---|---|
| 关闭（0） | 用 Swiss 内置背景，不必删文件 |
| 1 ~ 9 | 读取 `swiss/backdropN.tpl`；选 1 且该文件不存在时，自动回退旧名 `swiss/backdrop.tpl` |

- 左右键切换**立即生效**，无需重启；值保存在 `global.ini` 的 `BackdropIndex`
- 文件缺失或解析失败会立刻回退内置背景，不会黑屏
- 每次切换会先 `TPL_CloseTPLFile()` 释放上一张贴图（libogc2 里只有它会 `free` 纹理数据），反复切换不漏内存

配套的背景图制作工具见同作者的 [swiss-gc-Imager](https://github.com/hualazimo7/swiss-gc-Imager)（`SwissBackdrop.exe`），生成的文件改名成 `backdrop1.tpl` / `backdrop2.tpl` 即可。截图：[`docs/screenshots/07-backdrop.png`](docs/screenshots/07-backdrop.png)。

## 实机验证状态

- 中文界面、设置项显示层汉化（配置文件仍写英文值，不破坏 `swiss.ini`）、顶部温度与日期同行显示
- 中文文件名、自定义背景、SD 卡启动游戏、冷启动
- **背景图切换已实机通过**（2026-11-09）：开机按 `BackdropIndex` 加载、设置页内左右键即时换图、缺文件回退内置背景、连续切换 14 次无异常
- **`A + Z + Start` 复位已真机通过**（2026-11-09）：回到中文 Swiss 主界面，无机器重启；`R + Z + Start` 沿用同一逻辑，未单独按键复测
- `apploader.img` 写入 SD 卡后 `/get` 回读与本地逐字节一致
- ✅ **GCLoader `boot.iso` 已真机通过**（2026-11-10 用户实机反馈，当时为 r7 固件）：
  放 GCLoader SD 卡根目录即可启动中文 Swiss。20 项自检通过、与官方 r2119 镜像结构对齐
  （光盘头、catalog/DOL LBA、platform ID 与校验和）；Dolphin 加载官方盘同样黑屏，
  属模拟器不支持该 El Torito 启动路径，不作为判断依据。
  **r8 ~ r10 换了固件但 ISO 结构与生成方式未变**（r10 起去掉尾部填充，体积更小），仍建议 GCLoader 用户重测一次当前版 `boot.iso`
- **r10 的字体效果已实机验证**（2026-11-12）：中英混排、中文游戏名、全角括号与方括号、
  列表省略号、顶栏 `commit` / `revision`、容量数字全部正常；繁体「斑鳩雙實無測試」逐字可读；
  `/overflow` 无溢出记录。改前改后对比见 Release 说明
- **Action Replay / FlippyDrive / Wiikey Fusion / Wii / WODE / 记忆卡尚未实机验证**：
  各产物与上游 r2119 发布包结构逐项对齐，Wii 的 DOL 段注入与两个 GCI 另与上游
  `dol2ipl.py` / `dol2gci.exe` 输出逐字节一致；等待各设备用户反馈

## 目录

```
firmware/    正式 DOL（自解压版 + wiiload 版）与安装说明
gcloader/    GCLoader 用的 boot.iso + 使用说明
iso/         NTSC-U / NTSC-J / PAL 三个区域镜像
ActionReplay/  AUTOEXEC.DOL + SDLOADER.BIN
FlippyDrive/   EXTRACT_TO_ROOT.zip（boot.dol）
WiikeyFusion/  .fzn / .fzn.fw / RecoveryISO/
Wii/           EXTRACT_TO_ROOT.zip（apps/swiss-gc/）
WODE/          wode_extcfg ISO
MemoryCard/    boot.gci / xeno.gci
igr/         apploader.img、离线 SD 卡包、中文安装说明
Licenses/    上游第三方依赖许可文本
source/      translations/*.tsv、fonts/unifont.hex、tools/、build-config/
tools/       build_apploader.py / build_gcloader_iso.py / build_boot_variants.py /
             upload_file.py / wiiload.py / swiss_client.py /
             rename_games_cn.py / publish_release.py
tools/iso/   上游 eltorito-*.hdr（生成可引导 ISO 用）
tools/boot/  各启动方式的引导资产与来源说明
docs/        IGR 原理、各启动方式说明、汉化实现、游戏名中文化、译名表、
             实机截图、RELEASE_POLICY.md（发布规则）
```

## 附：为什么版本号是 2154，官方却是 2119

Swiss 的 `revision` **不是 SVN 号**，而是 `git rev-list HEAD | wc -l`，即**当前 commit 的提交总数**。数字来自构建脚本本身：

- `cube/swiss/Makefile`：`-D'GIT_REVISION="$(shell git rev-list HEAD | wc -l)"'`
- 顶层 `Makefile`：`SVN_REVISION = swiss_r$(REVISION)`（变量名里的 `SVN_` 是历史遗留）

对照表：

| 版本 | commit | 日期 | `git rev-list` 计数 |
|---|---|---|---:|
| 官方最新发布 **v0.6r2119** | `163f8b1d` | 2026-09-24 | 2119（tag 名里的数字就等于当时的计数） |
| **本构建的基线** | **`62a8b9a2`** | **2026-11-05** | **2154** |

也就是说：**2119 是官方最后一个打过 tag 的发布版，2154 是它之后第 35 个提交的 master 快照**。两者不是同一类东西——一个是发布号，一个是提交计数；本构建比官方发布**新 35 个提交**，功能上只多不少。

上游在 2026-11-08 的提交 `Get Swiss version from last Git tag.` 里给界面加了取自 `git describe --tags` 的 `GIT_VERSION`（形如 `0.6`），但 `revision` 仍然用提交计数，所以这个差异会长期存在。

⚠️ **自己从源码构建时，这个数字会变**：它取决于你本地仓库的提交数。如果你 `git fetch` 到了更新的上游提交，或者在自己的 fork 上又提交了汉化改动，编出来的 `revision` 就不再是 2154——这时 `apploader.img` 的版本标记（`*swiss_r<数字>.dol`）也会跟着变，属于正常现象，只要**固件与 `apploader.img` 出自同一次构建**即可。

## 许可与致谢

> ⚠️ 本仓库**原创内容禁止商业使用**；上游 GPL-2.0 材料不受此限制。完整条款见
> [`LICENSE`](LICENSE)，范围界定与商用示例见 [`NOTICE.md`](NOTICE.md)。

- **本项目原创贡献**（翻译表、构建/校验工具、文档、离线包中文材料、截图）：《非商业使用许可 v1.0》，**禁止商用**
- **上游 Swiss**：[emukidid/swiss-gc](https://github.com/emukidid/swiss-gc)，GPL-2.0，全文见 [`LICENSE-GPL-2.0.txt`](LICENSE-GPL-2.0.txt)，版本信息见 [`UPSTREAM.txt`](UPSTREAM.txt)。`firmware/*.dol` 与 `igr/apploader.img` 为该许可下的衍生作品，可依 GPL-2.0 使用（含商业使用）
- **字体**：[GNU Unifont](https://unifoundry.com/unifont/)，GPL-2.0+ 及字体例外
- 配套 PC 工具：[swiss-gc-Imager](https://github.com/hualazimo7/swiss-gc-Imager)（背景图）、[swiss-gc-ftp](https://github.com/hualazimo7/swiss-gc-ftp)（文件传输）
