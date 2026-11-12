# 更新记录

## 2026-11-12 — 字体重做：矢量字体灰度反锯齿（发布为 `v2154-zh-r10`）

- 反馈：中文、英文、阿拉伯数字三种字形的观感都差。放大参考截图后确认，官方那套的档次
  来自**矢量字体 16px 灰度抗锯齿**，不是更精细的点阵；此前的组合是 Unifont 1bpp 汉字
  + IPL ROM 粗拉丁 + 自绘数字，三套字混在一行里，怎么调都不会协调
- 字库存储 **1bpp → 4bpp 灰度**（每字 32 → 128 字节），布局即 GX I4 tiling，
  运行时按 8×8 tile 逐行 memcpy，不再逐像素展开
- 字体源换成 **Noto Sans SC**（SIL OFL 可分发）：汉字 Medium 16px 满格，
  拉丁/数字 Bold 18px；**中英数同源同基线**，数字改为比例字宽（新增 `cjkfont_advance[]`）
- 字符集 8887 → **8972 字**：十个自绘数字换成可打印 ASCII 0x20–0x7E，图集仍 18 页 / 1152 KB；
  `cjkfont_bitmaps` 284 KB → 1.15 MB，raw DOL 3.36 → 4.30 MB，自解压 DOL 1.06 → 1.59 MB
- 渲染：`GX_NEAR` → `GX_LINEAR`；删除 `LATIN_FIT` / `ATLAS_DIGIT_*` 分支，统一 `draw_glyph()`；
  新增 `LATIN_MIN_SCALE 0.75` / `CJK_MIN_SCALE 1.0` 下限（UI 调用点按旧 26px 字体写死 0.45）；
  导出 `GetEffectiveTextScale()` 修顶栏温度压在日期上；`CJK_BASELINE_NUDGE` 2→4 消除顶栏碎点
- `gen_font.py`：ASCII 裁切窗口 7→5（数字底边与汉字齐平）、`gjpqy` 降部重采样、
  `()[]{}` 整体压缩进 16 行；`preflight.py` 改用完整字库参数（原来用 `--gb2312`
  会把整库覆盖成 4085 字）
- `build_gcloader_iso.py` 加 `-no-pad`：mkisofs 默认补 300 KB 尾部填充，会顶破
  Wiikey Fusion 的 1856 KB 上限；ISO 1,501,184 → 1,746,944 B
- 验证：apploader 12/12、ISO 19/19 ×4、变体 26/26、只读复核 24/24、`sha256sum -c` 19/19、脱敏 0 命中
- ✅ **实机验证通过**（2026-11-12）：中英混排、中文游戏名、括号、顶栏、容量数字、
  繁体「斑鳩雙實無測試」，`/overflow` 无溢出记录
- 按不可变规则另发 `v2154-zh-r10`（Latest），r1~r9 与 `v2154-zh` 全部原样保留；
  升级时 `IPL.dol` 与 `apploader.img` 必须同时替换，r9 / r10 文件不能混用


## 2026-11-11 — 混排数字改成与汉字同高（发布为 `v2154-zh-r9`）

- 反馈：中文串里的阿拉伯数字「有点小」。逐点阵核对：Unifont 的 `0-9` 只占
  **10 行 / 6 列**，汉字是 15 行 / 13 列，视觉高度约六成，确实小一圈
- 不采用的方案：运行时 GX 缩放（老坑，会变形）、生成阶段放大 Unifont 位图
  （笔画变 2px 过粗）、骨架细化（`0` / `7` / `4` 断裂）、换 Unifont 全角数字
  （同样只有 11 行高）
- `gen_font.py` 新增 `DIGIT_SEG` / `DIGIT_PATHS` 与 `fullsize_digit_bitmaps()`：
  用 1px 线段路径在 16×16 网格里重绘十个数字，**14 行高 / 9 列宽 / 1px 笔画**，
  与汉字同网格、同基线、同笔画粗细，运行时仍 1:1 纹理映射
- `IPLFontWrite.c`：`ATLAS_DIGIT_XOFF` 4→0（中心对齐）、
  `ATLAS_DIGIT_ADVANCE` 10→12（字距不挤，汉字为 17）
- 发布仓库与 i18n 两份 `gen_font.py` 同步；发布副本保持 `SWISS_GC_WORKSPACE`
  环境变量写法，脱敏 0 命中
