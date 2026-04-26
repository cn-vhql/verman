"""Helpers for locating the packaged VerMan executable."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, Optional

from app_info import APP_EXECUTABLE_NAME


def _iter_search_roots(search_roots: Optional[Iterable[Path]] = None):
    seen = set()

    def add(root: Optional[Path]):
        if not root:
            return
        resolved = Path(root).resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        yield resolved

    if search_roots:
        for root in search_roots:
            yield from add(root)

    if sys.argv and sys.argv[0]:
        yield from add(Path(sys.argv[0]).resolve().parent)

    yield from add(Path(__file__).resolve().parent)
    yield from add(Path.cwd())


def find_packaged_executable(search_roots: Optional[Iterable[Path]] = None) -> Optional[str]:
    """Return the packaged GUI executable path when available."""
    if getattr(sys, "frozen", False):
        runtime_executable = Path(sys.executable).resolve()
        if runtime_executable.exists():
            return str(runtime_executable)

    for root in _iter_search_roots(search_roots):
        candidates = (
            root / APP_EXECUTABLE_NAME,
            root / "dist" / APP_EXECUTABLE_NAME,
        )
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)

    return None
