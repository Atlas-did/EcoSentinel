"""Minimal .env **parser** for demo use — no external dependencies required.

This module is intentionally pure: it reads text and returns a dict. It must **not**
mutate ``os.environ``; applying values to the process environment is the job of
``energy_system.config.env`` (the single place allowed to touch the environment —
see the refactor design §3.1 rule 4).

Supports:
- UTF-8 with/without BOM, UTF-16 variants
- Lines: KEY=VALUE, # comments, // comments, empty lines
- Multiple file paths (loaded in order; first definition wins)

Does NOT depend on python-dotenv, keeping deployment simple for
competition environments where pip install may be restricted.
"""

from pathlib import Path


def _read_text_with_fallback(p: Path) -> str:
    """Try multiple encodings to read a text file."""
    try:
        data = p.read_bytes()
    except OSError:
        return ""
    for enc in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return ""


def parse_dotenv_text(text: str) -> dict[str, str]:
    """Parse KEY=VALUE lines into a dict (first definition wins, values stripped)."""
    values: dict[str, str] = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip().lstrip("\ufeff")
        v = v.strip().strip('"').strip("'")
        if k and v:
            values.setdefault(k, v)
    return values


def read_dotenv(p: Path) -> dict[str, str]:
    """Read one .env file into a dict; missing/unreadable file ⇒ {} (never raises)."""
    return parse_dotenv_text(_read_text_with_fallback(Path(p)))
