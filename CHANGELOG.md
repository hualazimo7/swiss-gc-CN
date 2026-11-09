# 更新记录

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

## 2026-11-08 — 简中汉化构建 r2154

基于上游 `emukidid/swiss-gc` 的 r2154 / commit `62a8b9a2`：

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
