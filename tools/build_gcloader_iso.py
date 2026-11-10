#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_gcloader_iso.py — 把 Swiss 汉化版 DOL 打包成可启动的 GameCube ISO。

除 GCLoader / 三个区域 ISO 外，同一套流程也用于 WODE (`eltorito-wode.hdr`)
与 Wiikey Fusion (`eltorito-wkf.hdr`)：`--all` 仍只生成常用 4 个，
`--all-variants` 生成全部 6 个，`--region wode|wkf` 可单独生成。
各启动方式的完整组装由 tools/build_boot_variants.py 负责。

上游 Swiss 的 Makefile 就是这么生成 GCLoader/boot.iso 的：

    mkisofs -R -J -G buildtools/iso/eltorito-gcode.hdr \\
        -no-emul-boot -eltorito-platform PPC -b swiss_rXXXX.dol \\
        -o dist/GCLoader/boot.iso swiss_rXXXX.dol LICENSE.txt

原理
----
* 32 KiB 的 eltorito-*.hdr 被 mkisofs 的 -G 原样写到 ISO 的前 16 个扇区，
  里面是 GameCube 光盘头 + "El Torito" apploader + 最小 FST。
* GameCube IPL 从 0x2440 加载这个 apploader；apploader 解析 El Torito
  boot catalog 的 validation entry / default entry，找到 boot image 的 LBA，
  把该处内容当作 DOL 校验并加载到内存执行。
* 因此 validation entry 的 platform ID 必须是 1 (PowerPC)，校验和必须有效；
  老版本 Windows mkisofs (如 VMware 附带的 2.01) 不支持
  -eltorito-platform PPC，会写成 0 (x86)。本脚本在生成后强制修正该字节
  并重算 16 位校验和，使输出与上游 CI (xorrisofs) 的产物等价。

用法
----
    python tools/build_gcloader_iso.py                 # 生成 GCLoader/boot.iso
    python tools/build_gcloader_iso.py --all          # 另加 NTSC-U/J/PAL 三个 ISO
    python tools/build_gcloader_iso.py --verify-only  # 只校验现有 ISO
    python tools/build_gcloader_iso.py --dol path/to/swiss.dol --out path/boot.iso

默认输入取本仓库 firmware/swiss.dol（packed 自解压 DOL，与 SD 卡 IPL.dol
同一次构建），默认头文件取 tools/iso/eltorito-*.hdr（源自上游 GPL-2.0 源码）。
若本机既没有 xorrisofs 也没有 mkisofs，脚本会给出安装/获取提示。

注意：ISO9660 会写入生成时刻的时间戳，因此同一份 DOL 重复生成得到的
SHA256 不同是正常现象；只要全部自检项通过，产物即等价。发布包内的
SHA256SUMS.txt 以当次实际发布的文件为准。
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

SECTOR = 2048
HDR_SIZE = 32768
DISC_MAGIC = b"\xc2\x33\x9f\x3d"

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ISODIR = HERE / "iso"

# region key -> (hdr 文件名, 期望的 6 字节 game ID, 输出相对路径)
REGIONS = {
    "gcode":  ("eltorito-gcode.hdr", b"GSWAGL", "gcloader/boot.iso"),
    "ntsc-u": ("eltorito-u.hdr",    b"GSWEGL", "iso/swiss-zh(ntsc-u).iso"),
    "ntsc-j": ("eltorito-j.hdr",    b"GSWWGL", "iso/swiss-zh(ntsc-j).iso"),
    "pal":    ("eltorito-e.hdr",    b"GSWPGL", "iso/swiss-zh(pal).iso"),
    "wode":   ("eltorito-wode.hdr", b"GWDPCF", "wode/swiss-zh(wode_extcfg).iso"),
    "wkf":    ("eltorito-wkf.hdr",  b"GSWAGL", "wiikeyfusion/swiss-zh.fzn"),
}

# --all 保持原来的「4 个常用 ISO」语义；WODE/WKF 由 --region 单独生成，
# 或由 build_boot_variants.py 组装成 .fzn / extcfg ISO。
BASE_REGIONS = ("gcode", "ntsc-u", "ntsc-j", "pal")


