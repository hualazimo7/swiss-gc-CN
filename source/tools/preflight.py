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


def run(script, *args):
    path = os.path.join(HERE, script)
    print(f"--- {script} {' '.join(args)}".rstrip())
    r = subprocess.run([sys.executable, path, *args])
    return r.returncode


def main():
    if run("check_config_arrays.py") != 0:
        print("\nPREFLIGHT FAILED: a config array was translated.")
        return 1
    if run("gen_font.py", "--from-source", "--gb2312") != 0:
        print("\nPREFLIGHT FAILED: glyph generation failed.")
        return 1
    if run("check_glyphs.py") != 0:
        print("\nPREFLIGHT FAILED: missing glyphs (see above).")
        return 1
    print("\nPREFLIGHT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
