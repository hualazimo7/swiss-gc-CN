#!/usr/bin/env python3
"""Generate cjkfont.c / cjkfont.h for a given charset.

Glyph storage: 1bpp, 16 rows x 2 bytes, MSB = leftmost pixel.
The runtime expands this into a GX I4 atlas (tiled/swizzled) once at init.

Glyphs come from a TrueType font that ships an embedded 16 px bitmap strike
(SimSun by default); anything it lacks falls back to GNU Unifont.

Usage:
  python gen_font.py --text "中文测试"
  python gen_font.py --charset out/charset.txt
  python gen_font.py --from-source --gb2312        # level 1 only (legacy)
  python gen_font.py --from-source --gb2312-full \
      --extra-chars ../dist/GameCube_中文译名表.md
  python gen_font.py --font C:/Windows/Fonts/simhei.ttf --from-source
  python gen_font.py --unifont-only --from-source  # old thin-stroke fallback

Production rule: file names are user data that arrive AFTER the firmware was
built, so the atlas must cover more than the strings compiled into Swiss.
--gb2312-full adds GB2312 level 2 (rare-but-real chars such as 噩 / 飙);
--big5-common adds the Big5 common-zone Hanzi so traditional/Japanese game
titles (e.g. 斑鳩, whose 鳩 U+9CE9 is outside GB2312) render correctly;
--extra-chars folds in any additional text (game name tables, variants).
Whatever is still missing renders as a tofu box instead of a silent blank.
ASCII digits 0-9 are always included: in mixed strings the firmware draws
them from this atlas so they match the Hanzi face and baseline.

Production command (r8+, 8887 glyphs / 18 atlas pages):
  python source/tools/gen_font.py --from-source --gb2312-full --big5-common \
      --extra-chars <game-name-table.md> --unifont-only
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = os.path.join(HERE, "..", "fonts", "unifont.hex")
def _env_path(var, default_rel):
    """Resolve a workspace path; override with an env var on other machines."""
    import os
    from pathlib import Path
    base = Path(os.environ.get(
        "SWISS_GC_WORKSPACE", str(Path(__file__).resolve().parents[3])))
    return Path(os.environ[var]) if os.environ.get(var) else base / default_rel


OUT_DIR = str(_env_path("SWISS_GC_GUI", "swiss-gc/cube/swiss/source/gui"))

CELL = 16
BYTES_PER_GLYPH = 32
# Always present in the atlas. Drawn whenever cjkfont_lookup() fails, so a
# missing code point shows up as a visible box rather than an empty gap.
FALLBACK_CP = 0x25A1  # □
# ASCII 0-9 are stored in the atlas too. Inside a string that contains CJK,
# IPLFontWrite.c routes these ten code points through the CJK path so digits
# use the very same 16x16 Unifont face, weight and baseline as the Hanzi next
# to them (the IPL ROM digits are a heavier, rounded face and used to read as
# a different font). Pure Latin strings still use the IPL font unchanged.
# Unifont keeps narrow glyphs centred at x=4..11, hence the half-width advance.
ATLAS_DIGITS = tuple(range(0x30, 0x3A))
# On-screen size of a glyph quad. Kept equal to CELL so the bitmap maps 1:1
# onto the screen; any upscale makes GX_NEAR repeat whole rows and columns.
DRAW = 16

# Optional glyph source: a TrueType font that ships an embedded 16 px bitmap
# strike (SimSun does). FreeType then returns exact 1bpp pixels, the same
# classic 16x16 dot matrix HZK16 and DOS-era Chinese software used.
#
# Off by default. Compared glyph by glyph, SimSun and Unifont produce identical
# bitmaps for 3714 of the 3769 characters; the 55 that differ are mostly
# punctuation, where SimSun's strike places 。：…“ at the LEFT edge of the cell
# (half-width forms meant for proportional text) and Unifont centres them
# properly. Unifont is also self-contained, so the build stays reproducible
# without a Windows font. Pass --font to opt in.
TTF_FONT = os.environ.get("CJK_TTF")     # e.g. C:\Windows\Fonts\simsun.ttc
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


def rasterize_ttf(codepoints, path=TTF_FONT, index=TTF_INDEX, size=TTF_SIZE):
    """Render each code point to a 16x16 1bpp bitmap.

    Uses the font's own embedded bitmap strike when it has one (SimSun at
    16 px), otherwise falls back to FreeType's hinted outline, thresholded to
    1bpp. Code points with no ink are left out so the caller can try Unifont.
    """
    if not path or not os.path.exists(path):
        print(f"font unavailable, falling back to Unifont: {path}")
        return {}
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow missing (pip install pillow), falling back to Unifont")
        return {}
    try:
        font = ImageFont.truetype(path, size, index=index)
    except OSError as exc:
        print(f"cannot open {path}: {exc}; falling back to Unifont")
        return {}

    img = Image.new("L", (CELL, CELL), 0)
    draw = ImageDraw.Draw(img)
    blank = [0, 0, CELL - 1, CELL - 1]
    out = {}
    for cp in codepoints:
        draw.rectangle(blank, fill=0)
        draw.text((0, 0), chr(cp), font=font, fill=255, anchor="la")
        px = img.load()
        rows = bytearray()
        ink = False
        for y in range(CELL):
            bits = 0
            for x in range(CELL):
                if px[x, y] > 127:
                    bits |= 0x8000 >> x
                    ink = True
            rows.append((bits >> 8) & 0xFF)
            rows.append(bits & 0xFF)
        if ink:
            out[cp] = bytes(rows)
    return out


def unifont_bytes(glyphs, cp):
    """Fallback glyph: expand a Unifont .hex row into the 32-byte 1bpp bitmap.

    Unifont stores CJK as 16x16 (64 hex digits) but Latin/punctuation as 8x16
    (32 hex digits). Narrow glyphs are centred in the 16 px cell so punctuation
    like “ ” sits sensibly next to CJK.
    """
    d = glyphs.get(cp)
    if not d:
        return None
    out = bytearray()
    if len(d) >= 64:
        for r in range(16):
            row = int(d[r * 4:(r + 1) * 4], 16)
            out.append((row >> 8) & 0xFF)
            out.append(row & 0xFF)
        return bytes(out)
    if len(d) >= 32:
        for r in range(16):
            b = int(d[r * 2:(r + 1) * 2], 16)      # 8 px, bit7 = leftmost
            row = (b << 4) & 0xFFFF                # centre: x = 4..11
            out.append((row >> 8) & 0xFF)
            out.append(row & 0xFF)
        return bytes(out)
    return None


def build_bitmaps(codepoints, font_path=TTF_FONT):
    """Resolve every code point to a 32-byte bitmap: TTF first, Unifont second."""
    ttf = rasterize_ttf(codepoints, font_path) if font_path else {}
    if ttf:
        print(f"glyph source : {os.path.basename(font_path)} at {TTF_SIZE}px "
              f"-> {len(ttf)}/{len(codepoints)}")
    else:
        print("glyph source : GNU Unifont (built-in)")
    fallback = [cp for cp in codepoints if cp not in ttf]
    unifont = load_font() if fallback else {}
    out = {}
    from_unifont = 0
    missing = []
    for cp in codepoints:
        b = ttf.get(cp)
        if b is None:
            b = unifont_bytes(unifont, cp)
            if b is not None:
                from_unifont += 1
        if b is None:
            missing.append(cp)
        else:
            out[cp] = b
    if from_unifont:
        print(f"glyph fallback: Unifont -> {from_unifont}")
    if missing:
        print("no glyph for: " + " ".join(f"U+{cp:04X}" for cp in missing))
    return out


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


def write_c(codepoints, bitmaps, header_path, source_path):
    n = len(codepoints)
    with open(header_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("/* Auto-generated by tools/gen_font.py - do not edit */\n")
        fh.write("#ifndef CJKFONT_H\n#define CJKFONT_H\n\n")
        fh.write(f"#define CJKFONT_CELL      {CELL}\n")
        fh.write(f"#define CJKFONT_BYTES     {BYTES_PER_GLYPH}\n")
        fh.write(f"#define CJKFONT_COUNT     {n}\n")
        # Drawn size on screen. The bitmap is 16x16 but the IPL Latin glyphs
        # read larger, so we upscale slightly; GX_LINEAR smooths the stretch.
        fh.write(f"#define CJKFONT_DRAW      {DRAW}\n")
        fh.write(f"#define CJKFONT_ADVANCE   {DRAW + 1}\n")
        fh.write(f"#define CJKFONT_PAGE_W    {PAGE_W}\n")
        fh.write(f"#define CJKFONT_PAGE_H    {PAGE_H}\n")
        fh.write(f"#define CJKFONT_COLS      {COLS}\n")
        fh.write(f"#define CJKFONT_PER_PAGE  {PER_PAGE}\n")
        fh.write(f"#define CJKFONT_PAGES     {page_count(n)}\n")
        fh.write(f"#define CJKFONT_FALLBACK_GLYPH {codepoints.index(FALLBACK_CP)}\n\n")
        fh.write("extern const unsigned int  cjkfont_codepoints[CJKFONT_COUNT];\n")
        fh.write("extern const unsigned char cjkfont_bitmaps[CJKFONT_COUNT * CJKFONT_BYTES];\n\n")
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
        fh.write("const unsigned char cjkfont_bitmaps[CJKFONT_COUNT * CJKFONT_BYTES] = {\n")
        for idx in range(n):
            fh.write(f"    /* {chr(codepoints[idx])} U+{codepoints[idx]:04X} */\n")
            b = bitmaps[idx]
            for r in range(16):
                fh.write(f"    0x{b[r*2]:02X}, 0x{b[r*2+1]:02X},\n")
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
                    help="optional TrueType font with a 16 px bitmap strike; "
                         "default is Unifont")
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
    # Digits in mixed CJK/Latin strings are drawn from this atlas, not the IPL
    # font, so they must be present even though collect_charset() drops ASCII.
    codepoints = sorted(set(codepoints) | set(ATLAS_DIGITS))
    # Guarantee a visible fallback for anything still outside the atlas.
    codepoints = sorted(set(codepoints) | {FALLBACK_CP})
    if not codepoints:
        print("empty charset")
        return 1

    resolved = build_bitmaps(codepoints, None if args.unifont_only else args.font)
    bitmaps = []
    missing = []
    for cp in codepoints:
        b = resolved.get(cp)
        if b is None:
            missing.append(cp)
            b = bytes(BYTES_PER_GLYPH)
        bitmaps.append(b)

    hp = os.path.join(args.out_dir, "cjkfont.h")
    sp = os.path.join(args.out_dir, "cjkfont.c")
    write_c(codepoints, bitmaps, hp, sp)

    print(f"glyphs : {len(codepoints)}")
    print(f"data   : {len(codepoints) * BYTES_PER_GLYPH} bytes 1bpp")
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