- 固件重编 → `make apploader`（12/12）→ 同批 packer 资产 → 4 个 ISO +
  6 类启动方式文件全部重生成；Wii `boot.dol` 与两个 GCI 再次与上游工具逐字节一致
- 验证：按真实字距常量做 PC 精确排版模拟（数字齐平、笔画一致、字距不挤）、
  ISO 20/20、变体 26/26、只读复核 24/24、`sha256sum -c` 19/19、脱敏 0 命中
- ⚠️ 本次实机离线，**数字画面效果待开机确认**；r8 的 18 页图集与繁体字已实机验证
- 按不可变规则另发 `v2154-zh-r9`（Latest），r1~r8 与 `v2154-zh` 全部原样保留；
  升级时 `IPL.dol` 与 `apploader.img` 必须同时替换，r8 / r9 文件不能混用

## 2026-11-10 — 字库扩到 8887 字，补齐繁体/日文常用字（发布为 `v2154-zh-r8`）

- 反馈：「斑鸠」的「鸠」不显示。逐字节复核确认**简体「鸠」U+9E20 在 r5~r7 里
  码位与位图都完好**（GB2312 二级字，7002 字库已收录）；真实原因是日版原名
  「斑鳩」的「鳩」U+9CE9 不在 GB2312，或反馈者仍在用 r1~r4 的 3771 字旧库
- `gen_font.py` 新增 `--big5-common`，用内置 big5 编解码枚举标准常用区
  A440–C67E；字库 7002 → **8887 字**，GB2312 全量 6763 与 Big5 常用区 5401
  **均 0 缺失**，「鸠」「鳩」及 1885 个常用繁体字都有完整 Unifont 字形
- 图集 14 → **18 页 / 1152 KB**（+256 KB 常驻），`.bss` = 0x287150 链接正常；
  packed DOL 1,076,352 → 1,106,336 B（`26d133f3…`），
  `apploader.img` → 1,106,112 B（`12d86f3c…`）
- **固件重编触发全链路更新**：`make dev` + `make apploader`（12/12 校验）、
  同批 `SDLOADER.BIN` / `reboot.dol`、4 个 ISO、6 类启动方式文件全部重新生成；
  Wii `boot.dol` 与两个 GCI 再次与上游 `dol2ipl.py` / `dol2gci.exe` 逐字节一致
- 验证：ISO 20/20、变体 26/26、只读复核 24/24、`sha256sum -c` 19/19、
  脱敏 0 命中；`SHA256SUMS.txt`、README、安装说明、发布包 CHANGELOG 同步
- ✅ 用户实机确认 **GCLoader `boot.iso` 可用**（r7 固件）；r8 仅换镜像内 DOL、
  结构未变，仍建议 GCLoader 用户重测一次 r8 版
- 按不可变发布规则另发独立 tag `v2154-zh-r8`（Latest），r1~r7 与 `v2154-zh`
  全部原样保留；升级时 `IPL.dol` 与 `apploader.img` 必须同时替换

## 2026-11-10 — 补齐各启动方式专用文件（固件本体未改动，发布为 `v2154-zh-r7`）

- 反馈：官方 r2119 发布包按 JB / ODE 方式分目录（ActionReplay、FlippyDrive、
  WiikeyFusion、Wii、WODE、MemoryCard、PicoBoot…），此前本包只有
  DOL / apploader / GCLoader / ISO，其它设备的用户没有现成文件
- 复刻上游顶层 `Makefile` 的 `build` / `build-AR` / `build-wii` /
  `recovery-iso` / `build-gci` 目标，新增 `tools/build_boot_variants.py`：
  以 `firmware/swiss.dol` 与 `tools/boot/` 内同批引导资产为输入，
  纯 Python 生成全部变体，26 项自检，`--verify-only` 可只读复核
