"""Phase 2 runtime helper for observing requested metadata from an opened FreeCAD document."""

from __future__ import annotations

import math
from typing import Any, Mapping

from parametron_freecad.observation.verification_contract import (
    EXPECTED_FIELD_METADATA,
    EXPECTED_METADATA_FIELD_ID,
    EXPECTED_METADATA_FIELD_KEY,
    EXPECTED_METADATA_FIELD_OWNER_ID,
    FIELD_EXPECTED,
    FIELD_OBSERVE,
    OBSERVE_FIELD_METADATA,
)
from parametron_freecad.observation.observed_contract import (
    OBSERVED_METADATA_FIELD_ID,
    OBSERVED_METADATA_FIELD_KEY,
    OBSERVED_METADATA_FIELD_OWNER_ID,
    OBSERVED_METADATA_FIELD_VALUE,
    OBSERVED_METADATA_FIELD_VALUE_KIND,
    OBSERVED_METADATA_VALUE_KIND_BOOLEAN,
    OBSERVED_METADATA_VALUE_KIND_INTEGER,
    OBSERVED_METADATA_VALUE_KIND_NUMBER,
    OBSERVED_METADATA_VALUE_KIND_STRING,
)
from parametron_freecad.runtime.metadata_access import (
    MetadataAccessDocumentError,
    MetadataAccessOwnerNotFoundError,
    MetadataAccessPropertyReadError,
    read_metadata_value,
    resolve_metadata_owner,
)

# ---------------------------------------------------------------------------
# Typed deterministic errors
# ---------------------------------------------------------------------------


class MetadataObservationError(ValueError):
    """Base class for all metadata observation errors."""


class MetadataObservationRequestError(MetadataObservationError):
    """Raised when the metadata observation request data is malformed."""


class MetadataObservationDocumentError(MetadataObservationError):
    """Raised when the document object is invalid or getObject raises unexpectedly."""


class MetadataObservationOwnerNotFoundError(MetadataObservationError):
    """Raised when getObject returns None for a requested owner id."""


class MetadataObservationPropertyError(MetadataObservationError):
    """Raised when a requested metadata property cannot be read."""


