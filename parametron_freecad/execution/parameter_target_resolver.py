"""Deterministic Phase 1 parameter target parsing and resolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from parametron_freecad.runtime.parameter_access import (
    ParameterAccessDocumentError,
    ParameterAccessObjectNotFoundError,
    resolve_parameter_object,
    validate_parameter_access_document,
)


class ParameterTargetResolutionError(ValueError):
    """Base class for deterministic parameter target resolution failures."""


class ParameterTargetSyntaxError(ParameterTargetResolutionError):
    """Raised when a target string is malformed."""


class UnsupportedParameterTargetError(ParameterTargetResolutionError):
    """Raised when a target uses a target family unsupported in Phase 1."""


class ParameterTargetObjectNotFoundError(ParameterTargetResolutionError):
    """Raised when a target object cannot be resolved from the document."""


class ParameterTargetDocumentError(ParameterTargetResolutionError):
    """Raised when the supplied document cannot resolve parameter targets."""


@dataclass(frozen=True, slots=True)
class ParsedParameterTarget:
    """A parsed Phase 1 parameter target."""

    original: str
    object_name: str
    property_name: str


@dataclass(frozen=True, slots=True)
class ResolvedParameterTarget:
    """A resolved Phase 1 parameter target."""

    original: str
    object_name: str
    property_name: str
    object: Any


def parse_parameter_target(target: str) -> ParsedParameterTarget:
    """Parse the supported Phase 1 target syntax."""

    if not isinstance(target, str):
        raise ParameterTargetSyntaxError(
            "parameter target must be a string"
        )

    if target.count(".") != 1:
        raise UnsupportedParameterTargetError(
            "parameter target must use the exact format "
            "<ObjectName>.<PropertyName>"
        )

    object_name, property_name = target.split(".", maxsplit=1)
    if object_name == "" or property_name == "":
        raise ParameterTargetSyntaxError(
            "parameter target must use the exact format "
            "<ObjectName>.<PropertyName>"
        )

    return ParsedParameterTarget(
        original=target,
        object_name=object_name,
        property_name=property_name,
    )


def validate_parameter_target_document(document: Any) -> None:
    """Validate that a document can resolve Phase 1 parameter targets."""

    try:
        validate_parameter_access_document(document)
    except ParameterAccessDocumentError as exc:
        raise ParameterTargetDocumentError(
            "document does not provide getObject for parameter target resolution"
        ) from exc


def resolve_parameter_target(
    document: Any,
    target: str,
) -> ResolvedParameterTarget:
    """Resolve a supported Phase 1 target against a supplied document."""

    parsed_target = parse_parameter_target(target)

    try:
        resolved_object = resolve_parameter_object(
            document,
            parsed_target.object_name,
        )
    except ParameterAccessDocumentError as exc:
        if exc.__cause__ is not None:
            raise ParameterTargetDocumentError(
                f"failed to resolve object '{parsed_target.object_name}'"
            ) from exc.__cause__
        raise ParameterTargetDocumentError(
            "document does not provide getObject for parameter target resolution"
        ) from exc
    except ParameterAccessObjectNotFoundError as exc:
        raise ParameterTargetObjectNotFoundError(
            f"object '{parsed_target.object_name}' was not found"
        ) from exc

    return ResolvedParameterTarget(
        original=parsed_target.original,
        object_name=parsed_target.object_name,
        property_name=parsed_target.property_name,
        object=resolved_object.object,
    )


__all__ = [
    "ParameterTargetDocumentError",
    "ParameterTargetObjectNotFoundError",
    "ParameterTargetResolutionError",
    "ParameterTargetSyntaxError",
    "ParsedParameterTarget",
    "ResolvedParameterTarget",
    "UnsupportedParameterTargetError",
    "parse_parameter_target",
    "resolve_parameter_target",
    "validate_parameter_target_document",
]
