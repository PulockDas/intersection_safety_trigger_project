"""
utils.py — General-purpose helpers shared across notebooks.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# sys.path helpers
# ─────────────────────────────────────────────────────────────────────────────

def add_src_to_path(src_dir: Path) -> None:
    """
    Add *src_dir* to the front of sys.path if not already present.
    Call this from notebooks before importing project modules.
    """
    src_str = str(src_dir.resolve())
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
        print(f"[INFO]  sys.path ← {src_str}")
    else:
        print(f"[INFO]  sys.path already contains: {src_str}")


# ─────────────────────────────────────────────────────────────────────────────
# Unit conversion / formatting
# ─────────────────────────────────────────────────────────────────────────────

def bytes_to_gb(n: int | float) -> float:
    """Convert bytes to gigabytes, rounded to 3 decimal places."""
    return round(n / 1_000_000_000, 3)


def format_size(n: int | float) -> str:
    """Return a human-readable file size string (B / KB / MB / GB)."""
    for unit, threshold in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= threshold:
            return f"{n / threshold:.2f} {unit}"
    return f"{int(n)} B"


# ─────────────────────────────────────────────────────────────────────────────
# Safe nested access
# ─────────────────────────────────────────────────────────────────────────────

def safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    """
    Safely traverse nested dicts/lists.

    Examples
    --------
    >>> safe_get({"a": {"b": 1}}, "a", "b")
    1
    >>> safe_get({"a": {}}, "a", "missing", default="N/A")
    'N/A'
    """
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, default)
        elif isinstance(obj, list):
            try:
                obj = obj[int(key)]
            except (IndexError, ValueError):
                return default
        else:
            return default
    return obj


# ─────────────────────────────────────────────────────────────────────────────
# Print helpers
# ─────────────────────────────────────────────────────────────────────────────

def section(title: str, width: int = 60) -> None:
    """Print a visual section divider."""
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}")


def check_mark(condition: bool) -> str:
    """Return a Unicode check or cross mark."""
    return "✓" if condition else "✗"


def yes_no(condition: bool) -> str:
    return "YES" if condition else "NO"
