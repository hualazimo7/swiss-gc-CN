#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为当前汉化 Swiss 生成 / 校验 / 部署「游戏内复位」用的 apploader.img。

为什么不能用官方 release 里的 apploader.img
------------------------------------------
Swiss 的 IGR Type = Apploader 会把 <启动设备>:/swiss/patches/apploader.img
当作游戏的 apploader 注入到 0x2440。这个文件不是通用补丁：它由
buildtools/dol2ipl.py 把 cube/packer/reboot.dol 展平成内存镜像而来，而
reboot.dol 里链接了 executable.xz —— **本次编译的 Swiss 压缩镜像**。
按 A+Z+Start 复位后，机器回到的是这个文件里内嵌的那份 Swiss。
拿开源/官方版 apploader.img，内嵌的就是另一份（另一 commit、未汉化、
内存布局不同）的 Swiss，复位后自然黑屏、重启或回到英文原版。

因此：每次 swiss.elf 变化，都必须重跑 `make apploader` 重新生成。

用法
----
    python tools/build_apploader.py --build          # 调 make apploader 重编译
    python tools/build_apploader.py                 # 校验 + 生成 SD 卡离线包
    python tools/build_apploader.py --upload <GameCube-IP>
    python tools/build_apploader.py --img X.img     # 只校验某个现成 img
    python tools/build_apploader.py --no-package    # 只校验不产出

校验链（逐级字节比对，任何一环断掉都判失败）：
    swiss.elf --objcopy--> executable.bin --7z--> executable.xz
             --link--> reboot.dol --dol2ipl--> apploader.img
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
import zlib
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TOOLS = Path(__file__).resolve().parent
I18N = TOOLS.parent
# Public-friendly defaults: override with --repo or env vars.
# SWISS_GC_REPO / DEVKITPPC / MSYS_BASH let the tool work on any machine.
REPO_CANDIDATES = tuple(
    p for p in [
        Path(os.environ["SWISS_GC_REPO"]) if os.environ.get("SWISS_GC_REPO") else None,
        I18N.parent / "swiss-gc",
        I18N / "swiss-gc",
        Path.cwd() / "swiss-gc",
        Path("C:/swiss-gc"),
    ] if p is not None
)
_DEVKITPPC = Path(os.environ.get("DEVKITPPC", "C:/msys64/opt/devkitpro/devkitPPC"))
OBJCOPY = _DEVKITPPC / "bin" / "powerpc-eabi-objcopy.exe"
MSYS_BASH = Path(os.environ.get("MSYS_BASH", "C:/msys64/usr/bin/bash.exe"))

REMOTE_PATH = "swiss/patches/apploader.img"
REMOTE_ROOT = "sdb:/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_repo(explicit: str | None) -> Path:
    candidates = [Path(explicit)] if explicit else list(REPO_CANDIDATES)
    for p in candidates:
        if (p / "Makefile").is_file() and (p / "buildtools" / "dol2ipl.py").is_file():
            return p
    raise SystemExit("找不到 swiss-gc 仓库，请用 --repo 指定路径")


def load_flatten(repo: Path):
    spec = importlib.util.spec_from_file_location(
        "dol2ipl_local", repo / "buildtools" / "dol2ipl.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.flatten_dol


def msys_path(p: Path) -> str:
    s = str(p).replace("\\", "/")
    drive, rest = s.split(":", 1)
    return f"/{drive.lower()}{rest}"


def run_build(repo: Path) -> None:
    """通过 build-local.sh 跑 make apploader（它会处理 MSYS2 缺 python3 的问题）。"""
    if not MSYS_BASH.is_file():
        raise SystemExit(f"找不到 MSYS2 bash：{MSYS_BASH}")
    script = msys_path(repo / "build-local.sh")
    cmd = [str(MSYS_BASH), "-lc", f'bash "{script}" apploader']
    print("==> 重编译 packer 并生成 apploader.img")
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-4000:])
    if r.stderr:
        print(r.stderr[-2000:], file=sys.stderr)
    if r.returncode != 0:
        raise SystemExit(f"make apploader 失败（exit {r.returncode}）")


