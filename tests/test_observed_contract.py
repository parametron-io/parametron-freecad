"""Tests for the Phase 2 prm.observed.json output contract surface."""

import importlib
import sys
import types
import unittest
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.observed_contract"


def _import_contract_module():
    return importlib.import_module(MODULE_NAME)


class TestImportSafety(unittest.TestCase):
    """The contract module must import under ordinary Python without FreeCAD."""

    def test_import_succeeds_without_freecad(self):
        guarded_names = {"FreeCAD", "FreeCADGui", "freecad"}

        def guarded_import(name, *args, **kwargs):
            if name in guarded_names:
                raise AssertionError(f"{name} must not be imported")
            return real_import(name, *args, **kwargs)

        real_import = __import__
        previous = sys.modules.pop(MODULE_NAME, None)
        self.addCleanup(
            lambda: sys.modules.__setitem__(MODULE_NAME, previous)
            if previous is not None
            else sys.modules.pop(MODULE_NAME, None)
        )

        with mock.patch("builtins.__import__", side_effect=guarded_import):
            module = _import_contract_module()

        self.assertIsInstance(module, types.ModuleType)
        self.assertNotIn("FreeCAD", sys.modules)
        self.assertNotIn("freecad", sys.modules)

    def test_module_is_a_module(self):
        self.assertIsInstance(_import_contract_module(), types.ModuleType)


class _ContractTestCase(unittest.TestCase):
    def setUp(self):
        self.oc = _import_contract_module()


class TestFilenameAndSchemaVersion(_ContractTestCase):
    def test_filename_is_exact(self):
        self.assertEqual(
            self.oc.PARAMETRON_OBSERVED_FILENAME,
            "prm.observed.json",
        )

    def test_schema_version_is_exact(self):
        self.assertEqual(self.oc.PARAMETRON_OBSERVED_SCHEMA_VERSION, "1.0")

    def test_filename_and_schema_version_are_strings(self):
        self.assertIsInstance(self.oc.PARAMETRON_OBSERVED_FILENAME, str)
        self.assertIsInstance(self.oc.PARAMETRON_OBSERVED_SCHEMA_VERSION, str)


class TestTopLevelFields(_ContractTestCase):
    def test_top_level_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.TOP_LEVEL_FIELDS,
            ("schemaVersion", "workingCopy", "observation"),
        )

    def test_required_top_level_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.REQUIRED_TOP_LEVEL_FIELDS,
            ("schemaVersion", "workingCopy", "observation"),
        )

    def test_no_optional_top_level_fields(self):
        optional = getattr(self.oc, "OPTIONAL_TOP_LEVEL_FIELDS", ())
        self.assertEqual(optional, ())

    def test_top_level_field_constants(self):
        self.assertEqual(self.oc.FIELD_SCHEMA_VERSION, "schemaVersion")
        self.assertEqual(self.oc.FIELD_WORKING_COPY, "workingCopy")
        self.assertEqual(self.oc.FIELD_OBSERVATION, "observation")

    def test_top_level_fields_are_tuples(self):
        self.assertIsInstance(self.oc.TOP_LEVEL_FIELDS, tuple)
        self.assertIsInstance(self.oc.REQUIRED_TOP_LEVEL_FIELDS, tuple)

    def test_top_level_fields_are_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.TOP_LEVEL_FIELDS[0] = "mutated"
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.REQUIRED_TOP_LEVEL_FIELDS[0] = "mutated"


class TestWorkingCopyFields(_ContractTestCase):
    def test_working_copy_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.WORKING_COPY_FIELDS,
            ("path", "sha256"),
        )

    def test_working_copy_field_constants(self):
        self.assertEqual(self.oc.WORKING_COPY_FIELD_PATH, "path")
        self.assertEqual(self.oc.WORKING_COPY_FIELD_SHA256, "sha256")

    def test_working_copy_fields_is_tuple(self):
        self.assertIsInstance(self.oc.WORKING_COPY_FIELDS, tuple)

    def test_working_copy_fields_is_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.WORKING_COPY_FIELDS[0] = "mutated"


