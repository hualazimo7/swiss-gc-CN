#!/usr/bin/env python3
"""Immutable release helper for swiss-gc-CN.

Published releases are FROZEN.  This tool refuses to overwrite an existing
tag, release, or archive, so history can never be silently replaced again.
See docs/RELEASE_POLICY.md for the full rules.

Typical workflow::

    # 1. build the archive only (no network side effects, safe to repeat)
    python tools/publish_release.py --tag v2154-zh-r6 --notes notes.md

    # 2. review the archive, then publish it under a NEW tag (no repacking)
    python tools/publish_release.py --tag v2154-zh-r6 --notes notes.md --publish --reuse

Never use `gh release upload --clobber`, `gh release delete-asset`, or
`gh release edit --notes-file` on a published tag.  Fix a bad release by
publishing a new tag, not by editing the old one.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO.parent / "releases"

# Files that are part of the repository but must not ship in the SD-card pack.
SKIP_NAMES = {".gitignore"}
SKIP_PARTS = {"__pycache__", ".git"}


def run(args, *, cwd=REPO, binary=False, check=True):
    r = subprocess.run(args, cwd=cwd, capture_output=True,
                       text=not binary, encoding=None if binary else "utf-8")
    if check and r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace") if binary else (r.stderr or "")
        raise RuntimeError("%s failed (%d): %s" %
                           (" ".join(str(a) for a in args), r.returncode, err.strip()))
    return r


def git(*args, **kw):
    return run(["git", *args], **kw)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_target(target: str) -> tuple[str, str]:
    full = git("rev-parse", target).stdout.strip()
    short = full[:8]
    return full, short


def guard_tag(tag: str, *, remote: bool) -> None:
    """Abort if the tag or release already exists anywhere."""
    local = git("tag", "-l", tag).stdout.strip()
    if local:
        raise RuntimeError("tag %s already exists locally -> pick a NEW tag" % tag)

    if remote:
        # A single call lists everything, so a network failure aborts instead
        # of silently passing the check.
        r = run(["gh", "release", "list", "--limit", "200",
                 "--json", "tagName", "--jq", ".[].tag_name"], check=True)
        existing = {x.strip() for x in r.stdout.splitlines() if x.strip()}
        if tag in existing:
            raise RuntimeError("release %s already exists on GitHub -> pick a NEW tag" % tag)
        tags = git("ls-remote", "--tags", "origin", "refs/tags/" + tag).stdout.strip()
        if tags:
            raise RuntimeError("tag %s already exists on origin -> pick a NEW tag" % tag)


def use_existing_archive(src: Path, target_sha: str, out_zip: Path) -> dict:
    """Ship a previously published archive byte-for-byte (history recovery).

    The old packs were built from the worktree, so their text files do not
    always match the git blobs.  For archived releases we keep the original
    bytes and verify the firmware against that commit's SHA256SUMS instead.
    """
    if not src.is_file():
        raise RuntimeError("archive not found: %s" % src)
    if out_zip.exists():
        raise RuntimeError("archive already exists, refusing to overwrite: %s" % out_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.testzip() is not None:
            raise RuntimeError("archive failed CRC check: %s" % src)
        names = z.namelist()
        if "firmware/swiss.dol" not in names:
            raise RuntimeError("not a swiss-gc-CN full pack: %s" % src)
        fw = z.read("firmware/swiss.dol")
        count = len([n for n in names if not n.endswith("/")])
        sums = (z.read("SHA256SUMS.txt").decode("utf-8", "replace")
                if "SHA256SUMS.txt" in names else "")
    expected = git("show", "%s:SHA256SUMS.txt" % target_sha).stdout
    if sha256(fw) not in expected:
        raise RuntimeError("firmware in %s does not match commit %s" % (src.name, target_sha[:8]))
    out_zip.write_bytes(data)
    return {"archive": str(out_zip), "files": count, "bytes": len(data),
            "sha256": sha256(data), "firmware_sums": sums,
            "source": "original published pack (byte-identical)"}


def describe_archive(archive: Path, target_sha: str) -> dict:
    """Read-only check of an already-built archive before publishing it."""
    if not archive.is_file():
        raise RuntimeError("no archive to reuse: %s (run without --reuse first)" % archive)
    data = archive.read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if z.testzip() is not None:
            raise RuntimeError("archive failed CRC check: %s" % archive)
        names = z.namelist()
        fw = z.read("firmware/swiss.dol") if "firmware/swiss.dol" in names else b""
        sums = (z.read("SHA256SUMS.txt").decode("utf-8", "replace")
                if "SHA256SUMS.txt" in names else "")
        count = len([n for n in names if not n.endswith("/")])
    expected = git("show", "%s:SHA256SUMS.txt" % target_sha).stdout
    if not fw or sha256(fw) not in expected:
        raise RuntimeError("firmware in %s does not match commit %s" %
                           (archive.name, target_sha[:8]))
    return {"archive": str(archive), "files": count, "bytes": len(data),
            "sha256": sha256(data), "firmware_sums": sums,
            "source": "reused archive (unchanged)"}


def build_archive(target_sha: str, out_zip: Path) -> dict:
    """Reproduce the exact git tree of target_sha as a distributable zip."""
    if out_zip.exists():
        raise RuntimeError("archive already exists, refusing to overwrite: %s" % out_zip)
    out_zip.parent.mkdir(parents=True, exist_ok=True)

    # Disable autocrlf so zip entries are byte-identical to the git blobs.
    raw = git("-c", "core.autocrlf=false", "archive", "--format=zip",
              target_sha, binary=True).stdout
    entries = []
    with zipfile.ZipFile(io.BytesIO(raw)) as src:
        for info in src.infolist():
            p = Path(info.filename)
            if info.is_dir() or p.name in SKIP_NAMES or SKIP_PARTS.intersection(p.parts):
                continue
            entries.append((info.filename, src.read(info.filename)))

    if not entries:
        raise RuntimeError("git archive produced no files")

    # Verify every byte against the git object database, not the worktree.
    for name, data in entries:
        blob = git("show", "%s:%s" % (target_sha, name), binary=True).stdout
        if blob != data:
            raise RuntimeError("tree mismatch: %s" % name)

    tmp = out_zip.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in entries:
            z.writestr(name, data)
    with zipfile.ZipFile(tmp) as z:
        if z.testzip() is not None:
            raise RuntimeError("archive failed CRC check")
    tmp.replace(out_zip)

    data = out_zip.read_bytes()
    sums = ""
    with zipfile.ZipFile(out_zip) as z:
        if "SHA256SUMS.txt" in z.namelist():
            sums = z.read("SHA256SUMS.txt").decode("utf-8").strip()
    return {
        "archive": str(out_zip),
        "files": len(entries),
        "bytes": len(data),
        "sha256": sha256(data),
        "firmware_sums": sums,
    }


def publish(tag: str, target_full: str, title: str, notes: Path,
            archive: Path, latest: bool) -> str:
    cmd = ["gh", "release", "create", tag,
           "--target", target_full,
           "--title", title,
           "--notes-file", str(notes),
           "--latest=" + ("true" if latest else "false"),
           str(archive)]
    r = run(cmd, check=True)
    return (r.stdout or "").strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="build / publish an immutable swiss-gc-CN release")
    ap.add_argument("--tag", required=True,
                    help="NEW tag, e.g. v2154-zh-r6 (must not exist yet)")
    ap.add_argument("--target", default="HEAD",
                    help="commit the release should point at (default: HEAD)")
    ap.add_argument("--notes", type=Path,
                    help="markdown notes file; required for --publish")
    ap.add_argument("--title", default=None, help="release title (default: tag)")
    ap.add_argument("--archive", type=Path,
                    help="ship this existing pack byte-for-byte (history recovery); "
                         "otherwise the pack is rebuilt from --target's git tree")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--latest", action="store_true",
                    help="mark as Latest (default: false, keeps v2154-zh as Latest)")
    ap.add_argument("--publish", action="store_true",
                    help="actually create the GitHub release; otherwise just build the archive")
    ap.add_argument("--reuse", action="store_true",
                    help="publish the already-built archive instead of packing again")
    args = ap.parse_args()

    if not args.tag.startswith("v2154-zh"):
        print("warning: unexpected tag prefix %r" % args.tag, file=sys.stderr)
    if args.publish and not (args.notes and args.notes.is_file()):
        ap.error("--publish requires an existing --notes file")

    try:
        full, short = resolve_target(args.target)
        guard_tag(args.tag, remote=args.publish)
        archive = args.out_dir / ("swiss-gc-CN_%s_full.zip" % args.tag)
        if args.reuse:
            info = describe_archive(archive, full)
        elif args.archive:
            info = use_existing_archive(args.archive.resolve(), full, archive)
        else:
            info = build_archive(full, archive)
            info["source"] = "rebuilt from git tree %s (byte-identical to blobs)" % short
        info.update({"tag": args.tag, "target": full, "short": short})
        print(json.dumps(info, ensure_ascii=False, indent=2))

        if not args.publish:
            print("\n[pack-only] nothing published. Review the archive, then re-run with --publish.")
            return 0

        url = publish(args.tag, full, args.title or args.tag,
                      args.notes.resolve(), archive.resolve(), args.latest)
        print("\npublished:", url or args.tag)
        print("This release is now FROZEN. Never re-upload its assets or edit its notes.")
        return 0
    except (RuntimeError, OSError, zipfile.BadZipFile) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
