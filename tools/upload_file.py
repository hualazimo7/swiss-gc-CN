#!/usr/bin/env python3
"""Push a file onto the GameCube's SD card through Swiss' /upload endpoint.

The remote name is sent percent-encoded so UTF-8 (Chinese) file names survive;
Swiss decodes it byte-wise and hands the raw UTF-8 path to FatFs, which is
built with FF_LFN_UNICODE=2.

    python tools/upload_file.py 192.168.1.2 local.iso "中文测试.iso"

Run `python tools/upload_file.py <ip> --probe` to check the endpoint first.
"""
import os
import socket
import sys
import time
import urllib.parse


def parse_response(data):
    """Split an HTTP response into (status_line, body_bytes)."""
    sep = data.find(b"\r\n\r\n")
    if sep < 0:
        return data.split(b"\r\n", 1)[0].decode("latin-1", "replace"), b""
    head = data[:sep].decode("latin-1", "replace")
    return head.split("\r\n", 1)[0], data[sep + 4:]


def upload(host, local_path, remote_name=None, port=80, root=None,
           timeout=180, chunk=16384, progress=True):
    if remote_name is None:
        remote_name = os.path.basename(local_path)

    size = os.path.getsize(local_path)
    if size == 0:
        raise ValueError("refusing to upload an empty file")

    query = "name=" + urllib.parse.quote(remote_name, safe="")
    if root:
        query += "&root=" + urllib.parse.quote(root, safe=":/")

    header = (
        "POST /upload?%s HTTP/1.1\r\n"
        "Host: %s\r\n"
        "Content-Length: %d\r\n"
        "Connection: close\r\n"
        "\r\n" % (query, host, size)
    ).encode("ascii", "strict")

    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)

    try:
        sock.sendall(header)

        sent = 0
        started = time.time()
        with open(local_path, "rb") as fh:
            while sent < size:
                block = fh.read(min(chunk, size - sent))
                if not block:
                    break
                sock.sendall(block)
                sent += len(block)
                if progress:
                    pct = sent * 100 // size
                    rate = sent / max(1e-6, time.time() - started) / 1024.0
                    sys.stderr.write("\r  %5.1f%%  %d/%d bytes  %.0f KB/s" %
                                     (pct, sent, size, rate))
                    sys.stderr.flush()
        if progress:
            sys.stderr.write("\n")

        data = b""
        while True:
            try:
                block = sock.recv(4096)
            except socket.timeout:
                break
            if not block:
                break
            data += block
    finally:
        sock.close()

    status, body = parse_response(data)
    return sent, status, body.decode("utf-8", "replace").strip()


def probe(host, port=80, timeout=10):
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        sock.sendall(b"GET / HTTP/1.1\r\nHost: %s\r\nConnection: close\r\n\r\n"
                     % host.encode())
        data = b""
        while True:
            block = sock.recv(4096)
            if not block:
                break
            data += block
    finally:
        sock.close()
    status, body = parse_response(data)
    return status, body.decode("utf-8", "replace")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2

    host = argv[1]

    if "--probe" in argv:
        status, body = probe(host)
        print(status)
        print(body)
        return 0

    if len(argv) < 3:
        print("usage: upload_file.py <ip> <local-file> [remote-name] [root]")
        return 2

    local_path = argv[2]
    remote_name = argv[3] if len(argv) > 3 else None
    root = argv[4] if len(argv) > 4 else None

    sent, status, reply = upload(host, local_path, remote_name, root=root)
    print(status)
    print(reply)
    ok = reply.startswith("ok ") and "/%d bytes" % sent in reply.replace("%", "%")
    return 0 if status.startswith("HTTP/1.1 200") and reply.startswith("ok ") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