class TestObservationCategories(_ContractTestCase):
    def test_observation_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.OBSERVATION_FIELDS,
            ("parameters", "metadata", "references", "components"),
        )

    def test_observation_field_constants(self):
        self.assertEqual(self.oc.OBSERVATION_FIELD_PARAMETERS, "parameters")
        self.assertEqual(self.oc.OBSERVATION_FIELD_METADATA, "metadata")
        self.assertEqual(self.oc.OBSERVATION_FIELD_REFERENCES, "references")
        self.assertEqual(self.oc.OBSERVATION_FIELD_COMPONENTS, "components")

    def test_observation_fields_is_tuple(self):
        self.assertIsInstance(self.oc.OBSERVATION_FIELDS, tuple)

    def test_observation_fields_is_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVATION_FIELDS[0] = "mutated"

    def test_supported_observation_categories_helper_returns_exact_tuple(self):
        self.assertEqual(
            self.oc.supported_observation_categories(),
            ("parameters", "metadata", "references", "components"),
        )

    def test_supported_observation_categories_returns_tuple(self):
        self.assertIsInstance(self.oc.supported_observation_categories(), tuple)

    def test_supported_observation_categories_is_deterministic(self):
        self.assertEqual(
            self.oc.supported_observation_categories(),
            self.oc.supported_observation_categories(),
        )


class TestObservedParameterFields(_ContractTestCase):
    def test_observed_parameter_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.OBSERVED_PARAMETER_FIELDS,
            ("id", "name", "groupId", "value", "valueKind"),
        )

    def test_observed_parameter_field_constants(self):
        self.assertEqual(self.oc.OBSERVED_PARAMETER_FIELD_ID, "id")
        self.assertEqual(self.oc.OBSERVED_PARAMETER_FIELD_NAME, "name")
        self.assertEqual(self.oc.OBSERVED_PARAMETER_FIELD_GROUP_ID, "groupId")
        self.assertEqual(self.oc.OBSERVED_PARAMETER_FIELD_VALUE, "value")
        self.assertEqual(self.oc.OBSERVED_PARAMETER_FIELD_VALUE_KIND, "valueKind")

    def test_observed_parameter_fields_is_tuple(self):
        self.assertIsInstance(self.oc.OBSERVED_PARAMETER_FIELDS, tuple)

    def test_observed_parameter_fields_is_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_PARAMETER_FIELDS[0] = "mutated"


class TestObservedMetadataFields(_ContractTestCase):
    def test_observed_metadata_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.OBSERVED_METADATA_FIELDS,
            ("id", "key", "ownerId", "value", "valueKind"),
        )

    def test_observed_metadata_field_constants(self):
        self.assertEqual(self.oc.OBSERVED_METADATA_FIELD_ID, "id")
        self.assertEqual(self.oc.OBSERVED_METADATA_FIELD_KEY, "key")
        self.assertEqual(self.oc.OBSERVED_METADATA_FIELD_OWNER_ID, "ownerId")
        self.assertEqual(self.oc.OBSERVED_METADATA_FIELD_VALUE, "value")
        self.assertEqual(self.oc.OBSERVED_METADATA_FIELD_VALUE_KIND, "valueKind")

    def test_observed_metadata_fields_is_tuple(self):
        self.assertIsInstance(self.oc.OBSERVED_METADATA_FIELDS, tuple)

    def test_observed_metadata_fields_is_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_METADATA_FIELDS[0] = "mutated"


class TestObservedReferenceFields(_ContractTestCase):
    def test_observed_reference_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.OBSERVED_REFERENCE_FIELDS,
            ("kind", "name"),
        )

    def test_observed_reference_field_constants(self):
        self.assertEqual(self.oc.OBSERVED_REFERENCE_FIELD_KIND, "kind")
        self.assertEqual(self.oc.OBSERVED_REFERENCE_FIELD_NAME, "name")

    def test_observed_reference_fields_is_tuple(self):
        self.assertIsInstance(self.oc.OBSERVED_REFERENCE_FIELDS, tuple)

    def test_observed_reference_fields_is_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_REFERENCE_FIELDS[0] = "mutated"


class TestObservedComponentFields(_ContractTestCase):
    def test_observed_component_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.OBSERVED_COMPONENT_FIELDS,
            ("id", "kind", "name", "parentId"),
        )

    def test_observed_component_field_constants(self):
        self.assertEqual(self.oc.OBSERVED_COMPONENT_FIELD_ID, "id")
        self.assertEqual(self.oc.OBSERVED_COMPONENT_FIELD_KIND, "kind")
        self.assertEqual(self.oc.OBSERVED_COMPONENT_FIELD_NAME, "name")
        self.assertEqual(self.oc.OBSERVED_COMPONENT_FIELD_PARENT_ID, "parentId")

    def test_observed_component_fields_is_tuple(self):
        self.assertIsInstance(self.oc.OBSERVED_COMPONENT_FIELDS, tuple)

    def test_observed_component_fields_is_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_COMPONENT_FIELDS[0] = "mutated"


