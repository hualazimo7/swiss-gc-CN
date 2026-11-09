# 授权边界说明 / NOTICE

本文件用通俗语言解释 [LICENSE](LICENSE) 的适用范围。若与 `LICENSE` 正文不一致，以 `LICENSE` 为准。

## 一句话结论

本仓库**原创的翻译表、工具、文档、离线包中文材料禁止商业使用**；而源自上游 Swiss /
GNU Unifont 的固件二进制及其整体属 GPL-2.0 衍生作品，**著作权人无权禁止其商业使用**，
该部分仍按 GPL-2.0 授权。

## 为什么不能「整个仓库一概禁止商用」

GPL-2.0 第 6 条规定：「You may not impose any further restrictions on the recipients'
exercise of the rights granted herein.」（不得对接收人行使本许可授予的权利施加进一步限制），
并且 GPL 明确允许商业性分发。`swiss.dol`、`apploader.img` 是上游 Swiss 的编译产物，
本项目只贡献了翻译文本与少量显示层改动，无法单方面把它们改成「禁止商用」。
强行声明不仅无效，还会使本项目的分发行为与 GPL-2.0 冲突。因此采用双轨授权：
能禁止的部分明确禁止，不能禁止的部分如实说明。

## 具体怎么分

| 材料 | 能否商用 | 依据 |
|---|---|---|
| `firmware/*.dol`、`igr/apploader.img`（固件整体） | 可，须遵守 GPL-2.0 | GPL-2.0 衍生作品 |
| `source/fonts/unifont.*` | 可，须遵守 GPL-2.0+ 及字体例外 | 第三方字体 |
| `source/translations/*.tsv` 翻译表（单独使用） | **否** | 本项目原创，非商业许可 |
| `source/tools/*.py`、`tools/*.py` | **否** | 本项目原创，非商业许可 |
| `docs/`、截图、离线包内中文安装说明与打包脚本 | **否** | 本项目原创，非商业许可 |
| 仓库名、项目名称、品牌标识 | 未授权 | 本许可不授予商标权 |

## 商业使用的典型例子

以下行为**需要**事先取得书面许可（针对受本非商业许可约束的材料）：

- 把工具 / EXE / 离线包放进付费网盘、付费群、付费教程或付费订阅里提供；
- 把汉化版或工具预装到**对外销售**的 SD 卡、硬盘、GameCube 整机、烧录卡、改装机中；
- 收费提供「代刷机 / 代汉化 / 代装游戏 / 代配置」服务；
- 在带广告、带货、付费会员或流量分成的渠道里以本项目的材料吸引付费；
- 把本项目材料集成进交付给客户的商业产品或企业经营性流程。

以下行为**不需要**申请：

- 自己用、给朋友用、备份、学习、研究、上课演示；
- 免费发到论坛、QQ/微信群、网盘、GitHub 镜像（不以此收费或变现）；
- 免费写教程、做视频、发评测并注明出处；
- 修改源码供自己或非营利社区使用；
- 依 GPL-2.0 使用上游 Swiss / GNU Unifont 的材料（遵守 GPL-2.0 义务即可）。

## 商业授权

请在本仓库 Issues / Discussions 说明用途、分发范围、期限与方式，取得**书面**同意后方可使用。

## 第三方与历史版本

- GNU General Public License v2 完整原文：[`LICENSE-GPL-2.0.txt`](LICENSE-GPL-2.0.txt)
- 上游 Swiss：https://github.com/emukidid/swiss-gc （GPL-2.0）
- GNU Unifont（GPL-2.0+ 及字体例外）；devkitPro / libogc 构建工具链
- 历史版本：首个公开提交以 GPL-2.0 发布，已分发副本的授权不可撤销；本次变更仅对当前及后续版本生效

## 免责

本项目与 Swiss、Nintendo、devkitPro 及 GameCube 商标持有人均无关联。
GameCube 是 Nintendo 的商标。按「现状」提供，刷机、改名、覆盖文件前请自行备份。
