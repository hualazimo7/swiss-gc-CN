#!/usr/bin/env python3
"""Verify the shipped cjkfont.c against Unifont, then render a preview
from the shipped glyph data (same atlas math as IPLFontWrite.c).

Proves: font file -> cjkfont.c -> atlas layout -> pixels on screen.
"""
import os
import re
import struct
import sys

def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    import os
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


GUI = str(_env_path("SWISS_GC_GUI", "swiss-gc/cube/swiss/source/gui"))
UNIFONT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "fonts", "unifont.hex")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")


def parse_header():
    txt = open(os.path.join(GUI, "cjkfont.h"), encoding="utf-8").read()
    def g(name):
        m = re.search(rf"#define\s+{name}\s+(\d+)", txt)
        return int(m.group(1))
    return dict(count=g("CJKFONT_COUNT"), cell=g("CJKFONT_CELL"),
                cols=g("CJKFONT_COLS"), aw=g("CJKFONT_ATLAS_W"),
                ah=g("CJKFONT_ATLAS_H"), adv=g("CJKFONT_ADVANCE"))


def parse_font():
    txt = open(os.path.join(GUI, "cjkfont.c"), encoding="utf-8").read()
    cps = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{4}),", txt.split("cjkfont_bitmaps")[0])]
    body = txt.split("cjkfont_bitmaps")[1]
    body = body.split("{", 1)[1]
    vals = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2}),", body)]
    glyphs = [bytes(vals[i * 32:(i + 1) * 32]) for i in range(len(cps))]
    return cps, glyphs


def unifont_glyph(cp):
    for line in open(UNIFONT, encoding="utf-8", errors="replace"):
        line = line.strip()
        if ":" not in line:
            continue
        c, data = line.split(":", 1)
        if int(c, 16) == cp:
            out = bytearray()
            for r in range(16):
                row = int(data[r * 4:(r + 1) * 4], 16)
                out += bytes(((row >> 8) & 0xFF, row & 0xFF))
            return bytes(out)
    return None


def gx_i4_offset(w, x, y):
    return ((w >> 3) << 5) * (y >> 3) + ((x >> 3) << 5) + ((y & 7) << 2) + ((x & 7) >> 1)


class Canvas:
    def __init__(self, w, h, bg=(20, 20, 24)):
        self.w, self.h = w, h
        self.px = [[bg] * w for _ in range(h)]

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def save_bmp(self, path, zoom=3):
        w, h = self.w * zoom, self.h * zoom
        pad = (w * 3 + 3) & ~3
        pad -= w * 3
        data = bytearray()
        for y in range(self.h - 1, -1, -1):
            row = bytearray()
            for x in range(self.w):
                r, g, b = self.px[y][x]
                row += bytes((b, g, r)) * zoom
            row += b"\x00" * pad
            data += row * zoom
        hdr = b"BM" + struct.pack("<IHHI", 54 + len(data), 0, 0, 54)
        dib = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0)
        open(path, "wb").write(hdr + dib + data)


def main():
    hdr = parse_header()
    cps, glyphs = parse_font()

    # 1. shipped data must equal the font source
    bad = []
    for cp, bm in zip(cps, glyphs):
        ref = unifont_glyph(cp)
        if ref != bm:
            bad.append(cp)
    print(f"glyphs: {len(cps)}  mismatched vs unifont: {len(bad)}"
          + ("" if not bad else " -> " + " ".join(f"U+{c:04X}" for c in bad[:8])))

    # 2. build the atlas exactly like IPLFontWrite.c
    atlas = bytearray(hdr["aw"] * hdr["ah"] // 2)
    for i, bm in enumerate(glyphs):
        cx = (i % hdr["cols"]) * hdr["cell"]
        cy = (i // hdr["cols"]) * hdr["cell"]
        for y in range(hdr["cell"]):
            left, right = bm[y * 2], bm[y * 2 + 1]
            for x in range(16):
                bit = (left & (0x80 >> x)) if x < 8 else (right & (0x80 >> (x - 8)))
                if not bit:
                    continue
                px, py = cx + x, cy + y
                off = gx_i4_offset(hdr["aw"], px, py)
                atlas[off] |= 0xF0 if px % 2 == 0 else 0x0F

    # 3. decode the atlas back and render a real UI string from it
    def atlas_px(px, py):
        off = gx_i4_offset(hdr["aw"], px, py)
        return 1 if ((atlas[off] >> 4) if px % 2 == 0 else (atlas[off] & 0x0F)) else 0

    index = {cp: i for i, cp in enumerate(cps)}

    def draw(c, x, y, text, color=(238, 238, 244)):
        for ch in text:
            cp = ord(ch)
            if cp < 0x80:
                x += 8  # not rendered here: latin comes from the IPL font
                continue
            if cp not in index:
                x += hdr["adv"]
                continue
            i = index[cp]
            gx = (i % hdr["cols"]) * hdr["cell"]
            gy = (i // hdr["cols"]) * hdr["cell"]
            for yy in range(16):
                for xx in range(16):
                    if atlas_px(gx + xx, gy + yy):
                        c.put(x + xx, y + yy, color)
            x += hdr["adv"]
        return x

    cv = Canvas(420, 96)
    cv.put(1, 1, (1, 1, 1))
    draw(cv, 8, 10, "全局设置")
    draw(cv, 8, 40, "界面设置")
    draw(cv, 8, 68, "系统信息")
    p = os.path.join(OUT, "preview_from_atlas.bmp")
    os.makedirs(OUT, exist_ok=True)
    cv.save_bmp(p, zoom=3)
    print("atlas :", hdr["aw"], "x", hdr["ah"], "I4 =", len(atlas), "bytes")
    print("wrote", os.path.abspath(p))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