class TestSupportedValueSets(_ContractTestCase):
    def test_supported_observed_component_kinds_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.SUPPORTED_OBSERVED_COMPONENT_KINDS,
            ("assembly", "part"),
        )

    def test_supported_observed_parameter_value_kinds_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS,
            ("number", "integer", "string", "boolean"),
        )

    def test_supported_observed_metadata_value_kinds_are_exact_and_ordered(self):
        self.assertEqual(
            self.oc.SUPPORTED_OBSERVED_METADATA_VALUE_KINDS,
            ("number", "integer", "string", "boolean"),
        )

    def test_value_set_constants_are_tuples(self):
        self.assertIsInstance(self.oc.SUPPORTED_OBSERVED_COMPONENT_KINDS, tuple)
        self.assertIsInstance(self.oc.SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS, tuple)
        self.assertIsInstance(self.oc.SUPPORTED_OBSERVED_METADATA_VALUE_KINDS, tuple)

    def test_value_set_constants_are_immutable(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.SUPPORTED_OBSERVED_COMPONENT_KINDS[0] = "mutated"
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS[0] = "mutated"
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.SUPPORTED_OBSERVED_METADATA_VALUE_KINDS[0] = "mutated"


class TestHelperFunctions(_ContractTestCase):
    def test_supported_observed_component_kinds_helper_returns_exact_tuple(self):
        self.assertEqual(
            self.oc.supported_observed_component_kinds(),
            ("assembly", "part"),
        )

    def test_supported_observed_parameter_value_kinds_helper_returns_exact_tuple(self):
        self.assertEqual(
            self.oc.supported_observed_parameter_value_kinds(),
            ("number", "integer", "string", "boolean"),
        )

    def test_supported_observed_metadata_value_kinds_helper_returns_exact_tuple(self):
        self.assertEqual(
            self.oc.supported_observed_metadata_value_kinds(),
            ("number", "integer", "string", "boolean"),
        )

    def test_helper_functions_return_tuples(self):
        helpers = (
            self.oc.supported_observation_categories,
            self.oc.supported_observed_component_kinds,
            self.oc.supported_observed_parameter_value_kinds,
            self.oc.supported_observed_metadata_value_kinds,
        )

        for helper in helpers:
            with self.subTest(helper=helper.__name__):
                self.assertIsInstance(helper(), tuple)

    def test_helper_function_results_are_deterministic(self):
        helpers = (
            self.oc.supported_observation_categories,
            self.oc.supported_observed_component_kinds,
            self.oc.supported_observed_parameter_value_kinds,
            self.oc.supported_observed_metadata_value_kinds,
        )

        for helper in helpers:
            with self.subTest(helper=helper.__name__):
                self.assertEqual(helper(), helper())

    def test_helper_function_results_are_immutable(self):
        results = (
            self.oc.supported_observation_categories(),
            self.oc.supported_observed_component_kinds(),
            self.oc.supported_observed_parameter_value_kinds(),
            self.oc.supported_observed_metadata_value_kinds(),
        )

        for result in results:
            with self.subTest(result=result):
                with self.assertRaises((TypeError, AttributeError)):
                    result[0] = "mutated"


class TestTuplePublicSurfaces(_ContractTestCase):
    def test_public_field_and_value_set_collections_are_tuples(self):
        collection_names = (
            "TOP_LEVEL_FIELDS",
            "REQUIRED_TOP_LEVEL_FIELDS",
            "WORKING_COPY_FIELDS",
            "OBSERVATION_FIELDS",
            "OBSERVED_PARAMETER_FIELDS",
            "OBSERVED_METADATA_FIELDS",
            "OBSERVED_REFERENCE_FIELDS",
            "OBSERVED_COMPONENT_FIELDS",
            "SUPPORTED_OBSERVED_COMPONENT_KINDS",
            "SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS",
            "SUPPORTED_OBSERVED_METADATA_VALUE_KINDS",
        )

        for name in collection_names:
            with self.subTest(name=name):
                self.assertIsInstance(getattr(self.oc, name), tuple)

    def test_public_field_and_value_set_collections_reject_item_assignment(self):
        collections = (
            self.oc.TOP_LEVEL_FIELDS,
            self.oc.REQUIRED_TOP_LEVEL_FIELDS,
            self.oc.WORKING_COPY_FIELDS,
            self.oc.OBSERVATION_FIELDS,
            self.oc.OBSERVED_PARAMETER_FIELDS,
            self.oc.OBSERVED_METADATA_FIELDS,
            self.oc.OBSERVED_REFERENCE_FIELDS,
            self.oc.OBSERVED_COMPONENT_FIELDS,
            self.oc.SUPPORTED_OBSERVED_COMPONENT_KINDS,
            self.oc.SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS,
            self.oc.SUPPORTED_OBSERVED_METADATA_VALUE_KINDS,
        )

        for value in collections:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, AttributeError)):
                    value[0] = "mutated"


