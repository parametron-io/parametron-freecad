"""Shared deterministic metadata owner and property access helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class MetadataAccessError(ValueError):
    """Base class for deterministic metadata access failures."""


class MetadataAccessDocumentError(MetadataAccessError):
    """Raised when a document cannot support metadata access."""


class MetadataAccessOwnerNotFoundError(MetadataAccessError):
    """Raised when getObject returns None for an exact owner id."""


class MetadataAccessPropertyReadError(MetadataAccessError):
    """Raised when a metadata property cannot be read from a resolved owner."""


@dataclass(frozen=True, slots=True)
class ResolvedMetadataOwner:
    """A FreeCAD owner object resolved by exact owner id."""

    owner_id: str
    owner: Any


def validate_metadata_access_document(document: Any) -> None:
    """Validate that a document exposes callable getObject for metadata access."""

    _require_callable_get_object(document)


def resolve_metadata_owner(document: Any, owner_id: str) -> ResolvedMetadataOwner:
    """Resolve an exact FreeCAD metadata owner id through document.getObject."""

    get_object = _require_callable_get_object(document)

    try:
        owner = get_object(owner_id)
    except Exception as exc:
        raise MetadataAccessDocumentError(
            f"failed to resolve metadata owner '{owner_id}'"
        ) from exc

    if owner is None:
        raise MetadataAccessOwnerNotFoundError(
            f"metadata owner '{owner_id}' was not found"
        )

    return ResolvedMetadataOwner(owner_id=owner_id, owner=owner)


def read_metadata_value(
    owner: Any,
    key: str,
    *,
    owner_id: str = "",
) -> Any:
    """Read an exact metadata attribute/property from a resolved owner."""

    del owner_id

    try:
        return getattr(owner, key)
    except Exception as exc:
        raise MetadataAccessPropertyReadError(
            f"failed to read metadata key '{key}'"
        ) from exc


def _require_callable_get_object(document: Any) -> Callable[[str], Any]:
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise MetadataAccessDocumentError(
            "document does not provide callable getObject for metadata access"
        )

    return get_object


__all__ = [
    "MetadataAccessDocumentError",
    "MetadataAccessError",
    "MetadataAccessOwnerNotFoundError",
    "MetadataAccessPropertyReadError",
    "ResolvedMetadataOwner",
    "read_metadata_value",
    "resolve_metadata_owner",
    "validate_metadata_access_document",
]