def verify(img: Path, repo: Path, deep: bool = True):
    """返回 [(检查项, 是否通过, 说明), ...] 和摘要 dict。"""
    checks: list[tuple[str, bool, str]] = []

    def ck(label: str, ok: bool, detail: str = "") -> None:
        checks.append((label, bool(ok), detail))

    if not img.is_file():
        return [("apploader.img 存在", False, str(img))], {}

    data = img.read_bytes()
    reboot = repo / "cube" / "packer" / "reboot.dol"
    swiss_elf = repo / "cube" / "swiss" / "swiss.elf"
    exe_bin = repo / "cube" / "packer" / "build" / "executable.bin"
    exe_xz = repo / "cube" / "packer" / "build" / "executable.xz"

    ck("源文件齐全", reboot.is_file() and swiss_elf.is_file() and exe_bin.is_file()
       and exe_xz.is_file(), "reboot.dol / swiss.elf / executable.bin / executable.xz")
    if not all(p.is_file() for p in (reboot, swiss_elf, exe_bin, exe_xz)):
        return checks, {}

    ck("文件长度 ≥ 32+1", len(data) >= 64, f"{len(data)} B")
    if len(data) < 64:
        return checks, {}

    date_b, entry, size, reboot_size, crc = struct.unpack(">16s 4I", data[:32])
    payload = data[32:]
    date = date_b.split(b"\0", 1)[0].decode("latin-1", "replace")

    ck("ApploaderHeader.entry == 0", entry == 0, f"0x{entry:08X}")
    ck("ApploaderHeader.size == 0（纯 reboot 镜像）", size == 0, str(size))
    ck("rebootSize 与 payload 长度一致", reboot_size == len(payload),
       f"header={reboot_size} / payload={len(payload)}")
    ck("CRC32 与 payload 一致", crc == zlib.crc32(payload) & 0xFFFFFFFF,
       f"0x{crc:08X}")
    ck("date 以 '*' 开头（patcher.c 走 0x81300000 地址分支）",
       date.startswith("*"), repr(date))

    flatten = load_flatten(repo)
    e2, l2, flat = flatten(bytearray(reboot.read_bytes()))
    # dol2ipl.py masks both with 0x017FFFFF before the 0x81300000 check.
    ck("reboot.dol 入口/加载地址正确",
       (e2 & 0x017FFFFF | 0x80000000) == 0x81300000 and (l2 & 0x017FFFFF) == 0x01300000,
       f"entry=0x{e2:08X} load=0x{l2:08X} masked=0x{l2 & 0x017FFFFF:08X}")
    ck("payload 与 reboot.dol 展平镜像逐字节相同", bytes(flat) == payload,
       f"{len(flat)} B")

    xz = exe_xz.read_bytes()
    off = payload.find(xz)
    ck("payload 内嵌本次编译的 executable.xz", off >= 0,
       f"offset=0x{off:X} / {len(xz)} B" if off >= 0 else "未找到")

    ck("reboot.dol 不早于 swiss.elf（配套）",
       reboot.stat().st_mtime >= swiss_elf.stat().st_mtime - 1,
       f"reboot={reboot.stat().st_mtime:.0f} elf={swiss_elf.stat().st_mtime:.0f}")

    if deep and OBJCOPY.is_file():
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "swiss.bin"
            r = subprocess.run([str(OBJCOPY), "-O", "binary", str(swiss_elf), str(tmp)],
                               capture_output=True)
            ok = r.returncode == 0 and tmp.is_file() and tmp.read_bytes() == exe_bin.read_bytes()
            ck("executable.bin 就是当前 swiss.elf 的镜像", ok,
               sha256(exe_bin.read_bytes())[:16] if ok else r.stderr.decode("latin-1", "replace")[:120])
    elif deep:
        ck("objcopy 可用（深度校验）", False, f"缺少 {OBJCOPY}")

    summary = {
        "img": str(img),
        "bytes": len(data),
        "sha256": sha256(data),
        "date": date,
        "reboot_size": reboot_size,
        "crc": f"0x{crc:08X}",
    }
    return checks, summary


