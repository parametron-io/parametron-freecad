"""Native bounded fact evidence for explicitly requested properties."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.common.paths import resolve_path
from parametron_freecad.runtime.evidence_sidecar import (
    EvidenceSidecarError,
    EvidenceSidecarWriteError,
    remove_evidence_sidecar,
    write_canonical_json_sidecar_atomically,
)
from parametron_freecad.runtime.fact_access import (
    FactValueUnavailable,
    FactValueUnsupported,
    NativeFactValue,
    extract_fact_value,
    native_subject_type,
    read_native_property,
)
from parametron_freecad.runtime.fact_request import (
    FACT_REQUIREMENT_REQUIRED,
    FactBinding,
    FactRequest,
)
from parametron_freecad.runtime.occurrence_request import OccurrenceEntity
from parametron_freecad.runtime.resource_inventory import (
    ResourceBinding,
    ResourceInventory,
)

FACT_EVIDENCE_FILENAME = "prm.fact-evidence.json"
FACT_EVIDENCE_SCHEMA_VERSION = "1.0"
FACT_EVIDENCE_KIND = "native_fact_evidence"

FACT_AVAILABILITY_OBSERVED = "observed"
FACT_AVAILABILITY_UNAVAILABLE = "unavailable"
FACT_AVAILABILITY_UNSUPPORTED = "unsupported"


class FactObservationError(ValueError):
    """Raised when fact evidence cannot be observed or emitted."""


class FactEvidenceError(FactObservationError):
    """Raised when fact evidence cannot be written safely."""


class RequiredFactUnavailableError(FactObservationError):
    """Raised when a required binding is not observed."""


@dataclass(frozen=True, slots=True)
class FactSubjectEvidence:
    """Observed subject qualification for one fact binding."""

    entity: OccurrenceEntity
    document: str
    native_type: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "entity": self.entity.to_payload(),
            "document": self.document,
            "nativeType": self.native_type,
        }


@dataclass(frozen=True, slots=True)
class FactEvidenceEntry:
    """One explicitly bound fact observation state."""

    binding: FactBinding
    subject: FactSubjectEvidence
    value_kind: str
    value: int | float | str | bool | None
    unit: str
    availability: str
    diagnostic: str | None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.binding.kind,
            "subject": self.subject.to_payload(),
            "context": [frame.to_payload() for frame in self.binding.context],
            "property": self.binding.property,
            "availability": self.availability,
        }
        if self.availability == FACT_AVAILABILITY_OBSERVED:
            payload["valueKind"] = self.value_kind
            payload["value"] = self.value
            if self.unit:
                payload["unit"] = self.unit
        elif self.diagnostic:
            payload["diagnostic"] = self.diagnostic
        return payload


@dataclass(frozen=True, slots=True)
class FactEvidenceObservation:
    """Complete fact evidence for one request."""

    freecad_version: str
    facts: tuple[FactEvidenceEntry, ...]

    def to_payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": FACT_EVIDENCE_SCHEMA_VERSION,
            "kind": FACT_EVIDENCE_KIND,
            "freecadVersion": self.freecad_version,
            "facts": [fact.to_payload() for fact in self.facts],
        }


class _DocumentPool(AbstractContextManager["_DocumentPool"]):
    """Read-only secondary document access closed before the source closes."""

    def __init__(
        self,
        freecad_module: Any,
        *,
        source_path: str | Path,
        source_document: Any,
    ) -> None:
        self._module = freecad_module
        self._documents: dict[Path, Any] = {
            resolve_path(source_path): source_document,
        }
        self._opened_names: list[str] = []
        self._open_document = getattr(freecad_module, "openDocument", None)
        self._close_document = getattr(freecad_module, "closeDocument", None)
        self._collect_existing_documents()

    def _collect_existing_documents(self) -> None:
        list_documents = getattr(self._module, "listDocuments", None)
        get_document = getattr(self._module, "getDocument", None)
        if not callable(list_documents) or not callable(get_document):
            return
        try:
            names = tuple(list_documents())
        except Exception:
            return
        for name in names:
            try:
                document = get_document(name)
            except Exception:
                continue
            file_name = getattr(document, "FileName", None)
            if isinstance(file_name, (str, Path)) and str(file_name):
                self._documents.setdefault(resolve_path(file_name), document)

    def get(self, binding: ResourceBinding) -> Any | None:
        path = binding.resolved_path
        document = self._documents.get(path)
        if document is not None:
            return document
        if not callable(self._open_document):
            return None
        try:
            document = self._open_document(str(path))
        except Exception:
            return None
        if document is None:
            return None
        opened_path = getattr(document, "FileName", None)
        if (
            isinstance(opened_path, (str, Path))
            and str(opened_path)
            and resolve_path(opened_path) != path
        ):
            return None
        self._documents[path] = document
        name = getattr(document, "Name", None)
        if isinstance(name, str) and name:
            self._opened_names.append(name)
        return document

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        if callable(self._close_document):
            for name in self._opened_names:
                try:
                    self._close_document(name)
                except Exception:
                    pass
        self._opened_names.clear()
        return None


def inspect_fact_evidence(
    source_document: Any,
    request: FactRequest,
    *,
    source_path: str | Path,
    inventory: ResourceInventory | None,
    freecad_module: Any,
    freecad_version: str,
) -> FactEvidenceObservation:
    """Observe every requested binding on the open or declared resources."""
    entries: list[FactEvidenceEntry] = []

    with _DocumentPool(
        freecad_module,
        source_path=source_path,
        source_document=source_document,
    ) as documents:
        for binding in sorted(request.bindings, key=lambda item: item.key()):
            entry = _observe_binding(binding, documents, inventory)
            if (
                binding.requirement == FACT_REQUIREMENT_REQUIRED
                and entry.availability != FACT_AVAILABILITY_OBSERVED
            ):
                raise RequiredFactUnavailableError(
                    f"required fact {binding.property!r} is {entry.availability}"
                )
            entries.append(entry)

    return FactEvidenceObservation(
        freecad_version=freecad_version,
        facts=tuple(entries),
    )


def prepare_fact_evidence(
    *,
    working_copy: str | Path,
    output_directory: str | Path | None,
) -> None:
    """Validate the evidence destination and remove a stale sidecar."""
    if output_directory is None:
        raise FactEvidenceError("fact evidence requires an existing output directory")
    try:
        remove_evidence_sidecar(
            working_copy=working_copy,
            output_directory=output_directory,
            filename=FACT_EVIDENCE_FILENAME,
        )
    except (EvidenceSidecarError, EvidenceSidecarWriteError) as exc:
        raise FactEvidenceError("fact evidence destination is not usable") from exc


def write_fact_evidence(
    observation: FactEvidenceObservation,
    *,
    working_copy: str | Path,
    output_directory: str | Path | None,
) -> Path:
    """Write the canonical fact evidence sidecar for a successful run."""
    if output_directory is None:
        raise FactEvidenceError("fact evidence requires an existing output directory")
    try:
        return write_canonical_json_sidecar_atomically(
            working_copy=working_copy,
            output_directory=output_directory,
            filename=FACT_EVIDENCE_FILENAME,
            payload=observation.to_payload(),
        )
    except (EvidenceSidecarError, EvidenceSidecarWriteError) as exc:
        raise FactEvidenceError("fact evidence could not be written") from exc


def _observe_binding(
    binding: FactBinding,
    documents: _DocumentPool,
    inventory: ResourceInventory | None,
) -> FactEvidenceEntry:
    subject = FactSubjectEvidence(
        entity=binding.subject,
        document="",
        native_type="",
    )

    resource_binding = _binding_for_subject(inventory, binding.subject)
    if resource_binding is None:
        return _unobserved(
            binding,
            subject,
            FACT_AVAILABILITY_UNAVAILABLE,
            _missing_resource_diagnostic(inventory),
        )

    subject = FactSubjectEvidence(
        entity=binding.subject,
        document=resource_binding.materialized_coordinate,
        native_type="",
    )

    if not resource_binding.resolved_path.is_file():
        return _unobserved(
            binding,
            subject,
            FACT_AVAILABILITY_UNAVAILABLE,
            f"declared resource coordinate "
            f"{resource_binding.materialized_coordinate!r} is missing",
        )

    document = documents.get(resource_binding)
    if document is None:
        return _unobserved(
            binding,
            subject,
            FACT_AVAILABILITY_UNAVAILABLE,
            f"declared resource coordinate "
            f"{resource_binding.materialized_coordinate!r} is unavailable",
        )

    native_object = _find_native_object(document, binding.subject.name)
    if native_object is None:
        return _unobserved(
            binding,
            subject,
            FACT_AVAILABILITY_UNAVAILABLE,
            "subject native object is unavailable",
        )

    subject = FactSubjectEvidence(
        entity=binding.subject,
        document=resource_binding.materialized_coordinate,
        native_type=native_subject_type(native_object),
    )

    if binding.context:
        return _unobserved(
            binding,
            subject,
            FACT_AVAILABILITY_UNSUPPORTED,
            "occurrence context is unsupported",
        )

    try:
        native_value = read_native_property(native_object, binding.property)
        value = extract_fact_value(
            native_value,
            binding.value_kind,
            binding.unit,
        )
    except FactValueUnavailable as exc:
        return _unobserved(
            binding,
            subject,
            FACT_AVAILABILITY_UNAVAILABLE,
            str(exc),
        )
    except FactValueUnsupported as exc:
        return _unobserved(
            binding,
            subject,
            FACT_AVAILABILITY_UNSUPPORTED,
            str(exc),
        )

    return _observed(binding, subject, value)


def _observed(
    binding: FactBinding,
    subject: FactSubjectEvidence,
    value: NativeFactValue,
) -> FactEvidenceEntry:
    return FactEvidenceEntry(
        binding=binding,
        subject=subject,
        value_kind=value.value_kind,
        value=value.value,
        unit=value.unit,
        availability=FACT_AVAILABILITY_OBSERVED,
        diagnostic=None,
    )


def _unobserved(
    binding: FactBinding,
    subject: FactSubjectEvidence,
    availability: str,
    diagnostic: str,
) -> FactEvidenceEntry:
    return FactEvidenceEntry(
        binding=binding,
        subject=subject,
        value_kind="",
        value=None,
        unit="",
        availability=availability,
        diagnostic=diagnostic,
    )


def _binding_for_subject(
    inventory: ResourceInventory | None,
    subject: OccurrenceEntity,
) -> ResourceBinding | None:
    if inventory is None:
        return None
    binding = inventory.binding_for_logical_id(subject.resource.logical_id)
    if binding is None or binding.kind != subject.resource.kind:
        return None
    return binding


def _missing_resource_diagnostic(inventory: ResourceInventory | None) -> str:
    if inventory is None:
        return "declared resource inventory is unavailable"
    return "subject resource is not a declared resource"


def _find_native_object(document: Any, name: str) -> Any | None:
    get_object = getattr(document, "getObject", None)
    if not callable(get_object):
        return None
    try:
        return get_object(name)
    except Exception:
        return None


__all__ = [
    "FACT_AVAILABILITY_OBSERVED",
    "FACT_AVAILABILITY_UNAVAILABLE",
    "FACT_AVAILABILITY_UNSUPPORTED",
    "FACT_EVIDENCE_FILENAME",
    "FACT_EVIDENCE_KIND",
    "FACT_EVIDENCE_SCHEMA_VERSION",
    "FactEvidenceEntry",
    "FactEvidenceError",
    "FactEvidenceObservation",
    "FactObservationError",
    "FactSubjectEvidence",
    "RequiredFactUnavailableError",
    "inspect_fact_evidence",
    "prepare_fact_evidence",
    "write_fact_evidence",
]