class MetadataObservationValueError(MetadataObservationError):
    """Raised when an observed metadata value is not a supported scalar kind."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_metadata_enabled(verification_data: Mapping[str, Any]) -> bool:
    observe = verification_data.get(FIELD_OBSERVE)
    if not isinstance(observe, Mapping):
        return False
    return bool(observe.get(OBSERVE_FIELD_METADATA))


def _read_metadata_requests(verification_data: Mapping[str, Any]) -> list[Any]:
    expected = verification_data.get(FIELD_EXPECTED)
    if not isinstance(expected, Mapping):
        raise MetadataObservationRequestError(
            f"verification data missing or invalid {FIELD_EXPECTED!r}: "
            f"expected a mapping, got {type(expected).__name__!r}"
        )
    metadata = expected.get(EXPECTED_FIELD_METADATA)
    if metadata is None:
        raise MetadataObservationRequestError(
            f"{FIELD_EXPECTED!r}.{EXPECTED_FIELD_METADATA!r} is absent; "
            "metadata observation is enabled but no metadata requests are provided"
        )
    if isinstance(metadata, (str, bytes)):
        raise MetadataObservationRequestError(
            f"{FIELD_EXPECTED!r}.{EXPECTED_FIELD_METADATA!r} must be a list of "
            f"mappings, got {type(metadata).__name__!r}"
        )
    try:
        metadata_list = list(metadata)
    except TypeError:
        raise MetadataObservationRequestError(
            f"{FIELD_EXPECTED!r}.{EXPECTED_FIELD_METADATA!r} is not iterable: "
            f"got {type(metadata).__name__!r}"
        ) from None
    return metadata_list


def _validate_metadata_request(index: int, metadata_request: Any) -> tuple[str, str, str]:
    if not isinstance(metadata_request, Mapping):
        raise MetadataObservationRequestError(
            f"metadata request at index {index} must be a mapping, "
            f"got {type(metadata_request).__name__!r}"
        )
    metadata_id = metadata_request.get(EXPECTED_METADATA_FIELD_ID)
    key = metadata_request.get(EXPECTED_METADATA_FIELD_KEY)
    owner_id = metadata_request.get(EXPECTED_METADATA_FIELD_OWNER_ID)
    if not isinstance(metadata_id, str):
        raise MetadataObservationRequestError(
            f"metadata request at index {index}: "
            f"{EXPECTED_METADATA_FIELD_ID!r} must be a string, "
            f"got {type(metadata_id).__name__!r}"
        )
    if not isinstance(key, str):
        raise MetadataObservationRequestError(
            f"metadata request at index {index}: "
            f"{EXPECTED_METADATA_FIELD_KEY!r} must be a string, "
            f"got {type(key).__name__!r}"
        )
    if not isinstance(owner_id, str):
        raise MetadataObservationRequestError(
            f"metadata request at index {index}: "
            f"{EXPECTED_METADATA_FIELD_OWNER_ID!r} must be a string, "
            f"got {type(owner_id).__name__!r}"
        )
    return metadata_id, key, owner_id


def _resolve_owner(document: Any, owner_id: str) -> Any:
    try:
        return resolve_metadata_owner(document, owner_id).owner
    except MetadataAccessDocumentError as exc:
        if exc.__cause__ is None:
            raise MetadataObservationDocumentError(
                "document does not have a callable 'getObject' method"
            ) from None
        raise MetadataObservationDocumentError(
            f"document.getObject({owner_id!r}) raised an error: {exc.__cause__}"
        ) from exc.__cause__
    except MetadataAccessOwnerNotFoundError:
        raise MetadataObservationOwnerNotFoundError(
            f"document.getObject({owner_id!r}) returned None; "
            "no object with that ownerId exists in the document"
        ) from None


def _read_metadata_value(owner: Any, owner_id: str, key: str) -> Any:
    try:
        return read_metadata_value(owner, key, owner_id=owner_id)
    except MetadataAccessPropertyReadError as exc:
        cause = exc.__cause__
        raise MetadataObservationPropertyError(
            f"owner {owner_id!r} metadata key {key!r} could not be read: {cause}"
        ) from cause


def _derive_value_kind(value: Any, owner_id: str, key: str) -> str:
    if isinstance(value, bool):
        return OBSERVED_METADATA_VALUE_KIND_BOOLEAN
    if isinstance(value, int):
        return OBSERVED_METADATA_VALUE_KIND_INTEGER
    if isinstance(value, float):
        if not math.isfinite(value):
            raise MetadataObservationValueError(
                f"metadata key {key!r} on owner {owner_id!r} has a non-finite float "
                f"value {value!r}; only finite floats are supported"
            )
        return OBSERVED_METADATA_VALUE_KIND_NUMBER
    if isinstance(value, str):
        return OBSERVED_METADATA_VALUE_KIND_STRING
    raise MetadataObservationValueError(
        f"metadata key {key!r} on owner {owner_id!r} has an unsupported value type "
        f"{type(value).__name__!r}; supported types are bool, int, finite float, str"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def observe_requested_metadata(
    document: Any,
    verification_data: Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Observe only the metadata requested in verification_data from document.

    Returns an empty tuple when observe.metadata is not enabled.
    Returns one observed metadata dict per request, in request order.
    Raises a MetadataObservationError subclass for all failure modes.
    """
    if not _is_metadata_enabled(verification_data):
        return ()

    metadata_requests = _read_metadata_requests(verification_data)

    results: list[dict[str, Any]] = []
    for index, metadata_request in enumerate(metadata_requests):
        metadata_id, key, owner_id = _validate_metadata_request(
            index, metadata_request
        )
        owner = _resolve_owner(document, owner_id)
        raw_value = _read_metadata_value(owner, owner_id, key)
        value_kind = _derive_value_kind(raw_value, owner_id, key)
        results.append(
            {
                OBSERVED_METADATA_FIELD_ID: metadata_id,
                OBSERVED_METADATA_FIELD_KEY: key,
                OBSERVED_METADATA_FIELD_OWNER_ID: owner_id,
                OBSERVED_METADATA_FIELD_VALUE: raw_value,
                OBSERVED_METADATA_FIELD_VALUE_KIND: value_kind,
            }
        )

    return tuple(results)


__all__ = [
    "MetadataObservationDocumentError",
    "MetadataObservationError",
    "MetadataObservationOwnerNotFoundError",
    "MetadataObservationPropertyError",
    "MetadataObservationRequestError",
    "MetadataObservationValueError",
    "observe_requested_metadata",
]
