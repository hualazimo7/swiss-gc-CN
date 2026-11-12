#!/usr/bin/env python3
"""Generate cjkfont.c / cjkfont.h for a given charset.

Glyph storage: 4bpp greyscale, 16 rows x 8 bytes (two nibbles per byte, high
nibble = even pixel). This is byte-for-byte the GX_TF_I4 tiling of a 16x16
cell, so the runtime just copies rows into the atlas - no per-pixel expansion,
and antialiasing survives to the screen instead of being thresholded away.

Glyphs are rendered from a Unicode TrueType/OpenType CJK face at 16 px. The
default is Noto Sans SC Medium: one family covers Hanzi, Latin and digits, so
a mixed string like "合金装备 孪蛇 (Disc 1)" has a single stroke weight and a
single baseline. GNU Unifont is only a last-resort fallback for code points
the face lacks.

Layout inside the 16x16 cell (measured on Noto Sans SC at 16 px, ascender 19):
  - Hanzi ink is exactly 16x16 at y 5..20, so it fills the cell edge to edge
    and the advance is a flat 16 px (CJKFONT_ADVANCE).
  - Latin/digit ink sits on the same baseline: cap height 12 px, so digits
    reach y 2..13 and ascenders a little higher. That is normal typography -
    digits are meant to be shorter than Hanzi, and forcing them to Hanzi
    height makes them look stretched and thin.
  - A per-glyph advance table (cjkfont_advance) carries the font's own
    proportional widths, so "64.1" is narrower than four Hanzi.

Usage:
  python gen_font.py --text "中文测试"
  python gen_font.py --charset out/charset.txt
  python gen_font.py --from-source --gb2312        # level 1 only (legacy)
  python gen_font.py --from-source --gb2312-full \
      --extra-chars ../dist/GameCube_中文译名表.md

Production rule: file names are user data that arrive AFTER the firmware was
built, so the atlas must cover more than the strings compiled into Swiss.
--gb2312-full adds GB2312 level 2 (rare-but-real chars such as 噩 / 飙);
--extra-chars folds in any additional text (game name tables, variants);
--big5-common adds the Big5 common-zone Hanzi so traditional/Japanese game
titles (e.g. 斑鳩) render. Whatever is still missing shows a tofu box instead
of a silent blank.

Production command (r10+, 8972 glyphs / 18 atlas pages):
  python gen_font.py --from-source --gb2312-full --big5-common \
      --extra-chars <game-name-table.md> \
      --font "C:/Windows/Fonts/Noto Sans SC Medium (TrueType).otf"
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "fonts", "unifont.hex")


def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


OUT_DIR = str(_env_path("SWISS_GC_GUI", "swiss-gc/cube/swiss/source/gui"))

CELL = 16
# 16 rows x 8 bytes: one byte holds two 4-bit pixels (I4 layout).
BYTES_PER_GLYPH = 128
# Always present in the atlas. Drawn whenever cjkfont_lookup() fails, so a
# missing code point shows up as a visible box rather than an empty gap.
FALLBACK_CP = 0x25A1  # □
# Printable ASCII is stored in the atlas so Latin and digits use the same face
# as the Hanzi. U+20 is included because it needs an advance entry.
ATLAS_ASCII = tuple(range(0x20, 0x7F))
# On-screen size of a glyph quad. Kept equal to CELL so the bitmap maps 1:1
# onto the screen; any upscale makes GX_NEAR repeat whole rows and columns.
DRAW = 16
# Hanzi advance. The face's Hanzi ink is a full 16 px wide, so anything larger
# adds a visible gap inside Chinese words.
ADVANCE = CELL

# Vertical crop offset inside the 16 px em box: the face's ascender is 19 px,
# Hanzi ink spans y 5..20. Cropping from y=5 puts the Hanzi exactly in the
# 16x16 cell and leaves Latin/digits on the same baseline (cell y 14).
CROP_Y = 5
# Latin and digits are rasterised at 18 px, not 16. At 16 px a capital is only
# 12 px tall (0.69 of a Hanzi) and a digit stroke is a single soft pixel, so
# file sizes and the clock read as small print next to the Chinese text. 18 px
# gives 13 px caps and a firmer stroke while the advance only grows ~12%.
#
# The crop offset aligns INK BOTTOMS, not the mathematical baseline. Both faces
# do share a baseline (Hanzi 19 in a 16 px cell => cell y 14, Latin 21 at 18 px
# with crop 7 => cell y 14), but a CJK glyph is drawn to sit one pixel BELOW
# that baseline while a digit stops one pixel ABOVE it. Baseline alignment
# therefore left every digit floating 2 px above the Chinese beside it - the
# "digits ride high" report from the hardware test.
# Cropping from 5 lands the digit/cap ink on cell rows 2..15 against the Hanzi
# on 0..15: identical bottoms, the digit just 2 px shorter at the cap. Cost:
# descenders (g p q y) and brackets lose 2 extra rows at the cell edge. That is
# unavoidable at this size - an 18 px cap plus descender spans ~19 rows and the
# cell only holds 16. Keeping the digits correct matters more: filenames,
# capacities and version numbers are almost all digits and capitals.
ASCII_SIZE = 18
ASCII_CROP_Y = 5
# Descenders (g j p q y) need their own pass. At 18 px their ink spans 10 rows
# of x-height plus 4 rows of descender and the baseline has to stay on cell 15
# with the digits - so rows 16..19 fall outside the cell. Simply clipping them
# turns g into a plain circle that reads as a Greek sigma (the "gbi-config"
# filenames came out as "σbi-config" on hardware). Instead the x-height block
# is lifted one row and the descender is collapsed to a single row at the very
# bottom, keeping the stroke core intact: these five letters end up 1 px taller
# than their neighbours, which is far less visible than a missing tail.
DESCENDER_CHARS = frozenset("gjpqy")
DESCENDER_SPAN = 24     # rows to read after the crop, enough for g at y 6..19
# Brackets span 19 rows at 18 px - taller than the cell - and clipping them
# strips the end bars, turning [ into 厂. They carry no baseline, so the whole
# ink box is resampled down to the full 16 rows instead of being cut.
TALL_CHARS = frozenset("()[]{}")
# Latin/digits also take a heavier cut than the Hanzi. At 18 px a digit stroke
# is ~1 px of partially covered pixels, which reads grey; the Bold cut brings
# it to a solid 2 px so file sizes and the clock hold their own beside the
# Chinese text. Hanzi stay Medium - Bold at 16 px fuses the inner strokes of
# characters like 备 / 實 into a blob.
ASCII_TTF = os.environ.get(
    "CJK_ASCII_TTF",
    r"C:\Windows\Fonts\Noto Sans SC Bold (TrueType).otf",
)
# Mild gamma lift: 4bpp storage plus GX blending makes mid-tones read grey on
# a CRT-ish 480p signal, so push antialiased edges a little brighter while
# keeping the stroke cores at full white.
GAMMA = 0.78

# Default glyph source: a real CJK outline face. Noto Sans SC is SIL OFL, so
# the generated bitmaps ship without a licensing question. SimSun/SimHei also
# work via --font but their 16 px strikes are older and heavier.
TTF_FONT = os.environ.get(
    "CJK_TTF",
    r"C:\Windows\Fonts\Noto Sans SC Medium (TrueType).otf",
)
TTF_INDEX = 0
TTF_SIZE = CELL


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


def _lift(value):
    """Gamma-lift one 0..255 coverage sample, then quantise to 4 bits."""
    v = (value / 255.0) ** GAMMA
    return min(15, int(round(v * 15.0)))


def _fit_descender(tall):
    """Squeeze a descender letter into the 16-row cell without clipping it.

    ``tall`` is a CELL-wide strip whose row 15 is the shared baseline. The
    x-height block is 10 rows; resampling it to 9 leaves two rows at the bottom
    for the descender, which is the minimum that survives the 0.75 downscale
    applied to Latin-only strings - a single row of tail got interpolated into
    a flat dash and g read as a Greek sigma on the hardware. The body is
    resampled instead of cropped so no stroke disappears; the letter ends up
    one pixel shorter than its neighbours, which is invisible next to a tail
    that actually reads.
    """
    from PIL import Image

    out = Image.new("L", (CELL, CELL), 0)
    body = tall.crop((0, 6, CELL, 16)).resize((CELL, 9), Image.LANCZOS)
    out.paste(body, (0, 5))
    if tall.height > 16:
        src = tall.load()
        dst = out.load()
        # Rows 16..19 are the descender: fold them into cell rows 14 and 15,
        # per column max so a thin stroke keeps its weight.
        for y, lo, hi in ((14, 16, 18), (15, 18, tall.height)):
            for x in range(CELL):
                peak = max(src[x, yy] for yy in range(lo, min(hi, tall.height)))
                if peak > dst[x, y]:
                    dst[x, y] = peak
    return out


def _fit_tall(tall):
    """Shrink an oversized glyph (brackets) into the cell as a whole.

    Returns None when the glyph already fits, so the caller keeps the plain
    crop. Brackets have no baseline of their own - they are expected to stand
    slightly proud of the letters - so normalising the ink box to rows 0..15 is
    exactly the right look, and it keeps both end bars.
    """
    from PIL import Image

    px = tall.load()
    top = bot = None
    for y in range(tall.height):
        if max(px[x, y] for x in range(CELL)) > 8:
            if top is None:
                top = y
            bot = y
    if top is None or bot - top + 1 <= CELL:
        return None
    seg = tall.crop((0, top, CELL, bot + 1))
    return seg.resize((CELL, CELL), Image.LANCZOS)


def rasterize_aa(codepoints, path=TTF_FONT, index=TTF_INDEX, size=TTF_SIZE):
    """Render each code point to a 16x16 4bpp cell plus its advance.

    Returns (bitmaps, advances). bitmaps maps cp -> 128-byte I4 tile,
    advances maps cp -> on-screen width in pixels. Code points with no ink
    (space) still get an advance so layout stays correct.
    """
    if not path or not os.path.exists(path):
        print(f"font unavailable, falling back to Unifont: {path}")
        return {}, {}
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow missing (pip install pillow), falling back to Unifont")
        return {}, {}

    font = ImageFont.truetype(path, size, index=index)
    ascii_path = ASCII_TTF if os.path.exists(ASCII_TTF) else path
    ascii_font = ImageFont.truetype(ascii_path, ASCII_SIZE, index=index)
    pad = size * 2
    canvas = Image.new("L", (size * 3, size * 4), 0)
    draw = ImageDraw.Draw(canvas)
    bitmaps, advances = {}, {}
    for cp in codepoints:
        ch = chr(cp)
        latin = 0x20 <= cp < 0x7F
        face = ascii_font if latin else font
        crop_y = ASCII_CROP_Y if latin else CROP_Y
        advance = int(round(face.getlength(ch)))
        bbox = face.getbbox(ch)
        if bbox is None or bbox[2] <= bbox[0]:
            # Whitespace: empty cell, width from the font metrics.
            bitmaps[cp] = bytes(BYTES_PER_GLYPH)
            advances[cp] = max(advance, 3)
            continue
        draw.rectangle([0, 0, canvas.width, canvas.height], fill=0)
        draw.text((pad, pad), ch, font=face, fill=255, anchor="la")
        # Fixed vertical crop, not bbox-anchored: bbox would top-align every
        # glyph and destroy the shared baseline.
        cell = canvas.crop((pad, pad + crop_y, pad + CELL, pad + crop_y + CELL))
        if latin and ch in DESCENDER_CHARS:
            tall = canvas.crop((pad, pad + crop_y, pad + CELL,
                                pad + crop_y + DESCENDER_SPAN))
            cell = _fit_descender(tall)
        elif latin and ch in TALL_CHARS:
            tall = canvas.crop((pad, pad + crop_y, pad + CELL,
                                pad + crop_y + DESCENDER_SPAN))
            fitted = _fit_tall(tall)
            if fitted is not None:
                cell = fitted
        px = cell.load()
        rows = bytearray(BYTES_PER_GLYPH)
        ink = False
        for y in range(CELL):
            base = y * 8
            for x in range(CELL):
                v = px[x, y]
                if v:
                    ink = True
                    nib = _lift(v)
                    if x & 1:
                        rows[base + (x >> 1)] |= nib
                    else:
                        rows[base + (x >> 1)] |= nib << 4
        if ink:
            bitmaps[cp] = bytes(rows)
            advances[cp] = max(advance, 1)
        else:
            advances[cp] = max(advance, 3)
    return bitmaps, advances


def unifont_cells(glyphs, cp):
    """Fallback glyph: expand a Unifont .hex row into a 16x16 4bpp tile.

    Unifont stores CJK as 16x16 (64 hex digits) but Latin/punctuation as 8x16
    (32 hex digits). Narrow glyphs are centred in the 16 px cell so punctuation
    like “ ” sits sensibly next to CJK. Coverage is full-on/full-off only -
    Unifont has no antialiasing to preserve.
    """
    d = glyphs.get(cp)
    if not d:
        return None
    grid = [[0] * CELL for _ in range(CELL)]
    if len(d) >= 64:
        for r in range(16):
            row = int(d[r * 4:(r + 1) * 4], 16)
            for x in range(16):
                if row & (0x8000 >> x):
                    grid[r][x] = 15
    elif len(d) >= 32:
        for r in range(16):
            b = int(d[r * 2:(r + 1) * 2], 16)      # 8 px, bit7 = leftmost
            for x in range(8):
                if b & (0x80 >> x):
                    grid[r][x + 4] = 15
    else:
        return None
    rows = bytearray(BYTES_PER_GLYPH)
    for y in range(CELL):
        base = y * 8
        for x in range(CELL):
            nib = grid[y][x]
            if not nib:
                continue
            if x & 1:
                rows[base + (x >> 1)] |= nib
            else:
                rows[base + (x >> 1)] |= nib << 4
    return bytes(rows)


def build_bitmaps(codepoints, font_path=TTF_FONT):
    """Resolve every code point to a 128-byte 4bpp tile plus its advance.

    The outline face is the primary source; Unifont only fills code points it
    does not cover (and those fall back to a 1-bit look, which is why a glyph
    showing up at all is a signal the face is missing something).
    """
    ttf, adv = rasterize_aa(codepoints, font_path) if font_path else ({}, {})
    if ttf:
        print(f"glyph source : {os.path.basename(font_path)} at {TTF_SIZE}px "
              f"-> {len(ttf)}/{len(codepoints)}")
    else:
        print("glyph source : GNU Unifont (built-in)")
    fallback = [cp for cp in codepoints if cp not in ttf]
    unifont = load_font() if fallback else {}
    out = {}
    advances = {}
    from_unifont = 0
    missing = []
    for cp in codepoints:
        b = ttf.get(cp)
        if b is None:
            b = unifont_cells(unifont, cp)
            if b is not None:
                from_unifont += 1
                # Unifont has no advance table; CJK is full width, the rest
                # is roughly half width, which is what the .hex format means.
                adv[cp] = CELL if cp > 0x2E80 else CELL // 2
        if b is None:
            missing.append(cp)
        else:
            out[cp] = b
            advances[cp] = adv.get(cp, CELL)
    if from_unifont:
        print(f"glyph fallback: Unifont -> {from_unifont}")
    if missing:
        print("no glyph for: " + " ".join(f"U+{cp:04X}" for cp in missing))
    return out, advances


def collect_charset(text="", charset_file=None):
    chars = set()
    if text:
        chars.update(text)
    if charset_file:
        with open(charset_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                chars.update(line)
    # keep only what will actually route through the CJK path
    return sorted(cp for cp in (ord(c) for c in chars) if cp >= 0x80)


DEFAULT_TEST = "中文测试系统信息设置视频模式区域存档管理正在加载版本游戏列表返回"


def gb2312_level1():
    """Every character in GB2312 level 1 (3755 chars, the common set).

    Needed for dynamic text such as file names, which are not known at build
    time. Level 2 (3008 rarer chars) is skipped: including it would need more
    than a 1024x1024 atlas.
    """
    chars = set()
    for b1 in range(0xB0, 0xD8):
        for b2 in range(0xA1, 0xFF):
            try:
                chars.add(bytes([b1, b2]).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    return chars


def gb2312_full():
    """Both GB2312 levels (6763 chars).

    Level 1 alone covers only the 3755 most common characters. Game names are
    full of level-2 characters (噩 in 忍者神龟3：变异噩梦, 飙, 鑫, ...), and
    those are exactly the ones that used to disappear from the file browser.
    File names are not known at build time, so cover the whole encoding.
    """
    chars = set()
    for b1 in range(0xB0, 0xF8):
        for b2 in range(0xA1, 0xFF):
            try:
                chars.add(bytes([b1, b2]).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    return chars


# Traditional / Japanese / variant forms that appear in game titles but live
# outside GB2312. Shipped in the generator so a plain production build is
# already safe; append freely and regenerate. Duplicates are harmless.
EXTRA_VARIANTS = (
    "惡夢龜龍鳳劍俠傳說戰爭勝敗與會兒萬億臺灣港澳靈寶體國圖書寫電話腦遊戲機"
    "電視聲樂園島嶼風雲雷電霧門開關間題聞問時間長短寬離歸還進退買賣價格貴賤"
    "謝歡選決應該結束繼續練習習認識知識語讀聽說計算測驗證確認保護維護復製造"
    "創設計劃組織管理領導揮監督察發現藝術技術科學研究產銷購買消費投資財務經濟"
    "貿易貨幣銀行帳戶密碼登錄註冊員資格權限角色職業專家顧問醫師學童婦女家庭"
    "父母兄弟姊妹親戚朋友夥伴敵對軍隊武器裝備防禦擊傷害治療魔咒技能屬飾服裝"
    "品道具寶藏財富資源材料礦屬木材皮革布料食物飲料藥毒疾病詛祝福祈禱祭祀"
    "神聖邪黑暗光明焰流土壤空氣生命死魂精神意識記憶想希望勇氣智慧力量速度"
    "敏幸運命運預言傳奇史詩冒險旅程探索征服統治王國帝國聯邦部落村莊城鎮首都"
    "邊境疆土海洋湖泊河山脈森林沙漠草原沼澤洞穴迷宮塔樓城堡宮殿寺廟教堂祭壇"
    "廢墟遺蹟博物館學院醫院商店市場酒館旅館餐廳食堂廚房臥室客廳陽台花園庭院"
    "馬廄倉庫工場礦坑碼頭港口機場車站道路橋樑隧道運河鐵路公路街道巷弄廣場"
    "公園運動競技劇院電影美術展覽體育泳健身遊樂動物植水族"
    # Japanese shinjitai / kokuji
    "悪亀竜伝説戦闘仮実写駅鉄桜辺弁円済広毎歩黒白青赤緑黄紫灰茶色匂峠畑込々〆"
)


def big5_common_chars():
    """Big5 常用字区 A440-C67E (5401 码位) 里的 CJK 汉字。

    GB2312 only covers Simplified Chinese. Game titles from JP/TW releases use
    traditional forms (e.g. Ikaruga is 斑鳩, whose 鳩 U+9CE9 is not in GB2312).
    Enumerating the standard Big5 common zone is reproducible via Python's
    built-in big5 codec, so no external character table is needed.
    """
    out = set()
    for hi in range(0xA4, 0xC7):
        low_bytes = list(range(0x40, 0x7F))
        if hi < 0xC6:               # C67E is the last common-zone code point
            low_bytes += list(range(0xA1, 0xFF))
        for lo in low_bytes:
            try:
                ch = bytes((hi, lo)).decode("big5")
            except UnicodeDecodeError:
                continue
            if len(ch) == 1 and 0x4E00 <= ord(ch) <= 0x9FFF:
                out.add(ord(ch))
    return out


def collect_from_source(src_root=None):
    """Collect every non-ASCII code point used in string literals in the tree.

    Keeps the charset in sync with the translations automatically, which is the
    only reliable way to avoid "character silently not drawn" bugs.
    """
    import re
    src_root = src_root or os.path.join(os.path.dirname(HERE), "..", "swiss-gc",
                                         "cube", "swiss", "source")
    src_root = os.path.abspath(src_root)
    skip = {"littlefs"}
    str_re = re.compile(r'"(?:\\.|[^"\\])*"')
    used = set()
    for root, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d not in skip]
        for name in files:
            if not name.endswith(".c"):
                continue
            path = os.path.join(root, name)
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    s = line.lstrip()
                    if s.startswith("*") or s.startswith("//"):
                        continue
                    for lit in str_re.findall(line):
                        for ch in lit:
                            cp = ord(ch)
                            if cp > 0xFF and cp != 0xFFFD:
                                used.add(cp)
    return sorted(used)


# Page geometry, tuned on hardware. The GX only keeps the first ~440 rows of a
# 512x512 I4 texture resident; beyond that the hardware sampled stale TMEM and
# glyphs came out blank. 512x256 (64 KB) fits comfortably, at the cost of more
# page switches: 512 glyphs per page instead of 1024.
PAGE_W = 512
PAGE_H = 256
COLS = PAGE_W // CELL
PER_PAGE = COLS * (PAGE_H // CELL)


def page_count(n):
    return (n + PER_PAGE - 1) // PER_PAGE


def write_c(codepoints, bitmaps, advances, header_path, source_path):
    n = len(codepoints)
    with open(header_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Auto-generated by tools/gen_font.py - do not edit */\n")
        fh.write("#ifndef CJKFONT_H\n#define CJKFONT_H\n\n")
        fh.write(f"#define CJKFONT_CELL      {CELL}\n")
        fh.write(f"#define CJKFONT_BYTES     {BYTES_PER_GLYPH}\n")
        fh.write(f"#define CJKFONT_COUNT     {n}\n")
        fh.write(f"#define CJKFONT_DRAW      {DRAW}\n")
        # Default advance, used only if the table lookup fails.
        fh.write(f"#define CJKFONT_ADVANCE   {ADVANCE}\n")
        fh.write(f"#define CJKFONT_PAGE_W    {PAGE_W}\n")
        fh.write(f"#define CJKFONT_PAGE_H    {PAGE_H}\n")
        fh.write(f"#define CJKFONT_COLS      {COLS}\n")
        fh.write(f"#define CJKFONT_PER_PAGE  {PER_PAGE}\n")
        fh.write(f"#define CJKFONT_PAGES     {page_count(n)}\n")
        fh.write(f"#define CJKFONT_FALLBACK_GLYPH {codepoints.index(FALLBACK_CP)}\n\n")
        fh.write("extern const unsigned int  cjkfont_codepoints[CJKFONT_COUNT];\n")
        fh.write("extern const unsigned char cjkfont_bitmaps[CJKFONT_COUNT * CJKFONT_BYTES];\n")
        fh.write("extern const unsigned char cjkfont_advance[CJKFONT_COUNT];\n\n")
        fh.write("/* binary search; returns glyph index or -1 */\n")
        fh.write("int cjkfont_lookup(unsigned int codepoint);\n\n#endif\n")

    with open(source_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Auto-generated by tools/gen_font.py - do not edit */\n")
        fh.write('#include "cjkfont.h"\n\n')
        fh.write(f"const unsigned int cjkfont_codepoints[CJKFONT_COUNT] = {{\n")
        for i in range(0, n, 8):
            chunk = ", ".join(f"0x{cp:04X}" for cp in codepoints[i:i + 8])
            fh.write(f"    {chunk},\n")
        fh.write("};\n\n")
        fh.write("const unsigned char cjkfont_advance[CJKFONT_COUNT] = {\n")
        for i in range(0, n, 16):
            chunk = ", ".join(f"{advances[j]:2d}" for j in range(i, min(i + 16, n)))
            fh.write(f"    {chunk},\n")
        fh.write("};\n\n")
        fh.write("/* 4bpp tiles in GX_TF_I4 order: 16 rows x 8 bytes, high nibble\n"
                 "   is the even pixel - the runtime copies them straight into\n"
                 "   the atlas texture. */\n")
        fh.write("const unsigned char cjkfont_bitmaps[CJKFONT_COUNT * CJKFONT_BYTES] = {\n")
        for idx in range(n):
            fh.write(f"    /* {chr(codepoints[idx])} U+{codepoints[idx]:04X} */\n")
            b = bitmaps[idx]
            for r in range(16):
                fh.write("    " + ", ".join(f"0x{b[r*8+k]:02X}" for k in range(8)) + ",\n")
        fh.write("};\n\n")
        fh.write("""int cjkfont_lookup(unsigned int codepoint)
{
    int lo = 0, hi = CJKFONT_COUNT - 1;
    while (lo <= hi) {
        int mid = (lo + hi) >> 1;
        if (cjkfont_codepoints[mid] == codepoint) return mid;
        if (cjkfont_codepoints[mid] < codepoint) lo = mid + 1;
        else hi = mid - 1;
    }
    return -1;
}
""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="")
    ap.add_argument("--charset", default=None)
    ap.add_argument("--from-source", action="store_true",
                    help="take the charset from the strings already in the source tree")
    ap.add_argument("--gb2312", action="store_true",
                    help="also include GB2312 level 1 (legacy, 3755 chars)")
    ap.add_argument("--gb2312-full", action="store_true",
                    help="include both GB2312 levels (6763 chars) for arbitrary "
                         "Simplified Chinese file names")
    ap.add_argument("--extra-chars", nargs="*", default=[], metavar="FILE",
                    help="extra UTF-8 text files whose non-ASCII characters "
                         "must be in the atlas (game name tables, variants)")
    ap.add_argument("--big5-common", action="store_true",
                    help="add the Big5 common-zone Hanzi (traditional/Japanese "
                         "game titles) on top of GB2312")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--font", default=TTF_FONT,
                    help="CJK outline font used to rasterise every glyph; "
                         "defaults to Noto Sans SC Medium")
    ap.add_argument("--unifont-only", action="store_true",
                    help="ignore the TTF and use GNU Unifont for everything")
    args = ap.parse_args()

    if args.from_source:
        codepoints = collect_from_source()
        print(f"charset from source: {len(codepoints)} code points")
    else:
        text = args.text or ("" if args.charset else DEFAULT_TEST)
        codepoints = collect_charset(text, args.charset)

    if args.gb2312:
        extra = sorted(ord(c) for c in gb2312_level1())
        codepoints = sorted(set(codepoints) | set(extra))
        print(f"charset with GB2312 level 1: {len(codepoints)} code points")
    if args.gb2312_full:
        extra = sorted(ord(c) for c in gb2312_full())
        codepoints = sorted(set(codepoints) | set(extra))
        print(f"charset with GB2312 level 1+2: {len(codepoints)} code points")
    if args.extra_chars:
        extra = set()
        for path in args.extra_chars:
            with open(path, encoding="utf-8", errors="replace") as fh:
                extra.update(ord(ch) for ch in fh.read() if ord(ch) > 0x7F)
            print(f"extra chars from {path}: {len(extra)} distinct so far")
        codepoints = sorted(set(codepoints) | extra)
        print(f"charset with extra chars: {len(codepoints)} code points")
    if args.big5_common:
        extra = big5_common_chars()
        codepoints = sorted(set(codepoints) | extra)
        print(f"charset with Big5 common zone ({len(extra)} Hanzi): "
              f"{len(codepoints)} code points")
    # Game titles also use traditional / Japanese variants outside GB2312.
    codepoints = sorted(set(codepoints) | {ord(c) for c in EXTRA_VARIANTS
                                           if ord(c) > 0x7F})
    # Printable ASCII is rendered from the same face as the Hanzi, so Latin
    # and digits stop looking like a second font pasted into the line.
    codepoints = sorted(set(codepoints) | set(ATLAS_ASCII))
    # Guarantee a visible fallback for anything still outside the atlas.
    codepoints = sorted(set(codepoints) | {FALLBACK_CP})
    if not codepoints:
        print("empty charset")
        return 1

    resolved, advances = build_bitmaps(
        codepoints, None if args.unifont_only else args.font)
    bitmaps = []
    adv_list = []
    fallback_adv = advances.get(FALLBACK_CP, ADVANCE)
    missing = []
    for cp in codepoints:
        b = resolved.get(cp)
        if b is None:
            missing.append(cp)
            b = bytes(BYTES_PER_GLYPH)
        bitmaps.append(b)
        adv_list.append(max(1, min(255, advances.get(cp, fallback_adv))))

    hp = os.path.join(args.out_dir, "cjkfont.h")
    sp = os.path.join(args.out_dir, "cjkfont.c")
    write_c(codepoints, bitmaps, adv_list, hp, sp)

    print(f"glyphs : {len(codepoints)}")
    print(f"data   : {len(codepoints) * BYTES_PER_GLYPH} bytes 4bpp")
    pages = page_count(len(codepoints))
    print(f"atlas  : {pages} page(s) of {PAGE_W}x{PAGE_H} I4 "
          f"= {pages * PAGE_W * PAGE_H // 2 // 1024} KB total, "
          f"{PER_PAGE} glyphs/page")
    if missing:
        print("MISSING in font:", " ".join(f"U+{c:04X}" for c in missing))
    print("wrote", hp)
    print("wrote", sp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
