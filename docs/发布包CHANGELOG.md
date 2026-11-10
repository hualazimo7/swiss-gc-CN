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

- 字模：`fonts/unifont.hex` → 16×16 1bpp，每字 32 字节
- 字符集：**GB2312 全量 6763 字 ∪ 源码用字 ∪ 中文译名表 ∪ 常见繁/日异体 ∪ ASCII 0-9 = 7002 字**
  （`gen_font.py --from-source --gb2312-full --extra-chars <译名表> --unifont-only`；
  早期版本只有一级 3755 字，游戏名里的「噩」等二级字会静默留白，2026-11-10 修复）
- 混排数字：含中文的字符串里 `0-9` 也从这张图集取字形，与汉字同字体/同基线、半角 10px；
  纯拉丁行仍用 IPL 字体
- 图集：**14 页 × 512×256 I4（64KB/页），512 字/页**，运行时按字绑页
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

镜像内的 DOL 是 `firmware/swiss.dol`（packed 自解压版，1,076,352 B，
DOL 头 2 段、32 B 对齐、entry `0x803381E0`、末段 `0x8043ED60`）。
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

✅ 2026-11-10 用户实机反馈：**GCLoader `boot.iso` 已验证可用**。

⚠️ 其余五种设备（Action Replay / FlippyDrive / Wiikey Fusion / Wii / WODE / 记忆卡）
尚未真机实测，结构与官方 r2119 发布包逐项对齐，等待用户反馈。
