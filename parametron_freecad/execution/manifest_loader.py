"""Strict loading for Phase 1 export manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn


@dataclass(frozen=True, slots=True)
class LoadedManifest:
    """Resolved manifest path and decoded root JSON object."""

    path: Path
    data: Mapping[str, Any]


class ManifestLoadError(ValueError):
    """Base class for strict manifest loading failures."""


class ManifestFileError(ManifestLoadError):
    """Raised when the manifest file cannot be read from disk."""


class ManifestDecodeError(ManifestLoadError):
    """Raised when the manifest file is not valid JSON."""


class ManifestDuplicateKeyError(ManifestLoadError):
    """Raised when a JSON object contains duplicate keys."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"manifest contains duplicate object key: {key!r}")


class ManifestRootTypeError(ManifestLoadError):
    """Raised when the manifest root is not a JSON object."""


class _NonJsonConstantError(ValueError):
    """Raised internally when Python's JSON decoder sees non-standard constants."""

    def __init__(self, constant: str) -> None:
        self.constant = constant
        super().__init__(constant)


def _reject_non_json_constant(constant: str) -> NoReturn:
    raise _NonJsonConstantError(constant)


def _reject_duplicate_object_keys(
    pairs: Iterable[tuple[str, Any]],
) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ManifestDuplicateKeyError(key)
        obj[key] = value
    return obj


def load_export_manifest_v1(path: str | Path) -> LoadedManifest:
    """Load an export manifest from disk with strict JSON object-key handling."""

    manifest_path = Path(path).expanduser().resolve(strict=False)

    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestFileError(
            f"unable to read manifest file: {manifest_path}"
        ) from exc

    try:
        decoded = json.loads(
            raw_text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_non_json_constant,
        )
    except ManifestDuplicateKeyError:
        raise
    except _NonJsonConstantError as exc:
        raise ManifestDecodeError(
            f"manifest contains malformed JSON constant: {exc.constant}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ManifestDecodeError(
            "manifest contains malformed JSON "
            f"at line {exc.lineno} column {exc.colno} (char {exc.pos})"
        ) from exc

    if not isinstance(decoded, dict):
        raise ManifestRootTypeError("manifest root must be a JSON object")

    return LoadedManifest(path=manifest_path, data=decoded)


__all__ = [
    "LoadedManifest",
    "ManifestDecodeError",
    "ManifestDuplicateKeyError",
    "ManifestFileError",
    "ManifestLoadError",
    "ManifestRootTypeError",
    "load_export_manifest_v1",
]
