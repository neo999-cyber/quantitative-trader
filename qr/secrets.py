"""API keys, read from `~/.qr/secrets.env` and never from the repository.

One `KEY=VALUE` a line; the file is the owner's, mode 600, outside any git
checkout. A key already present in the environment wins. Nothing here logs
or prints a value, and `require` names the variable it is missing rather
than the value it wanted.
"""
from __future__ import annotations

import os
from pathlib import Path

SECRETS_FILE = Path(os.environ.get("QR_SECRETS", Path.home() / ".qr" / "secrets.env"))


def load(path: Path | None = None) -> dict[str, str]:
    """Read the file into the environment (without overriding) and return what it holds."""
    path = path or SECRETS_FILE
    found: dict[str, str] = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if not value:
            continue
        found[key] = value
        os.environ.setdefault(key, value)
    return found


def require(name: str) -> str:
    load()
    value = os.environ.get(name, "")
    if not value:
        raise KeyError(f"{name} is not set; put `{name}=...` in {SECRETS_FILE}")
    return value


def present(*names: str) -> dict[str, bool]:
    load()
    return {n: bool(os.environ.get(n)) for n in names}
