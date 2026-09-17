"""FreeCAD-native suppression mutation execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class SuppressionMutationError(ValueError):
    """Base class for deterministic native suppression failures."""


class SuppressionTargetNotFoundError(SuppressionMutationError):
    """Raised when an exact native object name does not resolve."""


class UnsupportedSuppressionTargetError(SuppressionMutationError):
    """Raised when an object lacks the supported native suppression property."""


class SuppressionNativeOperationError(SuppressionMutationError):
    """Raised when native suppression lookup, inspection, or writing fails."""


def apply_suppression_mutations(
    document: Any,
    mutations: Sequence[Mapping[str, Any]],
) -> None:
    """Apply validated suppression entries in caller-provided order."""

    try:
        get_object = document.getObject
    except Exception as exc:
        raise SuppressionNativeOperationError(
            "document native getObject access failed for suppression mutations"
        ) from exc

    if not callable(get_object):
        raise SuppressionNativeOperationError(
            "document does not provide callable native getObject for "
            "suppression mutations"
        )

    for index, mutation in enumerate(mutations):
        object_name = mutation["object"]
        requested_state = mutation["suppressed"]

        try:
            target = get_object(object_name)
        except Exception as exc:
            raise SuppressionNativeOperationError(
                _format_mutation_message(
                    index,
                    object_name,
                    "native object lookup failed",
                )
            ) from exc

        if target is None:
            raise SuppressionTargetNotFoundError(
                _format_mutation_message(
                    index,
                    object_name,
                    "exact native object was not found",
                )
            )

        _require_native_suppression_property(target, index, object_name)

        try:
            target.Suppressed = requested_state
        except Exception as exc:
            raise SuppressionNativeOperationError(
                _format_mutation_message(
                    index,
                    object_name,
                    "native Suppressed property write failed",
                )
            ) from exc


def _require_native_suppression_property(
    target: Any,
    index: int,
    object_name: str,
) -> None:
    try:
        properties = target.PropertiesList
    except AttributeError as exc:
        raise UnsupportedSuppressionTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Suppressed property is unsupported",
            )
        ) from exc
    except Exception as exc:
        raise SuppressionNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native property inspection failed",
            )
        ) from exc

    try:
        supports_suppression = "Suppressed" in properties
    except Exception as exc:
        raise SuppressionNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native property inspection failed",
            )
        ) from exc

    if not supports_suppression:
        raise UnsupportedSuppressionTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Suppressed property is unsupported",
            )
        )

    try:
        get_property_type = target.getTypeIdOfProperty
    except AttributeError as exc:
        raise UnsupportedSuppressionTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Suppressed property type inspection is unsupported",
            )
        ) from exc
    except Exception as exc:
        raise SuppressionNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native Suppressed property type inspection failed",
            )
        ) from exc

    if not callable(get_property_type):
        raise UnsupportedSuppressionTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Suppressed property type inspection is unsupported",
            )
        )

    try:
        property_type = get_property_type("Suppressed")
    except Exception as exc:
        raise SuppressionNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native Suppressed property type inspection failed",
            )
        ) from exc

    if property_type != "App::PropertyBool":
        raise UnsupportedSuppressionTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Suppressed property must be App::PropertyBool; "
                f"found {property_type!r}",
            )
        )


def _format_mutation_message(index: int, object_name: str, detail: str) -> str:
    return f"suppression[{index}] object '{object_name}': {detail}"


__all__ = [
    "SuppressionMutationError",
    "SuppressionNativeOperationError",
    "SuppressionTargetNotFoundError",
    "UnsupportedSuppressionTargetError",
    "apply_suppression_mutations",
]
