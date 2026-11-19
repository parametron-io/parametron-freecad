"""Atomic canonical JSON sidecar writing for runtime evidence."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from parametron_freecad.common.canonical_json import dumps_canonical
from parametron_freecad.common.paths import (
    require_child_path,
    require_existing_directory,
    resolve_path,
)


class EvidenceSidecarError(ValueError):
    """Raised when an evidence sidecar payload or location is invalid."""


class EvidenceSidecarContainmentError(EvidenceSidecarError):
    """Raised when an evidence sidecar would escape the working copy."""


class EvidenceSidecarWriteError(OSError):
    """Raised when an evidence sidecar cannot be written atomically."""


def resolve_evidence_sidecar_path(
    *,
    working_copy: str | Path,
    output_directory: str | Path,
    filename: str,
) -> Path:
    """Resolve one confined evidence sidecar destination."""
    try:
        resolved_working_copy = require_existing_directory(working_copy)
    except ValueError as exc:
        raise EvidenceSidecarContainmentError(
            "working copy must be an existing directory"
        ) from exc

    try:
        resolved_output_directory = require_existing_directory(
            output_directory,
            base=resolved_working_copy,
        )
    except ValueError as exc:
        raise EvidenceSidecarContainmentError(
            "output directory must be an existing directory"
        ) from exc

    try:
        resolved_output_directory = require_child_path(
            resolved_working_copy,
            resolved_output_directory,
        )
    except ValueError as exc:
        raise EvidenceSidecarContainmentError(
            "output directory must resolve inside the working copy"
        ) from exc

    target = resolve_path(resolved_output_directory / _validated_filename(filename))
    try:
        target = require_child_path(resolved_working_copy, target)
    except ValueError as exc:
        raise EvidenceSidecarContainmentError(
            "evidence sidecar path must resolve inside the working copy"
        ) from exc

    if target.is_dir():
        raise EvidenceSidecarContainmentError(
            "evidence sidecar path must not be an existing directory"
        )
    return target


def remove_evidence_sidecar(
    *,
    working_copy: str | Path,
    output_directory: str | Path,
    filename: str,
) -> None:
    """Remove one confined stale evidence sidecar without following symlinks."""
    resolve_evidence_sidecar_path(
        working_copy=working_copy,
        output_directory=output_directory,
        filename=filename,
    )

    try:
        resolved_working_copy = require_existing_directory(working_copy)
        resolved_output_directory = require_existing_directory(
            output_directory,
            base=resolved_working_copy,
        )
    except ValueError as exc:
        raise EvidenceSidecarContainmentError(
            "evidence sidecar location is not usable"
        ) from exc

    lexical_target = resolved_output_directory / _validated_filename(filename)
    if lexical_target.is_symlink():
        raise EvidenceSidecarContainmentError(
            "evidence sidecar path must not be a symbolic link"
        )
    if lexical_target.is_dir():
        raise EvidenceSidecarContainmentError(
            "evidence sidecar path must not be an existing directory"
        )

    try:
        lexical_target.unlink(missing_ok=True)
    except OSError as exc:
        raise EvidenceSidecarWriteError(
            f"failed to remove evidence sidecar {filename!r}"
        ) from exc


def write_canonical_json_sidecar_atomically(
    *,
    working_copy: str | Path,
    output_directory: str | Path,
    filename: str,
    payload: Any,
) -> Path:
    """Serialize one payload and atomically replace a confined sidecar."""
    target = resolve_evidence_sidecar_path(
        working_copy=working_copy,
        output_directory=output_directory,
        filename=filename,
    )

    try:
        serialized = dumps_canonical(payload).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise EvidenceSidecarError(
            "evidence sidecar payload is not canonical-JSON serializable"
        ) from exc

    descriptor: int | None = None
    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as output_file:
            descriptor = None
            output_file.write(serialized)
        os.replace(temporary_path, target)
        temporary_path = None
    except OSError as exc:
        raise EvidenceSidecarWriteError(
            f"failed to atomically write evidence sidecar {filename!r}"
        ) from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass

    return target


def _validated_filename(filename: str) -> str:
    if (
        not isinstance(filename, str)
        or not filename
        or filename != filename.strip()
        or "\x00" in filename
        or "/" in filename
        or "\\" in filename
        or filename in {".", ".."}
        or Path(filename).name != filename
    ):
        raise EvidenceSidecarContainmentError(
            "evidence sidecar filename must be a plain file name"
        )
    return filename


__all__ = [
    "EvidenceSidecarContainmentError",
    "EvidenceSidecarError",
    "EvidenceSidecarWriteError",
    "remove_evidence_sidecar",
    "resolve_evidence_sidecar_path",
    "write_canonical_json_sidecar_atomically",
]
