#!/usr/bin/env python3
"""Render a Swiss-like screen mock with Unifont glyphs, to judge legibility.

Outputs a 24-bit BMP (no external deps). Dark background + white text matches
the Swiss UI, so what you see is roughly what a CRT will show.
"""
import struct
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "fonts", "unifont.hex")


def load_font(path=FONT):
    glyphs = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if ":" not in line:
                continue
            cp, data = line.split(":", 1)
            try:
                glyphs[int(cp, 16)] = data
            except ValueError:
                continue
    return glyphs


def glyph_bitmap(glyphs, ch):
    """Return 16 rows of 16-bit ints, or None."""
    d = glyphs.get(ord(ch))
    if not d or len(d) < 64:
        return None
    return [int(d[r * 4:(r + 1) * 4], 16) for r in range(16)]


class Canvas:
    def __init__(self, w, h, bg=(24, 24, 28)):
        self.w, self.h = w, h
        self.px = [[bg for _ in range(w)] for _ in range(h)]

    def put(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = color

    def rect(self, x0, y0, x1, y1, color):
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.put(x, y, color)

    def draw_text(self, x, y, text, scale=1.0, color=(235, 235, 240), glyphs=None):
        """Nearest-neighbour scaling, emulating the GX quad scale."""
        cx = x
        for ch in text:
            bm = glyph_bitmap(glyphs, ch)
            if bm is None:
                cx += int(16 * scale)
                continue
            if scale == 1.0:
                for r in range(16):
                    for c in range(16):
                        if bm[r] & (1 << (15 - c)):
                            self.put(cx + c, y + r, color)
            else:
                # area-average + 50% threshold: emulates GX_LINEAR sampling
                out_w = max(1, int(round(16 * scale)))
                out_h = max(1, int(round(16 * scale)))
                for oy in range(out_h):
                    sy0, sy1 = oy * 16 / out_h, (oy + 1) * 16 / out_h
                    for ox in range(out_w):
                        sx0, sx1 = ox * 16 / out_w, (ox + 1) * 16 / out_w
                        cov = 0.0
                        for sy in range(int(sy0), max(int(sy0) + 1, int(sy1 + 0.999))):
                            for sx in range(int(sx0), max(int(sx0) + 1, int(sx1 + 0.999))):
                                if 0 <= sy < 16 and 0 <= sx < 16 and (bm[sy] & (1 << (15 - sx))):
                                    wy = min(sy1, sy + 1) - max(sy0, sy)
                                    wx = min(sx1, sx + 1) - max(sx0, sx)
                                    cov += max(0.0, wy) * max(0.0, wx)
                        if cov / ((sy1 - sy0) * (sx1 - sx0)) >= 0.5:
                            self.put(cx + ox, y + oy, color)
            cx += int(round(16 * scale)) + 1
        return cx

    def save_bmp(self, path, zoom=2):
        w, h = self.w * zoom, self.h * zoom
        row_bytes = (w * 3 + 3) & ~3
        pad = row_bytes - w * 3
        data = bytearray()
        for y in range(self.h - 1, -1, -1):
            row = bytearray()
            for x in range(self.w):
                r, g, b = self.px[y][x]
                for _ in range(zoom):
                    row += bytes((b, g, r))
            row += b"\x00" * pad
            for _ in range(zoom):
                data += row
        size = 54 + len(data)
        hdr = b"BM" + struct.pack("<IHHI", size, 0, 0, 54)
        dib = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(data), 2835, 2835, 0, 0)
        with open(path, "wb") as fh:
            fh.write(hdr + dib + data)


def main():
    glyphs = load_font()
    c = Canvas(640, 240)
    # fake title bar
    c.rect(0, 0, 640, 30, (40, 40, 48))
    c.draw_text(12, 7, "Swiss 汉化预览", 1.0, glyphs=glyphs)

    y = 40
    items = [
        ("系统信息 (1/5):", 1.0, "菜单主文本 scale 1.0"),
        ("全局设置 (1/6):", 1.0, ""),
        ("视频模式:", 1.0, ""),
        ("区域:", 0.75, "次级信息 scale 0.75"),
        ("存档管理", 0.75, ""),
        ("正在加载…", 0.65, "小字号 scale 0.65 ← 关键"),
        ("版本 0.6.2154", 0.55, "最小字号 scale 0.55"),
    ]
    for text, sc, note in items:
        c.draw_text(20, y, text, sc, glyphs=glyphs)
        if note:
            c.draw_text(220, y + 4, note, 1.0, (120, 120, 130), glyphs=glyphs)
        y += 26

    out = os.path.join(HERE, "..", "out", "preview_cjk.bmp")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    c.save_bmp(out, zoom=2)
    print("wrote", os.path.abspath(out), f"{c.w*2}x{c.h*2}")


if __name__ == "__main__":
    main()
