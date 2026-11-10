# 更新记录

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
