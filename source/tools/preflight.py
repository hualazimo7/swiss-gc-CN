#!/usr/bin/env python3
"""Pre-build checks for the localisation work.

Run this before every build; it catches the two failure modes that only show up
on real hardware:

  1. a settings value array got translated -> swiss.ini stops parsing
  2. a translated character has no glyph  -> the character silently disappears

Steps: config-array guard, regenerate the glyph set from the sources, verify
every used code point has a glyph.
"""
import subprocess
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# Must match the production command in gen_font.py's docstring. A narrower set
# here (it used to be --gb2312, level 1 only) silently overwrote the full atlas
# with a 4k-glyph one, so every build lost the level-2 and Big5 characters that
# game file names need even though the standalone generation step had them.
FONT_ARGS = ["--from-source", "--gb2312-full", "--big5-common"]


def run(script, *args):
    path = os.path.join(HERE, script)
    print(f"--- {script} {' '.join(args)}".rstrip())
    r = subprocess.run([sys.executable, path, *args])
    return r.returncode


def main():
    if run("check_config_arrays.py") != 0:
        print("\nPREFLIGHT FAILED: a config array was translated.")
        return 1
    font_args = list(FONT_ARGS)
    name_table = os.path.join(HERE, "..", "dist", "GameCube_中文译名表.md")
    if os.path.exists(name_table):
        font_args += ["--extra-chars", name_table]
    if run("gen_font.py", *font_args) != 0:
        print("\nPREFLIGHT FAILED: glyph generation failed.")
        return 1
    if run("check_glyphs.py") != 0:
        print("\nPREFLIGHT FAILED: missing glyphs (see above).")
        return 1
    print("\nPREFLIGHT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