class TestFrozenDataclassBehavior(_ContractTestCase):
    def test_working_copy_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.WORKING_COPY_CONTRACT.fields = ("mutated",)

    def test_observed_parameter_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_PARAMETER_CONTRACT.id_field = "mutated"

    def test_observed_metadata_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_METADATA_CONTRACT.id_field = "mutated"

    def test_observed_reference_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_REFERENCE_CONTRACT.kind_field = "mutated"

    def test_observed_component_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVED_COMPONENT_CONTRACT.id_field = "mutated"

    def test_observation_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.OBSERVATION_CONTRACT.parameters_field = "mutated"

    def test_top_level_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.oc.PARAMETRON_OBSERVED_CONTRACT.filename = "mutated"


class TestCanonicalInstanceStability(_ContractTestCase):
    def test_top_level_contract_uses_canonical_constants_and_instances(self):
        contract = self.oc.PARAMETRON_OBSERVED_CONTRACT

        self.assertEqual(contract.filename, self.oc.PARAMETRON_OBSERVED_FILENAME)
        self.assertEqual(contract.schema_version, self.oc.PARAMETRON_OBSERVED_SCHEMA_VERSION)
        self.assertEqual(contract.schema_version_field, self.oc.FIELD_SCHEMA_VERSION)
        self.assertEqual(contract.top_level_fields, self.oc.TOP_LEVEL_FIELDS)
        self.assertEqual(contract.required_top_level_fields, self.oc.REQUIRED_TOP_LEVEL_FIELDS)
        self.assertEqual(contract.working_copy_field, self.oc.FIELD_WORKING_COPY)
        self.assertEqual(contract.observation_field, self.oc.FIELD_OBSERVATION)
        self.assertIs(contract.working_copy, self.oc.WORKING_COPY_CONTRACT)
        self.assertIs(contract.observation, self.oc.OBSERVATION_CONTRACT)

    def test_working_copy_contract_structure(self):
        contract = self.oc.WORKING_COPY_CONTRACT

        self.assertEqual(contract.fields, self.oc.WORKING_COPY_FIELDS)
        self.assertEqual(contract.path_field, self.oc.WORKING_COPY_FIELD_PATH)
        self.assertEqual(contract.sha256_field, self.oc.WORKING_COPY_FIELD_SHA256)

    def test_observation_contract_structure(self):
        contract = self.oc.OBSERVATION_CONTRACT

        self.assertEqual(contract.fields, self.oc.OBSERVATION_FIELDS)
        self.assertEqual(contract.parameters_field, self.oc.OBSERVATION_FIELD_PARAMETERS)
        self.assertEqual(contract.metadata_field, self.oc.OBSERVATION_FIELD_METADATA)
        self.assertEqual(contract.references_field, self.oc.OBSERVATION_FIELD_REFERENCES)
        self.assertEqual(contract.components_field, self.oc.OBSERVATION_FIELD_COMPONENTS)
        self.assertIs(contract.parameter, self.oc.OBSERVED_PARAMETER_CONTRACT)
        self.assertIs(contract.metadata, self.oc.OBSERVED_METADATA_CONTRACT)
        self.assertIs(contract.reference, self.oc.OBSERVED_REFERENCE_CONTRACT)
        self.assertIs(contract.component, self.oc.OBSERVED_COMPONENT_CONTRACT)

    def test_observed_parameter_contract_structure(self):
        contract = self.oc.OBSERVED_PARAMETER_CONTRACT

        self.assertEqual(contract.fields, self.oc.OBSERVED_PARAMETER_FIELDS)
        self.assertEqual(contract.id_field, self.oc.OBSERVED_PARAMETER_FIELD_ID)
        self.assertEqual(contract.name_field, self.oc.OBSERVED_PARAMETER_FIELD_NAME)
        self.assertEqual(contract.group_id_field, self.oc.OBSERVED_PARAMETER_FIELD_GROUP_ID)
        self.assertEqual(contract.value_field, self.oc.OBSERVED_PARAMETER_FIELD_VALUE)
        self.assertEqual(contract.value_kind_field, self.oc.OBSERVED_PARAMETER_FIELD_VALUE_KIND)
        self.assertEqual(
            contract.supported_value_kinds,
            self.oc.SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS,
        )

    def test_observed_metadata_contract_structure(self):
        contract = self.oc.OBSERVED_METADATA_CONTRACT

        self.assertEqual(contract.fields, self.oc.OBSERVED_METADATA_FIELDS)
        self.assertEqual(contract.id_field, self.oc.OBSERVED_METADATA_FIELD_ID)
        self.assertEqual(contract.key_field, self.oc.OBSERVED_METADATA_FIELD_KEY)
        self.assertEqual(contract.owner_id_field, self.oc.OBSERVED_METADATA_FIELD_OWNER_ID)
        self.assertEqual(contract.value_field, self.oc.OBSERVED_METADATA_FIELD_VALUE)
        self.assertEqual(contract.value_kind_field, self.oc.OBSERVED_METADATA_FIELD_VALUE_KIND)
        self.assertEqual(
            contract.supported_value_kinds,
            self.oc.SUPPORTED_OBSERVED_METADATA_VALUE_KINDS,
        )

    def test_observed_reference_contract_structure(self):
        contract = self.oc.OBSERVED_REFERENCE_CONTRACT

        self.assertEqual(contract.fields, self.oc.OBSERVED_REFERENCE_FIELDS)
        self.assertEqual(contract.kind_field, self.oc.OBSERVED_REFERENCE_FIELD_KIND)
        self.assertEqual(contract.name_field, self.oc.OBSERVED_REFERENCE_FIELD_NAME)

    def test_observed_component_contract_structure(self):
        contract = self.oc.OBSERVED_COMPONENT_CONTRACT

        self.assertEqual(contract.fields, self.oc.OBSERVED_COMPONENT_FIELDS)
        self.assertEqual(contract.id_field, self.oc.OBSERVED_COMPONENT_FIELD_ID)
        self.assertEqual(contract.kind_field, self.oc.OBSERVED_COMPONENT_FIELD_KIND)
        self.assertEqual(contract.name_field, self.oc.OBSERVED_COMPONENT_FIELD_NAME)
        self.assertEqual(contract.parent_id_field, self.oc.OBSERVED_COMPONENT_FIELD_PARENT_ID)
        self.assertEqual(contract.supported_kinds, self.oc.SUPPORTED_OBSERVED_COMPONENT_KINDS)

    def test_repeated_access_returns_equal_values(self):
        self.assertEqual(
            self.oc.PARAMETRON_OBSERVED_CONTRACT.top_level_fields,
            self.oc.PARAMETRON_OBSERVED_CONTRACT.top_level_fields,
        )
        self.assertEqual(
            self.oc.OBSERVATION_CONTRACT.fields,
            self.oc.OBSERVATION_CONTRACT.fields,
        )
        self.assertEqual(
            self.oc.OBSERVED_PARAMETER_CONTRACT.supported_value_kinds,
            self.oc.OBSERVED_PARAMETER_CONTRACT.supported_value_kinds,
        )


