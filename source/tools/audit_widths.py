#!/usr/bin/env python3
"""Check translated UI strings against the space they actually get.

Metrics come from the console, not from guesswork: `GET /fontwidths` dumps the
IPL font advance for every code point 0x20-0xFF, and CJK uses CJKFONT_ADVANCE
from cjkfont.h. Widths therefore match what GetTextSizeInPixels() computes.

Two checks:

1. Tooltip lines. tooltips_* arrays are drawn with a hard `max` scale of 0.75
   (`GetTextScaleToFitInWidthWithMax(..., 0.75f)`), but CJK is never allowed
   below CJK_MIN_SCALE, so every Chinese line is rendered at 1.0 no matter what
   width it was given. A line wider than the box at 1.0 simply runs over the
   border. Box width = fbWidth - 2*25 - 2*borderSize - 6.

2. Every other literal: report the widest ones per file so the outliers can be
   eyeballed. There is no generic way to know a label's box, so this is a
   sorted list rather than a pass/fail.

Usage:
  curl http://<gc>/fontwidths -o out/fontwidths.csv   # once per font change
  python tools/audit_widths.py
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "..", "swiss-gc", "cube", "swiss", "source"))
CJK_HEADER = os.path.join(SRC, "gui", "cjkfont.h")
WIDTHS = os.path.join(HERE, "..", "out", "fontwidths.csv")

FB_WIDTH = 640
BORDER = 4          # borderSize in FrameBufferMagic.c
TOOLTIP_MAX = 0.75  # hard cap passed to GetTextScaleToFitInWidthWithMax


def load_metrics():
    if not os.path.isfile(WIDTHS):
        sys.exit(f"missing {WIDTHS}\nrun: curl http://<gc>/fontwidths -o out/fontwidths.csv")
    adv = {}
    for line in open(WIDTHS, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cp, a = line.split(",")
        adv[int(cp)] = int(a)

    cjk = None
    for line in open(CJK_HEADER, encoding="utf-8"):
        m = re.match(r"#define\s+CJKFONT_ADVANCE\s+(\d+)", line)
        if m:
            cjk = int(m.group(1))
    if cjk is None:
        sys.exit("CJKFONT_ADVANCE not found in cjkfont.h")
    return adv, cjk


def text_width(s, adv, cjk):
    total = 0
    for ch in s:
        total += adv.get(ord(ch), cjk) if ord(ch) <= 0xFF else cjk
    return total


def decode_c(body):
    """Turn a C string body (without quotes) into real text."""
    out = []
    i = 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt == "n":
            out.append("\n")
        elif nxt == "t":
            out.append("\t")
        elif nxt == "r":
            out.append("\r")
        elif nxt == "\\":
            out.append("\\")
        elif nxt == '"':
            out.append('"')
        elif nxt.isdigit():                      # octal escape, e.g. \267
            j = i + 1
            while j < len(body) and j < i + 4 and body[j] in "01234567":
                j += 1
            out.append(chr(int(body[i + 1:j], 8)))
            i = j
            continue
        else:
            out.append(nxt)
        i += 2
    return "".join(out)


def tooltips(path):
    """Yield (key, line) for every line of every tooltips_* array."""
    src = open(path, encoding="utf-8").read()
    # declaration is `static char *tooltips_global[PAGE_GLOBAL_MAX+1] = {`
    for arr in re.finditer(r"static char \*tooltips_(\w+)\[[^\]]*\]\s*=\s*\{(.*?)\n\};", src, re.S):
        group, body = arr.group(1), arr.group(2)
        for entry in re.finditer(r"\[(\w+)\]\s*=\s*((?:\"(?:\\.|[^\"\\])*\"\s*)+)", body, re.S):
            key = entry.group(1)
            text = "".join(decode_c(m) for m in re.findall(r"\"((?:\\.|[^\"\\])*)\"", entry.group(2)))
            for line in text.split("\n"):
                yield f"{group}.{key}", line


def all_literals(path):
    """Yield every string literal in the file, decoded, for the wide-string list."""
    src = open(path, encoding="utf-8").read()
    for i, line in enumerate(src.splitlines(), 1):
        s = line.lstrip()
        if s.startswith("//") or s.startswith("*"):
            continue
        for m in re.finditer(r"\"((?:\\.|[^\"\\])*)\"", line):
            text = decode_c(m.group(1))
            if any(ord(c) > 0x7F for c in text):
                yield i, text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=FB_WIDTH - 2 * 25 - BORDER * 2 - 6,
                    help="tooltip line budget in pixels (default: computed from layout)")
    ap.add_argument("--top", type=int, default=8, help="widest strings to list per file")
    args = ap.parse_args()

    adv, cjk = load_metrics()
    print(f"metrics: {len(adv)} Latin code points, CJK advance {cjk}px")
    print(f"tooltip box: {FB_WIDTH}px wide -> {args.budget}px of usable line, "
          f"drawn at scale >= {TOOLTIP_MAX} (CJK is bumped to 1.0)")
    print(f"=> a Chinese tooltip line must be <= {args.budget}px at scale 1.0\n")

    over = []
    lines = 0
    for key, line in tooltips(os.path.join(SRC, "gui", "settings.c")):
        if not line.strip():
            continue
        lines += 1
        w = text_width(line, adv, cjk)
        if w > args.budget:
            over.append((w, key, line))

    print(f"tooltip lines checked: {lines}, over budget: {len(over)}")
    for w, key, line in sorted(over, reverse=True):
        print(f"  {w:4d}px  {key:<28} {line}")
    print()

    # Message boxes draw each line centred at 1.0 with no width limit at all
    # (DrawMessageBox -> DrawStyledLabel(..., 1.0f, ALIGN_CENTER)), so a line
    # wider than the screen is simply cut off by both edges.
    hard = 640
    warn = args.budget
    print(f"lines wider than {hard}px get clipped by the screen edge; "
          f"{warn}-{hard}px only fits if the box is full width\n")
    print("widest line per file (scale 1.0):")
    clipped = 0
    for root, dirs, files in os.walk(SRC):
        dirs[:] = [d for d in dirs if d not in ("littlefs", "fatfs")]
        for fn in sorted(files):
            if not fn.endswith(".c"):
                continue
            path = os.path.join(root, fn)
            try:
                rows = []
                for ln, t in all_literals(path):
                    for part in t.split("\n"):
                        w = text_width(part, adv, cjk)
                        if w > 0:
                            rows.append((w, ln, part))
            except UnicodeDecodeError:
                continue
            if not rows:
                continue
            rows.sort(reverse=True)
            widest = rows[0]
            if widest[0] < warn:
                continue
            rel = os.path.relpath(path, SRC)
            print(f"  {rel}")
            for w, ln, t in rows[:args.top]:
                flag = "CLIPPED" if w > hard else "tight"
                if w > hard:
                    clipped += 1
                print(f"    {w:4d}px {flag:<7} L{ln:<5} {t[:52]!r}")
    print()
    print(f"lines wider than the screen: {clipped}")
    return 1 if (over or clipped) else 0


if __name__ == "__main__":
    sys.exit(main())