- 新增目录与产物：
  - `ActionReplay/AUTOEXEC.DOL`（主 DOL 改名）+ `SDLOADER.BIN`（同批 packer 产物）
  - `FlippyDrive/EXTRACT_TO_ROOT.zip` → `boot.dol`（store 模式 zip）
  - `WiikeyFusion/swiss-zh.fzn`（wkf 头 ISO 补齐到 1856K）、
    `swiss-zh.fzn.fw`、`RecoveryISO/swiss-zh_Recovery.iso`（PAL ISO + 前 32K 恢复引导头）
  - `Wii/EXTRACT_TO_ROOT.zip` → `apps/swiss-gc/boot.dol`：
    Wii booter 由本基线源码用 libogc2 `wii_rules` 编译，再注入同批 `reboot.dol`
  - `WODE/swiss-zh(wode_extcfg).iso`、`MemoryCard/boot.gci` / `xeno.gci`
  - `Licenses/` 13 份上游第三方许可文本、`tools/boot/` 构建资产与来源说明
- `tools/build_gcloader_iso.py` 增加 `wode` / `wkf` 两个 El Torito 头与
  `--all-variants`；`--all` 仍只生成原来 4 个 ISO
- 验证：26/26 自检通过；Wii 的 DOL 段注入与上游 `dol2ipl.py`、
  两个 GCI 与上游 `dol2gci.exe` 输出**逐字节一致**；
  脚本会从主 DOL / SDLOADER.BIN / reboot.dol 提取内嵌 xz 流比对，
  确保三份产物出自同一次构建，不一致直接拒绝生成
- 文档：新增 `docs/启动方式文件说明.md`、`tools/boot/README.md`，
  README / 安装说明 / 发布包 CHANGELOG / SHA256SUMS.txt 同步
- 固件与 `apploader.img` 未重编，SHA-256 与 r5/r6 完全相同。按不可变发布规则
  另发独立 tag `v2154-zh-r7`（Latest），r1~r6 全部原样保留
- ✅ 2026-11-10 用户实机反馈：**GCLoader `boot.iso` 已验证可用**
- ⚠️ 其余五种设备（Action Replay / FlippyDrive / Wiikey Fusion / Wii / WODE / 记忆卡）
  **尚未真机实测**（本机为 PicoLoader / CubiBoot + SD 卡）；结构与官方 r2119 包
  对齐，等待各设备用户反馈

## 2026-11-10 — 新增 GCLoader 可引导 ISO（固件本体未改动）

- 反馈：GCLoader 等光驱替代设备把 SD 卡上的镜像当真实光盘引导，走
  IPL → apploader → DOL 链路，**不能直接加载 `.dol`**；此前发布包只有 DOL，
  这部分用户装不上。原版 Swiss 的发布包里也单独带 `GCLoader/boot.iso`
- 复刻上游 `Makefile` 的 GCLoader ISO 命令：`mkisofs -R -J -G eltorito-gcode.hdr
  -no-emul-boot -eltorito-platform PPC -b <dol> -o boot.iso <dol> LICENSE.txt`
- 新增 `tools/build_gcloader_iso.py`：自动查找 `mkisofs`/`xorrisofs`、
  自适应老版本缺 `-eltorito-platform PPC` 的情况（生成后修正 El Torito
  validation entry 的 platform ID 为 1 并重算 16 位校验和）、附 20 项自检
  （光盘头 / PVD / catalog / DOL 全文 / 目录记录 / apploader 的 DOL 头校验项）
- 新增 `tools/iso/eltorito-*.hdr`（来自上游 GPL-2.0 源码，各 32 KiB）
- 产物：`gcloader/boot.iso`（`GSWAGL` 全区，GCLoader 专用）+
  `iso/swiss-zh(ntsc-u|ntsc-j|pal).iso`（`GSWEGL`/`GSWWGL`/`GSWPGL`），
  每个 1,470,464 B；镜像内装的是 `firmware/swiss.dol` 同一份 packed DOL
- 验证：4 个 ISO 均 20/20 自检通过；与官方 `v0.6r2119` 的 `boot.iso` 对照，
  前 32 KiB 光盘头逐字节相同、boot catalog 同在 LBA 32、DOL 同在 LBA 42；
  `DolphinTool header` 正确识别。**Dolphin 直接启动官方盘与我们的盘都黑屏**，
  属模拟器不支持该 apploader，非镜像问题；当时 **GCLoader 真机仍待实测**
  （后续 2026-11-10 已实机验证通过，见上文）
- 文档：`gcloader/使用说明.md` 新增，README / `firmware/安装说明.md` 的方式 C /
  发布包 CHANGELOG / `SHA256SUMS.txt` 同步，README 修正了原先
  「`swiss.dol` 可直接给 GCLoader 用」的不准确表述
