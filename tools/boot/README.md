# `tools/boot/` 构建资产说明

这里放的是 `tools/build_boot_variants.py` 的**输入**，供离线重建各启动方式的专用文件用，
不是给最终用户直接拷贝到 SD 卡的成品。成品在各设备目录下。

| 文件 | 来源 | 说明 |
|---|---|---|
| `SDLOADER.BIN` | `cube/packer/SDLOADER.BIN` | Action Replay 用的 SD 加载器，由 packer 与固件同批编译，内嵌本次构建的 `executable.xz` |
| `reboot.dol` | `cube/packer/reboot.dol` | 链接在 `0x01300000` 的重启版 Swiss，Wii booter / IGR `apploader.img` 都用它的内存镜像 |
| `wii_booter.dol` | `wii/booter/boot.dol` | 用 libogc2 `wii_rules` 编译出的 Wii 模式启动器本体（**未**内嵌 DOL），源码在 `wii/booter/` |
| `autoboot.fzn.fw` | `buildtools/wkf/autoboot.fzn.fw` | Wiikey Fusion / WASP Fusion 的 v1.0 autoboot 固件恢复文件，12 KiB |
| `recovery_bootloader.iso` | `buildtools/wkf/recovery_bootloader.iso` | 恢复盘引导头，取前 32 KiB 覆盖 PAL ISO 的头部 |
| `dol2gci.cpp` | `buildtools/dol2gci.cpp` | 上游 GCI 打包工具源码；脚本从中解析 `dol_icon[]`，纯 Python 复刻出逐字节相同的 GCI |

以上都来自上游 `emukidid/swiss-gc` 的 GPL-2.0 源码或由它编译产生，
依 GPL-2.0 随本仓库分发；本仓库原创的脚本/文档另见根目录 `LICENSE` / `NOTICE.md`。

## 重新生成这些资产

升级固件（重编 `cube/swiss`）后，`SDLOADER.BIN` 与 `reboot.dol` **必须同步更新**，
否则 Action Replay / Wii 包里会装进旧版 Swiss。`tools/build_boot_variants.py`
会从三个文件里各自提取内嵌的 xz 流并比对 SHA-256，不一致就直接拒绝生成。

在 MSYS2 + devkitPPC + libogc2 环境下（仓库路径需为纯 ASCII）：

```bash
export SWISS_GC_REPO=/path/to/swiss-gc
export MSYSTEM=MSYS
export DEVKITPRO=/opt/devkitpro
export DEVKITPPC=/opt/devkitpro/devkitPPC
export PATH="$DEVKITPPC/bin:$DEVKITPRO/tools/bin:/usr/bin:$PATH"

cd "$SWISS_GC_REPO"
make -C cube/packer                 # 产出 SDLOADER.BIN / reboot.dol / swiss.dol
make -C wii/booter                  # 产出 wii_booter.dol（纯启动器，不含 DOL 段）
```

然后把 `cube/packer/SDLOADER.BIN`、`cube/packer/reboot.dol`、`wii/booter/boot.dol`
复制到本目录（后者改名 `wii_booter.dol`），`cube/packer/swiss.dol` 复制到
`firmware/swiss.dol`。`wii_booter.dol` 与固件版本无关，通常无需重编。

## 实现与上游的对应关系

| 上游 Makefile 目标 | 本仓库实现 |
|---|---|
| `build-AR` | `ActionReplay/AUTOEXEC.DOL` 改名 + 本目录 `SDLOADER.BIN` |
| `build` → FlippyDrive `boot.dol` | `FlippyDrive/EXTRACT_TO_ROOT.zip` |
| `build` → WKF ISO + `truncate -s 1856K` | `WiikeyFusion/swiss-zh.fzn` |
| `recovery-iso` → `dd bs=32K count=1 conv=notrunc` | `WiikeyFusion/RecoveryISO/swiss-zh_Recovery.iso` |
| `build-wii` → `dol2ipl boot.dol reboot.dol` | `Wii/EXTRACT_TO_ROOT.zip` 里的 `apps/swiss-gc/boot.dol` |
| `build` → WODE ISO | `WODE/swiss-zh(wode_extcfg).iso` |
| `build-gci` → `dol2gci` | `MemoryCard/boot.gci` / `xeno.gci` |

Wii 的 DOL 段注入与 GCI 组装都已在脚本内用纯 Python 复刻，并与上游
`dol2ipl.py` / `dol2gci.exe` 的输出做过逐字节比对，结果完全一致。
