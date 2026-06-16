import http.server
import os
import socket
import socketserver
import sys
from pathlib import Path

import qrcode


def get_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/serve_apk.py path/to/FloatMask.apk [port]")
        raise SystemExit(1)

    apk = Path(sys.argv[1]).resolve()
    if not apk.exists():
        print(f"APK not found: {apk}")
        raise SystemExit(1)

    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    os.chdir(apk.parent)

    ip = get_lan_ip()
    url = f"http://{ip}:{port}/{apk.name}"
    qr_path = apk.parent / "FloatMask_download_qr.png"
    qrcode.make(url).save(qr_path)

    print(f"Download URL: {url}")
    print(f"QR code saved: {qr_path}")
    print("Keep this window open while downloading from the phone.")

    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", port), handler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