- 固件与 `apploader.img` 未重新编译，SHA-256 与 `v2154-zh-r5` 完全相同。
  按不可变发布规则，本批改动发布为独立 tag `v2154-zh-r6`（Latest），
  不追加、不覆盖任何已发布 Release；`v2154-zh-r1` ~ `r5` 全部保留可回滚
- 补 `.gitattributes` 明确声明二进制扩展名与 `SHA256SUMS.txt` 的 LF 行尾，
  修正发布前检查脚本会漏写 ISO 校验项的问题

## 2026-11-10 — 发布方式改为不可变发布，历史版本全部归档

- 早期把每次更新的固件、完整包和 Release 说明反复覆盖到同一个 `v2154-zh`
  （`--clobber` + `release edit --notes-file`），导致旧版本在 GitHub 上消失、用户无法回滚
- 现补建 `v2154-zh-r1` ~ `v2154-zh-r5` 五个独立 Release，各 tag 用 `--target` 指向
  对应的历史 commit；附件为当时实际发布包的原样副本（r2 由 `3354acb` 的 git 树复现）
- `v2154-zh-r5`（数字点阵版，固件 `1ec622cb`）标为 **Latest**；`v2154-zh` 冻结保留，
  仅用于兼容论坛帖等已发出的下载链接，以后不再往它上传任何文件
- 新增 [docs/RELEASE_POLICY.md](docs/RELEASE_POLICY.md)：禁止 `--clobber` /
  `delete-asset` / 改写已发布说明 / 强推 tag；发错了就发下一个版本
- 新增 `tools/publish_release.py`：发布前检查本地与远端 tag、已有 Release 和 zip，
  任一存在即拒绝；支持 `--archive` 原样归档历史包、`--reuse` 两步发布、`--latest=false`
- README 增加版本历史表，各 Release 说明互相链接

## 2026-11-10 — 混排阿拉伯数字改用中文同款点阵字

- 实机反馈：中文游戏名里的数字（如 `忍者神龟3：变异噩梦`）和汉字「字体、位置出入比较大」。
  旧实现里中文走 16×16 Unifont 点阵，数字仍走 IPL ROM 字体贴图，只做了
  `LATIN_FIT 0.85` 等比缩小 + quad 底部对齐；字形是另一种粗圆体，基线也不是同一套
- `gen_font.py` 固定把 ASCII `0-9` 收进字库（6992 → **7002 字**，图集仍 14 页）；
  `IPLFontWrite.c` 在含中文的字符串里把这 10 个码位改走 CJK 绘制分支：同一字体、
  同一 16px 网格、同一 `yofs` 基线；Unifont 窄字形在 cell 内居中，故 quad 左移 4px、
  字宽改为半角 10px
- 三处绘制分支（`drawString` / `drawStringWithCaret` / `drawStringEllipsis`）与所有
  宽度计算（`text_advance` / `GetTextSizeInPixels` / `GetCharsThatFitInWidth` /
  `GetTextScaleToFitInWidth`）统一；顺带修正 `drawStringWithCaret` 按字节而非按码点
  量宽度导致中文输入框宽度偏大的老问题
- **纯拉丁字符串不受影响**：时钟、日期、`commit: … · revision: …`、启动信息保持 IPL 字体
- 实机 wiiload 抓屏对比确认数字由粗圆大字变为细点阵、与汉字同风格同基线；
  随后写入 SD 卡 `IPL.dol` 与 `swiss/patches/apploader.img`，逐字节回读一致
- 固件与 IGR 镜像同次重编，`build_apploader.py` 12/12 校验通过；校验值、离线包、
  README / 安装说明 / 发布包 CHANGELOG 同步

## 2026-11-10 — 修复中文游戏名缺字（「噩」等二级汉字）

- 实机反馈：`忍者神龟3：变异噩梦` 的「噩」显示为空，画面读成 `变异 梦`。
  根因不是渲染 bug：字库由 `gen_font.py --from-source --gb2312` 生成，只收
  **GB2312 一级 3755 字 + 界面译文用字 = 3771 字**；游戏文件名是编译后用户改的，
  凡「文件名有、界面没有」的字（噩 / 飙 / 鑫…）都查不到字形
