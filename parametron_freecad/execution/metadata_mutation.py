"""FreeCAD-native metadata mutation execution for existing native properties.

This consumer receives already-validated metadata mutation entries of the form
``{"object": ..., "property": ..., "value": ..., "valueKind": ...}`` and
performs the exact native property write on an opened document.

It never creates properties, property groups, aliases, or fallback properties,
and it never redirects an entry to a display label or another property.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from parametron_freecad.execution.manifest_contract import (
    METADATA_VALUE_KIND_BOOLEAN,
    METADATA_VALUE_KIND_INTEGER,
    METADATA_VALUE_KIND_NUMBER,
    METADATA_VALUE_KIND_STRING,
    SUPPORTED_METADATA_VALUE_KINDS,
)
from parametron_freecad.runtime.metadata_access import (
    MetadataAccessDocumentError,
    MetadataAccessError,
    MetadataAccessOwnerNotFoundError,
    MetadataAccessPropertyInspectionError,
    MetadataAccessPropertyNotFoundError,
    UnsupportedMetadataPropertyTypeError,
    metadata_value_kind_for_native_type,
    read_metadata_property,
    require_metadata_property,
    resolve_metadata_owner,
)

METADATA_INTEGER_MIN = -(2**63)
METADATA_INTEGER_MAX = 2**63

_READ_ONLY_MARKERS = ("read-only", "read only", "readonly")


class MetadataMutationError(ValueError):
    """Base class for deterministic native metadata mutation failures."""


class MetadataMutationDocumentError(MetadataMutationError):
    """Raised when the document cannot support native object resolution."""


class MetadataMutationObjectNotFoundError(MetadataMutationError):
    """Raised when an exact native object name does not resolve."""


class MetadataMutationPropertyNotFoundError(MetadataMutationError):
    """Raised when an exact native property does not exist on the object."""


class MetadataMutationPropertyInspectionError(MetadataMutationError):
    """Raised when native property presence or type inspection cannot complete."""


class MetadataMutationUnsupportedPropertyTypeError(MetadataMutationError):
    """Raised when the native property type is outside the metadata contract."""


class MetadataMutationValueKindMismatchError(MetadataMutationError):
    """Raised when the requested valueKind is incompatible with the native type."""


class MetadataMutationValueError(MetadataMutationError):
    """Raised when a value is invalid for the requested metadata value kind."""


class MetadataMutationNotWritableError(MetadataMutationError):
    """Raised when the native property rejects a write as not writable."""


class MetadataMutationNativeWriteError(MetadataMutationError):
    """Raised when the native property write fails for another native reason."""


class MetadataMutationVerificationError(MetadataMutationError):
    """Raised when a native write did not store the requested value."""


def apply_metadata_mutations(
    document: Any,
    mutations: Sequence[Mapping[str, Any]],
) -> None:
    """Apply validated metadata entries to existing native properties in order.

    Stops at the first failure. Earlier successful writes remain applied and
    no rollback is attempted. The supplied mutation mappings are only read.
    """

    for index, mutation in enumerate(mutations):
        object_name = mutation["object"]
        property_name = mutation["property"]
        value_kind = mutation["valueKind"]
        value = mutation["value"]

        owner = _resolve_native_owner(
            document,
            index,
            object_name,
            property_name,
        )
        native_type_id = _require_native_property(
            owner,
            index,
            object_name,
            property_name,
        )
        _require_supported_value_kind(
            value_kind,
            index,
            object_name,
            property_name,
        )
        native_value_kind = _native_value_kind(
            native_type_id,
            index,
            object_name,
            property_name,
        )
        _require_compatible_value_kind(
            value_kind,
            native_value_kind,
            native_type_id,
            index,
            object_name,
            property_name,
        )
        normalized_value = _normalize_value(
            value,
            value_kind,
            index,
            object_name,
            property_name,
        )
        _write_native_value(
            owner,
            property_name,
            normalized_value,
            index,
            object_name,
        )
        stored_value = _read_back_native_value(
            owner,
            property_name,
            object_name,
            index,
        )
        _verify_stored_value(
            stored_value,
            normalized_value,
            value_kind,
            index,
            object_name,
            property_name,
        )


def _resolve_native_owner(
    document: Any,
    index: int,
    object_name: str,
    property_name: str,
) -> Any:
    try:
        return resolve_metadata_owner(document, object_name).owner
    except MetadataAccessDocumentError as exc:
        cause = exc.__cause__ if exc.__cause__ is not None else exc
        raise MetadataMutationDocumentError(
            _entry_message(
                index,
                object_name,
                property_name,
                "document native object lookup failed",
            )
        ) from cause
    except MetadataAccessOwnerNotFoundError:
        raise MetadataMutationObjectNotFoundError(
            _entry_message(
                index,
                object_name,
                property_name,
                "exact native object was not found",
            )
        ) from None


def _require_native_property(
    owner: Any,
    index: int,
    object_name: str,
    property_name: str,
) -> str:
    try:
        return require_metadata_property(
            owner,
            property_name,
            owner_id=object_name,
        )
    except MetadataAccessPropertyNotFoundError:
        raise MetadataMutationPropertyNotFoundError(
            _entry_message(
                index,
                object_name,
                property_name,
                "exact native property was not found",
            )
        ) from None
    except MetadataAccessPropertyInspectionError as exc:
        cause = exc.__cause__ if exc.__cause__ is not None else exc
        raise MetadataMutationPropertyInspectionError(
            _entry_message(
                index,
                object_name,
                property_name,
                "native property presence or type inspection failed",
            )
        ) from cause


def _require_supported_value_kind(
    value_kind: Any,
    index: int,
    object_name: str,
    property_name: str,
) -> None:
    if value_kind not in SUPPORTED_METADATA_VALUE_KINDS:
        raise MetadataMutationValueError(
            _entry_message(
                index,
                object_name,
                property_name,
                f"unsupported metadata valueKind {value_kind!r}",
            )
        )


def _native_value_kind(
    native_type_id: str,
    index: int,
    object_name: str,
    property_name: str,
) -> str:
    try:
        return metadata_value_kind_for_native_type(native_type_id)
    except UnsupportedMetadataPropertyTypeError:
        raise MetadataMutationUnsupportedPropertyTypeError(
            _entry_message(
                index,
                object_name,
                property_name,
                f"unsupported native property type {native_type_id!r}",
            )
        ) from None


def _require_compatible_value_kind(
    value_kind: str,
    native_value_kind: str,
    native_type_id: str,
    index: int,
    object_name: str,
    property_name: str,
) -> None:
    if value_kind != native_value_kind:
        raise MetadataMutationValueKindMismatchError(
            _entry_message(
                index,
                object_name,
                property_name,
                f"requested valueKind {value_kind!r} is incompatible with "
                f"native property type {native_type_id!r} requiring "
                f"valueKind {native_value_kind!r}",
            )
        )


def _normalize_value(
    value: Any,
    value_kind: str,
    index: int,
    object_name: str,
    property_name: str,
) -> Any:
    if value_kind == METADATA_VALUE_KIND_STRING:
        if not isinstance(value, str):
            raise _value_error(
                index,
                object_name,
                property_name,
                f"value {value!r} is not a string",
            )
        return value

    if value_kind == METADATA_VALUE_KIND_BOOLEAN:
        if type(value) is not bool:
            raise _value_error(
                index,
                object_name,
                property_name,
                f"value {value!r} is not a boolean",
            )
        return value

    if value_kind == METADATA_VALUE_KIND_NUMBER:
        if type(value) is bool or not isinstance(value, (int, float)):
            raise _value_error(
                index,
                object_name,
                property_name,
                f"value {value!r} is not a number",
            )
        try:
            normalized = float(value)
        except (OverflowError, ValueError):
            raise _value_error(
                index,
                object_name,
                property_name,
                f"value {value!r} cannot be represented as a finite float",
            ) from None
        if not math.isfinite(normalized):
            raise _value_error(
                index,
                object_name,
                property_name,
                f"value {value!r} is not a finite number",
            )
        return normalized

    return _normalize_integer_value(
        value,
        index,
        object_name,
        property_name,
    )


def _normalize_integer_value(
    value: Any,
    index: int,
    object_name: str,
    property_name: str,
) -> int:
    if type(value) is bool:
        raise _value_error(
            index,
            object_name,
            property_name,
            f"value {value!r} is not an integer",
        )

    if isinstance(value, int):
        normalized = int(value)
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise _value_error(
                index,
                object_name,
                property_name,
                f"value {value!r} is not an integral number",
            )
        normalized = int(value)
    else:
        raise _value_error(
            index,
            object_name,
            property_name,
            f"value {value!r} is not an integer",
        )

    if not METADATA_INTEGER_MIN <= normalized < METADATA_INTEGER_MAX:
        raise _value_error(
            index,
            object_name,
            property_name,
            f"value {value!r} is outside the signed 64-bit integer range",
        )
    return normalized


def _write_native_value(
    owner: Any,
    property_name: str,
    normalized_value: Any,
    index: int,
    object_name: str,
) -> None:
    try:
        setattr(owner, property_name, normalized_value)
    except Exception as exc:
        if _indicates_read_only_failure(exc):
            raise MetadataMutationNotWritableError(
                _entry_message(
                    index,
                    object_name,
                    property_name,
                    "native property is not writable",
                )
            ) from exc
        raise MetadataMutationNativeWriteError(
            _entry_message(
                index,
                object_name,
                property_name,
                "native property write failed",
            )
        ) from exc


def _read_back_native_value(
    owner: Any,
    property_name: str,
    object_name: str,
    index: int,
) -> Any:
    try:
        return read_metadata_property(
            owner,
            property_name,
            owner_id=object_name,
        )
    except MetadataAccessError as exc:
        cause = exc.__cause__ if exc.__cause__ is not None else exc
        raise MetadataMutationVerificationError(
            _entry_message(
                index,
                object_name,
                property_name,
                "native property read-back failed after write",
            )
        ) from cause


def _verify_stored_value(
    stored: Any,
    requested_value: Any,
    value_kind: str,
    index: int,
    object_name: str,
    property_name: str,
) -> None:
    if stored.value_kind != value_kind:
        raise MetadataMutationVerificationError(
            _entry_message(
                index,
                object_name,
                property_name,
                f"native property now has value kind {stored.value_kind!r} "
                f"instead of the requested {value_kind!r}",
            )
        )
    if not _stored_value_matches(stored.value, requested_value, value_kind):
        raise MetadataMutationVerificationError(
            _entry_message(
                index,
                object_name,
                property_name,
                f"native property stored {stored.value!r} "
                f"instead of the requested {requested_value!r}",
            )
        )


def _stored_value_matches(
    stored_value: Any,
    requested_value: Any,
    value_kind: str,
) -> bool:
    if value_kind == METADATA_VALUE_KIND_STRING:
        return isinstance(stored_value, str) and stored_value == requested_value
    if value_kind == METADATA_VALUE_KIND_BOOLEAN:
        return type(stored_value) is bool and stored_value == requested_value
    if value_kind == METADATA_VALUE_KIND_NUMBER:
        return type(stored_value) is float and stored_value == requested_value
    if value_kind == METADATA_VALUE_KIND_INTEGER:
        return type(stored_value) is int and stored_value == requested_value
    return False


def _indicates_read_only_failure(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _READ_ONLY_MARKERS)


def _value_error(
    index: int,
    object_name: str,
    property_name: str,
    detail: str,
) -> MetadataMutationValueError:
    return MetadataMutationValueError(
        _entry_message(index, object_name, property_name, detail)
    )


def _entry_message(
    index: int,
    object_name: str,
    property_name: str,
    detail: str,
) -> str:
    return (
        f"metadata[{index}] object {object_name!r} property {property_name!r}: {detail}"
    )


__all__ = [
    "METADATA_INTEGER_MAX",
    "METADATA_INTEGER_MIN",
    "MetadataMutationDocumentError",
    "MetadataMutationError",
    "MetadataMutationNativeWriteError",
    "MetadataMutationNotWritableError",
    "MetadataMutationObjectNotFoundError",
    "MetadataMutationPropertyInspectionError",
    "MetadataMutationPropertyNotFoundError",
    "MetadataMutationUnsupportedPropertyTypeError",
    "MetadataMutationValueError",
    "MetadataMutationValueKindMismatchError",
    "MetadataMutationVerificationError",
    "apply_metadata_mutations",
]