def le32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def winpath(p: Path) -> str:
    """原生 Win32 程序不认 MSYS 的 /d/... 路径，统一给它 Windows 路径。"""
    return str(Path(p).resolve()).replace("\\", "/")


# --------------------------------------------------------------------------
# 工具查找
# --------------------------------------------------------------------------
def find_mkisofs(explicit: str | None = None) -> str:
    candidates: list[str] = []
    if explicit:
        p = Path(explicit)
        candidates = [str(p)] if p.is_file() else [shutil.which(explicit) or ""]
    else:
        for name in ("xorrisofs", "mkisofs", "genisoimage"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
        if os.name == "nt":
            for drive in "CDEFGH":
                candidates += [
                    f"{drive}:/Program Files (x86)/VMware/VMware Workstation/mkisofs.exe",
                    f"{drive}:/Program Files/VMware/VMware Workstation/mkisofs.exe",
                    f"{drive}:/msys64/usr/bin/xorrisofs.exe",
                    f"{drive}:/msys64/usr/bin/mkisofs.exe",
                ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    raise RuntimeError(
        "找不到 mkisofs / xorrisofs。\n"
        "  Linux : sudo apt install xorriso   (或 cdrtools / genisoimage)\n"
        "  MSYS2 : pacman -S xorriso\n"
        "  Windows: 安装 cdrtools/xorriso，或用 --mkisofs 指定 mkisofs.exe 的完整路径\n"
        "            （VMware Workstation 安装目录里通常自带 mkisofs.exe）"
    )


def run_mkisofs(tool: str, hdr: Path, dol_name: str, out: Path, tmp: Path) -> str:
    """按上游 Makefile 的顺序调用，自适应是否支持 -eltorito-platform PPC。"""
    base = [tool, "-R", "-J", "-G", winpath(hdr), "-no-emul-boot"]
    tail = ["-b", dol_name, "-o", winpath(out), dol_name, "LICENSE.txt"]
    last = ""
    for extra in (["-eltorito-platform", "PPC"], []):
        if out.exists():
            out.unlink()
        cmd = base + extra + tail
        r = subprocess.run(cmd, cwd=str(tmp), capture_output=True,
                           text=True, errors="replace")
        if r.returncode == 0 and out.is_file() and out.stat().st_size > HDR_SIZE:
            return " ".join((r.stdout or "") + (r.stderr or "")).strip()
        last = ((r.stderr or "") + (r.stdout or "")).strip()
        if "eltorito-platform" not in last and not out.is_file():
            # 不是参数兼容性问题，别再盲目重试
            break
    raise RuntimeError(f"mkisofs 执行失败：\n{last}")


# --------------------------------------------------------------------------
# ISO9660 / El Torito 解析
# --------------------------------------------------------------------------
def find_boot_catalog(data: bytes) -> int:
    """从 Boot Record Volume Descriptor (type 0) 读出 boot catalog 的 LBA。"""
    for i in range(16, 64):
        v = data[i * SECTOR:(i + 1) * SECTOR]
        if len(v) < SECTOR or v[1:6] != b"CD001":
            break
        if v[0] == 0:
            return le32(v, 0x47)
        if v[0] == 255:
            break
    raise ValueError("ISO 中找不到 El Torito Boot Record Volume Descriptor")


def root_records(data: bytes) -> list[tuple[bytes, int, int, int]]:
    pvd = data[16 * SECTOR:17 * SECTOR]
    root = pvd[156:190]
    lba, size = le32(root, 2), le32(root, 10)
    buf = data[lba * SECTOR:lba * SECTOR + size]
    out, off = [], 0
    while off + 34 <= len(buf):
        length = buf[off]
        if length == 0:
            off = ((off // SECTOR) + 1) * SECTOR
            continue
        rec = buf[off:off + length]
        if len(rec) < 34:
            break
        nl = rec[32]
        out.append((rec[33:33 + nl], le32(rec, 2), le32(rec, 10), rec[25]))
        off += length
    return out


def fix_platform(data: bytearray) -> tuple[int, int, int]:
    """把 validation entry 的 platform ID 改成 PowerPC(1) 并重算校验和。"""
    cat = find_boot_catalog(data)
    off = cat * SECTOR
    val = bytearray(data[off:off + 32])
    if val[0] != 0x01 or val[30:32] != b"\x55\xaa":
        raise ValueError("El Torito validation entry 格式不正确")
    old = val[1]
    val[1] = 1
    struct.pack_into("<H", val, 28, 0)
    checksum = (-sum(struct.unpack("<16H", val))) & 0xFFFF
    struct.pack_into("<H", val, 28, checksum)
    data[off:off + 32] = val
    return cat, old, checksum


def check_dol(dol: bytes) -> tuple[bool, str]:
    if len(dol) < 0x100:
        return False, "DOL 太短"
    # DOL 头 0x100 字节：0x00 段偏移 / 0x48 段内存地址 / 0x90 段大小 /
    #                     0xD8 BSS 地址 / 0xDC BSS 大小 / 0xE0 入口点
    offs = struct.unpack(">18I", dol[0:0x48])
    addrs = struct.unpack(">18I", dol[0x48:0x90])
    sizes = struct.unpack(">18I", dol[0x90:0xD8])
    bss_addr, _bss_size, entry = struct.unpack(">3I", dol[0xD8:0xE4])

    # 以下逐条对应 eltorito hdr 内 "El Torito" apploader 的报错字符串：
    #   detected unaligned section offset / unaligned section address
    #   segment past DOL file size / segment above 0x81200000
    #   BSS segment below 2GB / entry point out of text segment
    nseg = 0
    for i, (o, a, s) in enumerate(zip(offs, addrs, sizes)):
        if not s:
            continue
        nseg += 1
        if o % 32 or a % 32:
            return False, f"第 {i} 段未按 32 字节对齐"
        if o < 0x100:
            return False, f"第 {i} 段偏移落在 DOL 头内 (0x{o:x})"
        if o + s > len(dol):
            return False, f"第 {i} 段越界 (0x{o:x}+0x{s:x} > 0x{len(dol):x})"
        if a + s > 0x81200000:
            return False, f"第 {i} 段地址超过 0x81200000"
    if bss_addr < 0x80000000:
        return False, f"BSS 地址异常 0x{bss_addr:08x}"
    if not any(addrs[i] <= entry < addrs[i] + sizes[i]
               for i in range(7) if sizes[i]):
        return False, f"入口 0x{entry:08x} 不在任何 text 段内"
    return True, (f"entry=0x{entry:08x}, {nseg} 段 32B 对齐、不越界、"
                  f"末段 0x{max(a + s for a, s in zip(addrs, sizes) if s):08x}")


def verify(iso: Path, hdr: Path, dol: bytes, game_id: bytes,
           reference: Path | None = None) -> tuple[bool, dict]:
    data = iso.read_bytes()
    expected_hdr = hdr.read_bytes()
    checks: list[tuple[str, bool, str]] = []

    def chk(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, bool(ok), detail))

    chk("文件大小为 2048 整数倍", len(data) % SECTOR == 0, f"{len(data)} B / {len(data)//SECTOR} 扇区")
    chk("前 32 KiB 与 eltorito hdr 逐字节一致",
        data[:HDR_SIZE] == expected_hdr, f"hdr={hdr.name}")
    chk("光盘头 magic 0xC2339F3D", data[0x1C:0x20] == DISC_MAGIC)
    chk("Game ID 匹配区域", data[0:6] == game_id,
        f"{data[0:6].decode('ascii', 'replace')} (期望 {game_id.decode()})")

    pvd = data[16 * SECTOR:17 * SECTOR]
    chk("PVD 有效 (type=1, CD001)", pvd[0] == 1 and pvd[1:6] == b"CD001")
    vol_size = le32(pvd, 80)
    chk("PVD volume space size 正确", vol_size == len(data) // SECTOR,
        f"{vol_size} 扇区")

    cat = find_boot_catalog(data)
    val = data[cat * SECTOR:cat * SECTOR + 32]
    ent = data[cat * SECTOR + 32:cat * SECTOR + 64]
    chk("Boot catalog validation entry", val[0] == 1, f"@LBA {cat}")
    chk("platform ID = PowerPC (1)", val[1] == 1, f"实际 {val[1]}")
    chk("validation 校验和", sum(struct.unpack("<16H", val)) & 0xFFFF == 0,
        f"0x{struct.unpack_from('<H', val, 28)[0]:04x}")
    chk("validation 结束标志 0xAA55", val[30:32] == b"\x55\xaa")
    chk("default entry 可引导 (0x88)", ent[0] == 0x88)
    chk("boot media = 无模拟 (0)", ent[1] == 0)

    boot_lba = le32(ent, 8)
    boot_sectors = struct.unpack_from("<H", ent, 6)[0]
    boot_nbytes = boot_sectors * 512
    chk("boot image LBA 在镜像内", 0 < boot_lba < len(data) // SECTOR,
        f"LBA {boot_lba}")
    chk("boot image 内容 == 源 DOL",
        data[boot_lba * SECTOR:boot_lba * SECTOR + len(dol)] == dol,
        f"{len(dol)} B, catalog 声明 {boot_nbytes} B")
    chk("catalog 声明长度覆盖 DOL", boot_nbytes >= len(dol))

    ok_dol, detail = check_dol(dol)
    chk("DOL 头满足 apploader 的全部校验项", ok_dol, detail)

    recs = [r for r in root_records(data) if r[1] == boot_lba and not (r[3] & 2)]
    chk("根目录存在指向 boot image 的记录", len(recs) == 1,
        recs[0][0].decode("ascii", "replace") if recs else "-")
    if recs:
        chk("目录记录中的 DOL 大小正确", recs[0][2] == len(dol),
            f"{recs[0][2]} B")
    chk("光盘内包含 LICENSE.TXT", any(r[0].startswith(b"LICENSE") for r in root_records(data)))

    if reference and reference.is_file():
        ref = reference.read_bytes()
        ref_cat = find_boot_catalog(ref)
        ref_ent = ref[ref_cat * SECTOR + 32:ref_cat * SECTOR + 64]
        chk("与官方 ISO 布局一致 (catalog/boot LBA)",
            ref_cat == cat and le32(ref_ent, 8) == boot_lba,
            f"官方 catalog={ref_cat} boot={le32(ref_ent, 8)} / 本镜像 {cat}/{boot_lba}")

    info = {
        "iso": str(iso),
        "size": len(data),
        "sectors": len(data) // SECTOR,
        "sha256": hashlib.sha256(data).hexdigest(),
        "dol_size": len(dol),
        "dol_sha256": hashlib.sha256(dol).hexdigest(),
        "catalog_lba": cat,
        "boot_lba": boot_lba,
        "checks": checks,
    }
    return all(c[1] for c in checks), info


# --------------------------------------------------------------------------
def build_one(region: str, dol: bytes, dol_name: str, license_src: Path,
              out: Path, tool: str, reference: Path | None) -> tuple[bool, dict]:
    hdr_name, game_id, _ = REGIONS[region]
    hdr = ISODIR / hdr_name
    if not hdr.is_file():
        raise FileNotFoundError(f"缺少头文件或路径不对: {hdr}")
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="swissiso_") as td:
        tmp = Path(td)
        (tmp / dol_name).write_bytes(dol)
        shutil.copyfile(license_src, tmp / "LICENSE.txt")
        log = run_mkisofs(tool, hdr, dol_name, out, tmp)

    data = bytearray(out.read_bytes())
    cat, old_platform, checksum = fix_platform(data)
    out.write_bytes(data)
    ok, info = verify(out, hdr, dol, game_id, reference)
    info["region"] = region
    info["game_id"] = game_id.decode()
    info["platform_before"] = old_platform
    info["platform_checksum"] = f"0x{checksum:04x}"
    info["mkisofs"] = log
    return ok, info


def print_report(info: dict) -> None:
    print(f"\n=== {info.get('region', '-')}  {info['iso']} ===")
    print(f"  大小        : {info['size']} B ({info['sectors']} 扇区)")
    print(f"  Game ID     : {info.get('game_id', '-')}")
    print(f"  DOL         : {info['dol_size']} B  sha256 {info['dol_sha256'][:16]}…")
    print(f"  catalog LBA : {info['catalog_lba']}   boot LBA : {info['boot_lba']}")
    print(f"  platform    : {info.get('platform_before', '-')} -> 1, checksum {info.get('platform_checksum','-')}")
    print(f"  ISO SHA256  : {info['sha256']}")
    for name, ok, detail in info["checks"]:
        print(f"  [{'OK' if ok else 'FAIL':4}] {name}" + (f"  ({detail})" if detail else ""))
    print(f"  自检        : {sum(1 for c in info['checks'] if c[1])}/{len(info['checks'])} 通过"
          f"  -> {'PASS' if all(c[1] for c in info['checks']) else 'FAIL'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="生成/校验 GCLoader 可启动的 Swiss ISO")
    ap.add_argument("--dol", type=Path, default=REPO / "firmware" / "swiss.dol",
                    help="packed 自解压 DOL（默认 firmware/swiss.dol）")
    ap.add_argument("--license", type=Path, default=REPO / "LICENSE-GPL-2.0.txt",
                    help="写入光盘根目录的许可证（默认 LICENSE-GPL-2.0.txt）")
    ap.add_argument("--out-dir", type=Path, default=REPO, help="输出根目录")
    ap.add_argument("--out", type=Path, help="仅生成单个 ISO 到指定路径")
    ap.add_argument("--region", choices=list(REGIONS), default="gcode")
    ap.add_argument("--all", action="store_true", help="生成 GCLoader + NTSC-U/J/PAL 共 4 个 ISO")
    ap.add_argument("--all-variants", action="store_true",
                    help="连同 WODE / WiikeyFusion 头一起生成全部 6 个 ISO")
    ap.add_argument("--name", default="swiss-zh.dol", help="光盘内 DOL 文件名")
    ap.add_argument("--mkisofs", help="显式指定 mkisofs/xorrisofs 可执行文件")
    ap.add_argument("--reference", type=Path, help="官方 boot.iso，用于对比布局（可选）")
    ap.add_argument("--verify-only", action="store_true", help="只校验已有 ISO，不重新生成")
    args = ap.parse_args()

    dol = args.dol.read_bytes()
    ok_dol, detail = check_dol(dol)
    print(f"源 DOL : {args.dol}  ({len(dol)} B, {detail})")
    if not ok_dol:
        print("错误：源 DOL 头不合法", file=sys.stderr)
        return 2
    if not args.license.is_file():
        print(f"错误：找不到许可证文件 {args.license}", file=sys.stderr)
        return 2

    if args.all_variants:
        regions = list(REGIONS)
    elif args.all:
        regions = list(BASE_REGIONS)
    else:
        regions = [args.region]
    if args.out:
        regions = [args.region]

    if args.verify_only:
        tool = ""
    else:
        try:
            tool = find_mkisofs(args.mkisofs)
        except RuntimeError as e:
            print(f"错误：{e}", file=sys.stderr)
            return 2
        print(f"ISO 工具: {tool}")

    results = []
    for region in regions:
        hdr_name, game_id, rel = REGIONS[region]
        out = args.out if args.out else args.out_dir / rel
        if args.verify_only:
            if not out.is_file():
                print(f"错误：找不到待校验的 ISO {out}", file=sys.stderr)
                return 2
            ok, info = verify(out, ISODIR / hdr_name, dol, game_id, args.reference)
            info["region"] = region
            info["game_id"] = game_id.decode()
        else:
            ok, info = build_one(region, dol, args.name, args.license, out,
                                 tool, args.reference)
        print_report(info)
        results.append((region, ok, info))

    failed = [r for r, ok, _ in results if not ok]
    print("\n总计: " + (f"{len(results)} 个 ISO 全部通过自检" if not failed
                       else f"失败: {', '.join(failed)}"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
