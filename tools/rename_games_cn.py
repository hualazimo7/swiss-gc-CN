#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 Swiss SD 卡上 GameCube 游戏目录里的英文文件名批量改成中文译名。

只改文件名（FatFs f_rename），不改文件内容、不改扩展名、不跨目录移动。
所有操作通过 Swiss httpd 的 /rename 端点完成，因此 Swiss 当前设备必须是
那块 SD 卡（sdb:/），否则 /rename 会返回 FR_NOT_ENABLED(12)。

用法：
    python tools/rename_games_cn.py --dry-run          # 只校验并生成译名表
    python tools/rename_games_cn.py --apply           # 执行（可重复运行，自动跳过已完成）
    python tools/rename_games_cn.py --apply --recent  # 同时迁移 recent.ini
    python tools/rename_games_cn.py --rollback        # 一键还原全部文件名
    python tools/rename_games_cn.py --verify          # 复核目录状态

译名表在下面的 MAP 里，改完直接重跑 --apply 即可（已改过名的会自动跳过）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from swiss_client import SwissClient, SwissError  # noqa: E402

DEFAULT_HOST = "192.168.1.2"
DEFAULT_DIR = "sdb:/root/game/GameCube"
RECORD = ROOT / "dist" / "GameCube_改名记录.json"
MAPTABLE = ROOT / "dist" / "GameCube_中文译名表.md"
BAD_CHARS = set('<>:"/\\|?*')

