#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按启动方式生成 Swiss 简中版的专用文件。

上游 Swiss 的发布包按 JB / ODE 方式分目录提供不同的引导文件，本脚本复刻
顶层 Makefile 的 build / build-AR / build-wii / recovery-iso / build-gci
目标，把同一份汉化固件包装成各设备需要的形态：

    ActionReplay/  AUTOEXEC.DOL + SDLOADER.BIN      (直接改名 + 同批 SD 加载器)
    FlippyDrive/   EXTRACT_TO_ROOT.zip -> boot.dol   (直接改名)
    WiikeyFusion/  *.fzn / *.fzn.fw / RecoveryISO/  (wkf 头 ISO + 1856K 补齐 + 恢复盘)
    Wii/           EXTRACT_TO_ROOT.zip -> apps/swiss-gc/boot.dol
                   (Wii 模式 booter 内嵌同批 reboot.dol)
    WODE/          swiss-zh(wode_extcfg).iso        (wode 头 ISO)
    MemoryCard/    boot.gci / xeno.gci              (记忆卡存档格式)

所有输入都在本仓库内：firmware/swiss.dol、tools/boot/*、tools/iso/*.hdr、
LICENSE-GPL-2.0.txt、NOTICE.md、Licenses/*。ISO 复用 build_gcloader_iso.py。
唯一外部依赖是 mkisofs / xorrisofs（生成 ISO 时需要），--verify-only 不需要。

用法::

    python tools/build_boot_variants.py            # 生成全部并自检
    python tools/build_boot_variants.py --verify-only
    python tools/build_boot_variants.py --only wii,wode

重新运行会覆盖工作区里的同名产物；已发布的 Release 附件不可改动，
改产物请发布新 tag（见 docs/RELEASE_POLICY.md）。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import lzma
import re
import struct
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
BOOT = HERE / "boot"
MAIN_DOL = REPO / "firmware" / "swiss.dol"
LICENSE_GPL = REPO / "LICENSE-GPL-2.0.txt"
NOTICE = REPO / "NOTICE.md"
LICENSES_DIR = REPO / "Licenses"
DOL_NAME = "swiss-zh.dol"
FZN_SIZE = 1856 * 1024            # Makefile: truncate -s 1856K
RECOVERY_HDR_SIZE = 32 * 1024     # Makefile: dd bs=32K count=1 conv=notrunc
WII_BASE = 0x80800000 - 32        # dol2ipl.py: gchomebrew dol 段地址
DOL_MAGIC = b"gchomebrew dol"

# 复用 ISO 生成/校验模块
_spec = importlib.util.spec_from_file_location(
    "swiss_iso", HERE / "build_gcloader_iso.py")
iso = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(iso)

CHECKS: list[tuple[str, bool, str]] = []


def chk(name: str, ok: bool, detail: str = "") -> bool:
    CHECKS.append((name, bool(ok), detail))
    print(f"  [{'OK' if ok else 'FAIL':4}] {name}" + (f"  ({detail})" if detail else ""))
    return bool(ok)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_xz(blob: bytes) -> bytes:
    """定位并完整取出 blob 内嵌的 xz 流（用于确认三个产物出自同一次构建）。"""
    start = blob.find(b"\xfd7zXZ\x00")
    if start < 0:
        raise ValueError("找不到 xz 流")
    dec = lzma.LZMADecompressor()
    dec.decompress(blob[start:])
    if not dec.eof:
        raise ValueError("xz 流不完整")
    length = len(blob) - start - len(dec.unused_data)
    return blob[start:start + length]


def dol_segments(data: bytes):
    offs = struct.unpack(">18I", data[0:0x48])
    addrs = struct.unpack(">18I", data[0x48:0x90])
    sizes = struct.unpack(">18I", data[0x90:0xD8])
    return [(i, o, a, s) for i, (o, a, s) in enumerate(zip(offs, addrs, sizes)) if s]


def append_dol(data: bytes, trailer: bytes, base_address: int) -> bytes:
    """复刻 dol2ipl.py 的 append_dol：把 DOL 追加到空闲段（或替换同地址旧段）。"""
    header = struct.unpack(">64I", data[:256])
    offsets, addresses, sizes = list(header[:18]), list(header[18:36]), list(header[36:54])
    for section, (offset, address, size) in enumerate(
            zip(offsets[7:], addresses[7:], sizes[7:]), 7):
        if address == base_address and offset + size == len(data):
            data = data[:offset]
            offset = address = size = 0
        if offset == 0:
            offset, address, size = len(data), base_address, len(trailer)
            data = data + trailer
            break
    offsets[section] = offset
    addresses[section] = address
    sizes[section] = size
    new_header = struct.pack(">64I", *offsets, *addresses, *sizes, *header[54:64])
    return new_header + data[256:]


def make_wii_boot(booter: bytes, reboot_dol: bytes) -> bytes:
    magic_header = struct.pack(">32s", DOL_MAGIC)
    return append_dol(booter, magic_header + reboot_dol, WII_BASE)


def parse_gci_icon(cpp: Path) -> bytes:
    """从上游 dol2gci.cpp 抽出 const u8 dol_icon[] 的字节，避免附带二进制图标。"""
    text = cpp.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"dol_icon\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;", text, re.S)
    if not m:
        raise ValueError("dol2gci.cpp 里找不到 dol_icon[]")
    return bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", m.group(1)))


def make_gci(dol: bytes, filename: str, icon: bytes) -> bytes:
    """复刻 buildtools/dol2gci.cpp 的 GCI 组装逻辑（纯 Python，跨平台）。"""
    icon_size = (len(icon) + 31) & ~31
    data_size = 64 + icon_size + len(dol)
    blocks = (data_size + 8191) // 8192
    out = bytearray(64 + blocks * 8192)
    out[0x00:0x04] = b"DOLX"
    out[0x04:0x06] = b"00"
    out[0x06] = 0xFF
    out[0x07] = 0x00
    out[0x08:0x08 + min(len(filename), 31)] = filename.encode("ascii")[:31]
    struct.pack_into(">I", out, 0x28, 0)
    struct.pack_into(">I", out, 0x2C, 0x140)
    struct.pack_into(">H", out, 0x30, 0x0001)
    struct.pack_into(">H", out, 0x32, 0x0002)
    out[0x34], out[0x35] = 0x04, 0x00
    struct.pack_into(">H", out, 0x36, 0)
    struct.pack_into(">H", out, 0x38, blocks)
    struct.pack_into(">H", out, 0x3A, 0xFFFF)
    struct.pack_into(">I", out, 0x3C, 0x100)
    out[0x40:0x140] = dol[:256]
    for i in range(18):
        off = 0x40 + i * 4
        pos = struct.unpack_from(">I", out, off)[0]
        if pos >= 0x100:
            struct.pack_into(">I", out, off, pos + 0x40 + icon_size)
    out[0x140:0x180] = b"Dolphin Application".ljust(64, b"\x00")
    out[0x160:0x160 + min(len(filename), 31)] = filename.encode("ascii")[:31]
    out[0x180:0x180 + len(icon)] = icon
    out[0x180 + icon_size:0x180 + icon_size + len(dol) - 256] = dol[256:]
    return bytes(out)


def write_zip_stored(out: Path, entries: list[tuple[str, bytes]]) -> None:
    """官方用 zip -0（不压缩）打包 EXTRACT_TO_ROOT.zip，这里保持一致。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
        dirs: set[str] = set()
        for name, data in entries:
            parts = name.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                d = "/".join(parts[:i]) + "/"
                if d not in dirs:
                    dirs.add(d)
                    zi = zipfile.ZipInfo(d)
                    zi.compress_type = zipfile.ZIP_STORED
                    zi.external_attr = 0o40775 << 16 | 0x10
                    z.writestr(zi, b"")
            zi = zipfile.ZipInfo(name)
            zi.compress_type = zipfile.ZIP_STORED
            zi.external_attr = 0o100644 << 16
            z.writestr(zi, data)


def gen_iso(region: str, out: Path, dol: bytes, tool: str) -> bool:
    ok, info = iso.build_one(region, dol, DOL_NAME, LICENSE_GPL, out, tool, None)
    return chk(f"ISO {region} 自检", ok,
               f"{info['size']} B, {sum(1 for c in info['checks'] if c[1])}/{len(info['checks'])} 项")


# --------------------------------------------------------------------------
def build_action_replay(root: Path, main: bytes, sdloader: bytes, verify: bool) -> list[Path]:
    print("\n=== ActionReplay ===")
    d = root / "ActionReplay"
    auto, sdl = d / "AUTOEXEC.DOL", d / "SDLOADER.BIN"
    if not verify:
        d.mkdir(parents=True, exist_ok=True)
        auto.write_bytes(main)
        sdl.write_bytes(sdloader)
    if not (auto.is_file() and sdl.is_file()):
        chk("ActionReplay 文件齐全", False, "缺少产物")
        return []
    chk("AUTOEXEC.DOL == 主 DOL", auto.read_bytes() == main, f"{auto.stat().st_size} B")
    chk("SDLOADER.BIN 与主固件同批", extract_xz(sdl.read_bytes()) == extract_xz(main),
        f"{sdl.stat().st_size} B")
    return [auto, sdl]


def build_flippy(root: Path, main: bytes, verify: bool) -> list[Path]:
    print("\n=== FlippyDrive ===")
    z = root / "FlippyDrive" / "EXTRACT_TO_ROOT.zip"
    if not verify:
        write_zip_stored(z, [("boot.dol", main)])
    if not z.is_file():
        chk("FlippyDrive zip 存在", False)
        return []
    with zipfile.ZipFile(z) as f:
        names = f.namelist()
        ok = chk("zip 内含 boot.dol", "boot.dol" in names, ", ".join(n for n in names if not n.endswith("/")))
        ok &= chk("boot.dol == 主 DOL", "boot.dol" in names and f.read("boot.dol") == main)
        ok &= chk("zip 不压缩 (store)", all(i.compress_type == 0 for i in f.infolist()))
    return [z] if ok else []


def build_wiikeyfusion(root: Path, main: bytes, tool: str, verify: bool) -> list[Path]:
    print("\n=== WiikeyFusion ===")
    d = root / "WiikeyFusion"
    fzn = d / "swiss-zh.fzn"
    fw = d / "swiss-zh.fzn.fw"
    rec = d / "RecoveryISO" / "swiss-zh_Recovery.iso"
    pal = root / "iso" / "swiss-zh(pal).iso"
    if not verify:
        d.mkdir(parents=True, exist_ok=True)
        rec.parent.mkdir(parents=True, exist_ok=True)
        raw = d / ".fzn.raw"
        if not gen_iso("wkf", raw, main, tool):
            return []
        data = raw.read_bytes()
        if len(data) > FZN_SIZE:
            chk("fzn 补齐到 1856K", False, f"ISO 已有 {len(data)} B，超过 1856K")
            return []
        fzn.write_bytes(data.ljust(FZN_SIZE, b"\x00"))
        raw.unlink()
        fw.write_bytes((BOOT / "autoboot.fzn.fw").read_bytes())
        if not pal.is_file():
            chk("PAL ISO 存在（Recovery 用）", False, str(pal))
            return []
        recovery = bytearray(pal.read_bytes())
        bootloader = (BOOT / "recovery_bootloader.iso").read_bytes()
        recovery[:RECOVERY_HDR_SIZE] = bootloader[:RECOVERY_HDR_SIZE]
        rec.write_bytes(recovery)
    ok = True
    if fzn.is_file():
        data = fzn.read_bytes()
        ok &= chk("fzn 大小 = 1856K", len(data) == FZN_SIZE, f"{len(data)} B")
        ok &= chk("fzn 盘头 = wkf.hdr", data[:32768] == (HERE / "iso" / "eltorito-wkf.hdr").read_bytes())
        ok &= chk("fzn 内含主 DOL", main in data)
        ok &= chk("fzn 尾部为补零", data[FZN_SIZE - 4096:] == b"\x00" * 4096)
    else:
        ok &= chk("fzn 存在", False)
    ok &= chk("fzn.fw 存在且 12 KiB", fw.is_file() and fw.stat().st_size == 12288,
              f"{fw.stat().st_size if fw.is_file() else 0} B")
    if rec.is_file():
        r = rec.read_bytes()
        bl = (BOOT / "recovery_bootloader.iso").read_bytes()
        ok &= chk("Recovery 前 32K = 引导器", r[:RECOVERY_HDR_SIZE] == bl[:RECOVERY_HDR_SIZE],
                  f"Game ID {r[:6].decode('ascii', 'replace')}")
        ok &= chk("Recovery 盘体 = PAL ISO", r[RECOVERY_HDR_SIZE:] == pal.read_bytes()[RECOVERY_HDR_SIZE:]
                  if pal.is_file() else False)
    else:
        ok &= chk("Recovery ISO 存在", False)
    return [fzn, fw, rec] if ok else []


def build_wii(root: Path, reboot_dol: bytes, verify: bool) -> list[Path]:
    print("\n=== Wii ===")
    z = root / "Wii" / "EXTRACT_TO_ROOT.zip"
    if not verify:
        booter = (BOOT / "wii_booter.dol").read_bytes()
        boot = make_wii_boot(booter, reboot_dol)
        entries = [(f"apps/swiss-gc/boot.dol", boot),
                   ("apps/swiss-gc/LICENSE.txt", LICENSE_GPL.read_bytes()),
                   ("apps/swiss-gc/NOTICE.md", NOTICE.read_bytes())]
        for p in sorted(LICENSES_DIR.glob("*.txt")):
            entries.append((f"apps/swiss-gc/licenses/{p.name}", p.read_bytes()))
        write_zip_stored(z, entries)
    if not z.is_file():
        chk("Wii zip 存在", False)
        return []
    with zipfile.ZipFile(z) as f:
        names = f.namelist()
        boot = f.read("apps/swiss-gc/boot.dol")
        expect = struct.pack(">32s", DOL_MAGIC) + reboot_dol
        segs = dol_segments(boot)
        injected = [s for s in segs if s[2] == WII_BASE]
        ok = chk("boot.dol 内嵌了 reboot.dol", expect in boot, f"{len(boot)} B")
        ok &= chk("内嵌段地址 0x807FFFE0", bool(injected) and injected[0][3] == len(expect),
                  str([(hex(s[2]), hex(s[3])) for s in injected]))
        ok &= chk("Wii booter 本体保留", len(segs) >= 3 and segs[0][2] == 0x80003F00,
                  f"{len(segs)} 段")
        ok &= chk("zip 内含许可与 NOTICE", all(
            n in names for n in ("apps/swiss-gc/LICENSE.txt", "apps/swiss-gc/NOTICE.md")))
        ok &= chk("zip 内含第三方许可文本", sum(1 for n in names if "/licenses/" in n and n.endswith(".txt")) >= 10,
                  f"{sum(1 for n in names if '/licenses/' in n and n.endswith('.txt'))} 个")
        ok &= chk("zip 不压缩 (store)", all(i.compress_type == 0 for i in f.infolist()))
    return [z] if ok else []


def build_wode(root: Path, main: bytes, tool: str, verify: bool) -> list[Path]:
    print("\n=== WODE ===")
    out = root / "WODE" / "swiss-zh(wode_extcfg).iso"
    if not verify:
        if not gen_iso("wode", out, main, tool):
            return []
    ok = out.is_file() and iso.verify(out, HERE / "iso" / "eltorito-wode.hdr",
                                      main, b"GWDPCF", None)[0]
    chk("WODE ISO 自检", bool(ok), f"{out.stat().st_size if out.is_file() else 0} B, Game ID GWDPCF")
    return [out] if ok else []


def build_memorycard(root: Path, main: bytes, verify: bool) -> list[Path]:
    print("\n=== MemoryCard ===")
    d = root / "MemoryCard"
    icon = parse_gci_icon(BOOT / "dol2gci.cpp")
    outs = []
    for name in ("boot.dol", "xeno.dol"):
        p = d / (name.replace(".dol", ".gci"))
        if not verify:
            d.mkdir(parents=True, exist_ok=True)
            p.write_bytes(make_gci(main, name, icon))
        outs.append(p)
    ok = True
    for p in outs:
        if not p.is_file():
            ok &= chk(f"{p.name} 存在", False)
            continue
        g = p.read_bytes()
        ok &= chk(f"{p.name} GCI 头合法",
                  g[:4] == b"DOLX" and g[4:6] == b"00" and
                  struct.unpack_from(">H", g, 0x38)[0] == (len(g) - 64) // 8192,
                  f"{len(g)} B")
        ok &= chk(f"{p.name} 内含主 DOL", main[256:] in g)
    return outs if ok else []


def main() -> int:
    ap = argparse.ArgumentParser(description="生成各启动方式专用的 Swiss 简中版文件")
    ap.add_argument("--out-dir", type=Path, default=REPO, help="输出根目录")
    ap.add_argument("--verify-only", action="store_true", help="只校验已有产物，不重新生成")
    ap.add_argument("--only", help="只处理指定类别，逗号分隔：ar,flippy,wkf,wii,wode,gci")
    ap.add_argument("--mkisofs", help="显式指定 mkisofs/xorrisofs 可执行文件")
    args = ap.parse_args()

    all_kinds = ("ar", "flippy", "wkf", "wii", "wode", "gci")
    kinds = tuple(k.strip() for k in args.only.split(",")) if args.only else all_kinds
    unknown = [k for k in kinds if k not in all_kinds]
    if unknown:
        ap.error("未知类别: " + ", ".join(unknown))

    for p in (MAIN_DOL, LICENSE_GPL, NOTICE, BOOT / "SDLOADER.BIN",
              BOOT / "reboot.dol", BOOT / "wii_booter.dol", BOOT / "dol2gci.cpp"):
        if not p.is_file():
            print(f"错误：缺少输入文件 {p}", file=sys.stderr)
            return 2
    main_dol = MAIN_DOL.read_bytes()
    sdloader = (BOOT / "SDLOADER.BIN").read_bytes()
    reboot_dol = (BOOT / "reboot.dol").read_bytes()

    print("=== 同批构建校验 ===")
    try:
        xz = extract_xz(main_dol)
        ok = chk("主 DOL / SDLOADER.BIN / reboot.dol 内嵌同一份 xz 镜像",
                 extract_xz(sdloader) == xz and extract_xz(reboot_dol) == xz,
                 f"xz {len(xz)} B  sha256 {sha(xz)[:16]}")
    except (ValueError, lzma.LZMAError) as e:
        ok = chk("同批构建校验", False, str(e))
    if not ok:
        print("\n中止：packer 产物与固件不是同一次构建，请先重新编译。", file=sys.stderr)
        return 1

    tool = ""
    if not args.verify_only and ({"wkf", "wode"} & set(kinds)):
        try:
            tool = iso.find_mkisofs(args.mkisofs)
        except RuntimeError as e:
            print(f"错误：{e}", file=sys.stderr)
            return 2
        print(f"ISO 工具: {tool}")

    root = args.out_dir
    made: list[Path] = []
    if "ar" in kinds:
        made += build_action_replay(root, main_dol, sdloader, args.verify_only)
    if "flippy" in kinds:
        made += build_flippy(root, main_dol, args.verify_only)
    if "wkf" in kinds:
        made += build_wiikeyfusion(root, main_dol, tool, args.verify_only)
    if "wii" in kinds:
        made += build_wii(root, reboot_dol, args.verify_only)
    if "wode" in kinds:
        made += build_wode(root, main_dol, tool, args.verify_only)
    if "gci" in kinds:
        made += build_memorycard(root, main_dol, args.verify_only)

    print("\n=== 产物 SHA-256（供 SHA256SUMS.txt）===")
    for p in made:
        rel = p.relative_to(root).as_posix()
        print(f"{sha(p.read_bytes())}  {rel}")

    failed = [n for n, good, _ in CHECKS if not good]
    print(f"\n总计: {sum(1 for _, good, _ in CHECKS if good)}/{len(CHECKS)} 项检查通过"
          + (f"；失败: {', '.join(failed)}" if failed else "，全部通过"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
