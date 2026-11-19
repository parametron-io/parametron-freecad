"""Bounded native property access and typed fact value extraction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from parametron_freecad.runtime.fact_request import (
    FACT_VALUE_KIND_BOOLEAN,
    FACT_VALUE_KIND_INTEGER,
    FACT_VALUE_KIND_NUMBER,
    FACT_VALUE_KIND_STRING,
)

_NATIVE_UNIT_PREFIX = "Unit: "
_NATIVE_UNIT_SUFFIX_MARKER = " ("
# Go's json.Marshal for strings additionally escapes these code points compared
# with Python's json.dumps(ensure_ascii=False). Values containing them cannot be
# emitted without a custom crossing encoder.
_GO_ESCAPED_CHARACTERS = frozenset("<>&\u2028\u2029")


class FactAccessError(ValueError):
    """Base class for native fact access failures."""


class FactValueUnavailable(FactAccessError):
    """Raised when a native value cannot be observed at all."""


class FactValueUnsupported(FactAccessError):
    """Raised when a native value cannot be represented under the contract."""


@dataclass(frozen=True, slots=True)
class NativeFactValue:
    """One bounded native scalar observation."""

    value_kind: str
    value: int | float | str | bool
    unit: str


def native_subject_type(native_object: Any) -> str:
    """Return the subject native type or an empty token when unavailable."""
    value = getattr(native_object, "TypeId", None)
    if (
        isinstance(value, str)
        and value
        and value.strip() == value
        and "\x00" not in value
    ):
        return value
    return ""


def native_property_names(native_object: Any) -> frozenset[str] | None:
    """Return the explicit native property inventory when available."""
    properties = getattr(native_object, "PropertiesList", None)
    if isinstance(properties, (list, tuple)):
        return frozenset(str(name) for name in properties)
    return None


def read_native_property(native_object: Any, property_name: str) -> Any:
    """Read exactly one named native property without heuristics."""
    names = native_property_names(native_object)
    if names is not None and property_name not in names:
        raise FactValueUnavailable("native property is unavailable")
    try:
        value = getattr(native_object, property_name)
    except Exception as exc:
        raise FactValueUnavailable("native property is unavailable") from exc
    if value is None:
        raise FactValueUnavailable("native property value is unavailable")
    return value


def native_quantity_parts(value: Any) -> tuple[float, str] | None:
    """Return a native quantity numeric value and bounded unit token."""
    if not hasattr(value, "Value") or not hasattr(value, "Unit"):
        return None
    try:
        numeric = float(value.Value)
        unit_text = str(value.Unit)
    except Exception as exc:
        raise FactValueUnsupported(
            "native quantity representation is unsupported"
        ) from exc

    if not unit_text.startswith(_NATIVE_UNIT_PREFIX):
        raise FactValueUnsupported("native quantity unit token is unsupported")
    remainder = unit_text[len(_NATIVE_UNIT_PREFIX) :]
    token = remainder.split(_NATIVE_UNIT_SUFFIX_MARKER, 1)[0].strip()
    if "\x00" in token or any(character in token for character in "\n\r\t"):
        raise FactValueUnsupported("native quantity unit token is unsupported")
    return numeric, token


def extract_fact_value(
    native_value: Any,
    value_kind: str,
    requested_unit: str,
) -> NativeFactValue:
    """Extract one typed scalar or raise an explicit access state."""
    if value_kind == FACT_VALUE_KIND_BOOLEAN:
        if not isinstance(native_value, bool):
            raise FactValueUnsupported("native property value is not a boolean")
        return NativeFactValue(
            value_kind=FACT_VALUE_KIND_BOOLEAN,
            value=native_value,
            unit="",
        )

    if value_kind == FACT_VALUE_KIND_STRING:
        if not isinstance(native_value, str):
            raise FactValueUnsupported("native property value is not a string")
        _require_canonical_string(native_value)
        return NativeFactValue(
            value_kind=FACT_VALUE_KIND_STRING,
            value=native_value,
            unit="",
        )

    if isinstance(native_value, bool):
        raise FactValueUnsupported("native boolean value is not numeric fact material")

    quantity = native_quantity_parts(native_value)
    if quantity is None:
        if not isinstance(native_value, (int, float)):
            raise FactValueUnsupported("native property value is not numeric")
        numeric = float(native_value)
        native_unit = ""
        preserve_integer = isinstance(native_value, int)
    else:
        numeric, native_unit = quantity
        preserve_integer = False

    if math.isnan(numeric) or math.isinf(numeric):
        raise FactValueUnsupported("non-finite numeric value is unsupported")

    unit = _resolve_unit(native_unit, requested_unit)

    if value_kind == FACT_VALUE_KIND_INTEGER:
        if numeric != math.trunc(numeric):
            raise FactValueUnsupported("native property value is not an exact integer")
        return NativeFactValue(
            value_kind=FACT_VALUE_KIND_INTEGER,
            value=int(numeric),
            unit=unit,
        )

    if value_kind != FACT_VALUE_KIND_NUMBER:
        raise FactValueUnsupported("unsupported fact value kind")

    if preserve_integer:
        return NativeFactValue(
            value_kind=FACT_VALUE_KIND_NUMBER,
            value=int(numeric),
            unit=unit,
        )
    return NativeFactValue(
        value_kind=FACT_VALUE_KIND_NUMBER,
        value=float(numeric),
        unit=unit,
    )


def _resolve_unit(native_unit: str, requested_unit: str) -> str:
    if requested_unit:
        if not native_unit:
            raise FactValueUnsupported("native value has no matching explicit unit")
        if native_unit != requested_unit:
            raise FactValueUnsupported(
                f"native unit {native_unit!r} disagrees with requested "
                f"unit {requested_unit!r}"
            )
        return requested_unit
    if native_unit:
        raise FactValueUnsupported(f"native value has an implicit unit {native_unit!r}")
    return ""


def _require_canonical_string(value: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise FactValueUnsupported("string value is not valid UTF-8 text") from exc
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise FactValueUnsupported(
            "string value contains an unsupported surrogate code point"
        )
    if any(character in _GO_ESCAPED_CHARACTERS for character in value):
        raise FactValueUnsupported(
            "string value is not canonical under the bounded encoder"
        )


__all__ = [
    "FactAccessError",
    "FactValueUnavailable",
    "FactValueUnsupported",
    "NativeFactValue",
    "extract_fact_value",
    "native_property_names",
    "native_quantity_parts",
    "native_subject_type",
    "read_native_property",
]
