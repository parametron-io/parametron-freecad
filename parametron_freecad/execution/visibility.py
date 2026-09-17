"""FreeCAD-native visibility mutation execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class VisibilityMutationError(ValueError):
    """Base class for deterministic native visibility failures."""


class VisibilityTargetNotFoundError(VisibilityMutationError):
    """Raised when an exact native object name does not resolve."""


class UnsupportedVisibilityTargetError(VisibilityMutationError):
    """Raised when an object lacks the supported native visibility property."""


class VisibilityNativeOperationError(VisibilityMutationError):
    """Raised when native visibility lookup, inspection, or writing fails."""


def apply_visibility_mutations(
    document: Any,
    mutations: Sequence[Mapping[str, Any]],
) -> None:
    """Apply validated visibility entries in caller-provided order."""

    try:
        get_object = document.getObject
    except Exception as exc:
        raise VisibilityNativeOperationError(
            "document native getObject access failed for visibility mutations"
        ) from exc

    if not callable(get_object):
        raise VisibilityNativeOperationError(
            "document does not provide callable native getObject for "
            "visibility mutations"
        )

    for index, mutation in enumerate(mutations):
        object_name = mutation["object"]
        requested_state = mutation["visible"]

        try:
            target = get_object(object_name)
        except Exception as exc:
            raise VisibilityNativeOperationError(
                _format_mutation_message(
                    index,
                    object_name,
                    "native object lookup failed",
                )
            ) from exc

        if target is None:
            raise VisibilityTargetNotFoundError(
                _format_mutation_message(
                    index,
                    object_name,
                    "exact native object was not found",
                )
            )

        _require_native_visibility_property(target, index, object_name)

        try:
            target.Visibility = requested_state
        except Exception as exc:
            raise VisibilityNativeOperationError(
                _format_mutation_message(
                    index,
                    object_name,
                    "native Visibility property write failed",
                )
            ) from exc


def _require_native_visibility_property(
    target: Any,
    index: int,
    object_name: str,
) -> None:
    try:
        properties = target.PropertiesList
    except AttributeError as exc:
        raise UnsupportedVisibilityTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Visibility property is unsupported",
            )
        ) from exc
    except Exception as exc:
        raise VisibilityNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native property inspection failed",
            )
        ) from exc

    try:
        supports_visibility = "Visibility" in properties
    except Exception as exc:
        raise VisibilityNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native property inspection failed",
            )
        ) from exc

    if not supports_visibility:
        raise UnsupportedVisibilityTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Visibility property is unsupported",
            )
        )

    try:
        get_property_type = target.getTypeIdOfProperty
    except AttributeError as exc:
        raise UnsupportedVisibilityTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Visibility property type inspection is unsupported",
            )
        ) from exc
    except Exception as exc:
        raise VisibilityNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native Visibility property type inspection failed",
            )
        ) from exc

    if not callable(get_property_type):
        raise UnsupportedVisibilityTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Visibility property type inspection is unsupported",
            )
        )

    try:
        property_type = get_property_type("Visibility")
    except Exception as exc:
        raise VisibilityNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                "native Visibility property type inspection failed",
            )
        ) from exc

    if property_type != "App::PropertyBool":
        raise UnsupportedVisibilityTargetError(
            _format_mutation_message(
                index,
                object_name,
                "native Visibility property must be App::PropertyBool; "
                f"found {property_type!r}",
            )
        )


def _format_mutation_message(index: int, object_name: str, detail: str) -> str:
    return f"visibility[{index}] object '{object_name}': {detail}"


__all__ = [
    "UnsupportedVisibilityTargetError",
    "VisibilityMutationError",
    "VisibilityNativeOperationError",
    "VisibilityTargetNotFoundError",
    "apply_visibility_mutations",
]
