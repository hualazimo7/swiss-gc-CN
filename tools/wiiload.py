#!/usr/bin/env python3
"""Push a DOL/ELF to a running Swiss over TCP (wiiload v5 protocol).

Swiss listens on TCP 4299 (see cube/swiss/source/wiiload.c). The wire format is
a packed big-endian header followed by a zlib stream and the argv blob:

    char  magic[4]       "HAXX"
    u16   version        5
    u16   args_size
    u32   deflate_size   len(zlib stream)
    u32   inflate_size   len(raw file)

Usage:
    python tools/wiiload.py 192.168.1.42 build/swiss.dol
    python tools/wiiload.py 192.168.1.42 swiss.dol --arg swiss.dol

After a successful push Swiss decompresses the DOL into ARAM and boots it,
replacing the running instance. Power-cycle the console to fall back to the
known-good DOL on the SD card.
"""
import argparse
import os
import socket
import struct
import sys
import time
import zlib

PORT = 4299
MAGIC = b"HAXX"
VERSION = 5


def build_payload(path, arg_name):
    with open(path, "rb") as fh:
        raw = fh.read()
    comp = zlib.compress(raw, 9)
    args = (arg_name or os.path.basename(path)).encode("ascii", "replace") + b"\0"
    header = MAGIC + struct.pack(">HHII", VERSION, len(args), len(comp), len(raw))
    return header, comp, args, raw, comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host", help="GameCube IP shown in Swiss network settings")
    ap.add_argument("file", help="DOL or ELF to send")
    ap.add_argument("--arg", default=None, help="argv[0] sent to the target")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        print(f"no such file: {args.file}")
        return 2

    header, comp, argz, raw, _ = build_payload(args.file, args.arg)
    total = len(header) + len(comp) + len(argz)
    print(f"target {args.host}:{args.port}")
    print(f"file   {os.path.basename(args.file)}  {len(raw):,} B "
          f"-> {len(comp):,} B compressed ({(1 - len(comp)/max(1,len(raw)))*100:.1f}% saved)")

    # Probe first. A dead console gives a connection reset or a long hang, and
    # saying so up front beats a truncated traceback after a partial transfer:
    # an interrupted push used to leave Swiss with its main thread suspended.
    probe = socket.socket()
    probe.settimeout(4.0)
    try:
        probe.connect((args.host, args.port))
    except OSError as exc:
        print(f"console not accepting wiiload connections ({exc.__class__.__name__}).\n"
              f"Power-cycle the GameCube so PicoBoot reloads the SD copy, then retry.")
        return 3
    finally:
        probe.close()

    sock = socket.create_connection((args.host, args.port), timeout=args.timeout)
    sock.settimeout(args.timeout)
    t0 = time.time()
    try:
        sock.sendall(header)
        sent = 0
        for chunk in (comp[i:i + 65536] for i in range(0, len(comp), 65536)):
            sock.sendall(chunk)
            sent += len(chunk)
            pct = sent * 100 // max(1, len(comp))
            sys.stdout.write(f"\r  sending {pct:3d}%")
            sys.stdout.flush()
        sock.sendall(argz)
    except OSError as exc:
        # The DOL on the console now has a 10 s receive timeout, so it will
        # resume instead of hanging. Tell the user rather than dumping a stack.
        print(f"\ntransfer aborted ({exc.__class__.__name__}). "
              f"The console should stay alive; just push again.")
        return 4
    finally:
        sock.close()

    dt = time.time() - t0
    print(f"\r  sent {total:,} B in {dt:.2f}s ({total/dt/1024:.0f} KB/s)")
    print("Swiss should now be booting the new DOL. "
          "If the screen stays black, power-cycle to reload the SD copy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
