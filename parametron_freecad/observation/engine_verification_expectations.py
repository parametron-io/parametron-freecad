"""Compatibility classifier for Engine verification expectation payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from parametron_freecad.observation.engine_verification_compat import (
    ENGINE_METADATA_KEY_WORKING_COPY_SHA256,
    ENGINE_REFERENCE_KIND_WORKING_COPY_PATH,
)
from parametron_freecad.observation.verification_contract import (
    CHECK_FIELD_ENABLED,
    CHECKS_FIELD_COMPONENTS,
    CHECKS_FIELD_METADATA,
    CHECKS_FIELD_PARAMETERS,
    CHECKS_FIELD_REFERENCES,
    CHECKS_FIELDS,
    EXPECTED_FIELD_COMPONENTS,
    EXPECTED_FIELD_METADATA,
    EXPECTED_FIELD_PARAMETERS,
    EXPECTED_FIELD_REFERENCES,
    EXPECTED_FIELDS,
    EXPECTED_METADATA_FIELD_ID,
    EXPECTED_METADATA_FIELD_KEY,
    EXPECTED_METADATA_FIELD_OWNER_ID,
    EXPECTED_PARAMETER_FIELD_ID,
    EXPECTED_REFERENCE_FIELD_KIND,
    EXPECTED_REFERENCE_FIELD_NAME,
    FIELD_CHECKS,
    FIELD_EXPECTED,
    FIELD_OBSERVATION_CONTEXT,
    FIELD_OBSERVE,
    OBSERVATION_CONTEXT_FIELD_PARAMETERS,
    OBSERVATION_PARAMETER_FIELD_GROUP_NAME,
    OBSERVATION_PARAMETER_FIELD_ID,
    OBSERVATION_PARAMETER_FIELD_NAME,
    OBSERVE_FIELD_COMPONENTS,
    OBSERVE_FIELD_METADATA,
    OBSERVE_FIELD_PARAMETERS,
    OBSERVE_FIELD_REFERENCES,
    OBSERVE_FIELDS,
)

CATEGORY_COMPONENTS = "components"
CATEGORY_PARAMETERS = "parameters"
CATEGORY_METADATA = "metadata"
CATEGORY_REFERENCES = "references"

SEVERITY_INVALID = "invalid"
SEVERITY_UNSUPPORTED = "unsupported"

_CATEGORY_ORDER = (
    CATEGORY_COMPONENTS,
    CATEGORY_PARAMETERS,
    CATEGORY_METADATA,
    CATEGORY_REFERENCES,
)

_SUPPORTED_CATEGORY_SET = {
    CATEGORY_PARAMETERS,
    CATEGORY_METADATA,
    CATEGORY_REFERENCES,
}


@dataclass(frozen=True, slots=True)
class EngineVerificationExpectationDiagnostic:
    """A deterministic compatibility diagnostic for a verification expectation."""

    code: str
    path: str
    message: str
    severity: str
    category: str | None = None


@dataclass(frozen=True, slots=True)
class EngineVerificationExpectationCompatibility:
    """Compatibility classification for decoded Engine verification data."""

    compatible: bool
    diagnostics: tuple[EngineVerificationExpectationDiagnostic, ...]
    supported_categories: tuple[str, ...]
    unsupported_categories: tuple[str, ...]


class EngineVerificationExpectationCompatibilityError(ValueError):
    """Raised when Engine verification expectations are not FreeCAD-compatible."""

    def __init__(
        self,
        compatibility: EngineVerificationExpectationCompatibility,
    ) -> None:
        self.compatibility = compatibility
        details = "; ".join(
            f"{diagnostic.path}: {diagnostic.message}"
            for diagnostic in compatibility.diagnostics
        )
        super().__init__(
            "Engine verification expectations are not compatible"
            + (f": {details}" if details else "")
        )


def _diagnostic(
    *,
    code: str,
    path: str,
    message: str,
    severity: str,
    category: str | None = None,
) -> EngineVerificationExpectationDiagnostic:
    return EngineVerificationExpectationDiagnostic(
        code=code,
        path=path,
        message=message,
        severity=severity,
        category=category,
    )


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _is_enabled(checks: Mapping[str, Any] | None, category: str) -> bool:
    if checks is None:
        return False
    check = checks.get(category)
    if not isinstance(check, Mapping):
        return False
    return check.get(CHECK_FIELD_ENABLED) is True


def _sequence_or_none(surface: Mapping[str, Any] | None, category: str) -> Any:
    if surface is None:
        return None
    return surface.get(category)


def _has_non_empty_expected(expected: Mapping[str, Any] | None, category: str) -> bool:
    requests = _sequence_or_none(expected, category)
    return _is_sequence(requests) and len(requests) > 0


def _unknown_keys(mapping: Mapping[str, Any], allowed: tuple[str, ...]) -> tuple[str, ...]:
    allowed_set = set(allowed)
    return tuple(sorted(str(key) for key in mapping if key not in allowed_set))


def _read_parameter_bindings(
    observation_context: Mapping[str, Any] | None,
) -> tuple[Any, ...] | None:
    if observation_context is None:
        return None
    bindings = observation_context.get(OBSERVATION_CONTEXT_FIELD_PARAMETERS)
    if not _is_sequence(bindings):
        return None
    return tuple(bindings)


def _collect_valid_binding_ids(
    bindings: tuple[Any, ...] | None,
) -> tuple[set[str], list[EngineVerificationExpectationDiagnostic]]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    ids: set[str] = set()
    seen_ids: set[str] = set()
    if bindings is None:
        return ids, diagnostics

    for index, binding in enumerate(bindings):
        path = f"$.{FIELD_OBSERVATION_CONTEXT}.{OBSERVATION_CONTEXT_FIELD_PARAMETERS}[{index}]"
        if not isinstance(binding, Mapping):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.binding_invalid",
                    path=path,
                    message="Parameter observation binding must be a mapping.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_PARAMETERS,
                )
            )
            continue

        binding_id = binding.get(OBSERVATION_PARAMETER_FIELD_ID)
        name = binding.get(OBSERVATION_PARAMETER_FIELD_NAME)
        group_name = binding.get(OBSERVATION_PARAMETER_FIELD_GROUP_NAME)
        if not isinstance(binding_id, str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.binding_invalid",
                    path=f"{path}.{OBSERVATION_PARAMETER_FIELD_ID}",
                    message="Parameter observation binding id must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_PARAMETERS,
                )
            )
        elif binding_id in seen_ids:
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.binding_duplicate",
                    path=f"{path}.{OBSERVATION_PARAMETER_FIELD_ID}",
                    message=(
                        "Duplicate parameter observation binding id; parameter "
                        "identity alignment must be explicit and unambiguous."
                    ),
                    severity=SEVERITY_UNSUPPORTED,
                    category=CATEGORY_PARAMETERS,
                )
            )
        else:
            seen_ids.add(binding_id)
            ids.add(binding_id)

        if not isinstance(name, str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.binding_invalid",
                    path=f"{path}.{OBSERVATION_PARAMETER_FIELD_NAME}",
                    message="Parameter observation binding name must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_PARAMETERS,
                )
            )
        if not isinstance(group_name, str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.binding_invalid",
                    path=f"{path}.{OBSERVATION_PARAMETER_FIELD_GROUP_NAME}",
                    message="Parameter observation binding groupName must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_PARAMETERS,
                )
            )

    return ids, diagnostics


def _validate_root_surfaces(
    verification_data: Any,
) -> tuple[
    Mapping[str, Any] | None,
    Mapping[str, Any] | None,
    Mapping[str, Any] | None,
    Mapping[str, Any] | None,
    list[EngineVerificationExpectationDiagnostic],
]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    if not isinstance(verification_data, Mapping):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.root.invalid",
                path="$",
                message="Decoded verification data must be a mapping.",
                severity=SEVERITY_INVALID,
            )
        )
        return None, None, None, None, diagnostics

    observe = verification_data.get(FIELD_OBSERVE)
    expected = verification_data.get(FIELD_EXPECTED)
    checks = verification_data.get(FIELD_CHECKS)
    observation_context = verification_data.get(FIELD_OBSERVATION_CONTEXT)

    if observe is not None and not isinstance(observe, Mapping):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.observe.invalid",
                path=f"$.{FIELD_OBSERVE}",
                message="observe must be a mapping when present.",
                severity=SEVERITY_INVALID,
            )
        )
        observe = None
    if expected is not None and not isinstance(expected, Mapping):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.expected.invalid",
                path=f"$.{FIELD_EXPECTED}",
                message="expected must be a mapping when present.",
                severity=SEVERITY_INVALID,
            )
        )
        expected = None
    if checks is not None and not isinstance(checks, Mapping):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.checks.invalid",
                path=f"$.{FIELD_CHECKS}",
                message="checks must be a mapping when present.",
                severity=SEVERITY_INVALID,
            )
        )
        checks = None
    if observation_context is not None and not isinstance(
        observation_context, Mapping
    ):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.observation_context.invalid",
                path=f"$.{FIELD_OBSERVATION_CONTEXT}",
                message="observationContext must be a mapping when present.",
                severity=SEVERITY_INVALID,
            )
        )
        observation_context = None

    return observe, expected, checks, observation_context, diagnostics


def _validate_observe_surface(
    observe: Mapping[str, Any] | None,
) -> tuple[set[str], list[EngineVerificationExpectationDiagnostic]]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    requested: set[str] = set()
    if observe is None:
        return requested, diagnostics

    for category in _CATEGORY_ORDER:
        value = observe.get(category)
        if value is True:
            requested.add(category)
        if category == CATEGORY_COMPONENTS and value is True:
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.components.unsupported",
                    path=f"$.{FIELD_OBSERVE}.{OBSERVE_FIELD_COMPONENTS}",
                    message="Component observation remains planned and unsupported.",
                    severity=SEVERITY_UNSUPPORTED,
                    category=CATEGORY_COMPONENTS,
                )
            )

    for key in _unknown_keys(observe, OBSERVE_FIELDS):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.observe.unknown_category",
                path=f"$.{FIELD_OBSERVE}.{key}",
                message=(
                    "Unknown observe category is outside the implemented "
                    "FreeCAD observation compatibility contract."
                ),
                severity=SEVERITY_UNSUPPORTED,
                category=key,
            )
        )

    return requested, diagnostics


def _validate_checks_surface(
    checks: Mapping[str, Any] | None,
) -> tuple[set[str], list[EngineVerificationExpectationDiagnostic]]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    enabled: set[str] = set()
    if checks is None:
        return enabled, diagnostics

    for category in _CATEGORY_ORDER:
        check = checks.get(category)
        if check is None:
            continue
        path = f"$.{FIELD_CHECKS}.{category}"
        if not isinstance(check, Mapping):
            diagnostics.append(
                _diagnostic(
                    code=f"engine_verification.{category}.check_invalid",
                    path=path,
                    message="Category check request must be a mapping.",
                    severity=SEVERITY_INVALID,
                    category=category,
                )
            )
            continue
        enabled_value = check.get(CHECK_FIELD_ENABLED)
        if enabled_value is not None and not isinstance(enabled_value, bool):
            diagnostics.append(
                _diagnostic(
                    code=f"engine_verification.{category}.check_invalid",
                    path=f"{path}.{CHECK_FIELD_ENABLED}",
                    message="Category check enabled flag must be a boolean.",
                    severity=SEVERITY_INVALID,
                    category=category,
                )
            )
            continue
        if enabled_value is True:
            enabled.add(category)
            if category == CATEGORY_COMPONENTS:
                diagnostics.append(
                    _diagnostic(
                        code="engine_verification.components.unsupported",
                        path=f"{path}.{CHECK_FIELD_ENABLED}",
                        message=(
                            "Component verification remains planned and unsupported."
                        ),
                        severity=SEVERITY_UNSUPPORTED,
                        category=CATEGORY_COMPONENTS,
                    )
                )

    for key in _unknown_keys(checks, CHECKS_FIELDS):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.checks.unknown_category",
                path=f"$.{FIELD_CHECKS}.{key}",
                message=(
                    "Unknown checks category is outside the implemented "
                    "FreeCAD observation compatibility contract."
                ),
                severity=SEVERITY_UNSUPPORTED,
                category=key,
            )
        )

    return enabled, diagnostics


def _validate_expected_components(
    expected: Mapping[str, Any] | None,
) -> list[EngineVerificationExpectationDiagnostic]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    components = _sequence_or_none(expected, EXPECTED_FIELD_COMPONENTS)
    if components is None:
        return diagnostics
    path = f"$.{FIELD_EXPECTED}.{EXPECTED_FIELD_COMPONENTS}"
    if not _is_sequence(components):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.components.request_invalid",
                path=path,
                message="expected.components must be a list when present.",
                severity=SEVERITY_INVALID,
                category=CATEGORY_COMPONENTS,
            )
        )
        return diagnostics
    if len(components) > 0:
        diagnostics.append(
            _diagnostic(
                code="engine_verification.components.unsupported",
                path=path,
                message="Component expectations remain planned and unsupported.",
                severity=SEVERITY_UNSUPPORTED,
                category=CATEGORY_COMPONENTS,
            )
        )
    return diagnostics


def _validate_expected_parameters(
    expected: Mapping[str, Any] | None,
    *,
    requested_categories: set[str],
    check_categories: set[str],
    binding_ids: set[str],
) -> list[EngineVerificationExpectationDiagnostic]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    parameters = _sequence_or_none(expected, EXPECTED_FIELD_PARAMETERS)
    if parameters is None:
        return diagnostics
    path = f"$.{FIELD_EXPECTED}.{EXPECTED_FIELD_PARAMETERS}"
    if not _is_sequence(parameters):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.parameters.request_invalid",
                path=path,
                message="expected.parameters must be a list when present.",
                severity=SEVERITY_INVALID,
                category=CATEGORY_PARAMETERS,
            )
        )
        return diagnostics

    must_align = (
        len(parameters) > 0
        or CATEGORY_PARAMETERS in requested_categories
        or CATEGORY_PARAMETERS in check_categories
    )
    if not must_align:
        return diagnostics

    for index, request in enumerate(parameters):
        item_path = f"{path}[{index}]"
        if not isinstance(request, Mapping):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.request_invalid",
                    path=item_path,
                    message="Parameter expectation entry must be a mapping.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_PARAMETERS,
                )
            )
            continue
        parameter_id = request.get(EXPECTED_PARAMETER_FIELD_ID)
        if not isinstance(parameter_id, str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.identity_unmapped",
                    path=f"{item_path}.{EXPECTED_PARAMETER_FIELD_ID}",
                    message=(
                        "Parameter expectation id must be a string matching an "
                        "explicit observationContext.parameters binding; FreeCAD "
                        "must not infer parameter identity from Engine names."
                    ),
                    severity=SEVERITY_UNSUPPORTED,
                    category=CATEGORY_PARAMETERS,
                )
            )
        elif parameter_id not in binding_ids:
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.identity_unmapped",
                    path=f"{item_path}.{EXPECTED_PARAMETER_FIELD_ID}",
                    message=(
                        "Parameter expectation id has no matching explicit "
                        "observationContext.parameters binding; FreeCAD must not "
                        "infer parameter identity from Engine names or manifests."
                    ),
                    severity=SEVERITY_UNSUPPORTED,
                    category=CATEGORY_PARAMETERS,
                )
            )

    return diagnostics


def _validate_expected_metadata(
    expected: Mapping[str, Any] | None,
) -> list[EngineVerificationExpectationDiagnostic]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    metadata = _sequence_or_none(expected, EXPECTED_FIELD_METADATA)
    if metadata is None:
        return diagnostics
    path = f"$.{FIELD_EXPECTED}.{EXPECTED_FIELD_METADATA}"
    if not _is_sequence(metadata):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.metadata.request_invalid",
                path=path,
                message="expected.metadata must be a list when present.",
                severity=SEVERITY_INVALID,
                category=CATEGORY_METADATA,
            )
        )
        return diagnostics

    for index, request in enumerate(metadata):
        item_path = f"{path}[{index}]"
        if not isinstance(request, Mapping):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.metadata.request_invalid",
                    path=item_path,
                    message="Metadata expectation entry must be a mapping.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_METADATA,
                )
            )
            continue

        key = request.get(EXPECTED_METADATA_FIELD_KEY)
        has_id = EXPECTED_METADATA_FIELD_ID in request
        has_owner_id = EXPECTED_METADATA_FIELD_OWNER_ID in request
        if (
            key == ENGINE_METADATA_KEY_WORKING_COPY_SHA256
            and not has_id
            and not has_owner_id
        ):
            continue
        if not isinstance(request.get(EXPECTED_METADATA_FIELD_ID), str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.metadata.request_invalid",
                    path=f"{item_path}.{EXPECTED_METADATA_FIELD_ID}",
                    message="Document-backed metadata id must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_METADATA,
                )
            )
        if not isinstance(key, str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.metadata.request_invalid",
                    path=f"{item_path}.{EXPECTED_METADATA_FIELD_KEY}",
                    message="Metadata key must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_METADATA,
                )
            )
        if not isinstance(request.get(EXPECTED_METADATA_FIELD_OWNER_ID), str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.metadata.request_invalid",
                    path=f"{item_path}.{EXPECTED_METADATA_FIELD_OWNER_ID}",
                    message="Document-backed metadata ownerId must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_METADATA,
                )
            )

    return diagnostics


def _validate_expected_references(
    expected: Mapping[str, Any] | None,
) -> list[EngineVerificationExpectationDiagnostic]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    references = _sequence_or_none(expected, EXPECTED_FIELD_REFERENCES)
    if references is None:
        return diagnostics
    path = f"$.{FIELD_EXPECTED}.{EXPECTED_FIELD_REFERENCES}"
    if not _is_sequence(references):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.references.request_invalid",
                path=path,
                message="expected.references must be a list when present.",
                severity=SEVERITY_INVALID,
                category=CATEGORY_REFERENCES,
            )
        )
        return diagnostics

    for index, request in enumerate(references):
        item_path = f"{path}[{index}]"
        if not isinstance(request, Mapping):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.references.request_invalid",
                    path=item_path,
                    message="Reference expectation entry must be a mapping.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_REFERENCES,
                )
            )
            continue
        kind = request.get(EXPECTED_REFERENCE_FIELD_KIND)
        if kind == ENGINE_REFERENCE_KIND_WORKING_COPY_PATH:
            continue
        if not isinstance(kind, str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.references.request_invalid",
                    path=f"{item_path}.{EXPECTED_REFERENCE_FIELD_KIND}",
                    message="Reference kind must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_REFERENCES,
                )
            )
        if not isinstance(request.get(EXPECTED_REFERENCE_FIELD_NAME), str):
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.references.request_invalid",
                    path=f"{item_path}.{EXPECTED_REFERENCE_FIELD_NAME}",
                    message="Document-backed reference name must be a string.",
                    severity=SEVERITY_INVALID,
                    category=CATEGORY_REFERENCES,
                )
            )

    return diagnostics


def _validate_observation_context(
    observation_context: Mapping[str, Any] | None,
    *,
    parameter_observation_expected: bool,
) -> tuple[
    set[str],
    list[EngineVerificationExpectationDiagnostic],
]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    bindings = _read_parameter_bindings(observation_context)
    binding_ids, binding_diagnostics = _collect_valid_binding_ids(bindings)

    if parameter_observation_expected:
        if observation_context is None:
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.context_missing",
                    path=f"$.{FIELD_OBSERVATION_CONTEXT}",
                    message=(
                        "Parameter expectations require explicit "
                        "observationContext.parameters bindings; FreeCAD must "
                        "not infer parameter identity from Engine names or "
                        "execution manifests."
                    ),
                    severity=SEVERITY_UNSUPPORTED,
                    category=CATEGORY_PARAMETERS,
                )
            )
        elif bindings is None:
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.context_missing",
                    path=(
                        f"$.{FIELD_OBSERVATION_CONTEXT}."
                        f"{OBSERVATION_CONTEXT_FIELD_PARAMETERS}"
                    ),
                    message=(
                        "Parameter expectations require "
                        "observationContext.parameters to be a list of explicit "
                        "bindings."
                    ),
                    severity=SEVERITY_UNSUPPORTED,
                    category=CATEGORY_PARAMETERS,
                )
            )
        elif len(bindings) == 0:
            diagnostics.append(
                _diagnostic(
                    code="engine_verification.parameters.context_missing",
                    path=(
                        f"$.{FIELD_OBSERVATION_CONTEXT}."
                        f"{OBSERVATION_CONTEXT_FIELD_PARAMETERS}"
                    ),
                    message=(
                        "Parameter expectations require at least one explicit "
                        "observationContext.parameters binding."
                    ),
                    severity=SEVERITY_UNSUPPORTED,
                    category=CATEGORY_PARAMETERS,
                )
            )

    diagnostics.extend(binding_diagnostics)
    return binding_ids, diagnostics


def _validate_expected_unknown_categories(
    expected: Mapping[str, Any] | None,
) -> list[EngineVerificationExpectationDiagnostic]:
    diagnostics: list[EngineVerificationExpectationDiagnostic] = []
    if expected is None:
        return diagnostics
    for key in _unknown_keys(expected, EXPECTED_FIELDS):
        diagnostics.append(
            _diagnostic(
                code="engine_verification.expected.unknown_category",
                path=f"$.{FIELD_EXPECTED}.{key}",
                message=(
                    "Unknown expected category is outside the implemented "
                    "FreeCAD observation compatibility contract."
                ),
                severity=SEVERITY_UNSUPPORTED,
                category=key,
            )
        )
    return diagnostics


def _supported_categories(
    requested_categories: set[str],
    check_categories: set[str],
    expected: Mapping[str, Any] | None,
    unsupported_categories: set[str],
) -> tuple[str, ...]:
    candidates = set(requested_categories) | set(check_categories)
    for category in _CATEGORY_ORDER:
        if _has_non_empty_expected(expected, category):
            candidates.add(category)
    return tuple(
        category
        for category in _CATEGORY_ORDER
        if category in candidates
        and category in _SUPPORTED_CATEGORY_SET
        and category not in unsupported_categories
    )


def validate_engine_verification_expectations(
    verification_data: Mapping[str, Any],
) -> EngineVerificationExpectationCompatibility:
    """Classify decoded Engine verification expectations for FreeCAD support.

    This validator inspects already-decoded data only. It does not import
    FreeCAD, load files, touch a document, evaluate checks, compare expected
    values, or make verification decisions.
    """

    (
        observe,
        expected,
        checks,
        observation_context,
        diagnostics,
    ) = _validate_root_surfaces(verification_data)

    if observe is None and expected is None and checks is None:
        unsupported_categories = tuple(
            diagnostic.category
            for diagnostic in diagnostics
            if diagnostic.category is not None
        )
        return EngineVerificationExpectationCompatibility(
            compatible=not diagnostics,
            diagnostics=tuple(diagnostics),
            supported_categories=(),
            unsupported_categories=unsupported_categories,
        )

    requested_categories, observe_diagnostics = _validate_observe_surface(observe)
    diagnostics.extend(observe_diagnostics)

    check_categories, checks_diagnostics = _validate_checks_surface(checks)
    diagnostics.extend(checks_diagnostics)

    diagnostics.extend(_validate_expected_components(expected))

    parameter_observation_expected = (
        CATEGORY_PARAMETERS in requested_categories
        or CATEGORY_PARAMETERS in check_categories
        or _has_non_empty_expected(expected, EXPECTED_FIELD_PARAMETERS)
    )
    binding_ids, observation_context_diagnostics = _validate_observation_context(
        observation_context,
        parameter_observation_expected=parameter_observation_expected,
    )

    diagnostics.extend(
        _validate_expected_parameters(
            expected,
            requested_categories=requested_categories,
            check_categories=check_categories,
            binding_ids=binding_ids,
        )
    )
    diagnostics.extend(_validate_expected_metadata(expected))
    diagnostics.extend(_validate_expected_references(expected))
    diagnostics.extend(_validate_expected_unknown_categories(expected))
    diagnostics.extend(observation_context_diagnostics)

    unsupported_categories = tuple(
        category
        for category in _CATEGORY_ORDER
        if any(diagnostic.category == category for diagnostic in diagnostics)
    )
    unknown_unsupported_categories = tuple(
        sorted(
            {
                str(diagnostic.category)
                for diagnostic in diagnostics
                if diagnostic.category is not None
                and diagnostic.category not in _CATEGORY_ORDER
            }
        )
    )
    unsupported_categories = unsupported_categories + unknown_unsupported_categories

    return EngineVerificationExpectationCompatibility(
        compatible=not diagnostics,
        diagnostics=tuple(diagnostics),
        supported_categories=_supported_categories(
            requested_categories,
            check_categories,
            expected,
            set(unsupported_categories),
        ),
        unsupported_categories=unsupported_categories,
    )


def require_engine_verification_expectations_compatible(
    verification_data: Mapping[str, Any],
) -> None:
    """Raise if decoded Engine verification expectations are unsupported."""

    compatibility = validate_engine_verification_expectations(verification_data)
    if not compatibility.compatible:
        raise EngineVerificationExpectationCompatibilityError(compatibility)


__all__ = [
    "EngineVerificationExpectationCompatibility",
    "EngineVerificationExpectationCompatibilityError",
    "EngineVerificationExpectationDiagnostic",
    "SEVERITY_INVALID",
    "SEVERITY_UNSUPPORTED",
    "validate_engine_verification_expectations",
    "require_engine_verification_expectations_compatible",
]
