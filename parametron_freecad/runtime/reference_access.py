"""Shared deterministic reference object access helpers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class ReferenceAccessError(ValueError):
    """Base class for deterministic reference access failures."""


class ReferenceAccessDocumentError(ReferenceAccessError):
    """Raised when a document cannot support reference access."""


class ReferenceAccessReferenceNotFoundError(ReferenceAccessError):
    """Raised when getObject returns None for an exact reference name."""


@dataclass(frozen=True, slots=True)
class ResolvedReferenceObject:
    """A FreeCAD object resolved by exact reference name."""

    reference_name: str
    reference: Any


def validate_reference_access_document(document: Any) -> None:
    """Validate that a document exposes callable getObject for reference access."""

    _require_callable_get_object(document)


def resolve_reference_object(
    document: Any,
    reference_name: str,
) -> ResolvedReferenceObject:
    """Resolve an exact FreeCAD reference name through document.getObject."""

    get_object = _require_callable_get_object(document)

    try:
        reference = get_object(reference_name)
    except Exception as exc:
        raise ReferenceAccessDocumentError(
            f"failed to resolve reference '{reference_name}'"
        ) from exc

    if reference is None:
        raise ReferenceAccessReferenceNotFoundError(
            f"reference '{reference_name}' was not found"
        )

    return ResolvedReferenceObject(reference_name=reference_name, reference=reference)


def _require_callable_get_object(document: Any) -> Callable[[str], Any]:
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        raise ReferenceAccessDocumentError(
            "document does not provide callable getObject for reference access"
        )

    return get_object


__all__ = [
    "ReferenceAccessDocumentError",
    "ReferenceAccessError",
    "ReferenceAccessReferenceNotFoundError",
    "ResolvedReferenceObject",
    "resolve_reference_object",
    "validate_reference_access_document",
]
