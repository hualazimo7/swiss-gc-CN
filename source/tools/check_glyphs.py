#!/usr/bin/env python3
"""Verify that every non-ASCII character used in the source has a glyph.

Walks the Swiss source tree, collects every non-ASCII code point that appears
inside a string literal, and compares it against the generated cjkfont table.
Missing glyphs render as nothing at all, which is easy to miss by eye.

Exit code 1 if anything is missing (and prints the exact file:line).

File names are NOT in the source tree, so pass any dynamic text (game name
tables, user-provided titles) with --extra to check those too.

Usage:
  python tools/check_glyphs.py
  python tools/check_glyphs.py --extra ../dist/GameCube_中文译名表.md
"""
import argparse
import os
import re
import sys

def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    import os
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


SRC = str(_env_path("SWISS_GC_SRC", "swiss-gc/cube/swiss/source"))
CJKFONT_C = os.path.join(SRC, "gui", "cjkfont.c")
SKIP_DIRS = {"littlefs"}

# crude but adequate: find "...", tolerate escaped quotes
STR_RE = re.compile(r'"(?:\\.|[^"\\])*"')


def shipped_codepoints():
    txt = open(CJKFONT_C, encoding="utf-8").read()
    head = txt.split("cjkfont_bitmaps")[0]
    return set(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{4,6}),", head))


def used_codepoints():
    used = {}
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if not name.endswith(".c"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, SRC).replace("\\", "/")
            with open(path, encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    if line.lstrip().startswith("*") or line.lstrip().startswith("//"):
                        continue
                    for lit in STR_RE.findall(line):
                        for ch in lit:
                            if ord(ch) > 0x7F:
                                used.setdefault(ord(ch), (ch, rel, lineno))
    return used


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--extra", nargs="*", default=[], metavar="FILE",
                    help="extra UTF-8 text whose characters must also have "
                         "glyphs (e.g. a Chinese game name table)")
    args = ap.parse_args()

    shipped = shipped_codepoints()
    used = used_codepoints()
    for path in args.extra:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for ch in fh.read():
                cp = ord(ch)
                if cp > 0xFF and cp != 0xFFFD:
                    used.setdefault(cp, (ch, os.path.basename(path), 0))

    # Only code points above 0xFF need a CJK glyph: the IPL ROM font already
    # covers 0x20..0xFF, so Latin-1 (e.g. "Pok\xe9mon") renders through it.
    # U+FFFD is what a non-UTF-8 byte decodes to here; it is not a real glyph.
    used = {cp: info for cp, info in used.items() if cp > 0xFF and cp != 0xFFFD}
    missing = {cp: info for cp, info in used.items() if cp not in shipped}
    if not missing:
        print(f"glyphs OK: {len(used)} non-ASCII code points used, all present "
              f"({len(shipped)} in cjkfont.c)")
        return 0

    print(f"MISSING {len(missing)} glyph(s):")
    for cp, (ch, rel, line) in sorted(missing.items()):
        print(f"  U+{cp:04X} {ch!r:6}  {rel}:{line}")
    print("\nRegenerate with the missing text included:")
    print("  python tools/gen_font.py --from-source --gb2312-full "
          "--extra-chars <文件> --unifont-only")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