def make_package(img: Path, repo: Path, outdir: Path, summary: dict) -> Path:
    pkg = outdir / "swiss" / "patches"
    pkg.mkdir(parents=True, exist_ok=True)
    shutil.copy2(img, pkg / "apploader.img")

    text = f"""Swiss 游戏内复位（IGR / Apploader）配套文件
==========================================

本包由汉化版 Swiss 源码现场生成，版本标记：{summary.get('date', '')}
apploader.img SHA-256：{summary.get('sha256', '')}
大小：{summary.get('bytes', 0)} 字节

【安装】
把本目录下的 swiss 文件夹整个拷贝/合并到 SD 卡根目录，最终路径必须是：
    SD:\\swiss\\patches\\apploader.img
（不要改文件名，不要放到子目录里。）

【设置】
Swiss → 设置 → 游戏全局 → 游戏内复位 → 选「Apploader」。
配置文件里对应一行：IGRType=Apploader
注意：apploader.img 要放在「启动这个游戏所用的设备」的 /swiss/patches/ 下。
从 SD 卡启动就放 SD 卡；从 SMB/FTP 共享启动就放该共享根目录的同样位置。

【使用】
    A + Z + Start   → 退出游戏，回到 Swiss 主界面
    R + Z + Start   → 重启当前游戏

【重要】
1. 这个文件内嵌了本次编译的汉化 Swiss（reboot.dol → executable.xz），
   与 SD 卡根目录的 IPL.dol 是同一份源码的产物，两者版本必须一致。
2. 绝对不要使用官方 / 开源 release 包里的 apploader.img：它内嵌的是
   另一份 Swiss，复位后会黑屏、反复重启，或回到英文原版。
3. 每次重新编译/升级 Swiss 之后，都要重新生成并覆盖这个文件。
   生成命令：build-local.bat apploader
   校验/打包：python tools/build_apploader.py --build
"""
    (outdir / "【必读】游戏内复位-安装说明.txt").write_text(text, encoding="utf-8")
    (outdir / "SHA256SUMS.txt").write_text(
        f"{summary.get('sha256', '')}  swiss/patches/apploader.img\n", encoding="utf-8"
    )

    # Zip holds the package contents at its root, so extracting straight onto
    # the SD card produces SD:\swiss\patches\apploader.img.
    zip_path = outdir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(outdir.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(outdir))
    return outdir


def upload_and_verify(img: Path, host: str) -> tuple[bool, str]:
    sys.path.insert(0, str(TOOLS))
    from upload_file import upload  # noqa: E402

    sent, status, reply = upload(host, str(img), REMOTE_PATH,
                                 root=REMOTE_ROOT, progress=False)
    if not reply.startswith("ok "):
        return False, f"上传失败：{status} / {reply}"

    url = f"http://{host}/get?path={REMOTE_ROOT}{REMOTE_PATH}"
    with urllib.request.urlopen(url, timeout=90) as resp:
        body = resp.read()
    local = img.read_bytes()
    if body != local:
        return False, (f"回读不一致：远端 {len(body)} B / 本地 {len(local)} B；"
                       f"远端响应前 80 字节 = {body[:80]!r}")
    return True, f"{sent} 字节写入 {REMOTE_ROOT}{REMOTE_PATH}，回读 SHA-256 一致"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", help="swiss-gc 仓库路径（默认自动探测）")
    ap.add_argument("--img", help="要校验的 apploader.img（默认 dist/Apploader/...）")
    ap.add_argument("--build", action="store_true", help="先跑 make apploader 重新生成")
    ap.add_argument("--out-dir", help="SD 卡离线包输出目录（默认 dist/SDCard_IGR）")
    ap.add_argument("--no-package", action="store_true", help="不生成离线包")
    ap.add_argument("--no-deep", action="store_true", help="跳过 objcopy 深度校验")
    ap.add_argument("--upload", metavar="IP", help="顺带上传到实机 SD 卡并回读校验")
    args = ap.parse_args(argv)

    repo = find_repo(args.repo)
    if args.build:
        run_build(repo)
    img = Path(args.img) if args.img else repo / "dist" / "Apploader" / "swiss" / "patches" / "apploader.img"

    checks, summary = verify(img, repo, deep=not args.no_deep)
    print(f"\n=== 校验 {img} ===")
    for label, ok, detail in checks:
        print(f"  [{'OK' if ok else '!!'}] {label}" + (f"  ({detail})" if detail else ""))
    if summary:
        print(f"\n  date       = {summary['date']}")
        print(f"  rebootSize = {summary['reboot_size']} B")
        print(f"  CRC32      = {summary['crc']}")
        print(f"  SHA-256    = {summary['sha256']}")
    failed = [c for c in checks if not c[1]]
    if failed:
        print(f"\n校验失败 {len(failed)} 项，未产出/上传任何东西。", file=sys.stderr)
        return 1
    print(f"\n校验通过 {len(checks)}/{len(checks)} 项。")

    if not args.no_package:
        outdir = Path(args.out_dir) if args.out_dir else repo / "dist" / "SDCard_IGR"
        make_package(img, repo, outdir, summary)
        print(f"SD 卡离线包：{outdir}")

    if args.upload:
        print(f"\n=== 上传到 {args.upload} ===")
        ok, msg = upload_and_verify(img, args.upload)
        print(("  [OK] " if ok else "  [!!] ") + msg)
        if not ok:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
