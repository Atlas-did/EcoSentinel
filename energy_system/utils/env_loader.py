"""Minimal .env file loader for demo use — no external dependencies required.

Supports:
- UTF-8 with/without BOM, UTF-16 variants
- Lines: KEY=VALUE, # comments, // comments, empty lines
- Multiple file paths (loaded in order; first definition wins)

Does NOT depend on python-dotenv, keeping deployment simple for
competition environments where pip install may be restricted.
"""

import os
from pathlib import Path


def _read_text_with_fallback(p: Path) -> str:
    """Try multiple encodings to read a text file."""
    data = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return ""


def load_file(p: Path) -> None:
    """Load a single .env file, setting os.environ for each KEY=VALUE line."""
    if not p.exists():
        return
    text = _read_text_with_fallback(p)
    if not text:
        return
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().lstrip("﻿")
        v = v.strip().strip('"').strip("'")
        if k and v and k not in os.environ:
            os.environ[k] = v


def load_dotenv_if_present(*paths: str) -> None:
    """Load .env files from one or more paths.

    Each path is tried in order. Keys already present in os.environ are
    NOT overwritten (first-writer-wins semantics).

    Example:
        load_dotenv_if_present(".env", "ai_workspace/von.env")
    """
    for path in paths:
        try:
            load_file(Path(path))
        except Exception:
            continue
