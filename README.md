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
| `firmware/swiss.dol` | **自解压正式版**，放 SD 卡 / PicoBoot / GCLoader 等使用 |
| `firmware/swiss-wiiload.dol` | 原始构建，**仅**用于 wiiload 网络推送到已在运行的 Swiss |
| `igr/apploader.img` | 与上述固件同一份源码产出的 IGR 复位镜像 |
| `igr/SDCard_IGR/` + `.zip` | 给无网卡用户的离线包，解压到 SD 卡根目录即可 |
| `source/` | 复现汉化所需的翻译表、字模源文件与构建/校验脚本 |
| `tools/` | 可直接使用的构建校验、上传、wiiload、游戏改名工具 |
| `docs/` | IGR 原理、汉化实现、游戏名中文化的技术记录 |

## 快速开始

### 1. 安装固件

把 `firmware/swiss.dol` 复制到 SD 卡根目录：

- **PicoBoot / gekkoboot**：按你的配置改名为 `ipl.dol`（或 `IPL.dol`）
- **CubiBoot / 光驱替代设备**：在菜单里直接选它
- 升级前建议把旧 DOL 改名留一份备份

⚠️ **不要**把 `swiss-wiiload.dol` 放进 SD 卡启动。原始构建链接在 `0x80003100`，会覆盖 IPL 加载器自身，表现为选完文件立刻黑屏。

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
| `firmware/swiss.dol` | 1,028,608 B | `7351321f673f3836` |
| `firmware/swiss-wiiload.dol` | 3,247,008 B | `07abaa443cfd8b38` |
| `igr/apploader.img` | 1,028,384 B | `54ddd42f11fa637d` |

`apploader.img` 的版本标记为 `*swiss_r2154.dol`，与 SD 卡根目录的 `IPL.dol` 内嵌同一份 `executable.xz`。

## 为什么不能用官方 release 的 apploader.img

`apploader.img` 不是通用补丁。上游 `Makefile: build-ipl` 用 `buildtools/dol2ipl.py` 把 `cube/packer/reboot.dol` 展平成内存镜像（入口 `0x81300000`），前面加 32 字节 `ApploaderHeader`；而 `reboot.dol` 链接了 `executable.xz` —— **本次编译的 Swiss 压缩镜像**。按 `A+Z+Start` 复位后，回到的是这个文件里内嵌的那份 Swiss。

拿官方/release 版的同名文件，内嵌的是另一个 commit、未汉化、内存布局不同的 Swiss。详见 [`docs/IGR-技术说明.md`](docs/IGR-技术说明.md)。

本地构建原先一直缺这个文件，还有两个具体原因，本仓库的 `source/build-config/Makefile` 已修：

1. `build-local.bat dev|inc` 只跑 `compile-patches` + `compile`，从不跑 `compile-packer` / `build-ipl`；
2. MSYS2 里没有 `python3`，而 Makefile 原先直接执行 `dol2ipl.py`（shebang 找 `python3`），必然失败。现改为 `PYTHON ?= python3` + `$(PYTHON) …`，并新增精简目标 `apploader`。

## 从源码复现

需要 devkitPro / libogc2（PowerPC 交叉工具链）、MSYS2、7z、Python 3。

```bash
# 1) 准备上游源码，并让环境变量指向它
export SWISS_GC_REPO=/path/to/swiss-gc
export SWISS_GC_WORKSPACE=/path/to/workspace       # source/tools/* 的默认基准目录
export DEVKITPPC=/opt/devkitpro/devkitPPC
export MSYS_BASH=/c/msys64/usr/bin/bash.exe

# 2) 应用中文翻译与字模（source/tools/ 下）
py -3 source/tools/apply_translations.py source/translations/*.tsv
py -3 source/tools/gen_font.py
py -3 source/tools/preflight.py

# 3) 编译固件
bash "$SWISS_GC_REPO/build-local.sh" inc

# 4) 【关键】每次编译后重新生成 apploader.img，并做 12 项逐级字节校验
py -3 tools/build_apploader.py --build --repo "$SWISS_GC_REPO"

# 5) 可选：推送到实机并回读比对（需宽带网卡）
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

## 目录

```
firmware/    正式 DOL（自解压版 + wiiload 版）与安装说明
igr/         apploader.img、离线 SD 卡包、中文安装说明
source/      translations/*.tsv、fonts/unifont.hex、tools/、build-config/
tools/       build_apploader.py / upload_file.py / wiiload.py / swiss_client.py
             rename_games_cn.py
docs/        IGR 原理、汉化实现、游戏名中文化、译名表、实机截图
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

## 许可与致谢

> ⚠️ 本仓库**原创内容禁止商业使用**；上游 GPL-2.0 材料不受此限制。完整条款见
> [`LICENSE`](LICENSE)，范围界定与商用示例见 [`NOTICE.md`](NOTICE.md)。

- **本项目原创贡献**（翻译表、构建/校验工具、文档、离线包中文材料、截图）：《非商业使用许可 v1.0》，**禁止商用**
- **上游 Swiss**：[emukidid/swiss-gc](https://github.com/emukidid/swiss-gc)，GPL-2.0，全文见 [`LICENSE-GPL-2.0.txt`](LICENSE-GPL-2.0.txt)，版本信息见 [`UPSTREAM.txt`](UPSTREAM.txt)。`firmware/*.dol` 与 `igr/apploader.img` 为该许可下的衍生作品，可依 GPL-2.0 使用（含商业使用）
- **字体**：[GNU Unifont](https://unifoundry.com/unifont/)，GPL-2.0+ 及字体例外
- 配套 PC 工具：[swiss-gc-Imager](https://github.com/hualazimo7/swiss-gc-Imager)（背景图）、[swiss-gc-ftp](https://github.com/hualazimo7/swiss-gc-ftp)（文件传输）
