"""Runtime accessors for bundled VerMan assets."""

from __future__ import annotations

import sys
from pathlib import Path


def get_runtime_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def get_asset_path(relative_path: str) -> Path:
    return get_runtime_root() / relative_path
