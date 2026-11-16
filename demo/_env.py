"""Load the repository's .env into the environment (without overriding variables already set).

The demo scripts must reach the lab's ports, which are set in .env (for example MAILPIT_SMTP_PORT).
Without this, they fall back to the guide's default ports, which may belong to another service.
"""
import os
from pathlib import Path


def load():
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


load()
