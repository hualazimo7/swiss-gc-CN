# 变更说明

基线：上游 [swiss-gc](https://github.com/emukidid/swiss-gc) **master commit `62a8b9a2`**（2026-11-05，界面 revision 2154；官方最新发布 tag 为 `v0.6r2119`，本基线比它新 35 个提交）。
本文件记录汉化版相对该基线的全部改动。

规模：**27 个文件，+1456 / −730 行**（不含自动生成的 `cjkfont.c/h`）。

---

## 1. 中文渲染

### 1.1 UTF-8 文本通路

原有 `drawString` 系列按单字节处理字符串。改为逐码点解码（`utf8text.h`），
ASCII 走 IPL 字体、`>0xFF` 走中文图集，两者共用同一基线。

顺带修掉一个回归：IPL 字体实际覆盖 `0x20–0xFF`，而原判断按 `cp < 0x80` 分流，
导致 `nkit.c` 里 Latin-1 原始字节（`"Pok\xe9mon"`）被当成中文去查图集，
查不到就整字不画。现在条件为 `cp <= 0xFF`，且遇到 `U+FFFD` 回退用原始字节。

### 1.2 16×16 点阵图集

- 字模：r9 及以前 `fonts/unifont.hex` → 16×16 1bpp、每字 32 字节；**r10 起改为 Noto Sans SC 16px 灰度渲染，4bpp、每字 128 字节**（见第 14 节）
- 字符集：**GB2312 全量 6763 字 ∪ Big5 常用区 5401 字 ∪ 源码用字 ∪ 中文译名表
  ∪ 常见繁/日异体 ∪ ASCII 0-9 ∪ `□` = 8887 字**（r8 起）
  （`gen_font.py --from-source --gb2312-full --big5-common --extra-chars <译名表> --unifont-only`；
  早期版本只有一级 3755 字，游戏名里的「噩」等二级字会静默留白；r5 扩到 7002 字；
  r8 再补 Big5 常用区 1885 个繁体字，详见第 12 节）
- 混排数字：含中文的字符串里 `0-9` 也从这张图集取字形。**r9 起**由
  `fullsize_digit_bitmaps()` 按 1px 线段路径重绘为 **14 行高 / 9 列宽**，
  与汉字同高、同基线、同笔画粗细，字距 12（汉字 17）、quad 不左移以对齐中心；
  纯拉丁行仍用 IPL 字体。r5~r8 用的是 Unifont 原字形（10 行高 / 半角 10px），
  明显比汉字小，详见第 13 节
- 图集：**18 页 × 512×256 I4（64KB/页），512 字/页 = 1152 KB**，运行时按字绑页
  （早期依次为 8 页 / 512 KB、14 页 / 896 KB）
- 兜底：字库固定收录 `□`（U+25A1），查不到的码位画 `□` 而非留空
- 常量：`CJKFONT_DRAW = CJKFONT_CELL = 16`，1:1 像素映射

为什么不放大到 18px：GX_NEAR 在非整数缩放下会丢掉或重复整行整列，
「总」「可」「适」这类字会直接读不出来。要更大必须换 24px 字形源。

### 1.3 小字号钳制

```
#define CJK_MIN_SCALE ((float)CJKFONT_CELL / (float)CJKFONT_DRAW)   // = 1.0
```

含中文的字符串不低于此缩放；拉丁不受影响。代价是设置页里中文标签比英文取值略大，
但小于 1.0 的中文会糊成一片，这个取舍是必要的。

### 1.4 修掉的三个渲染 bug

| 现象 | 成因 | 修法 |
|---|---|---|
| 汉字周围一圈「点点」 | 绘制尺寸 18px 也用作了纹理坐标，越过 16 纹素的格子采到隔壁字形 | 位置用 `CJKFONT_DRAW`、纹理用 `CJKFONT_CELL` |
| 每个中文串的**第一个字**变成斜线团（「全」读作 `%`） | 图集绑定有「同页跳过」缓存，但面板/图标也写 `TEXMAP0`，缓存不知情 → 用错纹理采样 | CJK 绘制无条件 `GX_LoadTexObj` |
| 大图集后半部分字形空白/半字 | 单个 1024×1024 I4（512KB）纹理硬件只可靠采样前约 440 行 | 改 512×256 分页 |

定位方法记在 `docs/FONT_PLAN.md` 第 15 节：回读图集只能证明数据对，
要证明画得对必须把**屏幕像素反向搜图集**。

---

## 2. 中文文件名

```c
// fatfs/ffconf.h
#define FF_LFN_UNICODE  4   ->   2
```

原值是 ISO-8859-1，FatFs 把 UTF-16 长文件名转码时超出范围的字符直接变 `?`，
中文名根本到不了显示层。改为 UTF-8 后往返一致。

已实机验证 `中文测试.dol` / `中文游戏.iso` / `塞尔达传说.gcm` 三种扩展名正常显示。

---

## 3. 界面文本

- 全部界面字符串、提示、错误消息中文化（源码级审计：界面层已无英文残留）
- 设置页 **49 条帮助说明**全部翻译，并按中文行长重排换行
- 屏幕键盘：`Space` → `空格`，`(Y) Back` → `(Y)退格`
- 保留英文的三类：配置取值（`swiss.ini` 读写依赖）、硬件/协议名、诊断端点输出

翻译用映射表 + 批量替换（`translations/*.tsv` + `apply_translations.py`），
不直接手改 C 源码，便于复用与复核。

---

## 4. 诊断端点（`httpd.c`，端口 80）

在原有两个端点（`/dvd.iso`、`/ipl.bin`）之外新增：

| 端点 | 用途 |
|---|---|
| `GET /screen.bin` | 抓当前帧（YUY2 原始数据，PC 端解码为 BMP） |
| `POST /upload?name=<utf8>` | 写文件到 SD，支持中文名 |
| `GET /ls?path=` / `GET /rm?path=` | 列目录 / 删除 |
| `GET /pad?b=&ms=&repeat=&gap=` | 远程按键注入 |
| `GET /atlas.bin` | 回读 CJK 图集（校验字形） |
| `GET /glyph?cp=` | 查字形索引 |
| `GET /fontwidths` | 导出 IPL 字体每个字符的 advance（行宽审计用） |
| `GET /overflow` | 列出无法塞进控件的字符串 |

按键注入按**时间**计时而非帧数：UI 里有 `while(padsButtonsHeld() & BUTTON_A)`
这类忙等，帧计数会被瞬间耗尽。

> 这些端点是为汉化联调加的，正式使用不需要它们，也不会影响正常功能；
> 不希望暴露时把 `httpd.c` 里对应分支删掉重编即可。

---

## 5. 健壮性

- **wiiload 接收超时 10 秒**：`wiiload_handler` 会 `LWP_SuspendThread(main_thread)`
  再读数据，之前没有超时——PC 端中断传输会让主机永久挂起（画面冻结、ping 不通，
  只能断电）。实测遇到过两次，现改为超时后正常恢复
- `tools/wiiload.py` 发送前先探测端口，失败时给出「断电重启」提示而非 traceback

---

## 6. 构建与校验

- 构建：`build-local.sh dev`（全量，约 40s）/ `inc`（增量，约 6s）
- 单元测试：`tests/test_font.c`，**12041 项**（图集往返、字形一致性、分页边界等）
- 构建前预检：缺字检查、配置取值检查、字模同步检查，三项串在 `preflight.py`
- 行宽审计：`audit_widths.py`，209 行帮助说明 0 行超预算（最长 572px / 预算 576px）

---

## 7. 验证状态

| 版本 | 改动 | 实机状态 |
|---|---|---|
| 1 | 字体通路 + 试点译文 | 已验证 |
| 2 | 小字号钳制 + 首轮批量翻译 | 已验证 |
| 3 | 中文文件名 + 分页图集 + 渲染修复 | 已验证 |
| 4（本包） | 诊断端点（`/fontwidths`、`/overflow`）+ wiiload 超时 | **未复验**，界面部分与 3 相同 |

未验证的界面：金手指、MP3 播放器、SMB/FTP 浏览、补丁流程、设置页 4–6 页逐屏。

---

## 8. 发布包格式修正（关键，2026-11-08 追加）

### 现象

把本包的 `swiss.dol` 放到 SD 卡根目录，用 **CubiBoot** 选中后**黑屏**；
同一台机器上官方 `DOL/swiss_r2119.dol` 可以正常启动。

### 原因：发的是错误的产物形态

对比两者的 DOL 头：

| | 官方 r2119 | 本包（修正前） |
|---|---|---|
| 文件大小 | 1,350,216 B | 3,240,608 B |
| 加载地址 | **0x80397940**（高） | **0x80003100**（低） |
| 段数 | 2（14 KB stub + 1.34 MB 载荷） | 2（1.53 MB + 1.66 MB） |
| BSS | 30,752 B | 1,989,600 B |

上游的发布版不是 `cube/swiss/swiss.dol`，而是经 **`cube/packer`** 二次打包的自解压镜像：
一小段 stub 链接在加载器内存**之上**，运行时把 xz 压缩的载荷解压回 `0x80003100`。

原始构建链接在 `0x80003100`，正是 IPL 类加载器（CubiBoot / PicoBoot）自己占用的区间，
加载它会把正在运行的加载器覆盖掉 —— 表现就是选完文件立刻黑屏。
这也是为什么此前所有验证都通过 wiiload 进行（那时 Swiss 已在运行，`DOLtoARAM` 走 ARAM 中转，
不会互相覆盖），**冷启动路径完全没有被覆盖到**。

### 修正

发布流程补上打包步骤（与上游一致）：

```bash
bash build-local.sh dev      # -> cube/swiss/swiss.dol（原始，3.2 MB）
make -C cube/packer          # -> cube/packer/swiss.dol（自解压，1.0 MB）
```

打包需要 7-Zip（`pacman -S p7zip`），它用 `-mf=ppc -mx=9` 生成带 PowerPC BCJ 过滤器的
xz 流；固件里的 `xz_dec_bcj.c` 支持该过滤器。

包内现在提供两个文件：

- `swiss.dol` —— 自解压镜像，SD / ISO / 各类加载器用这个（1,022,240 B）
- `swiss-wiiload.dol` —— 原始构建，仅供 wiiload 推送到运行中的 Swiss

### 顺带修掉的构建问题

`cube/patches` 在 devkitPPC 16.2.0 下用 `-flto=auto` 会偶发丢失被汇编引用的符号
（`service_exception` / `idle_thread` 等），表现为链接失败且每次报错位置不同。
补丁体积只有几 KB，改为 `-fno-lto` 构建即可稳定。

### 校验

打包版结构：stub @0x8031A2A0（13,696 B）+ xz 载荷 @0x8031D820（1,008,288 B），
BSS 30,752 B —— 与官方同构。解压出的载荷中可检索到 `全局设置`、`文件浏览方式`、
`最近：`、`空格` 等本版译文，确认打入的是当前构建。

---

## 8. 发布包格式修正（关键，2026-11-08 追加）

### 现象

把本包的 `swiss.dol` 放到 SD 卡根目录，用 **CubiBoot** 选中后**黑屏**；
同一台机器上官方 `DOL/swiss_r2119.dol` 可以正常启动。

### 原因：发的是错误的产物形态

对比两者的 DOL 头：

| | 官方 r2119 | 本包（修正前） |
|---|---|---|
| 文件大小 | 1,350,216 B | 3,240,608 B |
| 加载地址 | **0x80397940**（高） | **0x80003100**（低） |
| 段数 | 2（14 KB stub + 1.34 MB 载荷） | 2（1.53 MB + 1.66 MB） |
| BSS | 30,752 B | 1,989,600 B |

上游的发布版不是 `cube/swiss/swiss.dol`，而是经 **`cube/packer`** 二次打包的自解压镜像：
一小段 stub 链接在加载器内存**之上**，运行时把 xz 压缩的载荷解压回 `0x80003100`。

原始构建链接在 `0x80003100`，正是 IPL 类加载器（CubiBoot / PicoBoot）自己占用的区间，
加载它会把正在运行的加载器覆盖掉 —— 表现就是选完文件立刻黑屏。
这也是为什么此前所有验证都通过 wiiload 进行（那时 Swiss 已在运行，`DOLtoARAM` 走 ARAM 中转，
不会互相覆盖），**冷启动路径完全没有被覆盖到**。

### 修正

发布流程补上打包步骤（与上游一致）：

```bash
bash build-local.sh dev      # -> cube/swiss/swiss.dol（原始，3.2 MB）
make -C cube/packer          # -> cube/packer/swiss.dol（自解压，1.0 MB）
```

打包需要 7-Zip（`pacman -S p7zip`），它用 `-mf=ppc -mx=9` 生成带 PowerPC BCJ 过滤器的
xz 流；固件里的 `xz_dec_bcj.c` 支持该过滤器。

包内现在提供两个文件：

- `swiss.dol` —— 自解压镜像，SD / ISO / 各类加载器用这个（1,022,240 B）
- `swiss-wiiload.dol` —— 原始构建，仅供 wiiload 推送到运行中的 Swiss

### 顺带修掉的构建问题

`cube/patches` 在 devkitPPC 16.2.0 下用 `-flto=auto` 会偶发丢失被汇编引用的符号
（`service_exception` / `idle_thread` 等），表现为链接失败且每次报错位置不同。
补丁体积只有几 KB，改为 `-fno-lto` 构建即可稳定。

### 校验

打包版结构：stub @0x8031A2A0（13,696 B）+ xz 载荷 @0x8031D820（1,008,288 B），
BSS 30,752 B —— 与官方同构。解压出的载荷中可检索到 `全局设置`、`文件浏览方式`、
`最近：`、`空格` 等本版译文，确认打入的是当前构建。

---

## 9. 冷启动实测与两处修正（2026-11-08 追加）

自解压 DOL 在 CubiBoot 上冷启动成功，随后把此前没覆盖的界面逐屏走了一遍。

### 9.1 设备选择页：底部两行提示重叠

`(Y) 设备详情` 与 `(Z) 显示全部设备` 的 y 坐标是 386 / 403。英文原版行高够用，
但中文按 1.0 绘制时字高 16 px + 基线偏移，两行实际占了 378–413 且**零间距**，
最后一行几乎压到面板边框（y=417）。

改为 **368 / 390**：留给上面描述行的间隔 4 px，两行之间 6 px，距边框 19 px。

### 9.2 溢出探针本身有两处误报

第一版 `note_overflow()` 会在两种情况下误报，现已修正：

1. **`WithMax` 的 `max` 低于中文下限就记录** —— 但 `max` 只是上限，短名字在 1.0 下
   本来就放得下。现在改为先算实际绘制宽度（`natural * CJK_MIN_SCALE`）再和控件宽度比。
2. **累加宽度时没在 `\n` 处停下** —— 多行帮助被当成一行（768 px）而误报整页帮助。
   测量函数本身遇到 `\n` 会 break，探针也必须一致。
3. 顺带修掉去重失效：存进日志时 `\n` 被替换为 `|`，但比较时用的是原文，永远不相等。

修正后走完全部已测界面，`/overflow` 返回**空**。

### 9.3 本轮新增验证的界面

设置页 4/5/6（此前未逐屏看过）、设置页 1–6 的帮助框、游戏信息面板、
金手指入口提示、单游戏设置（X）、最近列表（`最近：` 标题）、设备选择。

全部中文完整、无溢出、无错位。第 5、6 页按 Y 无帮助确认是原版索引 bug
（`tooltips_game[]` 用枚举值初始化，`get_tooltip()` 用页内序号索引）。

### 9.4 仍未验证

MP3 播放器（卡上无 mp3）、SMB/FTP 浏览（需服务器）、NKit 补丁流程、Wii 平台。

---

## 10. GCLoader 可引导 ISO（2026-11-10 追加）

发布包原先只有 DOL。GCLoader 这类光驱替代设备把 SD 卡上的镜像挂成一张真实光盘，
主机仍走原厂 IPL 的启动链，**不能直接加载 `.dol`**；上游 Swiss 也因此在发布包里
单独提供 `GCLoader/boot.iso`。本节补齐汉化版的对应产物。

### 10.1 上游做法与镜像结构

顶层 `Makefile` 的 `build` 目标：

```
mkisofs -R -J -G buildtools/iso/eltorito-gcode.hdr -no-emul-boot \
        -eltorito-platform PPC -b swiss_rXXXX.dol \
        -o dist/GCLoader/boot.iso swiss_rXXXX.dol LICENSE.txt
```

`-G` 把 32 KiB 头文件原样写进 ISO 前 16 扇区。该头含 GameCube 光盘头
（`GSWAGL`、`C2339F3D`）、bi2/FST 字段，以及从 0x2440 开始的一段
`"El Torito" apploader`（内部字符串含 `Invalid validation entry`、
`Default entry not bootable`、`segment past DOL file size` 等）。
apploader 解析 ISO9660 的 Boot Record Volume Descriptor 找到 boot catalog，
校验 validation entry，再按 default entry 给出的 LBA 读 boot image 当 DOL 加载。

因此镜像不是「把 DOL 塞进 ISO9660 文件系统」就够了，
**El Torito validation entry 的 platform ID 必须是 1（PowerPC）**，
16 位校验和也必须让 32 字节的 word 和为 0。

### 10.2 本机工具的坑

本机没有 `xorrisofs`，只有 VMware Workstation 附带的
`mkisofs 2.01-bootcd.ru`，它**不支持 `-eltorito-platform PPC`**，
默认写 platform ID = 0（x86）、checksum `0x55AA`。
`tools/build_gcloader_iso.py` 在生成后定位 boot catalog，
把 platform ID 改成 1，并按 `checksum -= 0x0100` 重算（`0x55AA → 0x54AA`）。
对照官方 r2119 `boot.iso`：两者 platform ID 与校验和完全一致。

### 10.3 产物与自检

| 文件 | Game ID | 大小 |
|---|---|---:|
| `gcloader/boot.iso` | `GSWAGL`（全区，GCLoader 用） | 1,470,464 B |
| `iso/swiss-zh(ntsc-u).iso` | `GSWEGL` | 1,470,464 B |
| `iso/swiss-zh(ntsc-j).iso` | `GSWWGL` | 1,470,464 B |
| `iso/swiss-zh(pal).iso` | `GSWPGL` | 1,470,464 B |

镜像内的 DOL 是 `firmware/swiss.dol`（r6 时为 packed 自解压版 1,076,352 B，
DOL 头 2 段、32 B 对齐、entry `0x803381E0`、末段 `0x8043ED60`）。
**r8 / r9 固件都已重编**：r8 为 1,106,336 B、entry `0x80348AE0`；
**r9 为 1,106,560 B、entry `0x80348AA0`、末段 `0x80456C20`**，
ISO 均为 1,501,184 B；上表大小是当时的历史值，当前校验值一律以
根目录 `SHA256SUMS.txt` 为准。
脚本自检 20 项：前 32 KiB 与 hdr 逐字节一致、PVD、catalog 的
validation/default entry、platform ID 与校验和、boot image 与源 DOL 全文一致、
目录记录大小、以及模拟 apploader 对 DOL 头做的全部检查（段偏移 ≥ 0x100、
32 B 对齐、不越界、地址 < 0x81200000、BSS ≥ 0x80000000、入口在 text 段内）。

与官方镜像对照：boot catalog 同在 LBA 32、DOL 同在 LBA 42、前 32 KiB 完全相同。
`DolphinTool header` 能识别两张盘；Dolphin 直接启动**官方盘同样黑屏**，
说明是模拟器不支持该 apploader 路径，与镜像无关。当时 GCLoader 真机待实测
（后续 2026-11-10 已实机验证通过，见 r7 章节）。

ISO9660 会写入生成时间戳，同一 DOL 重复生成的 SHA-256 不同属正常，
以发布包 `SHA256SUMS.txt` 为准。头文件 `tools/iso/eltorito-*.hdr`
与镜像内固件同属上游 GPL-2.0 材料。

## 11. 补齐各启动方式专用文件（v2154-zh-r7，固件未变）

官方发布包按设备分目录，本版补齐 Action Replay / FlippyDrive / Wiikey Fusion /
Wii / WODE / 记忆卡六种常用方式。所有产物装的是同一份 `firmware/swiss.dol`，
只是包装格式不同，详见 `docs/启动方式文件说明.md`。

| 目录 | 产物 | 上游对应目标 |
|---|---|---|
| `ActionReplay/` | `AUTOEXEC.DOL` + `SDLOADER.BIN` | `build-AR`（改名 + packer 同批产物） |
| `FlippyDrive/` | `EXTRACT_TO_ROOT.zip` → `boot.dol` | `build` + `zip -mr0` |
| `WiikeyFusion/` | `.fzn` / `.fzn.fw` / `RecoveryISO/` | `build`（wkf 头 + 1856K）、`recovery-iso` |
| `Wii/` | `EXTRACT_TO_ROOT.zip` → `apps/swiss-gc/boot.dol` | `build-wii` + `dol2ipl` |
| `WODE/` | `swiss-zh(wode_extcfg).iso` | `build`（wode 头） |
| `MemoryCard/` | `boot.gci` / `xeno.gci` | `build-gci` |

`tools/build_boot_variants.py` 一次生成全部并做 26 项自检，输入全部在仓库内
（`tools/boot/` 下的引导资产、`tools/iso/` 的 hdr、许可文本），
`--verify-only` 可只读复核。Wii 的 DOL 段注入与 GCI 组装用纯 Python 复刻了
`dol2ipl.py` / `dol2gci.cpp`，与上游工具输出逐字节一致；脚本还会比对
主 DOL / SDLOADER.BIN / reboot.dol 内嵌的 xz 流，防止把旧版固件打进新包。

✅ 2026-11-10 用户实机反馈：**GCLoader `boot.iso` 已验证可用**（r7 固件）。

⚠️ 其余五种设备（Action Replay / FlippyDrive / Wiikey Fusion / Wii / WODE / 记忆卡）
尚未真机实测，结构与官方 r2119 发布包逐项对齐，等待用户反馈。

## 12. 字库扩到 8887 字与全量重编（v2154-zh-r8，2026-11-10 追加）

### 12.1 报告与诊断

有用户反映「斑鸠」的「鸠」不显示。逐项复核后确认**简体字本身没有缺**：

| 检查 | 结果 |
|---|---|
| 简体「鸠」U+9E20 | GB2312 二级字（`f0af`），r5 起 7002 字库已收录，位图 31/32 非零 |
| 发布固件二进制 | 从 `swiss-wiiload.dol` 大端提取码位数组（7002 项有序，idx 6857）与位图，与 `cjkfont.c` **逐字节一致** |
| GB2312 全量覆盖 | 6763 字，缺失 0 |
| 图集页边界 | idx 6857 落在末页，14 页纹理均正常初始化，无越界 |

因此只有两种解释：文件名其实是日版原名「斑**鳩**」的「鳩」U+9CE9（不在 GB2312，
现版画 `□`），或反馈者仍在跑 r1~r4 的 3771 字旧字库（连简体二级字都没有、且无 `□` 兜底）。

### 12.2 顺带修掉的系统性缺口

`gen_font.py` 的 `EXTRA_VARIANTS` 是手工枚举的，常用繁体字漏得很多：
Big5 常用区 5401 字里有 **1885 字**未收录；抽 135 个游戏名常见繁体字就缺 31 个
（鳩、無、雙、實、戰、歐、鋼、賽、達…）。与其再一个字一个字补，不如一次把整个
常用区纳入。

新增 `--big5-common`，用 Python 内置 `big5` 编解码枚举标准常用区 A440–C67E，
不依赖外部字表；Unifont 对新增码位 100% 覆盖。生产命令：

```bash
python source/tools/gen_font.py --from-source --gb2312-full --big5-common \
    --extra-chars docs/GameCube_中文译名表.md --unifont-only
```

字库 7002 → **8887 字**，GB2312 全量与 Big5 常用区均 0 缺失；
图集 14 → **18 页**（896 → 1152 KB），`cjkfont.c` 约 2.5 MB，
编译后 `.bss` = 0x287150，链接正常。

### 12.3 固件变了，所有产物都要一起换

主 DOL 一变，`build_boot_variants.py` 的同源 xz 校验会拒绝旧的 `SDLOADER.BIN` /
`reboot.dol`，所以本次是**全链路重编**：

- `make dev` 重编 `cube/swiss`，`make apploader` 重生成 packer 三件套与 `apploader.img`
  （`build_apploader.py` 12/12 通过，新 SHA `12d86f3c…`）
- 4 个 ISO 与 6 类启动方式文件全部重生成；Wii 的 `boot.dol` 与两个 GCI 再次与上游
  `dol2ipl.py` / `dol2gci.exe` 输出**逐字节一致**
- 20/20 ISO 自检、26/26 生成自检、24/24 只读复核、`sha256sum -c` 19/19、脱敏 0 命中

⚠️ 刚实机验证通过的 GCLoader `boot.iso` 属于 r7 固件；r8 只换了镜像内的 DOL、
结构与生成方式完全没变，但**严格来说仍建议 GCLoader 用户重测一次 r8 版**。
升级时 `IPL.dol` 与 `swiss/patches/apploader.img` 必须同时换成 r8 的。
（r9 同理，见第 13 节。）

## 13. 混排数字改成与汉字同高（v2154-zh-r9，2026-11-11 追加）

### 13.1 反馈与量测

用户反馈中文串里的阿拉伯数字「有点小」。逐点阵核对确认不是错觉：

| 字形 | 占用行 | 占用列 |
|---|---|---|
| Unifont ASCII `0`-`9` | 4..13（**10 行**） | 5..10（**6 列**） |
| 汉字「国」 | 1..15（15 行） | 1..13（13 列） |
| 汉字「中」 | 0..15（16 行） | 2..12（11 列） |

数字视觉高度只有汉字约六成。r5 把数字从 IPL ROM 字体换到 Unifont 点阵解决了
「字体不一样」，但没解决「字号不一样」。

### 13.2 试过但不采用的做法

| 做法 | 结果 |
|---|---|
| 运行时把数字 quad 放大 | 记忆里的老坑：`GX_NEAR` 非整数缩放重复行列，汉字会变形 |
| 生成阶段把 Unifont 位图放大 1.5× | 笔画被复制成 **2px**，`11` 粗成黑块，比汉字重 |
| 放大后再做骨架细化 | 闭合轮廓被削成空心线框，`0` 变椭圆带斜线、`7` 丢斜线、`4` 变三角 |
| 换用 Unifont 全角数字 U+FF10 | 同样只有 11 行 / 7 列，只是居中在全角格里，并不更大 |

### 13.3 最终实现（方案 H）

在 `gen_font.py` 里新增 `DIGIT_SEG` / `DIGIT_PATHS`：把十个数字描述为
9×14 局部网格上的 **1px 线段**，用 Bresenham 栅格化进 16×16 单元
（列 3..11、行 1..14），由 `fullsize_digit_bitmaps()` 覆盖 Unifont 的 `0-9`。
十个字形全部 **14 行高、1px 笔画、无断裂**，与汉字同网格同基线。

`IPLFontWrite.c` 同步调整两个常量：`ATLAS_DIGIT_XOFF` 4→0（数字中心与汉字
中心对齐）、`ATLAS_DIGIT_ADVANCE` 10→12（9 列墨迹 + 3px 字距，对应汉字
13 列 + 4px / 17）。**运行时仍是 1:1 纹理映射，没有任何 GX 缩放。**

改数字字形只需编辑 `DIGIT_PATHS` / `DIGIT_SEG` 线段表，不要直接拉伸位图。

### 13.4 验证与产物

- 按真实 `text_advance` 常量做了 PC 精确排版模拟：`数字2026斑鳩` /
  `第2关2026年11月` 里数字与汉字齐平、笔画一致、字距不挤
- ⚠️ 本次实机离线，**画面效果待用户开机确认**；r8 的 18 页图集与繁体字已实机验证过，
  本版只改了十个数字位图和两个布局常量
- 固件重编 → `make apploader`（12/12）→ 同批 `SDLOADER.BIN` / `reboot.dol`
  → 4 个 ISO + 6 类启动方式文件全部重生成；Wii `boot.dol` 与两个 GCI 再次与上游
  `dol2ipl.py` / `dol2gci.exe` 逐字节一致
- ISO 20/20、变体 26/26、只读复核 24/24、`sha256sum -c` 19/19、脱敏 0 命中

r9 固件：`swiss.dol` 1,106,560 B `1106948d…`、
`apploader.img` 1,106,336 B `8c1f9d7d…`。升级时 `IPL.dol` 与
`swiss/patches/apploader.img` 必须同时换成 r9 的，GCLoader / ODE 用户还要换
`boot.iso` 或对应设备文件，**r8 与 r9 的同类文件不能混用**。

## 14. 字体重做：矢量字体灰度反锯齿（v2154-zh-r10，2026-11-12 追加）

### 14.1 为什么前九版怎么调都不协调

r1~r9 在屏幕上同时用了三套字形：Unifont 1bpp 点阵汉字、IPL ROM 粗体拉丁、
以及 r9 自绘的十个数字。三者字重、字高、字宽逻辑都不同，同一行里必然有一个显得
突兀。把参考截图放大到像素级后可以确认：官方那套观感来自**矢量字体在 16px 下做
灰度抗锯齿**，不是更精细的点阵——1bpp 的上限就在那里，继续调点阵没有出路。

### 14.2 存储格式：1bpp → 4bpp 灰度

| 项 | r9 | r10 |
|---|---|---|
| 每字字节数 | 32（16 行 × 2 字节） | **128（16 行 × 8 字节）** |
| 灰阶 | 2（有/无） | **16** |
| 运行时展开 | 逐像素拆位写 atlas | **按 8×8 I4 tile 逐行 memcpy** |
| 字符集 | 8887 | **8972**（十个自绘数字 → 可打印 ASCII 0x20–0x7E） |
| `cjkfont_bitmaps` | 284 KB | 1.15 MB |
| raw DOL | 3.36 MB | 4.30 MB |
| 自解压 DOL | 1.06 MB | 1.59 MB |

4bpp 的 8 字节行正好就是 GX_TF_I4 一个 tile 的两段 4 字节，所以 `init_cjk_atlas()`
不再需要 `cjk_atlas_set()` 逐像素置 nibble，直接 `memcpy` 两段即可；图集页数不变
（18 页 / 1152 KB），只是 `.bss` 里每字的源数据变大。

### 14.3 字体与排版

- 汉字：Noto Sans SC Medium 16px。墨迹实测为 y 5..20，裁切窗口取 5 正好满格 16×16，
  advance 固定 16（`CJKFONT_ADVANCE`）
- 拉丁与数字：同族 Bold 18px。16px 时大写只有 12px 高、数字笔画仅 1px 灰边，
  在中文旁边像小字；18px 给到 13px 大写高度与 2px 实笔画，advance 只涨约 12%
- 字宽：新增每字 `cjkfont_advance[]`（`u8`），`text_advance()` 直接返回字体原生宽度，
  于是 `64.1` 比四个汉字窄，中文词不再被数字挤开
- 数字与大写字母的墨迹底边落在 cell 第 15 行，与汉字墨迹**底边齐平**（不是数学基线齐平）

### 14.4 四个必须踩过才知道的坑

1. **数字整体浮起 2px**：两套字体的数学基线其实一致，但 CJK 字形墨迹比基线低 1px、
   数字停在基线以上 1px，按基线对齐恒差 2px。ASCII 裁切窗口 7→5 抵消，
   数字与大写的墨迹落到 cell 第 2..15 行，与汉字 0..15 的**底边**齐平。
2. **`gbi-config` 显示成 `σbi-config`**：18px 降部超出 16 行格子，尾巴被裁成圆圈。
   只压 1 行时又被 0.75 缩放插值抹成一条横线，仍然像 σ。最终 `gjpqy` 的 x-height
   重采样 10→9 行、降部压 **2 行**贴底——代价是这五个字母比邻居矮 1px，
   但尾巴不见了整行文件名都会读错。
3. **`[GCSEA4]` 的 `[` 变成 `厂`**：括号墨迹占 19 行，底部横线被裁。括号没有基线概念，
   整体等比压进 16 行，上下两端都保住。
4. **顶栏每行文字上方一条碎点带**：`drawString()` 缩的是 modelview 矩阵而不是字形，
   quad 顶边落在 `scale*(yofs-13)`；`yofs=7` 在 0.75 缩放下等于 **-4.5**（半像素），
   GX 只能把边缘行按部分覆盖率光栅化。`CJK_BASELINE_NUDGE` 2→4（`yofs` 7→9）后消失。

### 14.5 渲染管线

- `IPLFontWrite.c`：所有码位（含 ASCII）优先走 atlas，`draw_glyph()` 统一分发；
  atlas 未覆盖的才回落 IPL ROM（`drawIplGlyph`）。`LATIN_FIT 0.85`、`ATLAS_DIGIT_XOFF`、
  `ATLAS_DIGIT_ADVANCE`、`latinFit` 状态机全部删除
- 纹理采样改 **`GX_LINEAR`**：1:1 映射时仍落在像素中心，不会软化；只有小字缩放才插值。
  这套精度的前提是 4bpp 灰度——1bpp 时代 `LINEAR` 会把 `文` / `试` 糊成灰块
- 缩放下限：含 CJK 的串钳到 **1.0**（`CJK_MIN_SCALE`），纯拉丁串钳到 **0.75**
  （`LATIN_MIN_SCALE`）。UI 调用点写死的 `0.45f` / `0.6f` 是按旧 26px IPL 字体设计的，
  16px 字库下只剩 7px，必须抬下限
- `GetTextScaleToFitInWidth()` 返回同一套下限，否则测量与绘制不一致会导致溢出
- 导出 `GetEffectiveTextScale()`：手工按文本宽度定位的调用点（顶栏温度←日期宽度）
  必须用它，否则按 0.45 估宽、按 0.75 绘制，温度压在日期上

### 14.6 ISO 去掉尾部填充

mkisofs 默认把镜像尾部补到 150 扇区（300 KB）的整数倍。r9 的 DOL 只有 1.06 MB，
填充后 1.5 MB 仍在 Wiikey Fusion 的 1856 KB 上限内；r10 的 DOL 涨到 1.59 MB，
加填充就是 2.0 MB，`.fzn` 只能截断，等于损坏。生成命令统一加 `-no-pad` 后
**853 扇区 / 1,746,944 B**，留出约 150 KB 余量，GCLoader / WODE / 三区 ISO 一并变小。

### 14.7 工具修正

- `preflight.py` 原来用 `--gb2312`（仅一级字）重生成字库，构建前自检会把 9 千字的
  整库覆盖成 4 千字；现改为与生产命令一致的完整参数（`--gb2312-full --big5-common`
  + 译名表）
- 新增 `check_baseline.py` / `render_cjkfont.py`：直接读 `cjkfont.c` 报告每个字形的
  墨迹上下界，并按真实字宽表反向渲染排版。用来区分「字库数据错了」和「运行时绘制错了」
  ——r10 这两类问题都出现过

### 14.8 验证与产物

- ✅ **实机验证通过**（2026-11-12）：中英混排、中文游戏名、全角括号与方括号、
  列表省略号、顶栏 `commit` / `revision`、容量数字；繁体「斑鳩雙實無測試」逐字可读；
  `/overflow` 无溢出记录
- apploader 12/12、ISO 19/19 ×4、变体 26/26、只读复核 24/24、`sha256sum -c` 19/19、
  脱敏 0 命中

r10 固件：`swiss.dol` 1,659,648 B `45c79728…`、`swiss-wiiload.dol` 4,304,000 B
`1402216e…`、`apploader.img` 1,659,424 B `4426995c…`。升级时 `IPL.dol` 与
`swiss/patches/apploader.img` 必须同时换成 r10 的，GCLoader / ODE 用户还要换
`boot.iso` 或对应设备文件，**r9 与 r10 的同类文件不能混用**。

