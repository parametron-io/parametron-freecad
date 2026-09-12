"""Path helpers for Parametron FreeCAD runtime boundaries."""

from __future__ import annotations

from pathlib import Path


WORKING_COPY_DIR_NAME = "_working"


def resolve_path(path: str | Path, *, base: str | Path | None = None) -> Path:
    """Return path as an absolute resolved path."""
    candidate = Path(path).expanduser()

    if candidate.is_absolute():
        return candidate.resolve(strict=False)

    if base is None:
        return candidate.resolve(strict=False)

    resolved_base = Path(base).expanduser().resolve(strict=False)
    return (resolved_base / candidate).resolve(strict=False)


def require_existing_file(
    path: str | Path,
    *,
    base: str | Path | None = None,
) -> Path:
    """Return path as an absolute file path, or raise ValueError."""
    candidate = resolve_path(path, base=base)

    if not candidate.is_file():
        raise ValueError(f"expected existing file: {candidate}")

    return candidate


def require_existing_directory(
    path: str | Path,
    *,
    base: str | Path | None = None,
) -> Path:
    """Return path as an absolute directory path, or raise ValueError."""
    candidate = resolve_path(path, base=base)

    if not candidate.is_dir():
        raise ValueError(f"expected existing directory: {candidate}")

    return candidate


def find_working_copy_root(
    path: str | Path,
    *,
    base: str | Path | None = None,
) -> Path:
    """Return the nearest _working ancestor for path."""
    candidate = resolve_path(path, base=base)

    for current in (candidate, *candidate.parents):
        if current.name == WORKING_COPY_DIR_NAME:
            return current

    raise ValueError(
        f"path is not within a {WORKING_COPY_DIR_NAME} working copy: {candidate}"
    )


def is_within_working_copy(
    path: str | Path,
    *,
    base: str | Path | None = None,
) -> bool:
    """Return True when path is within a _working tree."""
    try:
        find_working_copy_root(path, base=base)
    except ValueError:
        return False

    return True


def require_within_working_copy(
    path: str | Path,
    *,
    base: str | Path | None = None,
) -> Path:
    """Return path when it is within a _working tree, or raise ValueError."""
    candidate = resolve_path(path, base=base)

    if not is_within_working_copy(candidate):
        raise ValueError(
            f"path is not within a {WORKING_COPY_DIR_NAME} working copy: {candidate}"
        )

    return candidate


def require_child_path(parent: str | Path, child: str | Path) -> Path:
    """Return child when it resolves to parent or a descendant of parent."""
    resolved_parent = resolve_path(parent)
    resolved_child = resolve_path(child)

    if resolved_child == resolved_parent or resolved_parent in resolved_child.parents:
        return resolved_child

    raise ValueError(
        f"path escapes parent directory: {resolved_child} is not within {resolved_parent}"
    )


def require_working_copy_child(
    path: str | Path,
    *,
    base: str | Path | None = None,
) -> Path:
    """Return path when it resolves within a _working tree."""
    candidate = resolve_path(path, base=base)
    working_copy_root = find_working_copy_root(candidate)

    return require_child_path(working_copy_root, candidate)
