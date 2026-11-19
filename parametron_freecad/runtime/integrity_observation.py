"""Pre-mutation baseline and post-save configured-result integrity evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from parametron_freecad.common.paths import resolve_path
from parametron_freecad.runtime.evidence_sidecar import (
    EvidenceSidecarError,
    EvidenceSidecarWriteError,
    remove_evidence_sidecar,
    write_canonical_json_sidecar_atomically,
)
from parametron_freecad.runtime.resource_inventory import (
    ResourceBinding,
    ResourceInventory,
)

INTEGRITY_EVIDENCE_FILENAME = "prm.integrity-evidence.json"
INTEGRITY_EVIDENCE_SCHEMA_VERSION = "1.0"

INTEGRITY_STATUS_OBSERVED = "observed"
INTEGRITY_STATUS_UNAVAILABLE = "unavailable"
INTEGRITY_STATUS_MISSING = "missing"
INTEGRITY_STATUS_UNSUPPORTED = "unsupported"

_HASH_CHUNK_SIZE = 1024 * 1024


class IntegrityObservationError(ValueError):
    """Raised when required integrity evidence cannot be observed."""


class IntegrityBaselineError(IntegrityObservationError):
    """Raised when a pre-mutation baseline cannot be established."""


class IntegrityResultError(IntegrityObservationError):
    """Raised when the persisted configured result cannot be identified."""


class IntegrityEvidenceError(IntegrityObservationError):
    """Raised when integrity evidence cannot be emitted."""


@dataclass(frozen=True, slots=True)
class PersistedResultIdentity:
    """Post-persistence configured-result identity."""

    coordinate: str
    sha256: str


@dataclass(frozen=True, slots=True)
class IntegrityResourceObservation:
    """Observed baseline state for one declared resource."""

    binding: ResourceBinding
    status: str
    baseline_sha256: str | None = None
    persisted_result: PersistedResultIdentity | None = None


@dataclass(frozen=True, slots=True)
class IntegrityObservation:
    """Observed baseline and configured-result state for one attempt."""

    resources: tuple[IntegrityResourceObservation, ...]

    @property
    def primary(self) -> IntegrityResourceObservation:
        for resource in self.resources:
            if resource.binding.expects_persisted_result:
                return resource
        raise IntegrityObservationError(
            "integrity observation has no persisted-result resource"
        )


def prepare_integrity_observation(
    inventory: ResourceInventory,
    *,
    working_copy: str | Path,
    output_directory: str | Path | None,
) -> IntegrityObservation:
    """Validate the evidence destination and observe all baselines."""
    _prepare_evidence_destination(
        working_copy=working_copy,
        output_directory=output_directory,
    )
    return observe_baseline_integrity(inventory)


def observe_baseline_integrity(
    inventory: ResourceInventory,
) -> IntegrityObservation:
    """Hash every declared resource before any native mutation or open."""
    resources: list[IntegrityResourceObservation] = []

    for binding in inventory.bindings:
        is_primary = binding.expects_persisted_result
        path = binding.resolved_path

        if not path.exists():
            if is_primary:
                raise IntegrityBaselineError(
                    "selected source resource "
                    f"{binding.materialized_coordinate!r} is missing"
                )
            resources.append(
                IntegrityResourceObservation(
                    binding=binding,
                    status=INTEGRITY_STATUS_MISSING,
                )
            )
            continue

        if not path.is_file():
            if is_primary:
                raise IntegrityBaselineError(
                    "selected source resource "
                    f"{binding.materialized_coordinate!r} is not a regular file"
                )
            resources.append(
                IntegrityResourceObservation(
                    binding=binding,
                    status=INTEGRITY_STATUS_UNAVAILABLE,
                )
            )
            continue

        try:
            digest = _sha256_file(path)
        except OSError as exc:
            if is_primary:
                raise IntegrityBaselineError(
                    "selected source resource "
                    f"{binding.materialized_coordinate!r} could not be hashed"
                ) from exc
            resources.append(
                IntegrityResourceObservation(
                    binding=binding,
                    status=INTEGRITY_STATUS_UNAVAILABLE,
                )
            )
            continue

        if digest != binding.baseline_sha256:
            raise IntegrityBaselineError(
                "baseline digest mismatch for resource coordinate "
                f"{binding.materialized_coordinate!r}"
            )

        resources.append(
            IntegrityResourceObservation(
                binding=binding,
                status=INTEGRITY_STATUS_OBSERVED,
                baseline_sha256=digest,
            )
        )

    return IntegrityObservation(resources=tuple(resources))


def observe_persisted_result(
    observation: IntegrityObservation,
    *,
    document: Any,
    opened_path: str | Path,
) -> IntegrityObservation:
    """Hash the post-save bytes of the single configured-result resource."""
    primary = observation.primary
    expected_path = primary.binding.resolved_path
    coordinate = primary.binding.materialized_coordinate

    resolved_opened_path = resolve_path(opened_path)
    if resolved_opened_path != expected_path:
        raise IntegrityResultError(
            "persisted configured result does not match the requested "
            f"coordinate {coordinate!r}"
        )

    document_file_name = getattr(document, "FileName", None)
    if isinstance(document_file_name, (str, Path)) and str(document_file_name):
        candidate = Path(document_file_name).expanduser()
        if not candidate.is_absolute():
            raise IntegrityResultError(
                "saved document path is not absolute for the requested "
                f"coordinate {coordinate!r}"
            )
        if resolve_path(candidate) != expected_path:
            raise IntegrityResultError(
                "saved document path does not match the requested "
                f"coordinate {coordinate!r}"
            )

    if not expected_path.is_file():
        raise IntegrityResultError(
            f"persisted configured result {coordinate!r} is missing"
        )

    try:
        digest = _sha256_file(expected_path)
    except OSError as exc:
        raise IntegrityResultError(
            f"persisted configured result {coordinate!r} could not be hashed"
        ) from exc

    updated = replace(
        primary,
        persisted_result=PersistedResultIdentity(
            coordinate=coordinate,
            sha256=digest,
        ),
    )
    return IntegrityObservation(
        resources=tuple(
            updated if resource is primary else resource
            for resource in observation.resources
        )
    )


def build_integrity_evidence_payload(
    observation: IntegrityObservation,
) -> dict[str, Any]:
    """Build the canonical schema-1.0 integrity evidence payload."""
    resources: list[dict[str, Any]] = []
    for resource in observation.resources:
        persisted_result: dict[str, str] | None = None
        if resource.persisted_result is not None:
            persisted_result = {
                "coordinate": resource.persisted_result.coordinate,
                "sha256": resource.persisted_result.sha256,
            }
        resources.append(
            {
                "logicalId": resource.binding.logical_id,
                "materializedCoordinate": resource.binding.materialized_coordinate,
                "status": resource.status,
                "baselineSha256": resource.baseline_sha256 or "",
                "persistedResult": persisted_result,
            }
        )

    return {
        "schemaVersion": INTEGRITY_EVIDENCE_SCHEMA_VERSION,
        "resources": resources,
    }


def write_integrity_evidence(
    observation: IntegrityObservation,
    *,
    working_copy: str | Path,
    output_directory: str | Path | None,
) -> Path:
    """Write the canonical integrity evidence sidecar for a successful run."""
    primary = observation.primary
    if primary.status != INTEGRITY_STATUS_OBSERVED or primary.persisted_result is None:
        raise IntegrityEvidenceError(
            "integrity evidence is incomplete for the selected source resource"
        )

    payload = build_integrity_evidence_payload(observation)
    try:
        return write_canonical_json_sidecar_atomically(
            working_copy=working_copy,
            output_directory=output_directory,
            filename=INTEGRITY_EVIDENCE_FILENAME,
            payload=payload,
        )
    except (EvidenceSidecarError, EvidenceSidecarWriteError) as exc:
        raise IntegrityEvidenceError("integrity evidence could not be written") from exc


def _prepare_evidence_destination(
    *,
    working_copy: str | Path,
    output_directory: str | Path | None,
) -> None:
    if output_directory is None:
        raise IntegrityEvidenceError(
            "integrity evidence requires an existing output directory"
        )

    try:
        remove_evidence_sidecar(
            working_copy=working_copy,
            output_directory=output_directory,
            filename=INTEGRITY_EVIDENCE_FILENAME,
        )
    except (EvidenceSidecarError, EvidenceSidecarWriteError) as exc:
        raise IntegrityEvidenceError(
            "integrity evidence destination is not usable"
        ) from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(_HASH_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "INTEGRITY_EVIDENCE_FILENAME",
    "INTEGRITY_EVIDENCE_SCHEMA_VERSION",
    "INTEGRITY_STATUS_MISSING",
    "INTEGRITY_STATUS_OBSERVED",
    "INTEGRITY_STATUS_UNAVAILABLE",
    "INTEGRITY_STATUS_UNSUPPORTED",
    "IntegrityBaselineError",
    "IntegrityEvidenceError",
    "IntegrityObservation",
    "IntegrityObservationError",
    "IntegrityResourceObservation",
    "IntegrityResultError",
    "PersistedResultIdentity",
    "build_integrity_evidence_payload",
    "observe_baseline_integrity",
    "observe_persisted_result",
    "prepare_integrity_observation",
    "write_integrity_evidence",
]