# ---------------------------------------------------------------------------
# 译名表：原文件名 -> 中文文件名
# 约定：保留原扩展名（.nkit.iso / .iso / .gcm），多光盘用中文盘号区分，
#       去掉 (USA)/(En,Ja)/(Rev 1) 等英文区域与版本标记；
#       仅在同名游戏存在多个版本时补中文限定（如「美版」）。
# ---------------------------------------------------------------------------
MAP: dict[str, str] = {
    "Capcom vs. SNK 2 EO (USA).nkit.iso":
        "卡普空对SNK2 极限进攻.nkit.iso",
    "Dragon Ball Z - Budokai 2 (USA).nkit.iso":
        "龙珠Z-武道会2.nkit.iso",
    "DreamWorks Over the Hedge (Europe).nkit.iso":
        "篱笆墙外.nkit.iso",
    "Fantastic 4 (USA).nkit.iso":
        "神奇四侠.nkit.iso",
    "FireBlade (USA).nkit.iso":
        "火刃.nkit.iso",
    "Game Boy Player Start-Up Disc (USA) (v1.02) Lite.iso":
        "Game Boy 播放器启动盘（精简版）.iso",
    "Game Boy Player Start-Up Disc.iso":
        "Game Boy 播放器启动盘.iso",
    "Hudson Selection Vol. 4 - Takahashi-Meijin no Boukenjima (Japan).nkit.iso":
        "哈德森精选集4-高桥名人之冒险岛.nkit.iso",
    "Ice Age 2 - The Meltdown (USA).nkit.iso":
        "冰川时代2-融冰之灾.nkit.iso",
    "Intellivision Lives! (USA).nkit.iso":
        "Intellivision 经典游戏合集.nkit.iso",
    "Legend of Zelda, The - Collector's Edition (USA).nkit.iso":
        "塞尔达传说-典藏版.nkit.iso",
    "Legend of Zelda, The - Ocarina of Time & Master Quest (USA).iso":
        "塞尔达传说-时之笛与大师任务.iso",
    "Lord of the Rings, The - The Two Towers (USA).nkit.iso":
        "指环王-双塔奇兵.nkit.iso",
    "Luigi's Mansion (USA).nkit.iso":
        "路易吉洋馆.nkit.iso",
    "Mario Kart - Double Dash!! (USA).nkit.iso":
        "马里奥赛车-双重冲刺.nkit.iso",
    "Mario Party 5 (USA).nkit.iso":
        "马里奥聚会5.nkit.iso",
    "Mario Party 6 (USA).nkit.iso":
        "马里奥聚会6.nkit.iso",
    "Medabots Infinity (USA).nkit.iso":
        "徽章战士-无限.nkit.iso",
    "Mega Man Anniversary Collection (USA) (Rev 1).nkit.iso":
        "洛克人周年纪念合集.nkit.iso",
    "Metal Gear Solid - The Twin Snakes (Japan) (En,Ja) (Disc 1).nkit.iso":
        "合金装备-双蛇（第1张）.nkit.iso",
    "Metal Gear Solid - The Twin Snakes (Japan) (En,Ja) (Disc 2).nkit.iso":
        "合金装备-双蛇（第2张）.nkit.iso",
    "Midway Arcade Treasures (USA).nkit.iso":
        "街机珍宝合集.nkit.iso",
    "Midway Arcade Treasures 2 (USA).nkit.iso":
        "街机珍宝合集2.nkit.iso",
    "Mortal Kombat - Deception (USA).nkit.iso":
        "真人快打-欺骗.nkit.iso",
    "Namco Museum (USA).nkit.iso":
        "南梦宫博物馆.nkit.iso",
    "NBA Live 06 (USA).iso":
        "劲爆美国职篮06.iso",
    "Need for Speed - Most Wanted (USA).iso":
        "极品飞车-最高通缉.iso",
    "Need for Speed - Underground 2 (USA).iso":
        "极品飞车-地下狂飙2.iso",
    "Nick Jr. Dora the Explorer - Journey to the Purple Planet (USA).nkit.iso":
        "爱探险的朵拉-紫色星球之旅.nkit.iso",
    "Prince of Persia - The Sands of Time (USA) (En,Fr,Es).nkit.iso":
        "波斯王子-时之砂.nkit.iso",
    "Resident Evil 4 (USA) (Disc 1).nkit.iso":
        "生化危机4（美版 第1张）.nkit.iso",
    "Resident Evil 4 (USA) (Disc 2).nkit.iso":
        "生化危机4（美版 第2张）.nkit.iso",
    "Shonen Jump's One Piece - Grand Adventure (USA).iso":
        "海贼王-伟大冒险.iso",
    "Simpsons, The - Hit & Run (USA).iso":
        "辛普森一家-横冲直撞.iso",
    "Sonic Gems Collection (USA).iso":
        "索尼克宝石合集.iso",
    "Sonic Heroes (USA) (En,Ja,Fr,De,Es,It).iso":
        "索尼克英雄.iso",
    "Soulcalibur II (USA).iso":
        "灵魂能力2.iso",
    "Spawn - Armageddon (USA).nkit.iso":
        "再生侠-末日.nkit.iso",
    "Star Fox - Assault (USA).iso":
        "星际火狐-突击.iso",
    "Star Fox Adventures (USA).iso":
        "星际火狐大冒险.iso",
    "Super Monkey Ball (USA).nkit.iso":
        "超级猴子球.nkit.iso",
    "Super Smash Bros. Melee (USA) (En,Ja) (Rev 1).nkit.iso":
        "任天堂明星大乱斗DX.nkit.iso",
    "swiss document.txt":
        "Swiss 使用说明.txt",
    "Tales of Symphonia (USA) (Disc 2).nkit.iso":
        "仙乐传说（第2张）.nkit.iso",
    "Teenage Mutant Ninja Turtles (USA).nkit.iso":
        "忍者神龟.nkit.iso",
    "Teenage Mutant Ninja Turtles 2 - Battle Nexus (USA) (Disc 1).iso":
        "忍者神龟2-战斗枢纽（第1张）.iso",
    "Teenage Mutant Ninja Turtles 2 - Battle Nexus (USA) (Disc 2).iso":
        "忍者神龟2-战斗枢纽（第2张）.iso",
    "TMNT - Mutant Melee (USA).iso":
        "忍者神龟-变种格斗.iso",
    "Tom and Jerry in War of the Whiskers (USA).nkit.iso":
        "猫和老鼠-胡须大战.nkit.iso",
    "Tom Clancy's Splinter Cell - Pandora Tomorrow (USA) (Rev 1).nkit.iso":
        "细胞分裂-明日潘多拉.nkit.iso",
    "Ultimate Spider-Man (USA).iso":
        "终极蜘蛛侠.iso",
    "Viewtiful Joe 2 (USA).nkit.iso":
        "红侠乔伊2.nkit.iso",
    "Wario World (USA).nkit.iso":
        "瓦力欧世界.nkit.iso",
    "WarioWare, Inc. - Mega Party Game$! (USA).nkit.iso":
        "瓦力欧制造-超级派对.nkit.iso",
    "Worms 3D (USA) (En,Fr).nkit.iso":
        "百战天虫3D.nkit.iso",
    "Worms Blast (USA) (En,Fr,Es).nkit.iso":
        "百战天虫-爆破.nkit.iso",
}

EXTS = (".nkit.iso", ".iso", ".gcm", ".dol", ".txt")


def suffix(name: str) -> str:
    for e in EXTS:
        if name.lower().endswith(e):
            return e
    return ""


def remote(dirpath: str, name: str) -> str:
    return "%s/%s" % (dirpath.rstrip("/"), name)


def header_len(host: str, src: str, dst: str) -> int:
    path = "/rename?from=%s&to=%s" % (
        urllib.parse.quote(src, safe=":/"),
        urllib.parse.quote(dst, safe=":/"),
    )
    head = "GET %s HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n" % (path, host)
    return len(head.encode("ascii"))


