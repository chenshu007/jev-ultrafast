"""Provider selection only; action construction and validation remain in model.py."""

import os
from pathlib import Path


def secret(name):
    """Environment takes precedence over an optional Docker secret file."""
    if value := os.environ.get(name):
        return value
    if filename := os.environ.get(name + "_FILE"):
        return Path(filename).read_text().strip()
    return ""


def decision_endpoint():
    provider = os.environ.get("JEV_PROVIDER", "typesafe")
    if provider == "typesafe":
        key = secret("TYPESAFE_API_KEY")
        if not key:
            raise ValueError("TYPESAFE_API_KEY is required for JEV_PROVIDER=typesafe")
        return "https://api.typesafe.ai/v1/systemone", key, os.environ.get("TYPESAFE_MODEL", "jev-latest")
    if provider == "vercel":
        # The adapter owns the Gateway credential; never silently fall back to TypeSafe.
        return (
            os.environ.get("JEV_ADAPTER_URL", "http://127.0.0.1:8767").rstrip("/") + "/evaluate",
            "",
            os.environ.get("JEV_MODEL", "typesafe-ai/jev"),
        )
    raise ValueError("JEV_PROVIDER must be vercel or typesafe")
