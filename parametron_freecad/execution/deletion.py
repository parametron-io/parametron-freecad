"""Conservative FreeCAD-native deletion mutation execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from parametron_freecad.execution.document_recompute import (
    DocumentRecomputeError,
    recompute_document,
)
from parametron_freecad.execution.post_mutation_validity import (
    PostMutationValidityError,
    inspect_document_post_mutation_validity,
    inspect_native_dependencies,
)


class DeletionMutationError(ValueError):
    """Base class for deterministic native deletion failures."""


class DeletionTargetNotFoundError(DeletionMutationError):
    """Raised when an exact native object name does not resolve."""


class UnsafeDeletionTargetError(DeletionMutationError):
    """Raised when surviving native dependents make deletion unsafe."""


class DeletionNativeOperationError(DeletionMutationError):
    """Raised when native lookup, dependency inspection, or removal fails."""


class DeletionValidityError(DeletionMutationError):
    """Raised when recompute or required post-delete validity cannot complete."""


def apply_deletion_mutations(
    document: Any,
    mutations: Sequence[Mapping[str, Any]],
) -> None:
    """Apply validated deletion entries in caller-provided order."""

    if not mutations:
        return

    get_object = _require_document_operation(document, "getObject")
    remove_object = _require_document_operation(document, "removeObject")

    for index, mutation in enumerate(mutations):
        object_name = mutation["object"]
        _resolve_target(get_object, index, object_name)
        _require_no_native_dependents(document, index, object_name)

        try:
            remove_object(object_name)
        except Exception as exc:
            raise DeletionNativeOperationError(
                _format_mutation_message(index, object_name, "native removal failed")
            ) from exc

        try:
            remaining_target = get_object(object_name)
        except Exception as exc:
            raise DeletionNativeOperationError(
                _format_mutation_message(
                    index,
                    object_name,
                    "post-removal native object lookup failed",
                )
            ) from exc
        if remaining_target is not None:
            raise DeletionNativeOperationError(
                _format_mutation_message(
                    index,
                    object_name,
                    "native removal did not remove the exact object",
                )
            )

        try:
            recompute_document(document)
            inspect_document_post_mutation_validity(document)
        except (DocumentRecomputeError, PostMutationValidityError) as exc:
            raise DeletionValidityError(
                _format_mutation_message(
                    index,
                    object_name,
                    f"post-delete native validity failed: {exc}",
                )
            ) from exc


def _require_document_operation(document: Any, operation_name: str) -> Any:
    try:
        operation = getattr(document, operation_name)
    except Exception as exc:
        raise DeletionNativeOperationError(
            f"document native {operation_name} access failed for deletion mutations"
        ) from exc
    if not callable(operation):
        raise DeletionNativeOperationError(
            f"document does not provide callable native {operation_name} for "
            "deletion mutations"
        )
    return operation


def _resolve_target(
    get_object: Any,
    index: int,
    object_name: str,
) -> Any:
    try:
        target = get_object(object_name)
    except Exception as exc:
        raise DeletionNativeOperationError(
            _format_mutation_message(index, object_name, "native object lookup failed")
        ) from exc
    if target is None:
        raise DeletionTargetNotFoundError(
            _format_mutation_message(
                index,
                object_name,
                "exact native object was not found",
            )
        )
    return target


def _require_no_native_dependents(
    document: Any,
    index: int,
    object_name: str,
) -> None:
    try:
        evidence = inspect_native_dependencies(document, object_name)
    except PostMutationValidityError as exc:
        raise DeletionNativeOperationError(
            _format_mutation_message(
                index,
                object_name,
                f"native dependency inspection failed: {exc}",
            )
        ) from exc

    if evidence.dependent_object_names:
        dependents = ", ".join(repr(name) for name in evidence.dependent_object_names)
        raise UnsafeDeletionTargetError(
            _format_mutation_message(
                index,
                object_name,
                f"native dependents prevent deletion: {dependents}",
            )
        )


def _format_mutation_message(index: int, object_name: str, detail: str) -> str:
    return f"deletion[{index}] object '{object_name}': {detail}"


__all__ = [
    "DeletionMutationError",
    "DeletionNativeOperationError",
    "DeletionTargetNotFoundError",
    "DeletionValidityError",
    "UnsafeDeletionTargetError",
    "apply_deletion_mutations",
]