- 旧代码在 `IPLFontWrite.c` 里 `if(idx >= 0)` 查不到就跳过绘制，但
  `text_advance()` 仍照常前进，于是留下一个字宽的空白，极易被误认成文件名里有空格
- 字库扩到 **6992 字**：GB2312 全量（一级+二级 6763 字）∪ 源码用字 ∪ 中文译名表
  ∪ 常见繁体/日文异体。`gen_font.py` 新增 `--gb2312-full` / `--extra-chars`，
  `check_glyphs.py` 新增 `--extra`，发布前可检查任意动态文本（游戏名表）
- 新增兜底：字库外码位统一画 `□`（字库固定收录 U+25A1，头文件导出
  `CJKFONT_FALLBACK_GLYPH`），`drawString` / `drawStringWithCaret` /
  `drawStringEllipsis` 三处绘制分支全部走同一逻辑，不再静默留白
- 实机验证：上传测试文件 `忍者神龟3：变异噩梦 (Disc 1).iso` 抓屏确认「噩」完整显示；
  `字体兜底测试龘` 的「龘」显示为 `□`；测试文件已清理，65 个中文游戏名全部正常
- 图集 8→14 页（512 KB→896 KB 常驻内存），DOL +113 KB；实机启动、文件列表与滚动无异常
- 固件与 `apploader.img` 已重新编译并保持配套，SD 卡 `IPL.dol` 已写入且回读一致
- 校验值更新：`SHA256SUMS.txt`、`igr/SDCard_IGR.zip`、README 校验表

## 2026-11-09 — 设置里增加背景图切换

- 「设置 → 界面设置（2/6）」新增「背景图」：关闭（0）/ 1~9
- 取值 N 读取 `swiss/backdropN.tpl`；选 1 且该文件不存在时自动回退到旧的 `swiss/backdrop.tpl`，旧安装升级后背景不丢
- 左右键切换即时重载，无需重启；值保存在 `global.ini` 的 `BackdropIndex`
- 修掉一个会漏内存的点：libogc2 的 `TPL_GetTexture*` 用 `memalign` 读盘、只有 `TPL_CloseTPLFile()` 会 `free`。现在每次切换/关闭前释放上一张贴图，加载失败还会回退内置背景，不留悬空指针
- 实机验证：开机加载生效、设置页内即时换图（红 → 青）、缺文件回退内置背景、连续切换 14 次无异常
- 固件与 `apploader.img` 已重新编译并保持配套，SD 卡 `IPL.dol` 同步更新

## 2026-11-09 — 统一汉字与拉丁字符的视觉大小

- 实机反馈：英文字母和数字比汉字大一圈。根因是汉字走 16px 点阵字库、拉丁字符走 IPL 原生字体，cap height 相差约 2px
- `IPLFontWrite.c` 新增 `LATIN_FIT`：**仅对含中文的字符串**把拉丁字形等比收缩，纯英文行（时钟、commit 行、启动信息）保持原样
- 同步修正 `GetTextSizeInPixels` / `GetCharsThatFitInWidth` / `GetTextScaleToFitInWidth` 等测宽路径，避免截断和居中偏移
- 0.875 与 0.85 两档实机对比后选定 **0.85**
- 固件与 `apploader.img` 已按新源码重新编译，两者仍严格配套；离线包、截图与校验值同步更新

## 2026-11-09 — README 增加爱发电赞助入口

- 主页标题下新增赞助按钮（本地静态 SVG `docs/afdian-sponsor.svg`，暖黄「请我喝一杯咖啡」+ 咖啡杯图形），点击跳转 <https://ifdian.net/a/hualazimo7>
- 按钮不依赖 shields.io 等外部图床，离线/内网环境也能正常显示
- 赞助属自愿打赏，**不构成商业授权**，不改变 [`LICENSE`](LICENSE) 的非商业条款

## 2026-11-09 — 增加禁止商用许可（非商业使用许可 v1.0）

- 仓库主许可改为《非商业使用许可 v1.0》：本仓库原创的翻译表、工具、文档与离线包中文材料仅限非商业用途，禁止出售、预装到售卖的硬件/存储卡、付费代刷、广告变现等商业使用
- 新增 [`LICENSE`](LICENSE) 正文与 [`NOTICE.md`](NOTICE.md)（范围界定、商用示例、授权申请方式）；原 GPL-2.0 全文原样留存为 `LICENSE-GPL-2.0.txt`
- 依 GPL-2.0 第 6 条，不对上游 Swiss / GNU Unifont 的 GPL 材料追加任何限制，该部分权利（含商业使用）不受影响
- 已按 GPL-2.0 分发的历史版本与既有 Release 附件，其授权不可撤销；本次变更对当前及后续版本生效
- README 顶部与许可章节已同步标注禁止商用

