"""Deterministic byte comparison for explicit artifact file pairs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from parametron_freecad.common.paths import resolve_path


ARTIFACT_COMPARISON_STATUS_MATCHED = "matched"
ARTIFACT_COMPARISON_STATUS_DIFFERENT = "different"
ARTIFACT_COMPARISON_STATUS_MISSING_LEFT = "missing_left"
ARTIFACT_COMPARISON_STATUS_MISSING_RIGHT = "missing_right"
ARTIFACT_COMPARISON_STATUS_MISSING_BOTH = "missing_both"
ARTIFACT_COMPARISON_STATUS_NOT_FILE_LEFT = "not_file_left"
ARTIFACT_COMPARISON_STATUS_NOT_FILE_RIGHT = "not_file_right"


class ArtifactComparisonError(ValueError):
    """Raised when artifact comparison requests cannot be evaluated."""


@dataclass(frozen=True, slots=True)
class ArtifactComparisonRequest:
    name: str
    role: str
    left_path: Path
    right_path: Path


@dataclass(frozen=True, slots=True)
class ArtifactComparisonResult:
    name: str
    role: str
    left_path: Path
    right_path: Path
    left_size: int | None
    right_size: int | None
    left_sha256: str | None
    right_sha256: str | None
    status: str
    matches: bool


@dataclass(frozen=True, slots=True)
class ArtifactComparisonReport:
    comparisons: tuple[ArtifactComparisonResult, ...]
    all_matched: bool


@dataclass(frozen=True, slots=True)
class _ArtifactFileMetadata:
    path: Path
    exists: bool
    is_file: bool
    size: int | None
    sha256: str | None
    content: bytes | None


def compare_artifact_files(
    requests: Iterable[ArtifactComparisonRequest],
) -> ArtifactComparisonReport:
    """Compare explicit artifact file pairs by exact bytes in request order."""

    try:
        iterator = iter(requests)
    except TypeError as exc:
        raise ArtifactComparisonError(
            "artifact comparison requests must be iterable"
        ) from exc

    comparisons = tuple(_compare_artifact_request(request) for request in iterator)
    return ArtifactComparisonReport(
        comparisons=comparisons,
        all_matched=all(result.matches for result in comparisons),
    )


def _compare_artifact_request(
    request: ArtifactComparisonRequest,
) -> ArtifactComparisonResult:
    _validate_request(request)

    left_path = _resolve_artifact_path(request.left_path, side="left")
    right_path = _resolve_artifact_path(request.right_path, side="right")
    left = _read_artifact_metadata(left_path, side="left")
    right = _read_artifact_metadata(right_path, side="right")

    status = _comparison_status(left=left, right=right)
    matches = (
        status == ARTIFACT_COMPARISON_STATUS_MATCHED
        and left.content is not None
        and left.content == right.content
    )

    return ArtifactComparisonResult(
        name=request.name,
        role=request.role,
        left_path=left.path,
        right_path=right.path,
        left_size=left.size,
        right_size=right.size,
        left_sha256=left.sha256,
        right_sha256=right.sha256,
        status=status,
        matches=matches,
    )


def _validate_request(request: ArtifactComparisonRequest) -> None:
    if not isinstance(request, ArtifactComparisonRequest):
        raise ArtifactComparisonError(
            f"expected ArtifactComparisonRequest, got {type(request).__name__}"
        )

    if not isinstance(request.name, str) or request.name == "":
        raise ArtifactComparisonError(
            "artifact comparison request name must be non-empty str"
        )

    if not isinstance(request.role, str) or request.role == "":
        raise ArtifactComparisonError(
            "artifact comparison request role must be non-empty str"
        )


def _resolve_artifact_path(path: Path, *, side: str) -> Path:
    try:
        return resolve_path(path)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ArtifactComparisonError(
            f"failed to resolve {side} artifact path"
        ) from exc


def _read_artifact_metadata(path: Path, *, side: str) -> _ArtifactFileMetadata:
    exists = _path_exists(path, side=side)
    if not exists:
        return _ArtifactFileMetadata(
            path=path,
            exists=False,
            is_file=False,
            size=None,
            sha256=None,
            content=None,
        )

    is_file = _path_is_file(path, side=side)
    if not is_file:
        return _ArtifactFileMetadata(
            path=path,
            exists=True,
            is_file=False,
            size=None,
            sha256=None,
            content=None,
        )

    content = _read_file_bytes(path, side=side)
    return _ArtifactFileMetadata(
        path=path,
        exists=True,
        is_file=True,
        size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        content=content,
    )


def _path_exists(path: Path, *, side: str) -> bool:
    try:
        return path.exists()
    except OSError as exc:
        raise ArtifactComparisonError(
            f"failed to inspect {side} artifact path: {path}"
        ) from exc


def _path_is_file(path: Path, *, side: str) -> bool:
    try:
        return path.is_file()
    except OSError as exc:
        raise ArtifactComparisonError(
            f"failed to inspect {side} artifact file type: {path}"
        ) from exc


def _read_file_bytes(path: Path, *, side: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ArtifactComparisonError(
            f"failed to read {side} artifact file: {path}"
        ) from exc


def _comparison_status(
    *,
    left: _ArtifactFileMetadata,
    right: _ArtifactFileMetadata,
) -> str:
    if not left.exists and not right.exists:
        return ARTIFACT_COMPARISON_STATUS_MISSING_BOTH
    if not left.exists:
        return ARTIFACT_COMPARISON_STATUS_MISSING_LEFT
    if not right.exists:
        return ARTIFACT_COMPARISON_STATUS_MISSING_RIGHT
    if not left.is_file:
        return ARTIFACT_COMPARISON_STATUS_NOT_FILE_LEFT
    if not right.is_file:
        return ARTIFACT_COMPARISON_STATUS_NOT_FILE_RIGHT
    if left.content == right.content:
        return ARTIFACT_COMPARISON_STATUS_MATCHED
    return ARTIFACT_COMPARISON_STATUS_DIFFERENT


__all__ = [
    "ARTIFACT_COMPARISON_STATUS_DIFFERENT",
    "ARTIFACT_COMPARISON_STATUS_MATCHED",
    "ARTIFACT_COMPARISON_STATUS_MISSING_BOTH",
    "ARTIFACT_COMPARISON_STATUS_MISSING_LEFT",
    "ARTIFACT_COMPARISON_STATUS_MISSING_RIGHT",
    "ARTIFACT_COMPARISON_STATUS_NOT_FILE_LEFT",
    "ARTIFACT_COMPARISON_STATUS_NOT_FILE_RIGHT",
    "ArtifactComparisonError",
    "ArtifactComparisonReport",
    "ArtifactComparisonRequest",
    "ArtifactComparisonResult",
    "compare_artifact_files",
]
