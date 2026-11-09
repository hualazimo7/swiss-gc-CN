#!/usr/bin/env python3
"""Find a GameCube running Swiss on the local network.

Swiss opens two TCP listeners when a Broadband Adapter is present:
  - 4299  wiiload
  - 80    httpd

Scans the /24 around this host for either port and reports what answered.

Usage: python tools/find_swiss.py [subnet-prefix]   e.g. 192.168.1
"""
import concurrent.futures as cf
import ipaddress
import socket
import sys


def local_prefix():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "192.168.1.1"
    finally:
        s.close()
    return ".".join(ip.split(".")[:3])


def probe(ip, port, timeout=0.35):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return (ip, port)
    except OSError:
        return None


def http_banner(ip, timeout=1.5):
    """Swiss httpd answers with a tiny HTML page on '/'."""
    try:
        with socket.create_connection((ip, 80), timeout=timeout) as s:
            s.sendall(b"GET / HTTP/1.0\r\n\r\n")
            data = s.recv(512)
            return data[:200].decode("latin-1", "replace").replace("\r\n", " | ")
    except OSError as e:
        return f"(no response: {e})"


def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else local_prefix()
    hosts = [str(ip) for ip in ipaddress.ip_network(f"{prefix}.0/24", strict=False).hosts()]
    me = socket.gethostbyname(socket.gethostname())
    print(f"scanning {prefix}.0/24 for TCP 4299 (wiiload) / 80 (httpd)...")

    hits = []
    with cf.ThreadPoolExecutor(max_workers=96) as pool:
        futures = []
        for h in hosts:
            if h == me:
                continue
            futures.append(pool.submit(probe, h, 4299))
            futures.append(pool.submit(probe, h, 80))
        for f in cf.as_completed(futures):
            r = f.result()
            if r:
                hits.append(r)

    if not hits:
        print("nothing found.")
        print("check: is Swiss running, BBA detected, and are they on the same subnet?")
        return 1

    by_ip = {}
    for ip, port in hits:
        by_ip.setdefault(ip, []).append(port)

    for ip, ports in sorted(by_ip.items()):
        tag = []
        if 4299 in ports:
            tag.append("wiiload")
        if 80 in ports:
            tag.append("httpd")
        print(f"  {ip:15s} ports={sorted(ports)}  -> {', '.join(tag)}")
        if 80 in ports:
            print(f"      GET / -> {http_banner(ip)}")

    swiss = [ip for ip, p in by_ip.items() if 4299 in p]
    if swiss:
        print(f"\nSwiss at: {swiss[0]}")
        print(f"push a build with:  dev-push.bat {swiss[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
