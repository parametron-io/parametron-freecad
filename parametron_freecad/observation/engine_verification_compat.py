"""Compatibility boundary for minimal Engine-generated verification contracts."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from parametron_freecad.observation.observation_ordering import (
    order_observation_payload,
)
from parametron_freecad.observation.observed_contract import (
    OBSERVATION_FIELD_METADATA,
    OBSERVATION_FIELD_REFERENCES,
    OBSERVED_METADATA_FIELD_ID,
    OBSERVED_METADATA_FIELD_KEY,
    OBSERVED_METADATA_FIELD_OWNER_ID,
    OBSERVED_METADATA_FIELD_VALUE,
    OBSERVED_METADATA_FIELD_VALUE_KIND,
    OBSERVED_METADATA_VALUE_KIND_STRING,
    OBSERVED_REFERENCE_FIELD_KIND,
    OBSERVED_REFERENCE_FIELD_NAME,
)
from parametron_freecad.observation.requested_scope_observation import (
    observe_requested_contract_scope,
)
from parametron_freecad.observation.verification_contract import (
    EXPECTED_FIELD_METADATA,
    EXPECTED_FIELD_REFERENCES,
    EXPECTED_METADATA_FIELD_ID,
    EXPECTED_METADATA_FIELD_KEY,
    EXPECTED_METADATA_FIELD_OWNER_ID,
    EXPECTED_REFERENCE_FIELD_KIND,
    FIELD_EXPECTED,
    FIELD_OBSERVE,
    OBSERVE_FIELD_METADATA,
    OBSERVE_FIELD_REFERENCES,
)

ENGINE_METADATA_KEY_WORKING_COPY_SHA256 = "working_copy_sha256"
ENGINE_METADATA_OWNER_WORKING_COPY = "workingCopy"
ENGINE_REFERENCE_KIND_WORKING_COPY_PATH = "working_copy_path"


class EngineVerificationCompatibilityError(ValueError):
    """Raised when Engine runtime-context observation cannot be composed."""


def _read_observe(
    verification_data: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    observe = verification_data.get(FIELD_OBSERVE)
    if not isinstance(observe, Mapping):
        return None
    return observe


def _read_expected_sequence(
    verification_data: Mapping[str, Any],
    field: str,
) -> tuple[Any, ...] | None:
    expected = verification_data.get(FIELD_EXPECTED)
    if not isinstance(expected, Mapping):
        return None

    requests = expected.get(field)
    if not isinstance(requests, (list, tuple)):
        return None
    return tuple(requests)


def _is_engine_working_copy_sha256_metadata_request(request: Any) -> bool:
    if not isinstance(request, Mapping):
        return False
    if (
        request.get(EXPECTED_METADATA_FIELD_KEY)
        != ENGINE_METADATA_KEY_WORKING_COPY_SHA256
    ):
        return False

    # Internal document-backed metadata requests own id/ownerId and must remain
    # routed through the existing FreeCAD object observer.
    return (
        EXPECTED_METADATA_FIELD_ID not in request
        and EXPECTED_METADATA_FIELD_OWNER_ID not in request
    )


def _is_engine_working_copy_path_reference_request(request: Any) -> bool:
    return (
        isinstance(request, Mapping)
        and request.get(EXPECTED_REFERENCE_FIELD_KIND)
        == ENGINE_REFERENCE_KIND_WORKING_COPY_PATH
    )


def _coerce_working_copy_path(
    working_copy_path: str | os.PathLike[str],
) -> str:
    try:
        path = os.fspath(working_copy_path)
    except TypeError as exc:
        raise EngineVerificationCompatibilityError(
            "working copy path must be a string or path-like value"
        ) from exc

    if not isinstance(path, str) or not path:
        raise EngineVerificationCompatibilityError(
            "working copy path must be a non-empty string"
        )
    return path


def _coerce_working_copy_sha256(working_copy_sha256: str) -> str:
    if not isinstance(working_copy_sha256, str) or not working_copy_sha256:
        raise EngineVerificationCompatibilityError(
            "working copy sha256 must be a non-empty string"
        )
    return working_copy_sha256


def _observed_working_copy_sha256_metadata(
    working_copy_sha256: str,
) -> dict[str, Any]:
    return {
        OBSERVED_METADATA_FIELD_ID: ENGINE_METADATA_KEY_WORKING_COPY_SHA256,
        OBSERVED_METADATA_FIELD_KEY: ENGINE_METADATA_KEY_WORKING_COPY_SHA256,
        OBSERVED_METADATA_FIELD_OWNER_ID: ENGINE_METADATA_OWNER_WORKING_COPY,
        OBSERVED_METADATA_FIELD_VALUE: _coerce_working_copy_sha256(
            working_copy_sha256
        ),
        OBSERVED_METADATA_FIELD_VALUE_KIND: OBSERVED_METADATA_VALUE_KIND_STRING,
    }


def _observed_working_copy_path_reference(
    working_copy_path: str | os.PathLike[str],
) -> dict[str, Any]:
    return {
        OBSERVED_REFERENCE_FIELD_KIND: ENGINE_REFERENCE_KIND_WORKING_COPY_PATH,
        OBSERVED_REFERENCE_FIELD_NAME: _coerce_working_copy_path(working_copy_path),
    }


def _without_engine_runtime_context_requests(
    verification_data: Mapping[str, Any],
    *,
    metadata_requests: tuple[Any, ...] | None,
    reference_requests: tuple[Any, ...] | None,
    has_runtime_metadata: bool,
    has_runtime_references: bool,
) -> dict[str, Any]:
    filtered_verification_data = dict(verification_data)
    expected = verification_data.get(FIELD_EXPECTED)
    if not isinstance(expected, Mapping):
        return filtered_verification_data

    filtered_expected = dict(expected)
    if has_runtime_metadata and metadata_requests is not None:
        filtered_expected[EXPECTED_FIELD_METADATA] = [
            request
            for request in metadata_requests
            if not _is_engine_working_copy_sha256_metadata_request(request)
        ]
    if has_runtime_references and reference_requests is not None:
        filtered_expected[EXPECTED_FIELD_REFERENCES] = [
            request
            for request in reference_requests
            if not _is_engine_working_copy_path_reference_request(request)
        ]

    filtered_verification_data[FIELD_EXPECTED] = filtered_expected
    return filtered_verification_data


def _merge_metadata_observations(
    base_observation: Mapping[str, Any],
    metadata_requests: tuple[Any, ...],
    *,
    working_copy_sha256: str,
) -> tuple[dict[str, Any], ...]:
    document_metadata = iter(base_observation.get(OBSERVATION_FIELD_METADATA, ()))
    merged: list[dict[str, Any]] = []

    for request in metadata_requests:
        if _is_engine_working_copy_sha256_metadata_request(request):
            merged.append(
                _observed_working_copy_sha256_metadata(working_copy_sha256)
            )
            continue
        try:
            merged.append(next(document_metadata))
        except StopIteration as exc:
            raise EngineVerificationCompatibilityError(
                "metadata observation count mismatch while composing Engine "
                "runtime-context observations"
            ) from exc

    return tuple(merged)


def _merge_reference_observations(
    base_observation: Mapping[str, Any],
    reference_requests: tuple[Any, ...],
    *,
    working_copy_path: str | os.PathLike[str],
) -> tuple[dict[str, Any], ...]:
    document_references = iter(base_observation.get(OBSERVATION_FIELD_REFERENCES, ()))
    merged: list[dict[str, Any]] = []

    for request in reference_requests:
        if _is_engine_working_copy_path_reference_request(request):
            merged.append(_observed_working_copy_path_reference(working_copy_path))
            continue
        try:
            merged.append(next(document_references))
        except StopIteration as exc:
            raise EngineVerificationCompatibilityError(
                "reference observation count mismatch while composing Engine "
                "runtime-context observations"
            ) from exc

    return tuple(merged)


def observe_engine_compatible_requested_scope(
    document: Any,
    verification_data: Mapping[str, Any],
    *,
    working_copy_path: str | os.PathLike[str],
    working_copy_sha256: str,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Observe requested scope plus minimal Engine runtime-context entries.

    Only the known Engine runtime-context requests are intercepted:
    ``working_copy_sha256`` metadata and ``working_copy_path`` references.
    All document-backed requests continue through the existing observers.
    """
    if not isinstance(verification_data, Mapping):
        return observe_requested_contract_scope(document, verification_data)

    observe = _read_observe(verification_data)
    if observe is None:
        return observe_requested_contract_scope(document, verification_data)

    metadata_requests = (
        _read_expected_sequence(verification_data, EXPECTED_FIELD_METADATA)
        if observe.get(OBSERVE_FIELD_METADATA)
        else None
    )
    reference_requests = (
        _read_expected_sequence(verification_data, EXPECTED_FIELD_REFERENCES)
        if observe.get(OBSERVE_FIELD_REFERENCES)
        else None
    )

    has_runtime_metadata = bool(
        metadata_requests
        and any(
            _is_engine_working_copy_sha256_metadata_request(request)
            for request in metadata_requests
        )
    )
    has_runtime_references = bool(
        reference_requests
        and any(
            _is_engine_working_copy_path_reference_request(request)
            for request in reference_requests
        )
    )

    if not has_runtime_metadata and not has_runtime_references:
        return observe_requested_contract_scope(document, verification_data)

    filtered_verification_data = _without_engine_runtime_context_requests(
        verification_data,
        metadata_requests=metadata_requests,
        reference_requests=reference_requests,
        has_runtime_metadata=has_runtime_metadata,
        has_runtime_references=has_runtime_references,
    )
    base_observation = observe_requested_contract_scope(
        document,
        filtered_verification_data,
    )

    observation = dict(base_observation)
    if has_runtime_metadata:
        assert metadata_requests is not None
        observation[OBSERVATION_FIELD_METADATA] = _merge_metadata_observations(
            base_observation,
            metadata_requests,
            working_copy_sha256=working_copy_sha256,
        )
    if has_runtime_references:
        assert reference_requests is not None
        observation[OBSERVATION_FIELD_REFERENCES] = _merge_reference_observations(
            base_observation,
            reference_requests,
            working_copy_path=working_copy_path,
        )

    return order_observation_payload(observation)


__all__ = [
    "ENGINE_METADATA_KEY_WORKING_COPY_SHA256",
    "ENGINE_REFERENCE_KIND_WORKING_COPY_PATH",
    "EngineVerificationCompatibilityError",
    "observe_engine_compatible_requested_scope",
]