def check(host: str, dirpath: str, entries: dict[str, int]) -> list[str]:
    """返回问题列表；空列表表示可以安全执行。"""
    problems: list[str] = []
    seen: dict[str, str] = {}
    for old, new in MAP.items():
        if old not in entries:
            # 已改名过的文件不算错误（断点续做时旧名必然不存在）
            if new not in entries:
                problems.append("源文件和目标文件都不存在：%s" % old)
            continue
        if old == new:
            problems.append("原名与目标名相同：%s" % old)
        if suffix(old) != suffix(new):
            problems.append("扩展名被改动：%s -> %s" % (old, new))
        bad = [c for c in new if c in BAD_CHARS or ord(c) < 32]
        if bad:
            problems.append("目标名含 FAT 非法字符 %r：%s" % (bad, new))
        if len(new.encode("utf-8")) > 240:
            problems.append("目标名超过 240 字节：%s" % new)
        if new in seen:
            problems.append("两个游戏重名：%s / %s -> %s" % (seen[new], old, new))
        seen[new] = old
        if new in entries and old in entries:
            problems.append("目标名已被占用：%s" % new)
        n = header_len(host, remote(dirpath, old), remote(dirpath, new))
        if n >= 1000:
            problems.append("请求头 %d 字节，超出 Swiss httpd 上限：%s" % (n, old))
    return problems


def write_maptable(entries: dict[str, int]) -> None:
    MAPTABLE.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GameCube 游戏中文译名表",
        "",
        "目录：`sdb:/root/game/GameCube/`　生成时间：%s"
        % dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "",
        "仅改文件名，不改内容与扩展名；`--rollback` 可一键还原。",
        "",
        "| # | 原文件名 | 中文文件名 | 大小 |",
        "|---:|---|---|---:|",
    ]
    for i, (old, new) in enumerate(MAP.items(), 1):
        size = entries.get(old, entries.get(new, 0))
        lines.append("| %d | `%s` | `%s` | %s |"
                     % (i, old, new, format(size, ",")))
    lines += [
        "",
        "## 未改动的文件",
        "",
        "已是中文名或非游戏文件，保持原样：",
        "",
    ]
    for name in sorted(entries):
        if name not in MAP and name not in MAP.values():
            lines.append("- `%s`" % name)
    lines += [
        "",
        "## 命名约定",
        "",
        "- 保留原扩展名（`.nkit.iso` / `.iso` 等），Swiss 靠扩展名识别格式。",
        "- 去掉 `(USA)` / `(En,Ja)` / `(Rev 1)` 等英文区域语言版本标记。",
        "- 多光盘游戏加 `（第1张）` / `（第2张）` 中文盘号，避免重名。",
        "- 与已有中文名同游戏时补中文限定，例如 `生化危机4（美版 第1张）`。",
        "- 品牌/缩写专名保留通用写法（Game Boy、Intellivision、SNK、DX、3D）。",
        "",
    ]
    MAPTABLE.write_text("\n".join(lines), encoding="utf-8")


def load_entries(c: SwissClient, dirpath: str) -> dict[str, int]:
    return {e.name: e.size for e in c.listdir(dirpath) if not e.is_dir}


