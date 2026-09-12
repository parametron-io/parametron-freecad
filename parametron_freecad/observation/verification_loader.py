"""Strict loading for Phase 2 verification contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn


@dataclass(frozen=True, slots=True)
class LoadedVerificationContract:
    """Resolved verification contract path and decoded root JSON object."""

    path: Path
    data: Mapping[str, Any]


class VerificationLoadError(ValueError):
    """Base class for strict verification contract loading failures."""


class VerificationFileError(VerificationLoadError):
    """Raised when the verification contract file cannot be read from disk."""


class VerificationDecodeError(VerificationLoadError):
    """Raised when the verification contract file is not valid JSON."""


class VerificationDuplicateKeyError(VerificationLoadError):
    """Raised when a JSON object contains duplicate keys."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"verification contract contains duplicate object key: {key!r}")


class VerificationRootTypeError(VerificationLoadError):
    """Raised when the verification contract root is not a JSON object."""


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
            raise VerificationDuplicateKeyError(key)
        obj[key] = value
    return obj


def load_parametron_verification_v1(
    path: str | Path,
) -> LoadedVerificationContract:
    """Load a verification contract with strict JSON object-key handling."""

    verification_path = Path(path).expanduser().resolve(strict=False)

    try:
        raw_text = verification_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise VerificationFileError(
            f"unable to read verification contract file: {verification_path}"
        ) from exc

    try:
        decoded = json.loads(
            raw_text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_non_json_constant,
        )
    except VerificationDuplicateKeyError:
        raise
    except _NonJsonConstantError as exc:
        raise VerificationDecodeError(
            "verification contract contains malformed JSON "
            f"constant: {exc.constant}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise VerificationDecodeError(
            "verification contract contains malformed JSON "
            f"at line {exc.lineno} column {exc.colno} (char {exc.pos})"
        ) from exc

    if not isinstance(decoded, dict):
        raise VerificationRootTypeError(
            "verification contract root must be a JSON object"
        )

    return LoadedVerificationContract(path=verification_path, data=decoded)


__all__ = [
    "LoadedVerificationContract",
    "VerificationDecodeError",
    "VerificationDuplicateKeyError",
    "VerificationFileError",
    "VerificationLoadError",
    "VerificationRootTypeError",
    "load_parametron_verification_v1",
]