## 2026-11-09 — 游戏名中文化（附加工具）

- `tools/rename_games_cn.py`：支持 `--dry-run` / `--apply --recent` / `--verify` / `--rollback`
- 实机把 `sdb:/root/game/GameCube/` 下 56 个英文文件名改为中文，`VERIFY: PASS`（64 文件、0 缺失、0 英文残留、大小逐项对应）
- 同步迁移 `recent.ini` 里 3 条旧路径；`settings/game`、`patches/game`、`saves`、`cheats` 按 GameID / 哈希命名，不受影响
- 记录 `FR_LOCKED(16)` 的根因与解锁流程：Swiss 文件浏览器持有当前目录所有文件的 FatFs 句柄

## 2026-11-09 — 游戏内复位真机验证通过

- 用户启动 SD 卡游戏后按 `A + Z + Start`，正常回到中文 Swiss 主界面，无机器重启
- 远程复核：`/state` 正常、正式版无测试标记、SD 卡 `apploader.img` 回读 1,027,200 B 与本地 SHA `d55d5a7d…` 一致
- `R + Z + Start` 沿用同一套 `CheckStatus` 逻辑，未单独按键复测

## 2026-11-08 — 补齐与汉化版配套的 apploader.img

- 定位根因：`apploader.img` 由 `dol2ipl.py` 把 `reboot.dol`（内嵌本次编译的 `executable.xz`）展平而来，不是通用补丁；用官方/release 版会黑屏、反复重启或回英文原版
- 修复构建链：`Makefile` 新增 `PYTHON ?= python3`、`DOL2IPL = $(PYTHON) …`、精简目标 `apploader`；`build-local.sh` 自动探测 Windows Python；`build-ipl` 的版本号 glob 加引号
- 新增 `tools/build_apploader.py`：一键构建 + 12 项逐级字节校验 + 生成离线 SD 卡包 + 联网推送并回读
- 产物：`igr/apploader.img` 1,027,200 B（32 B 头 + 1,027,168 B 镜像），版本标记 `*swiss_r2154.dol`
- 校验链 12/12 通过：`swiss.elf → executable.bin → executable.xz → reboot.dol → apploader.img`，并验证 SD 卡 `IPL.dol` 与 `apploader.img` 内嵌同一份 `executable.xz`

## 2026-11-08 — 简中汉化构建（基线 commit 62a8b9a2 / revision 2154）

基于上游 `emukidid/swiss-gc` 的 master commit `62a8b9a2`（2026-11-05）。Swiss 的 `revision` 是 `git rev-list HEAD | wc -l` 算出的提交总数 2154，官方最后一个发布 tag 是 `v0.6r2119`（commit `163f8b1d`，比本基线旧 35 个提交）：

- 界面文本、设置项、帮助说明、错误提示、设备名、设备错误信息全部中文化
- 设置取值（是/否等）在**显示层**汉化，配置文件仍写英文值，不破坏 `swiss.ini` / `global.ini`
- 生成本地化字体图集（GNU Unifont 字模），支持中文文件名（FatFs UTF-8 长文件名）
- 顶部温度改为与日期同行、紧邻显示
- 修复 `DrawLoadBackdrop()` 成功分支未关闭 `FILE*` 导致的背景文件锁（`FR_LOCKED(16)`）
- 新增 httpd 端点 `/rename`、`/get`、`/state`，供 PC 工具远程操作
- 修掉 FSP / SMB / MP3 / NKit 相关的若干显示与初始化问题
- 产出 `firmware/swiss.dol`（自解压正式版）与 `firmware/swiss-wiiload.dol`（仅网络推送）

## 实机验证

SD 卡启动游戏、断电冷启动、中文界面与温度/日期、中文文件名、自定义背景、SMB/FTP/MP3/NKit 流程均通过。FSP 直读游戏速度很慢，按约定只做轻量连通性确认，不建议用作游戏加载设备。