class TestPublicApiSurface(_ContractTestCase):
    def test_all_includes_expected_public_symbols(self):
        expected_symbols = {
            "PARAMETRON_OBSERVED_FILENAME",
            "PARAMETRON_OBSERVED_SCHEMA_VERSION",
            "FIELD_SCHEMA_VERSION",
            "FIELD_WORKING_COPY",
            "FIELD_OBSERVATION",
            "TOP_LEVEL_FIELDS",
            "REQUIRED_TOP_LEVEL_FIELDS",
            "WORKING_COPY_FIELD_PATH",
            "WORKING_COPY_FIELD_SHA256",
            "WORKING_COPY_FIELDS",
            "OBSERVATION_FIELD_PARAMETERS",
            "OBSERVATION_FIELD_METADATA",
            "OBSERVATION_FIELD_REFERENCES",
            "OBSERVATION_FIELD_COMPONENTS",
            "OBSERVATION_FIELDS",
            "OBSERVED_PARAMETER_FIELD_ID",
            "OBSERVED_PARAMETER_FIELD_NAME",
            "OBSERVED_PARAMETER_FIELD_GROUP_ID",
            "OBSERVED_PARAMETER_FIELD_VALUE",
            "OBSERVED_PARAMETER_FIELD_VALUE_KIND",
            "OBSERVED_PARAMETER_FIELDS",
            "OBSERVED_PARAMETER_VALUE_KIND_NUMBER",
            "OBSERVED_PARAMETER_VALUE_KIND_INTEGER",
            "OBSERVED_PARAMETER_VALUE_KIND_STRING",
            "OBSERVED_PARAMETER_VALUE_KIND_BOOLEAN",
            "OBSERVED_METADATA_FIELD_ID",
            "OBSERVED_METADATA_FIELD_KEY",
            "OBSERVED_METADATA_FIELD_OWNER_ID",
            "OBSERVED_METADATA_FIELD_VALUE",
            "OBSERVED_METADATA_FIELD_VALUE_KIND",
            "OBSERVED_METADATA_FIELDS",
            "OBSERVED_METADATA_VALUE_KIND_NUMBER",
            "OBSERVED_METADATA_VALUE_KIND_INTEGER",
            "OBSERVED_METADATA_VALUE_KIND_STRING",
            "OBSERVED_METADATA_VALUE_KIND_BOOLEAN",
            "OBSERVED_REFERENCE_FIELD_KIND",
            "OBSERVED_REFERENCE_FIELD_NAME",
            "OBSERVED_REFERENCE_FIELDS",
            "OBSERVED_COMPONENT_FIELD_ID",
            "OBSERVED_COMPONENT_FIELD_KIND",
            "OBSERVED_COMPONENT_FIELD_NAME",
            "OBSERVED_COMPONENT_FIELD_PARENT_ID",
            "OBSERVED_COMPONENT_FIELDS",
            "OBSERVED_COMPONENT_KIND_ASSEMBLY",
            "OBSERVED_COMPONENT_KIND_PART",
            "SUPPORTED_OBSERVED_COMPONENT_KINDS",
            "SUPPORTED_OBSERVED_PARAMETER_VALUE_KINDS",
            "SUPPORTED_OBSERVED_METADATA_VALUE_KINDS",
            "WorkingCopyContract",
            "ObservedParameterContract",
            "ObservedMetadataContract",
            "ObservedReferenceContract",
            "ObservedComponentContract",
            "ObservationContract",
            "ObservedContract",
            "WORKING_COPY_CONTRACT",
            "OBSERVED_PARAMETER_CONTRACT",
            "OBSERVED_METADATA_CONTRACT",
            "OBSERVED_REFERENCE_CONTRACT",
            "OBSERVED_COMPONENT_CONTRACT",
            "OBSERVATION_CONTRACT",
            "PARAMETRON_OBSERVED_CONTRACT",
            "supported_observation_categories",
            "supported_observed_component_kinds",
            "supported_observed_parameter_value_kinds",
            "supported_observed_metadata_value_kinds",
        }

        self.assertLessEqual(expected_symbols, set(self.oc.__all__))

    def test_all_does_not_include_behavioral_apis(self):
        denied_names = {
            "load_observed",
            "parse_observed",
            "validate_observed",
            "write_observed",
            "observe_parameters",
            "observe_metadata",
            "observe_references",
            "observe_components",
            "read_document",
            "open_document",
            "verify_observed",
            "compare_observed",
            "decide_observed",
        }

        self.assertTrue(denied_names.isdisjoint(set(self.oc.__all__)))

    def test_module_does_not_define_behavioral_callables(self):
        denied_callable_names = (
            "load_observed",
            "parse_observed",
            "validate_observed",
            "write_observed",
            "observe_parameters",
            "observe_metadata",
            "observe_references",
            "observe_components",
            "read_document",
            "open_document",
            "verify_observed",
            "compare_observed",
            "decide_observed",
            "accept_observed",
            "reject_observed",
        )

        for name in denied_callable_names:
            with self.subTest(name=name):
                self.assertFalse(
                    callable(getattr(self.oc, name, None)),
                    f"Contract module must not define callable '{name}'",
                )


if __name__ == "__main__":
    unittest.main()
