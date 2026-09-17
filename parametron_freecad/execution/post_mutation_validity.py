"""Read-only FreeCAD-native post-mutation validity inspection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class PostMutationValidityError(ValueError):
    """Base class for deterministic post-mutation validity failures."""


class NativeValidityEvidenceUnavailableError(PostMutationValidityError):
    """Raised when required native validity evidence is unsupported or absent."""


class NativeValidityInspectionError(PostMutationValidityError):
    """Raised when a supported native validity inspection operation fails."""


class InvalidNativeCadStateError(PostMutationValidityError):
    """Raised when native evidence proves that the resulting CAD state is invalid."""


@dataclass(frozen=True, slots=True)
class NativeShapeHealthEvidence:
    """Native shape-health facts for one exact PartDesign Body."""

    object_name: str
    is_null: bool
    is_valid: bool
    solid_count: int


@dataclass(frozen=True, slots=True)
class NativeDependencyEvidence:
    """Deterministically ordered native relationships for one exact object."""

    object_name: str
    dependent_object_names: tuple[str, ...]
    dependency_object_names: tuple[str, ...]


def inspect_post_mutation_validity(
    document: Any,
    object_name: str,
) -> NativeShapeHealthEvidence:
    """Inspect post-recompute native shape health for an exact PartDesign Body.

    The caller owns mutation and recompute. This function only reads the live
    document and raises a controlled error when evidence is unavailable, native
    inspection fails, or the obtained shape is null or invalid.
    """

    target = _resolve_native_object(document, object_name)
    _require_partdesign_body(target, object_name)
    shape = _read_required_attribute(target, "Shape", object_name)

    is_null = _call_shape_predicate(shape, "isNull", object_name)
    is_valid = _call_shape_predicate(shape, "isValid", object_name)

    if is_null:
        raise InvalidNativeCadStateError(
            _object_message(object_name, "native shape is null")
        )
    if not is_valid:
        raise InvalidNativeCadStateError(
            _object_message(object_name, "native shape reports invalid")
        )

    solid_count = _inspect_solid_count(shape, object_name)
    return NativeShapeHealthEvidence(
        object_name=object_name,
        is_null=is_null,
        is_valid=is_valid,
        solid_count=solid_count,
    )


def inspect_native_dependencies(
    document: Any,
    object_name: str,
) -> NativeDependencyEvidence:
    """Return sorted native InList and OutList object names without policy."""

    target = _resolve_native_object(document, object_name)
    dependents = _inspect_relationship_names(target, "InList", object_name)
    dependencies = _inspect_relationship_names(target, "OutList", object_name)
    return NativeDependencyEvidence(
        object_name=object_name,
        dependent_object_names=dependents,
        dependency_object_names=dependencies,
    )


def _resolve_native_object(document: Any, object_name: str) -> Any:
    try:
        get_object = document.getObject
    except AttributeError as exc:
        raise NativeValidityEvidenceUnavailableError(
            "document does not provide native getObject validity evidence"
        ) from exc
    except Exception as exc:
        raise NativeValidityInspectionError(
            "document native getObject access failed during validity inspection"
        ) from exc

    if not callable(get_object):
        raise NativeValidityEvidenceUnavailableError(
            "document does not provide callable native getObject validity evidence"
        )

    try:
        target = get_object(object_name)
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(object_name, "native object lookup failed")
        ) from exc

    if target is None:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(object_name, "exact native object was not found")
        )
    return target


def _require_partdesign_body(target: Any, object_name: str) -> None:
    try:
        is_derived_from = target.isDerivedFrom
    except AttributeError as exc:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                "native PartDesign Body type evidence is unavailable",
            )
        ) from exc
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(
                object_name,
                "native PartDesign Body type inspection failed",
            )
        ) from exc

    if not callable(is_derived_from):
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                "native PartDesign Body type evidence is unavailable",
            )
        )

    try:
        is_body = is_derived_from("PartDesign::Body")
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(
                object_name,
                "native PartDesign Body type inspection failed",
            )
        ) from exc

    if is_body is not True:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                "native target is not a supported PartDesign Body",
            )
        )


def _read_required_attribute(target: Any, attribute: str, object_name: str) -> Any:
    try:
        value = getattr(target, attribute)
    except AttributeError as exc:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(object_name, f"native {attribute} evidence is unavailable")
        ) from exc
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(object_name, f"native {attribute} inspection failed")
        ) from exc

    if value is None:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(object_name, f"native {attribute} evidence is unavailable")
        )
    return value


def _call_shape_predicate(shape: Any, method_name: str, object_name: str) -> bool:
    try:
        predicate = getattr(shape, method_name)
    except AttributeError as exc:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                f"native Shape.{method_name} evidence is unavailable",
            )
        ) from exc
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(
                object_name,
                f"native Shape.{method_name} inspection failed",
            )
        ) from exc

    if not callable(predicate):
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                f"native Shape.{method_name} evidence is unavailable",
            )
        )

    try:
        result = predicate()
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(
                object_name,
                f"native Shape.{method_name} inspection failed",
            )
        ) from exc

    if type(result) is not bool:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                f"native Shape.{method_name} did not return boolean evidence",
            )
        )
    return result


def _inspect_solid_count(shape: Any, object_name: str) -> int:
    solids = _read_required_attribute(shape, "Solids", object_name)
    try:
        solid_count = len(solids)
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(object_name, "native Shape.Solids inspection failed")
        ) from exc

    if type(solid_count) is not int or solid_count < 0:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                "native Shape.Solids did not provide usable count evidence",
            )
        )
    return solid_count


def _inspect_relationship_names(
    target: Any,
    relationship: str,
    object_name: str,
) -> tuple[str, ...]:
    related_objects = _read_required_attribute(target, relationship, object_name)
    try:
        iterator = iter(related_objects)
    except Exception as exc:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                f"native {relationship} evidence is not iterable",
            )
        ) from exc

    names: list[str] = []
    try:
        for related_object in iterator:
            related_name = related_object.Name
            if not isinstance(related_name, str) or not related_name:
                raise NativeValidityEvidenceUnavailableError(
                    _object_message(
                        object_name,
                        f"native {relationship} contains an object without "
                        "a stable Name",
                    )
                )
            names.append(related_name)
    except NativeValidityEvidenceUnavailableError:
        raise
    except AttributeError as exc:
        raise NativeValidityEvidenceUnavailableError(
            _object_message(
                object_name,
                f"native {relationship} contains an object without a stable Name",
            )
        ) from exc
    except Exception as exc:
        raise NativeValidityInspectionError(
            _object_message(object_name, f"native {relationship} inspection failed")
        ) from exc

    return tuple(sorted(set(names)))


def _object_message(object_name: str, detail: str) -> str:
    return f"post-mutation validity object '{object_name}': {detail}"


__all__ = [
    "InvalidNativeCadStateError",
    "NativeDependencyEvidence",
    "NativeShapeHealthEvidence",
    "NativeValidityEvidenceUnavailableError",
    "NativeValidityInspectionError",
    "PostMutationValidityError",
    "inspect_native_dependencies",
    "inspect_post_mutation_validity",
]
