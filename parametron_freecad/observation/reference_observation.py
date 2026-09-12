"""Phase 2 runtime helper for observing requested references from an opened FreeCAD document."""

from __future__ import annotations

from typing import Any, Mapping

from parametron_freecad.runtime.reference_access import (
    ReferenceAccessDocumentError,
    ReferenceAccessReferenceNotFoundError,
    resolve_reference_object,
)
from parametron_freecad.observation.verification_contract import (
    EXPECTED_FIELD_REFERENCES,
    EXPECTED_REFERENCE_FIELD_KIND,
    EXPECTED_REFERENCE_FIELD_NAME,
    FIELD_EXPECTED,
    FIELD_OBSERVE,
    OBSERVE_FIELD_REFERENCES,
)
from parametron_freecad.observation.observed_contract import (
    OBSERVED_REFERENCE_FIELD_KIND,
    OBSERVED_REFERENCE_FIELD_NAME,
)

# ---------------------------------------------------------------------------
# Typed deterministic errors
# ---------------------------------------------------------------------------


class ReferenceObservationError(ValueError):
    """Base class for all reference observation errors."""


class ReferenceObservationRequestError(ReferenceObservationError):
    """Raised when the reference observation request data is malformed."""


class ReferenceObservationDocumentError(ReferenceObservationError):
    """Raised when the document object is invalid or getObject raises unexpectedly."""


class ReferenceObservationReferenceNotFoundError(ReferenceObservationError):
    """Raised when getObject returns None for a requested reference name."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_references_enabled(verification_data: Mapping[str, Any]) -> bool:
    observe = verification_data.get(FIELD_OBSERVE)
    if not isinstance(observe, Mapping):
        return False
    return bool(observe.get(OBSERVE_FIELD_REFERENCES))


def _read_reference_requests(verification_data: Mapping[str, Any]) -> list[Any]:
    expected = verification_data.get(FIELD_EXPECTED)
    if not isinstance(expected, Mapping):
        raise ReferenceObservationRequestError(
            f"verification data missing or invalid {FIELD_EXPECTED!r}: "
            f"expected a mapping, got {type(expected).__name__!r}"
        )
    references = expected.get(EXPECTED_FIELD_REFERENCES)
    if references is None:
        raise ReferenceObservationRequestError(
            f"{FIELD_EXPECTED!r}.{EXPECTED_FIELD_REFERENCES!r} is absent; "
            "reference observation is enabled but no reference requests are provided"
        )
    if isinstance(references, (str, bytes)):
        raise ReferenceObservationRequestError(
            f"{FIELD_EXPECTED!r}.{EXPECTED_FIELD_REFERENCES!r} must be a list of "
            f"mappings, got {type(references).__name__!r}"
        )
    try:
        references_list = list(references)
    except TypeError:
        raise ReferenceObservationRequestError(
            f"{FIELD_EXPECTED!r}.{EXPECTED_FIELD_REFERENCES!r} is not iterable: "
            f"got {type(references).__name__!r}"
        ) from None
    return references_list


def _validate_reference_request(index: int, reference_request: Any) -> tuple[str, str]:
    if not isinstance(reference_request, Mapping):
        raise ReferenceObservationRequestError(
            f"reference request at index {index} must be a mapping, "
            f"got {type(reference_request).__name__!r}"
        )
    kind = reference_request.get(EXPECTED_REFERENCE_FIELD_KIND)
    name = reference_request.get(EXPECTED_REFERENCE_FIELD_NAME)
    if not isinstance(kind, str):
        raise ReferenceObservationRequestError(
            f"reference request at index {index}: "
            f"{EXPECTED_REFERENCE_FIELD_KIND!r} must be a string, "
            f"got {type(kind).__name__!r}"
        )
    if not isinstance(name, str):
        raise ReferenceObservationRequestError(
            f"reference request at index {index}: "
            f"{EXPECTED_REFERENCE_FIELD_NAME!r} must be a string, "
            f"got {type(name).__name__!r}"
        )
    return kind, name


def _resolve_reference(document: Any, name: str) -> Any:
    try:
        resolved = resolve_reference_object(document, name)
    except ReferenceAccessReferenceNotFoundError as exc:
        raise ReferenceObservationReferenceNotFoundError(
            f"document.getObject({name!r}) returned None; "
            "no object with that name exists in the document"
        ) from exc
    except ReferenceAccessDocumentError as exc:
        if exc.__cause__ is not None:
            raise ReferenceObservationDocumentError(
                f"document.getObject({name!r}) raised an error: {exc.__cause__}"
            ) from exc.__cause__
        raise ReferenceObservationDocumentError(
            "document does not have a callable 'getObject' method"
        ) from exc
    return resolved.reference


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def observe_requested_references(
    document: Any,
    verification_data: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Observe only the references requested in verification_data from document.

    Returns an empty tuple when observe.references is not enabled.
    Returns one observed reference dict per request, in request order.
    Raises a ReferenceObservationError subclass for all failure modes.
    """
    if not isinstance(verification_data, Mapping):
        raise ReferenceObservationRequestError(
            f"verification_data must be a mapping, "
            f"got {type(verification_data).__name__!r}"
        )
    if FIELD_OBSERVE in verification_data:
        observe = verification_data[FIELD_OBSERVE]
        if not isinstance(observe, Mapping):
            raise ReferenceObservationRequestError(
                f"{FIELD_OBSERVE!r} must be a mapping when present, "
                f"got {type(observe).__name__!r}"
            )
    if not _is_references_enabled(verification_data):
        return ()

    reference_requests = _read_reference_requests(verification_data)

    results: list[dict[str, Any]] = []
    for index, reference_request in enumerate(reference_requests):
        kind, name = _validate_reference_request(index, reference_request)
        _resolve_reference(document, name)
        results.append(
            {
                OBSERVED_REFERENCE_FIELD_KIND: kind,
                OBSERVED_REFERENCE_FIELD_NAME: name,
            }
        )

    return tuple(results)


__all__ = [
    "ReferenceObservationDocumentError",
    "ReferenceObservationError",
    "ReferenceObservationReferenceNotFoundError",
    "ReferenceObservationRequestError",
    "observe_requested_references",
]
