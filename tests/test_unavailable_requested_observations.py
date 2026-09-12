"""Controlled-failure tests for unavailable requested observations.

These tests prove that *unavailable* requested observations fail
deterministically and safely. An unavailable requested observation is one where
the verification request is structurally valid and explicitly requests a
supported observation category, but the requested CAD-side state is unavailable,
inaccessible, or unsupported at observation time.

Everything here runs under ordinary Python with fake document objects. No real
FreeCAD is required. The tests deliberately never:

* observe components,
* make verification decisions,
* perform Label lookup,
* traverse ``document.Objects``.

Fake documents expose ``Objects`` and ``Label`` as properties that raise if
touched, so any accidental discovery traversal or Label lookup fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from parametron_freecad.observation.metadata_observation import (
    MetadataObservationDocumentError,
    MetadataObservationError,
    MetadataObservationOwnerNotFoundError,
    MetadataObservationPropertyError,
    MetadataObservationValueError,
    observe_requested_metadata,
)
from parametron_freecad.observation.observed_output import (
    ObservedOutputError,
    generate_observed_output,
)
from parametron_freecad.observation.parameter_observation import (
    ParameterObservationDocumentError,
    ParameterObservationError,
    ParameterObservationObjectNotFoundError,
    ParameterObservationPropertyError,
    ParameterObservationValueError,
    observe_requested_parameters,
)
from parametron_freecad.observation.reference_observation import (
    ReferenceObservationDocumentError,
    ReferenceObservationError,
    ReferenceObservationReferenceNotFoundError,
    observe_requested_references,
)
from parametron_freecad.observation.requested_scope_observation import (
    observe_requested_contract_scope,
)


OBSERVED_FILENAME = "parametron.observed.json"
_WORKING_COPY_PATH = "/work/model.FCStd"
_WORKING_COPY_SHA256 = "a" * 64

# Representative unsupported observed values shared across categories.
UNSUPPORTED_VALUES = (
    None,
    [1, 2, 3],
    {"k": "v"},
    (1, 2),
    object(),
)

NON_FINITE_FLOATS = (
    float("nan"),
    float("inf"),
    float("-inf"),
)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeObject:
    """Minimal fake document object exposing arbitrary properties."""

    def __init__(self, **properties):
        for name, value in properties.items():
            setattr(self, name, value)


class RaisingPropertyObject:
    """Object whose every requested property getter raises."""

    def __getattr__(self, name):
        raise RuntimeError(f"cannot read {name}")


class HostileObject:
    """Object that proves existence but raises on any property access.

    Used to prove reference observation uses the resolved object only to prove
    existence and never validates or infers ``kind`` from it.
    """

    def __getattr__(self, name):
        raise AssertionError(f"reference observation must not read {name!r}")


class FakeDocument:
    """Fake FreeCAD document exposing only ``getObject``.

    ``Objects`` and ``Label`` raise if accessed, proving no discovery traversal
    or Label lookup occurs. ``calls`` records every requested name so ordering
    and stop-before-later-category behavior can be asserted.
    """

    def __init__(self, objects=None, exc=None):
        self._objects = dict(objects or {})
        self._exc = exc
        self.calls = []

    @property
    def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document.Objects must not be accessed")

    @property
    def Label(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document Label lookup must not be used")

    def getObject(self, name):  # noqa: N802 - mimic FreeCAD method name
        self.calls.append(name)
        if self._exc is not None:
            raise self._exc
        return self._objects.get(name)


class DocumentWithoutGetObject:
    """Document missing ``getObject`` entirely.

    ``Objects`` raises so we also prove no fallback traversal is attempted.
    """

    @property
    def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document.Objects must not be accessed")


class DocumentWithNonCallableGetObject:
    """Document whose ``getObject`` attribute is not callable."""

    getObject = "not callable"

    @property
    def Objects(self):  # noqa: N802 - mimic FreeCAD attribute name
        raise AssertionError("document.Objects must not be accessed")


# ---------------------------------------------------------------------------
# Verification-data builders
# ---------------------------------------------------------------------------


def _parameter_binding(param_id="p.length", name="Length", group_name="Spreadsheet"):
    return {"id": param_id, "name": name, "groupName": group_name}


def _parameter_verification(bindings):
    return {
        "observe": {"parameters": True},
        "observationContext": {"parameters": list(bindings)},
    }


def _metadata_request(metadata_id="m.author", key="Author", owner_id="Doc"):
    return {"id": metadata_id, "key": key, "ownerId": owner_id}


def _metadata_verification(requests):
    return {
        "observe": {"metadata": True},
        "expected": {"metadata": list(requests)},
    }


def _reference_request(kind="part", name="Body"):
    return {"kind": kind, "name": name}


def _reference_verification(requests):
    return {
        "observe": {"references": True},
        "expected": {"references": list(requests)},
    }


def _no_write_guard(monkeypatch):
    """Patch ``open`` so any file write attempt fails loudly."""

    def _forbidden(*args, **kwargs):
        raise AssertionError("observation helpers must not write files")

    monkeypatch.setattr("builtins.open", _forbidden)


# ===========================================================================
# 1. Parameter unavailable observations
# ===========================================================================


class TestParameterUnavailableObservations:
    def test_missing_get_object_raises_document_error(self):
        with pytest.raises(ParameterObservationDocumentError):
            observe_requested_parameters(
                DocumentWithoutGetObject(),
                _parameter_verification([_parameter_binding()]),
            )

    def test_non_callable_get_object_raises_document_error(self):
        with pytest.raises(ParameterObservationDocumentError):
            observe_requested_parameters(
                DocumentWithNonCallableGetObject(),
                _parameter_verification([_parameter_binding()]),
            )

    def test_raising_get_object_raises_document_error(self):
        document = FakeDocument(exc=RuntimeError("boom"))
        with pytest.raises(ParameterObservationDocumentError) as excinfo:
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding()]),
            )
        assert isinstance(excinfo.value.__cause__, RuntimeError)
        assert document.calls == ["Spreadsheet"]

    def test_get_object_none_raises_object_not_found_error(self):
        document = FakeDocument({})
        with pytest.raises(ParameterObservationObjectNotFoundError):
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding()]),
            )
        assert document.calls == ["Spreadsheet"]

    def test_missing_property_raises_property_error(self):
        document = FakeDocument({"Spreadsheet": FakeObject(Other=1)})
        with pytest.raises(ParameterObservationPropertyError):
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding(name="Length")]),
            )

    def test_property_getter_raising_raises_property_error(self):
        document = FakeDocument({"Spreadsheet": RaisingPropertyObject()})
        with pytest.raises(ParameterObservationPropertyError) as excinfo:
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding(name="Length")]),
            )
        assert isinstance(excinfo.value.__cause__, RuntimeError)

    @pytest.mark.parametrize("value", UNSUPPORTED_VALUES)
    def test_unsupported_values_raise_value_error(self, value):
        document = FakeDocument({"Spreadsheet": FakeObject(Length=value)})
        with pytest.raises(ParameterObservationValueError):
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding(name="Length")]),
            )

    @pytest.mark.parametrize("value", NON_FINITE_FLOATS)
    def test_non_finite_floats_raise_value_error(self, value):
        document = FakeDocument({"Spreadsheet": FakeObject(Length=value)})
        with pytest.raises(ParameterObservationValueError):
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding(name="Length")]),
            )

    def test_typed_errors_are_parameter_observation_errors(self):
        document = FakeDocument({})
        with pytest.raises(ParameterObservationError):
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding()]),
            )

    def test_failure_does_not_use_label_or_objects(self):
        # FakeDocument.Objects and .Label raise if touched. The miss below
        # must not trigger any fallback that reads them.
        document = FakeDocument({"Display Label": FakeObject(Length=1)})
        with pytest.raises(ParameterObservationObjectNotFoundError):
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding(group_name="Spreadsheet")]),
            )
        assert document.calls == ["Spreadsheet"]

    def test_failure_does_not_write_files(self, monkeypatch):
        _no_write_guard(monkeypatch)
        document = FakeDocument({})
        with pytest.raises(ParameterObservationObjectNotFoundError):
            observe_requested_parameters(
                document,
                _parameter_verification([_parameter_binding()]),
            )


# ===========================================================================
# 2. Metadata unavailable observations
# ===========================================================================


class TestMetadataUnavailableObservations:
    def test_missing_get_object_raises_document_error(self):
        with pytest.raises(MetadataObservationDocumentError):
            observe_requested_metadata(
                DocumentWithoutGetObject(),
                _metadata_verification([_metadata_request()]),
            )

    def test_non_callable_get_object_raises_document_error(self):
        with pytest.raises(MetadataObservationDocumentError):
            observe_requested_metadata(
                DocumentWithNonCallableGetObject(),
                _metadata_verification([_metadata_request()]),
            )

    def test_raising_get_object_raises_document_error(self):
        document = FakeDocument(exc=RuntimeError("boom"))
        with pytest.raises(MetadataObservationDocumentError) as excinfo:
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request()]),
            )
        assert isinstance(excinfo.value.__cause__, RuntimeError)
        assert document.calls == ["Doc"]

    def test_get_object_none_raises_owner_not_found_error(self):
        document = FakeDocument({})
        with pytest.raises(MetadataObservationOwnerNotFoundError):
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request()]),
            )
        assert document.calls == ["Doc"]

    def test_missing_property_raises_property_error(self):
        document = FakeDocument({"Doc": FakeObject(Other=1)})
        with pytest.raises(MetadataObservationPropertyError):
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request(key="Author")]),
            )

    def test_property_getter_raising_raises_property_error(self):
        document = FakeDocument({"Doc": RaisingPropertyObject()})
        with pytest.raises(MetadataObservationPropertyError) as excinfo:
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request(key="Author")]),
            )
        assert isinstance(excinfo.value.__cause__, RuntimeError)

    @pytest.mark.parametrize("value", UNSUPPORTED_VALUES)
    def test_unsupported_values_raise_value_error(self, value):
        document = FakeDocument({"Doc": FakeObject(Author=value)})
        with pytest.raises(MetadataObservationValueError):
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request(key="Author")]),
            )

    @pytest.mark.parametrize("value", NON_FINITE_FLOATS)
    def test_non_finite_floats_raise_value_error(self, value):
        document = FakeDocument({"Doc": FakeObject(Author=value)})
        with pytest.raises(MetadataObservationValueError):
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request(key="Author")]),
            )

    def test_typed_errors_are_metadata_observation_errors(self):
        document = FakeDocument({})
        with pytest.raises(MetadataObservationError):
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request()]),
            )

    def test_failure_does_not_use_label_or_objects(self):
        document = FakeDocument({"Display Label": FakeObject(Author="x")})
        with pytest.raises(MetadataObservationOwnerNotFoundError):
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request(owner_id="Doc")]),
            )
        assert document.calls == ["Doc"]

    def test_failure_does_not_write_files(self, monkeypatch):
        _no_write_guard(monkeypatch)
        document = FakeDocument({})
        with pytest.raises(MetadataObservationOwnerNotFoundError):
            observe_requested_metadata(
                document,
                _metadata_verification([_metadata_request()]),
            )


# ===========================================================================
# 3. Reference unavailable observations
# ===========================================================================


class TestReferenceUnavailableObservations:
    def test_missing_get_object_raises_document_error(self):
        with pytest.raises(ReferenceObservationDocumentError):
            observe_requested_references(
                DocumentWithoutGetObject(),
                _reference_verification([_reference_request()]),
            )

    def test_non_callable_get_object_raises_document_error(self):
        with pytest.raises(ReferenceObservationDocumentError):
            observe_requested_references(
                DocumentWithNonCallableGetObject(),
                _reference_verification([_reference_request()]),
            )

    def test_raising_get_object_raises_document_error(self):
        document = FakeDocument(exc=RuntimeError("boom"))
        with pytest.raises(ReferenceObservationDocumentError) as excinfo:
            observe_requested_references(
                document,
                _reference_verification([_reference_request()]),
            )
        assert isinstance(excinfo.value.__cause__, RuntimeError)
        assert document.calls == ["Body"]

    def test_get_object_none_raises_reference_not_found_error(self):
        document = FakeDocument({})
        with pytest.raises(ReferenceObservationReferenceNotFoundError):
            observe_requested_references(
                document,
                _reference_verification([_reference_request()]),
            )
        assert document.calls == ["Body"]

    def test_typed_errors_are_reference_observation_errors(self):
        document = FakeDocument({})
        with pytest.raises(ReferenceObservationError):
            observe_requested_references(
                document,
                _reference_verification([_reference_request()]),
            )

    def test_resolved_object_is_used_only_to_prove_existence(self):
        # A resolved object whose attribute access raises must still succeed:
        # reference observation must not validate or infer kind from it.
        document = FakeDocument({"Body": HostileObject()})
        result = observe_requested_references(
            document,
            _reference_verification([_reference_request(kind="part", name="Body")]),
        )
        assert result == ({"kind": "part", "name": "Body"},)

    def test_kind_is_echoed_from_request_not_inferred(self):
        # The emitted kind comes from the request, even when it does not match
        # any attribute on the resolved object.
        document = FakeDocument({"Body": FakeObject()})
        result = observe_requested_references(
            document,
            _reference_verification([_reference_request(kind="constraint", name="Body")]),
        )
        assert result == ({"kind": "constraint", "name": "Body"},)

    def test_failure_does_not_use_label_or_objects(self):
        document = FakeDocument({"Display Label": FakeObject()})
        with pytest.raises(ReferenceObservationReferenceNotFoundError):
            observe_requested_references(
                document,
                _reference_verification([_reference_request(name="Body")]),
            )
        assert document.calls == ["Body"]

    def test_failure_does_not_write_files(self, monkeypatch):
        _no_write_guard(monkeypatch)
        document = FakeDocument({})
        with pytest.raises(ReferenceObservationReferenceNotFoundError):
            observe_requested_references(
                document,
                _reference_verification([_reference_request()]),
            )


# ===========================================================================
# 4. Requested-scope composition failure behavior
# ===========================================================================


def _all_categories_verification():
    return {
        "observe": {
            "parameters": True,
            "metadata": True,
            "references": True,
        },
        "observationContext": {
            "parameters": [_parameter_binding(name="Length", group_name="Spreadsheet")],
        },
        "expected": {
            "metadata": [_metadata_request(key="Author", owner_id="Doc")],
            "references": [_reference_request(kind="part", name="Body")],
        },
    }


class TestRequestedScopeCompositionFailures:
    def test_propagates_parameter_error_unchanged(self):
        document = FakeDocument({})
        with pytest.raises(ParameterObservationObjectNotFoundError):
            observe_requested_contract_scope(
                document,
                _parameter_verification([_parameter_binding()]),
            )

    def test_propagates_metadata_error_unchanged(self):
        document = FakeDocument({})
        with pytest.raises(MetadataObservationOwnerNotFoundError):
            observe_requested_contract_scope(
                document,
                _metadata_verification([_metadata_request()]),
            )

    def test_propagates_reference_error_unchanged(self):
        document = FakeDocument({})
        with pytest.raises(ReferenceObservationReferenceNotFoundError):
            observe_requested_contract_scope(
                document,
                _reference_verification([_reference_request()]),
            )

    def test_stops_before_later_categories_after_parameter_failure(self):
        # Parameters fail first because the group name is unresolved. Metadata
        # owner and reference name must never be requested.
        document = FakeDocument({})
        with pytest.raises(ParameterObservationObjectNotFoundError):
            observe_requested_contract_scope(
                document,
                _all_categories_verification(),
            )
        assert document.calls == ["Spreadsheet"]
        assert "Doc" not in document.calls
        assert "Body" not in document.calls

    def test_components_remain_ignored_and_no_components_key_emitted(self):
        document = FakeDocument(
            {
                "Spreadsheet": FakeObject(Length=10),
                "Doc": FakeObject(Author="Jane"),
                "Body": FakeObject(),
            }
        )
        data = _all_categories_verification()
        data["observe"]["components"] = True

        observation = observe_requested_contract_scope(document, data)

        assert "components" not in observation
        assert set(observation.keys()) == {"parameters", "metadata", "references"}

    def test_no_objects_traversal_on_failure(self):
        # FakeDocument.Objects raises if accessed; reaching here proves the
        # failure path never traversed document.Objects.
        document = FakeDocument({})
        with pytest.raises(ParameterObservationObjectNotFoundError):
            observe_requested_contract_scope(
                document,
                _all_categories_verification(),
            )


# ===========================================================================
# 5. Observed-output boundary failure behavior
# ===========================================================================


def _observed_path(output_directory) -> Path:
    return Path(output_directory) / OBSERVED_FILENAME


def _generate(document, verification_data, output_directory):
    generate_observed_output(
        document,
        verification_data,
        working_copy_path=_WORKING_COPY_PATH,
        working_copy_sha256=_WORKING_COPY_SHA256,
        output_directory=output_directory,
    )


_UNAVAILABLE_CASES = {
    "parameter": (
        FakeDocument({}),
        _parameter_verification([_parameter_binding()]),
        ParameterObservationObjectNotFoundError,
    ),
    "metadata": (
        FakeDocument({}),
        _metadata_verification([_metadata_request()]),
        MetadataObservationOwnerNotFoundError,
    ),
    "reference": (
        FakeDocument({}),
        _reference_verification([_reference_request()]),
        ReferenceObservationReferenceNotFoundError,
    ),
}


class TestObservedOutputBoundaryFailures:
    @pytest.mark.parametrize("category", list(_UNAVAILABLE_CASES))
    def test_wraps_in_observed_output_error_with_cause(self, category, tmp_path):
        document, verification_data, expected_cause = _UNAVAILABLE_CASES[category]
        with pytest.raises(ObservedOutputError) as excinfo:
            _generate(document, verification_data, tmp_path)
        assert isinstance(excinfo.value.__cause__, expected_cause)

    @pytest.mark.parametrize("category", list(_UNAVAILABLE_CASES))
    def test_no_observed_file_created_on_failure(self, category, tmp_path):
        document, verification_data, _ = _UNAVAILABLE_CASES[category]
        with pytest.raises(ObservedOutputError):
            _generate(document, verification_data, tmp_path)
        assert not _observed_path(tmp_path).exists()

    @pytest.mark.parametrize("category", list(_UNAVAILABLE_CASES))
    def test_stale_observed_file_is_preserved_on_failure(self, category, tmp_path):
        document, verification_data, _ = _UNAVAILABLE_CASES[category]
        path = _observed_path(tmp_path)
        stale_bytes = b'{"stale":true,"leftover":[1,2,3]}\nextra\n'
        path.write_bytes(stale_bytes)

        with pytest.raises(ObservedOutputError):
            _generate(document, verification_data, tmp_path)

        assert path.read_bytes() == stale_bytes

    def test_no_partial_write_when_later_binding_fails(self, tmp_path):
        # First binding resolves; second is unavailable. Observation completes
        # fully before any write, so a later failure must leave no file.
        document = FakeDocument({"Spreadsheet": FakeObject(Length=10)})
        verification_data = _parameter_verification(
            [
                _parameter_binding(param_id="p.ok", name="Length", group_name="Spreadsheet"),
                _parameter_binding(param_id="p.bad", name="Length", group_name="Missing"),
            ]
        )
        with pytest.raises(ObservedOutputError) as excinfo:
            _generate(document, verification_data, tmp_path)
        assert isinstance(
            excinfo.value.__cause__, ParameterObservationObjectNotFoundError
        )
        assert not _observed_path(tmp_path).exists()

    def test_failure_does_not_observe_components_or_decide(self, tmp_path):
        # components enabled alongside a failing parameter request. Failure
        # surfaces as the parameter error (no decision, no component traversal).
        document = FakeDocument({})
        verification_data = _parameter_verification([_parameter_binding()])
        verification_data["observe"]["components"] = True
        with pytest.raises(ObservedOutputError) as excinfo:
            _generate(document, verification_data, tmp_path)
        assert isinstance(
            excinfo.value.__cause__, ParameterObservationObjectNotFoundError
        )
        assert not _observed_path(tmp_path).exists()

    def test_successful_generation_emits_no_components_key(self, tmp_path):
        # Sanity anchor: on success no components key is emitted and no
        # verification decision is added to the observed payload.
        document = FakeDocument(
            {
                "Spreadsheet": FakeObject(Length=10),
                "Doc": FakeObject(Author="Jane"),
                "Body": FakeObject(),
            }
        )
        data = _all_categories_verification()
        data["observe"]["components"] = True
        _generate(document, data, tmp_path)

        decoded = json.loads(_observed_path(tmp_path).read_text(encoding="utf-8"))
        assert "components" not in decoded["observation"]
        assert set(decoded.keys()) == {"schemaVersion", "workingCopy", "observation"}
