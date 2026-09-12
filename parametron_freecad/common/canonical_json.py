"""Canonical JSON helpers for Parametron FreeCAD.

The Engine owns final verification decisions. This module only provides stable
serialization helpers for files produced by the FreeCAD integration layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dumps_canonical(value: Any) -> str:
    """Return canonical JSON with sorted keys and one trailing newline."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"


def write_canonical_json(path: str | Path, value: Any) -> None:
    """Write canonical JSON bytes to path."""
    target = Path(path)
    target.write_text(dumps_canonical(value), encoding="utf-8")
