"""Restart the whole browser/session unit on crash or sustained unresponsiveness."""
import os
import signal
import subprocess
import time
from pathlib import Path

from healthcheck import check

children = []
stopping = False


def stop(*_):
    global stopping
    stopping = True


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
# A dedicated volume belongs to exactly one container. Container recreation changes hostname.
for name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
    Path("/data/chrome", name).unlink(missing_ok=True)
try:
    # Browser receives no model credentials. It never uses a personal or host Chrome profile.
    browser_env = {k: v for k, v in os.environ.items() if not any(
        word in k for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
    children.append(subprocess.Popen([
        "chromium", "--headless=new", "--no-sandbox", "--remote-debugging-address=127.0.0.1",
        "--remote-debugging-port=9222", "--user-data-dir=/data/chrome", "--no-first-run",
        "--no-default-browser-check", "about:blank",
    ], env=browser_env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    children.append(subprocess.Popen(["jev"]))
    started, last_check, failures = time.monotonic(), 0, 0
    while not stopping and all(child.poll() is None for child in children):
        now = time.monotonic()
        if now - started > 60 and now - last_check > 20:
            last_check = now
            try:
                check()
                failures = 0
            except Exception:
                failures += 1
            if failures >= 3:
                break
        time.sleep(1)
finally:
    for child in reversed(children):
        if child.poll() is None:
            child.terminate()
    for child in children:
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
raise SystemExit(0 if stopping else 1)
