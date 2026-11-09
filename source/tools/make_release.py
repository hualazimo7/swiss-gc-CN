#!/usr/bin/env python3
"""Assemble the release zip.

Contents:
  swiss.dol          the build itself
  README.md          install / usage / known limits (from RELEASE_README.md)
  CHANGELOG.md       every change against upstream r2154
  LICENSE            GPLv2, as required by the upstream project
  SHA256SUMS.txt     checksums for the binary and the docs
  source/            full modified source tree (GPLv2 compliance)
  i18n/              font generator, checkers, translation maps, this tooling

Usage:
  python tools/make_release.py [--skip-source]
"""
import argparse
import datetime
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
I18N = os.path.dirname(HERE)
SWISS = os.path.abspath(os.path.join(I18N, "..", "swiss-gc"))
DIST = os.path.join(I18N, "dist")
DOL_RAW = os.path.join(SWISS, "cube", "swiss", "swiss.dol")      # link at 0x80003100
DOL_PACKED = os.path.join(SWISS, "cube", "packer", "swiss.dol")  # self-extracting, for SD
TMP_SCRIPTS = os.path.join(os.environ.get("TEMP", ""), "swiss-build")

SOURCE_SKIP = {".git", "build", "__pycache__", "dist", "out", ".github", "disassembly",
                "payload"}   # payload = packer intermediate, no extension
SOURCE_SKIP_EXT = {".o", ".a", ".elf", ".dol", ".map", ".log", ".bmp", ".zip", ".pyc",
                   ".bin", ".xz"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args):
    return subprocess.run(["git", "-C", SWISS] + list(args),
                          capture_output=True, text=True).stdout.strip()


def copy_source(dest):
    def ignore(directory, names):
        dropped = set()
        for n in names:
            if n in SOURCE_SKIP:
                dropped.add(n)
            elif os.path.splitext(n)[1].lower() in SOURCE_SKIP_EXT:
                dropped.add(n)
        return dropped

    shutil.copytree(SWISS, dest, ignore=ignore, symlinks=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-source", action="store_true",
                    help="binary + docs only (NOT GPL compliant on its own)")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    if not os.path.isfile(DOL_RAW):
        sys.exit(f"missing build: {DOL_RAW}\nrun bash build-local.sh dev")
    if not os.path.isfile(DOL_PACKED):
        sys.exit(f"missing packed build: {DOL_PACKED}\n"
                 f"run: make -C cube/packer\n"
                 f"The raw DOL loads at 0x80003100 and overwrites the IPL loader "
                 f"(CubiBoot/PicoBoot), which shows up as a black screen.")

    rev = git("rev-parse", "--short", "HEAD")
    name = f"swiss-zh-r2154-{args.date}"
    stage = os.path.join(DIST, name)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    print(f"staging {stage}")
    # SD/ISO boot takes the packed image: its stub sits above the IPL loader's
    # own memory and decompresses the real payload into 0x80003100.
    shutil.copy2(DOL_PACKED, os.path.join(stage, "swiss.dol"))
    shutil.copy2(DOL_RAW, os.path.join(stage, "swiss-wiiload.dol"))
    shutil.copy2(os.path.join(I18N, "RELEASE_README.md"), os.path.join(stage, "README.md"))
    shutil.copy2(os.path.join(I18N, "CHANGELOG.md"), os.path.join(stage, "CHANGELOG.md"))
    shutil.copy2(os.path.join(SWISS, "LICENSE"), os.path.join(stage, "LICENSE"))

    i18n_dst = os.path.join(stage, "i18n")
    os.makedirs(os.path.join(i18n_dst, "docs"))
    os.makedirs(os.path.join(i18n_dst, "tools"))
    os.makedirs(os.path.join(i18n_dst, "translations"))
    os.makedirs(os.path.join(i18n_dst, "fonts"))
    os.makedirs(os.path.join(i18n_dst, "tests"))
    os.makedirs(os.path.join(i18n_dst, "scripts"))

    shutil.copy2(os.path.join(I18N, "FONT_PLAN.md"),
                 os.path.join(i18n_dst, "docs", "FONT_PLAN.md"))
    for fn in sorted(os.listdir(HERE)):
        if fn.endswith(".py"):
            shutil.copy2(os.path.join(HERE, fn), os.path.join(i18n_dst, "tools", fn))
    tr = os.path.join(I18N, "translations")
    for fn in sorted(os.listdir(tr)):
        if fn.endswith(".tsv"):
            shutil.copy2(os.path.join(tr, fn), os.path.join(i18n_dst, "translations", fn))
    shutil.copy2(os.path.join(I18N, "fonts", "unifont.hex"),
                 os.path.join(i18n_dst, "fonts", "unifont.hex"))
    shutil.copy2(os.path.join(I18N, "tests", "test_font.c"),
                 os.path.join(i18n_dst, "tests", "test_font.c"))
    if os.path.isdir(TMP_SCRIPTS):
        for fn in sorted(os.listdir(TMP_SCRIPTS)):
            if fn.endswith(".sh") and (fn.startswith("2") or fn.startswith("3")):
                shutil.copy2(os.path.join(TMP_SCRIPTS, fn),
                             os.path.join(i18n_dst, "scripts", fn))

    if not args.skip_source:
        print("copying source tree (this takes a moment)")
        copy_source(os.path.join(stage, "source"))
        shutil.copy2(os.path.join(SWISS, "build-local.sh"),
                     os.path.join(stage, "source", "build-local.sh"))
        with open(os.path.join(stage, "source", "UPSTREAM.txt"), "w", encoding="utf-8") as fh:
            fh.write("upstream : https://github.com/emukidid/swiss-gc\n"
                     f"baseline : r2154 / commit {rev}\n"
                     f"modified : {args.date}\n")

    sums = []
    for rel in ("swiss.dol", "swiss-wiiload.dol", "README.md", "CHANGELOG.md"):
        sums.append(f"{sha256(os.path.join(stage, rel))}  {rel}")
    with open(os.path.join(stage, "SHA256SUMS.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(sums) + "\n")

    zip_path = os.path.join(DIST, name + ".zip")
    print(f"zipping -> {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for root, dirs, files in os.walk(stage):
            dirs.sort()
            for fn in sorted(files):
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, DIST)
                zf.write(full, arc)

    print()
    print(f"package : {zip_path}")
    print(f"size    : {os.path.getsize(zip_path)/1024/1024:.1f} MB")
    print(f"dol     : {os.path.getsize(DOL_PACKED):,} bytes (packed)  sha256 {sha256(DOL_PACKED)[:16]}…")
    print(f"wiiload : {os.path.getsize(DOL_RAW):,} bytes (raw)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
