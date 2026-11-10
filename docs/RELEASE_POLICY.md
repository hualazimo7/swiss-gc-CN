# 发布规则：不可变发布（Immutable Releases）

> 生效日期：2026-11-10。适用于本账号下的 `swiss-gc-CN`、`swiss-gc-Imager`、
> `swiss-gc-ftp` 三个公开库。

## 为什么改

早期做法是把每次更新的固件、完整包和 Release 说明反复覆盖到同一个
`v2154-zh` Release 上（`--clobber` + `release edit --notes-file`），结果旧版本
在 GitHub 上彻底消失，用户既无法回滚，也无法确认自己下的是哪一版。
2026-11-10 起改为：**一个版本 = 一个 tag = 一个 Release，发布后即冻结**。

## 硬性规则

1. **禁止覆盖已发布的任何东西**：
   - 禁止 `gh release upload <tag> ... --clobber`
   - 禁止 `gh release delete-asset` / `gh release delete`
   - 禁止 `gh release edit <tag> --notes-file ...` 改写已发布说明（勘误写进下一个版本的说明）
   - 禁止 `git tag -f` / 强推已发布 tag
   - 禁止复用同名附件包（每个 tag 的 zip 文件名必须带 tag）
2. **固件或附件内容一变就发新 tag**，包括只重编固件、只换一张截图。
   纯文档的补充说明只更新 `main` 即可，**不要回头改已发布 Release 的说明或附件**
   （所以 `main` 上的文档可能比最新 Release 的 zip 更新一点，属正常）。
   `IPL.dol` 与 `apploader.img` 来自同一次构建，必须同版本配套，绝不能跨版本混用。
3. **发错了就发下一个版本**，在新版说明里写明「本版修正 rN 的 XX 问题」，
   旧版保持原样可下载，便于用户回滚或复现问题。
4. **tag 指向该版本对应的 commit**（`--target`），这样 Release 页面能直接回溯
   当时的源码、`SHA256SUMS.txt` 和全部二进制。
5. **Latest 只有一个**：每次发新版时用 `--latest` 指定，其余全部
   `--latest=false`。旧入口 tag 保留但不标 Latest。

## 版本命名

| 库 | 格式 | 示例 |
|---|---|---|
| `swiss-gc-CN` | `v2154-zh-rN`（N 递增） | `v2154-zh-r5` |
| `swiss-gc-Imager` | `vMAJOR.MINOR` | `v1.2` |
| `swiss-gc-ftp` | `vMAJOR.MINOR` | `v1.0` |

`v2154-zh` 是最初的发布 tag，**冻结保留**，仅用于兼容论坛帖等已发出的下载链接；
其附件内容与 `v2154-zh-r5` 相同。以后不要再往这个 tag 上传任何文件。

## 标准发布流程（swiss-gc-CN）

```bash
# 1. 改代码 → 重编固件 → build-local.sh apploader → build_apploader.py 12 项校验
# 2. 同步 firmware/ igr/ 二进制、文档与 SHA256SUMS.txt，commit + push
# 3. 写本次的 notes（例如 notes_r6.md，含许可声明、校验值、安装步骤、版本历史表）
# 4. 只打包、不发布；确认包内固件与 target commit 的 SHA256SUMS 一致
python tools/publish_release.py --tag v2154-zh-r6 --notes notes_r6.md

# 5. 审阅 zip 内容后发布（--reuse 表示直接用上面生成的包，不重新打包）
python tools/publish_release.py --tag v2154-zh-r6 --notes notes_r6.md \
    --publish --reuse --latest
```

`tools/publish_release.py` 会在发布前检查本地 tag、远端 tag 和已有 Release，
**只要任一存在就直接拒绝**；它也不会覆盖任何已有 zip。历史归档时可用
`--archive <旧包路径>` 原样收录当时的实际发布包（逐字节不变）。

打包默认从 `--target` 的 git 树精确复现（禁用 `core.autocrlf`，逐条目与 blob
校验），因此每个 Release 的附件都能由对应 commit 重新生成。

## 历史归档（2026-11-10 补建）

| tag | commit | 固件 | 说明 |
|---|---|---|---|
| `v2154-zh-r5` | `d7846d6` | `1ec622cb` | 数字改用点阵（**Latest**） |
| `v2154-zh-r4` | `1d4671a` | `777243c4` | 修复中文游戏名缺字，6992 字 |
| `v2154-zh-r3` | `295ff08` | `7351321f` | 背景图切换（关闭 / 1~9） |
| `v2154-zh-r2` | `3354acb` | `2a52fd27` | 拉丁字形 0.85 缩放 |
| `v2154-zh-r1` | `e3d05fb` | `56711059` | 首发 |
| `v2154-zh` | — | `1ec622cb` | 旧入口，冻结 |

r1 / r3 / r4 / r5 的附件是当时实际发布包的原样副本；r2 当时未单独留包，
由 `3354acb` 的 git 树逐字节复现。