def save_record(data: dict) -> None:
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def do_apply(c: SwissClient, host: str, dirpath: str, entries: dict[str, int]) -> int:
    if RECORD.exists():
        rec = json.loads(RECORD.read_text(encoding="utf-8"))
    else:
        rec = {
            "host": host,
            "dir": dirpath,
            "created": dt.datetime.now().isoformat(timespec="seconds"),
            "applied": [],
        }
    done = {x["old"] for x in rec["applied"]}
    n_ok = n_skip = 0
    for old, new in MAP.items():
        src = remote(dirpath, old)
        dst = remote(dirpath, new)
        if old not in entries:
            if new in entries:
                if old not in done:
                    rec["applied"].append({"old": old, "new": new,
                                           "size": entries[new]})
                    save_record(rec)
                n_skip += 1
                continue
            raise SwissError("源文件和目标文件都不存在：%s" % old)
        if new in entries:
            raise SwissError("目标名已被占用，停止以免覆盖：%s" % new)
        reply = c.rename(src, dst)
        print("  [%2d/%d] %s  ->  %s" % (n_ok + 1, len(MAP), old, new))
        rec["applied"].append({"old": old, "new": new, "size": entries[old]})
        save_record(rec)
        n_ok += 1
    rec["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    save_record(rec)
    print("改名完成：新改 %d 项，跳过已完成 %d 项，累计 %d 项"
          % (n_ok, n_skip, len(rec["applied"])))
    return n_ok


def do_rollback(c: SwissClient, dirpath: str) -> int:
    if not RECORD.exists():
        raise SwissError("没有改名记录，无法回滚：%s" % RECORD)
    rec = json.loads(RECORD.read_text(encoding="utf-8"))
    entries = load_entries(c, dirpath)
    n = 0
    for item in reversed(rec["applied"]):
        old, new = item["old"], item["new"]
        if new not in entries:
            if old in entries:
                continue
            print("  跳过（两个名字都不存在）：%s" % new)
            continue
        if old in entries:
            raise SwissError("原名已被占用，停止回滚：%s" % old)
        c.rename(remote(dirpath, new), remote(dirpath, old))
        print("  还原：%s  ->  %s" % (new, old))
        n += 1
    print("回滚完成：%d 项" % n)
    return n


def do_recent(c: SwissClient, dirpath: str) -> None:
    """recent.ini 里保存的是完整路径，改名后要同步，否则「最近打开」会指向不存在的文件。"""
    p = "sdb:/swiss/settings/recent.ini"
    tmp = ROOT / "tmp" / "recent_migrated.ini"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    bak = ROOT / "tmp" / "recent_before_rename.ini"
    c.download(p, str(bak))
    text = bak.read_text(encoding="utf-8", errors="replace")
    n = 0
    for old, new in MAP.items():
        a, b = remote(dirpath, old), remote(dirpath, new)
        if a in text:
            text = text.replace(a, b)
            n += 1
    tmp.write_text(text, encoding="utf-8")
    if n == 0:
        print("recent.ini 无需迁移（没有指向旧文件名的记录）")
        return
    c.upload(str(tmp), p, verify=True)
    back = ROOT / "tmp" / "recent_readback.ini"
    c.download(p, str(back))
    ok = back.read_text(encoding="utf-8", errors="replace") == text
    print("recent.ini 已迁移 %d 条路径，回读一致：%s" % (n, ok))
    if not ok:
        raise SwissError("recent.ini 回读不一致")


def do_verify(c: SwissClient, dirpath: str) -> None:
    entries = load_entries(c, dirpath)
    missing = [new for new in MAP.values() if new not in entries]
    left = [old for old in MAP if old in entries]
    size_bad = []
    if RECORD.exists():
        rec = json.loads(RECORD.read_text(encoding="utf-8"))
        for x in rec["applied"]:
            if x["new"] in entries and entries[x["new"]] != x["size"]:
                size_bad.append((x["new"], x["size"], entries[x["new"]]))
    print("目录文件数：%d" % len(entries))
    print("中文目标缺失：%d" % len(missing))
    print("英文原名残留：%d" % len(left))
    print("大小不符：%d" % len(size_bad))
    for m in missing[:10]:
        print("  缺失 %s" % m)
    for m in left[:10]:
        print("  残留 %s" % m)
    for name, want, got in size_bad[:10]:
        print("  大小 %s: %d -> %d" % (name, want, got))
    print("VERIFY: %s" % ("PASS" if not (missing or left or size_bad) else "FAIL"))
    print("英文名（非游戏 / 已是中文的除外）：")
    for name in sorted(entries):
        if name not in MAP and name not in MAP.values():
            print("  ", name)


def main() -> int:
    ap = argparse.ArgumentParser(description="Swiss SD 卡 GameCube 游戏名中文化")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--dir", default=DEFAULT_DIR)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="只校验并生成译名表")
    g.add_argument("--apply", action="store_true", help="执行改名")
    g.add_argument("--rollback", action="store_true", help="一键还原")
    g.add_argument("--verify", action="store_true", help="复核目录状态")
    ap.add_argument("--recent", action="store_true", help="apply 时同步 recent.ini")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    c = SwissClient(args.host)
    try:
        if args.rollback:
            do_rollback(c, args.dir)
            return 0
        if args.verify:
            do_verify(c, args.dir)
            return 0

        entries = load_entries(c, args.dir)
        print("已连接 %s，目录 %s，共 %d 个文件" % (args.host, args.dir, len(entries)))
        problems = check(args.host, args.dir, entries)
        write_maptable(entries)
        print("译名表：%s" % MAPTABLE)
        if problems:
            print("校验发现 %d 个问题：" % len(problems))
            for p in problems:
                print("  -", p)
            return 2
        print("校验通过：%d 条映射，无重名 / 无占用 / 无非法字符 / 请求头全部 < 1000 B"
              % len(MAP))
        if args.dry_run:
            for old, new in MAP.items():
                print("  %s\n    -> %s" % (old, new))
            return 0
        do_apply(c, args.host, args.dir, entries)
        if args.recent:
            do_recent(c, args.dir)
        do_verify(c, args.dir)
        return 0
    except (SwissError, OSError) as exc:
        print("错误：%s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
