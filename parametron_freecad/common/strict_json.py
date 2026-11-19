"""Strict JSON decoding for Parametron FreeCAD contract sidecars."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, NoReturn


class StrictJsonError(ValueError):
    """Raised when JSON content is not strict, deterministic JSON."""


class _DuplicateKeyError(ValueError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"duplicate JSON object key: {key!r}")


class _NonJsonConstantError(ValueError):
    def __init__(self, constant: str) -> None:
        self.constant = constant
        super().__init__(f"non-standard JSON constant: {constant}")


def _reject_duplicate_object_keys(
    pairs: Iterable[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(key)
        result[key] = value
    return result


def _reject_non_json_constant(constant: str) -> NoReturn:
    raise _NonJsonConstantError(constant)


def loads_strict_json(content: bytes | str) -> Any:
    """Decode strict JSON without duplicate keys or non-standard constants."""
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StrictJsonError("JSON content must be valid UTF-8") from exc
    elif isinstance(content, str):
        text = content
    else:
        raise StrictJsonError("JSON content must be bytes or text")

    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_non_json_constant,
        )
    except _DuplicateKeyError as exc:
        raise StrictJsonError(str(exc)) from exc
    except _NonJsonConstantError as exc:
        raise StrictJsonError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise StrictJsonError(f"invalid JSON: {exc.msg}") from exc


def load_strict_json_file(path: str | Path) -> Any:
    """Read and decode one strict JSON file without exposing raw content."""
    try:
        content = Path(path).read_bytes()
    except OSError as exc:
        raise StrictJsonError("JSON file could not be read") from exc

    return loads_strict_json(content)


__all__ = [
    "StrictJsonError",
    "load_strict_json_file",
    "loads_strict_json",
]
