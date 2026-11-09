# 游戏内复位（IGR / Apploader）技术说明

> 本文摘自本项目的开发记录，保留当时的分析过程与结论。
> 文中出现的工作区路径（`tools/`、`dist/`、`D:/…`）是开发时的目录，
> 在本仓库中的对应位置请以根目录 README 的目录表为准。

### 游戏内复位（IGR / Apploader）：`swiss/patches/apploader.img`

Swiss 的「游戏内复位」有 Reboot 与 Apploader 两种。选 Apploader 后，Swiss 会把
`<启动设备>:/swiss/patches/apploader.img` 当作游戏的 apploader 注入到 0x2440；
按 `A + Z + Start` 时 `pad.c` 触发 `OSResetSystem(OS_RESET_RESTART)`，由这份镜像
把 Swiss 重新拉起来（`R + Z + Start` 则是重启当前游戏）。

**这个文件不是通用补丁，更不能拿官方 release 里的同名文件。**
`Makefile: build-ipl` 用 `buildtools/dol2ipl.py` 把 `cube/packer/reboot.dol`
展平成内存镜像（入口 0x81300000 / 加载 0x01300000），前面加 32 字节
`ApploaderHeader`（date / entry / size / rebootSize / CRC32）。而 `reboot.dol`
链接了 `executable.xz` —— **本次编译的瑞士军刀本体（汉化 Swiss）的压缩镜像**。
所以按组合键回到的是「文件里内嵌的那份 Swiss」：用开源版 `apploader.img`
就是另一 commit、未汉化、内存布局不同的 Swiss，在 PicoLoader 直载 `IPL.dol`
的环境里表现为黑屏 / 反复重启 / 回到英文原版。

本地一直缺这个文件，有两个具体原因：

1. `build-local.bat dev` / `inc` 只跑 `compile-patches` + `compile`，从不跑
   `compile-packer` 与 `build-ipl`；
2. 就算跑 `make all`，MSYS2 里**没有 python3**，而 Makefile 原先直接执行
   `buildtools/dol2ipl.py`（shebang `#!/usr/bin/env python3`）→
   `/usr/bin/env: 'python3': No such file or directory`。

已修：`Makefile` 新增 `PYTHON ?= python3`，`DOL2IPL` 改为 `$(PYTHON) …`，
并新增精简目标 `apploader`（`compile-packer` + 生成镜像，不依赖 boot.iso 等）；
`build-local.sh` 自动探测 Windows Python 并 `export PYTHON`。
`build-ipl` 里 `*$(SVN_REVISION).dol` 也加了引号，避免 shell 意外展开。

```bash
# 一键：重编 packer + 生成镜像 + 12 项校验 + 产出 SD 卡离线包
cd <本地化工作区>
python tools/build_apploader.py --build

# 顺带推送到实机 SD 卡并回读比对（需网卡）
python tools/build_apploader.py --upload 192.168.1.2

# 或只要构建产物
<swiss-gc 源码>/build-local.bat apploader
```

产物：

| 路径 | 说明 |
|---|---|
| `dist/Apploader/swiss/patches/apploader.img` | 1,027,200 B（32 B 头 + 1,027,168 B 镜像） |
| `dist/SDCard_IGR/swiss/patches/apploader.img` | 离线包，整个 `swiss` 文件夹合并到 SD 卡根目录即可 |
| `dist/SDCard_IGR/【必读】游戏内复位-安装说明.txt` | 给没有网卡的用户 |
| `dist/SDCard_IGR/SHA256SUMS.txt` | 校验值 |
| `dist/SDCard_IGR.zip` | 同样的内容打包，解压到 SD 卡根目录即为 `swiss/patches/apploader.img` |

校验链 12/12 通过：`swiss.elf` →（objcopy）→ `executable.bin` →（7z）→
`executable.xz` →（链接）→ `reboot.dol` →（dol2ipl）→ `apploader.img`，
逐级字节比对；另外校验 header 的 `entry=0 / size=0 / rebootSize / CRC32`、
date 以 `*` 开头（决定 `patcher.c` 走 0x81300000 地址分支），以及
`reboot.dol` 不早于 `swiss.elf`。

2026-11-08 实机部署结果：文件已写入 `sdb:/swiss/patches/apploader.img`
（SHA `d55d5a7d…`，`/get` 回读逐字节一致），`global.ini` 里
`IGRType=Apploader` 本来就已启用。进一步验证 SD 卡根目录的 `IPL.dol`
与本地 `cube/packer/swiss.dol` 完全相同（SHA `0cb38542…`），且两者与
`apploader.img` 都内嵌同一份 `executable.xz` —— 复位目标就是当前这份汉化 Swiss。
**2026-11-09 真机复测已通过**：用户启动 SD 卡游戏后按 `A + Z + Start`，
复位功能正常，回到中文 Swiss 主界面，没有出现机器重启。开机后远程复核：
`192.168.1.2/state` 正常返回中文设备名与 65 项列表，`/screen.bin` 抓屏确认
顶部 `40°C` 与日期同行、`commit 62a8b9a2 / revision 2154`、背景图正常；
SD 卡 `apploader.img` 回读仍为 1,027,200 B、SHA `d55d5a7d…`，与本地逐字节一致。
`R + Z + Start`（重启当前游戏）沿用同一套 `CheckStatus` 逻辑，未单独按键复测。

> 注意：`deviceHandler-FAT.c` 用的是 `DEVICE_CUR`，即 apploader.img 必须放在
> **启动该游戏所用设备**的 `/swiss/patches/` 下；从 SMB/FTP 共享启动游戏，
> 就要放到该共享根目录的同样位置。每次重新编译 Swiss 都要重新生成此文件。
