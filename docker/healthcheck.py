"""Check both HTTP services without a model call or browser mutation."""
import json
import os
import urllib.request
from urllib.parse import urlparse


def check():
    with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=3) as response:
        assert json.load(response)["webSocketDebuggerUrl"].startswith("ws://")
    port = os.environ.get("TYPESAFE_DEMO_PORT", "8766")
    origin = os.environ.get("JEV_PUBLIC_ORIGIN") or f"http://127.0.0.1:{port}"
    request = urllib.request.Request(f"http://127.0.0.1:{port}/healthz", headers={"Host": urlparse(origin).netloc})
    with urllib.request.urlopen(request, timeout=3) as response:
        assert json.load(response)["status"] == "ok"


if __name__ == "__main__":
    check()
