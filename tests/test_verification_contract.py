"""Tests for the Phase 2 prm.verification.json contract surface."""

import importlib
import sys
import types
import unittest
from unittest import mock


MODULE_NAME = "parametron_freecad.observation.verification_contract"


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


class _ContractTestCase(unittest.TestCase):
    def setUp(self):
        self.vc = _import_contract_module()


class TestFilenameAndSchemaVersion(_ContractTestCase):
    def test_filename_and_schema_version_are_exact(self):
        self.assertEqual(
            self.vc.PARAMETRON_VERIFICATION_FILENAME,
            "prm.verification.json",
        )
        self.assertEqual(self.vc.PARAMETRON_VERIFICATION_SCHEMA_VERSION, "1.0")


class TestTopLevelFields(_ContractTestCase):
    def test_top_level_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.vc.TOP_LEVEL_FIELDS,
            ("schemaVersion", "observe", "observationContext", "expected", "checks"),
        )
        self.assertEqual(
            self.vc.REQUIRED_TOP_LEVEL_FIELDS,
            ("schemaVersion", "observe", "expected", "checks"),
        )
        self.assertEqual(self.vc.OPTIONAL_TOP_LEVEL_FIELDS, ("observationContext",))

    def test_required_and_optional_fields_are_top_level_fields(self):
        top_level_fields = set(self.vc.TOP_LEVEL_FIELDS)

        self.assertLessEqual(set(self.vc.REQUIRED_TOP_LEVEL_FIELDS), top_level_fields)
        self.assertLessEqual(set(self.vc.OPTIONAL_TOP_LEVEL_FIELDS), top_level_fields)
        self.assertIn("observationContext", self.vc.TOP_LEVEL_FIELDS)
        self.assertNotIn("observationContext", self.vc.REQUIRED_TOP_LEVEL_FIELDS)

    def test_top_level_field_constants(self):
        self.assertEqual(self.vc.FIELD_SCHEMA_VERSION, "schemaVersion")
        self.assertEqual(self.vc.FIELD_OBSERVE, "observe")
        self.assertEqual(self.vc.FIELD_OBSERVATION_CONTEXT, "observationContext")
        self.assertEqual(self.vc.FIELD_EXPECTED, "expected")
        self.assertEqual(self.vc.FIELD_CHECKS, "checks")


class TestObserveFields(_ContractTestCase):
    def test_observe_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.vc.OBSERVE_FIELDS,
            ("components", "parameters", "metadata", "references", "targetState"),
        )

    def test_observe_field_constants(self):
        self.assertEqual(self.vc.OBSERVE_FIELD_COMPONENTS, "components")
        self.assertEqual(self.vc.OBSERVE_FIELD_PARAMETERS, "parameters")
        self.assertEqual(self.vc.OBSERVE_FIELD_METADATA, "metadata")
        self.assertEqual(self.vc.OBSERVE_FIELD_REFERENCES, "references")
        self.assertEqual(self.vc.OBSERVE_FIELD_TARGET_STATE, "targetState")


class TestObservationContextFields(_ContractTestCase):
    def test_observation_context_fields_are_exact_and_ordered(self):
        self.assertEqual(self.vc.OBSERVATION_CONTEXT_FIELDS, ("parameters", "targetState"))
        self.assertEqual(self.vc.OBSERVATION_CONTEXT_FIELD_TARGET_STATE, "targetState")
        self.assertEqual(
            self.vc.OBSERVATION_PARAMETER_FIELDS,
            ("id", "name", "groupName"),
        )

    def test_observation_context_field_constants(self):
        self.assertEqual(self.vc.OBSERVATION_CONTEXT_FIELD_PARAMETERS, "parameters")
        self.assertEqual(self.vc.OBSERVATION_PARAMETER_FIELD_ID, "id")
        self.assertEqual(self.vc.OBSERVATION_PARAMETER_FIELD_NAME, "name")
        self.assertEqual(
            self.vc.OBSERVATION_PARAMETER_FIELD_GROUP_NAME,
            "groupName",
        )


class TestExpectedFields(_ContractTestCase):
    def test_expected_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.vc.EXPECTED_FIELDS,
            ("components", "parameters", "metadata", "references"),
        )
        self.assertEqual(
            self.vc.EXPECTED_COMPONENT_FIELDS,
            ("id", "kind", "name", "parentId"),
        )
        self.assertEqual(
            self.vc.EXPECTED_PARAMETER_FIELDS,
            ("id", "name", "type", "unit", "value"),
        )
        self.assertEqual(
            self.vc.EXPECTED_METADATA_FIELDS,
            ("id", "key", "ownerId", "value", "valueKind"),
        )
        self.assertEqual(self.vc.EXPECTED_REFERENCE_FIELDS, ("kind", "name"))

    def test_expected_category_field_constants(self):
        self.assertEqual(self.vc.EXPECTED_FIELD_COMPONENTS, "components")
        self.assertEqual(self.vc.EXPECTED_FIELD_PARAMETERS, "parameters")
        self.assertEqual(self.vc.EXPECTED_FIELD_METADATA, "metadata")
        self.assertEqual(self.vc.EXPECTED_FIELD_REFERENCES, "references")

    def test_expected_component_field_constants(self):
        self.assertEqual(self.vc.EXPECTED_COMPONENT_FIELD_ID, "id")
        self.assertEqual(self.vc.EXPECTED_COMPONENT_FIELD_KIND, "kind")
        self.assertEqual(self.vc.EXPECTED_COMPONENT_FIELD_NAME, "name")
        self.assertEqual(self.vc.EXPECTED_COMPONENT_FIELD_PARENT_ID, "parentId")

    def test_expected_parameter_field_constants(self):
        self.assertEqual(self.vc.EXPECTED_PARAMETER_FIELD_ID, "id")
        self.assertEqual(self.vc.EXPECTED_PARAMETER_FIELD_NAME, "name")
        self.assertEqual(self.vc.EXPECTED_PARAMETER_FIELD_TYPE, "type")
        self.assertEqual(self.vc.EXPECTED_PARAMETER_FIELD_UNIT, "unit")
        self.assertEqual(self.vc.EXPECTED_PARAMETER_FIELD_VALUE, "value")

    def test_expected_metadata_field_constants(self):
        self.assertEqual(self.vc.EXPECTED_METADATA_FIELD_ID, "id")
        self.assertEqual(self.vc.EXPECTED_METADATA_FIELD_KEY, "key")
        self.assertEqual(self.vc.EXPECTED_METADATA_FIELD_OWNER_ID, "ownerId")
        self.assertEqual(self.vc.EXPECTED_METADATA_FIELD_VALUE, "value")
        self.assertEqual(self.vc.EXPECTED_METADATA_FIELD_VALUE_KIND, "valueKind")

    def test_expected_reference_field_constants(self):
        self.assertEqual(self.vc.EXPECTED_REFERENCE_FIELD_KIND, "kind")
        self.assertEqual(self.vc.EXPECTED_REFERENCE_FIELD_NAME, "name")


class TestChecksFields(_ContractTestCase):
    def test_checks_fields_are_exact_and_ordered(self):
        self.assertEqual(
            self.vc.CHECKS_FIELDS,
            ("components", "parameters", "metadata", "references"),
        )
        self.assertEqual(self.vc.CHECK_FIELDS, ("enabled",))

    def test_checks_field_constants(self):
        self.assertEqual(self.vc.CHECKS_FIELD_COMPONENTS, "components")
        self.assertEqual(self.vc.CHECKS_FIELD_PARAMETERS, "parameters")
        self.assertEqual(self.vc.CHECKS_FIELD_METADATA, "metadata")
        self.assertEqual(self.vc.CHECKS_FIELD_REFERENCES, "references")
        self.assertEqual(self.vc.CHECK_FIELD_ENABLED, "enabled")


class TestSupportedValueSets(_ContractTestCase):
    def test_supported_value_sets_are_exact_and_ordered(self):
        self.assertEqual(
            self.vc.SUPPORTED_EXPECTED_COMPONENT_KINDS,
            ("assembly", "part"),
        )
        self.assertEqual(self.vc.SUPPORTED_EXPECTED_PARAMETER_TYPES, ("number",))
        self.assertEqual(self.vc.SUPPORTED_EXPECTED_PARAMETER_UNITS, ("mm",))
        self.assertEqual(
            self.vc.SUPPORTED_EXPECTED_METADATA_VALUE_KINDS,
            ("number", "integer", "string", "boolean"),
        )


class TestHelperFunctions(_ContractTestCase):
    def test_helper_function_return_values_are_exact(self):
        self.assertEqual(
            self.vc.supported_observation_categories(),
            ("components", "parameters", "metadata", "references", "targetState"),
        )
        self.assertEqual(
            self.vc.supported_expected_component_kinds(),
            ("assembly", "part"),
        )
        self.assertEqual(self.vc.supported_expected_parameter_types(), ("number",))
        self.assertEqual(self.vc.supported_expected_parameter_units(), ("mm",))
        self.assertEqual(
            self.vc.supported_expected_metadata_value_kinds(),
            ("number", "integer", "string", "boolean"),
        )

    def test_helper_function_results_are_stable(self):
        helpers = (
            self.vc.supported_observation_categories,
            self.vc.supported_expected_component_kinds,
            self.vc.supported_expected_parameter_types,
            self.vc.supported_expected_parameter_units,
            self.vc.supported_expected_metadata_value_kinds,
        )

        for helper in helpers:
            with self.subTest(helper=helper.__name__):
                self.assertEqual(helper(), helper())
                self.assertIsInstance(helper(), tuple)

    def test_helper_functions_do_not_expose_mutable_state(self):
        helper_results = (
            self.vc.supported_observation_categories(),
            self.vc.supported_expected_component_kinds(),
            self.vc.supported_expected_parameter_types(),
            self.vc.supported_expected_parameter_units(),
            self.vc.supported_expected_metadata_value_kinds(),
        )

        for result in helper_results:
            with self.subTest(result=result):
                with self.assertRaises((TypeError, AttributeError)):
                    result[0] = "mutated"


class TestTuplePublicSurfaces(_ContractTestCase):
    def test_public_field_and_value_set_collections_are_tuples(self):
        collection_names = (
            "TOP_LEVEL_FIELDS",
            "REQUIRED_TOP_LEVEL_FIELDS",
            "OPTIONAL_TOP_LEVEL_FIELDS",
            "OBSERVE_FIELDS",
            "OBSERVATION_CONTEXT_FIELDS",
            "OBSERVATION_PARAMETER_FIELDS",
            "EXPECTED_FIELDS",
            "EXPECTED_COMPONENT_FIELDS",
            "EXPECTED_PARAMETER_FIELDS",
            "EXPECTED_METADATA_FIELDS",
            "EXPECTED_REFERENCE_FIELDS",
            "CHECKS_FIELDS",
            "CHECK_FIELDS",
            "SUPPORTED_EXPECTED_COMPONENT_KINDS",
            "SUPPORTED_EXPECTED_PARAMETER_TYPES",
            "SUPPORTED_EXPECTED_PARAMETER_UNITS",
            "SUPPORTED_EXPECTED_METADATA_VALUE_KINDS",
        )

        for name in collection_names:
            with self.subTest(name=name):
                self.assertIsInstance(getattr(self.vc, name), tuple)

    def test_public_field_and_value_set_collections_reject_item_assignment(self):
        collections = (
            self.vc.TOP_LEVEL_FIELDS,
            self.vc.REQUIRED_TOP_LEVEL_FIELDS,
            self.vc.OPTIONAL_TOP_LEVEL_FIELDS,
            self.vc.OBSERVE_FIELDS,
            self.vc.OBSERVATION_CONTEXT_FIELDS,
            self.vc.OBSERVATION_PARAMETER_FIELDS,
            self.vc.EXPECTED_FIELDS,
            self.vc.EXPECTED_COMPONENT_FIELDS,
            self.vc.EXPECTED_PARAMETER_FIELDS,
            self.vc.EXPECTED_METADATA_FIELDS,
            self.vc.EXPECTED_REFERENCE_FIELDS,
            self.vc.CHECKS_FIELDS,
            self.vc.CHECK_FIELDS,
            self.vc.SUPPORTED_EXPECTED_COMPONENT_KINDS,
            self.vc.SUPPORTED_EXPECTED_PARAMETER_TYPES,
            self.vc.SUPPORTED_EXPECTED_PARAMETER_UNITS,
            self.vc.SUPPORTED_EXPECTED_METADATA_VALUE_KINDS,
        )

        for value in collections:
            with self.subTest(value=value):
                with self.assertRaises((TypeError, AttributeError)):
                    value[0] = "mutated"


class TestFrozenDataclassBehavior(_ContractTestCase):
    def test_top_level_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.vc.PARAMETRON_VERIFICATION_CONTRACT.filename = "mutated"

    def test_observe_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.vc.OBSERVE_CONTRACT.components_field = "mutated"

    def test_expected_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.vc.EXPECTED_CONTRACT.components_field = "mutated"

    def test_checks_contract_is_frozen(self):
        with self.assertRaises((TypeError, AttributeError)):
            self.vc.CHECKS_CONTRACT.components_field = "mutated"


class TestCanonicalContractStructure(_ContractTestCase):
    def test_top_level_contract_uses_canonical_constants_and_instances(self):
        contract = self.vc.PARAMETRON_VERIFICATION_CONTRACT

        self.assertEqual(contract.filename, self.vc.PARAMETRON_VERIFICATION_FILENAME)
        self.assertEqual(
            contract.schema_version,
            self.vc.PARAMETRON_VERIFICATION_SCHEMA_VERSION,
        )
        self.assertEqual(contract.schema_version_field, self.vc.FIELD_SCHEMA_VERSION)
        self.assertEqual(contract.top_level_fields, self.vc.TOP_LEVEL_FIELDS)
        self.assertEqual(
            contract.required_top_level_fields,
            self.vc.REQUIRED_TOP_LEVEL_FIELDS,
        )
        self.assertEqual(
            contract.optional_top_level_fields,
            self.vc.OPTIONAL_TOP_LEVEL_FIELDS,
        )
        self.assertEqual(contract.observe_field, self.vc.FIELD_OBSERVE)
        self.assertEqual(
            contract.observation_context_field,
            self.vc.FIELD_OBSERVATION_CONTEXT,
        )
        self.assertEqual(contract.expected_field, self.vc.FIELD_EXPECTED)
        self.assertEqual(contract.checks_field, self.vc.FIELD_CHECKS)
        self.assertIs(contract.observe, self.vc.OBSERVE_CONTRACT)
        self.assertIs(
            contract.observation_context,
            self.vc.OBSERVATION_CONTEXT_CONTRACT,
        )
        self.assertIs(contract.expected, self.vc.EXPECTED_CONTRACT)
        self.assertIs(contract.checks, self.vc.CHECKS_CONTRACT)

    def test_observe_contract_structure(self):
        contract = self.vc.OBSERVE_CONTRACT

        self.assertEqual(contract.fields, self.vc.OBSERVE_FIELDS)
        self.assertEqual(contract.components_field, self.vc.OBSERVE_FIELD_COMPONENTS)
        self.assertEqual(contract.parameters_field, self.vc.OBSERVE_FIELD_PARAMETERS)
        self.assertEqual(contract.metadata_field, self.vc.OBSERVE_FIELD_METADATA)
        self.assertEqual(contract.references_field, self.vc.OBSERVE_FIELD_REFERENCES)

    def test_observation_context_contract_structure(self):
        contract = self.vc.OBSERVATION_CONTEXT_CONTRACT
        parameter_binding = self.vc.OBSERVATION_PARAMETER_BINDING_CONTRACT

        self.assertEqual(contract.fields, self.vc.OBSERVATION_CONTEXT_FIELDS)
        self.assertEqual(
            contract.parameters_field,
            self.vc.OBSERVATION_CONTEXT_FIELD_PARAMETERS,
        )
        self.assertIs(contract.parameter_binding, parameter_binding)
        self.assertEqual(parameter_binding.fields, self.vc.OBSERVATION_PARAMETER_FIELDS)
        self.assertEqual(
            parameter_binding.id_field,
            self.vc.OBSERVATION_PARAMETER_FIELD_ID,
        )
        self.assertEqual(
            parameter_binding.name_field,
            self.vc.OBSERVATION_PARAMETER_FIELD_NAME,
        )
        self.assertEqual(
            parameter_binding.group_name_field,
            self.vc.OBSERVATION_PARAMETER_FIELD_GROUP_NAME,
        )

    def test_expected_contract_structure(self):
        contract = self.vc.EXPECTED_CONTRACT

        self.assertEqual(contract.fields, self.vc.EXPECTED_FIELDS)
        self.assertEqual(contract.components_field, self.vc.EXPECTED_FIELD_COMPONENTS)
        self.assertEqual(contract.parameters_field, self.vc.EXPECTED_FIELD_PARAMETERS)
        self.assertEqual(contract.metadata_field, self.vc.EXPECTED_FIELD_METADATA)
        self.assertEqual(contract.references_field, self.vc.EXPECTED_FIELD_REFERENCES)
        self.assertIs(contract.component, self.vc.EXPECTED_COMPONENT_CONTRACT)
        self.assertIs(contract.parameter, self.vc.EXPECTED_PARAMETER_CONTRACT)
        self.assertIs(contract.metadata, self.vc.EXPECTED_METADATA_CONTRACT)
        self.assertIs(contract.reference, self.vc.EXPECTED_REFERENCE_CONTRACT)

    def test_expected_nested_contract_structure(self):
        component = self.vc.EXPECTED_COMPONENT_CONTRACT
        parameter = self.vc.EXPECTED_PARAMETER_CONTRACT
        metadata = self.vc.EXPECTED_METADATA_CONTRACT
        reference = self.vc.EXPECTED_REFERENCE_CONTRACT

        self.assertEqual(component.fields, self.vc.EXPECTED_COMPONENT_FIELDS)
        self.assertEqual(component.id_field, self.vc.EXPECTED_COMPONENT_FIELD_ID)
        self.assertEqual(component.kind_field, self.vc.EXPECTED_COMPONENT_FIELD_KIND)
        self.assertEqual(component.name_field, self.vc.EXPECTED_COMPONENT_FIELD_NAME)
        self.assertEqual(
            component.parent_id_field,
            self.vc.EXPECTED_COMPONENT_FIELD_PARENT_ID,
        )
        self.assertEqual(
            component.supported_kinds,
            self.vc.SUPPORTED_EXPECTED_COMPONENT_KINDS,
        )

        self.assertEqual(parameter.fields, self.vc.EXPECTED_PARAMETER_FIELDS)
        self.assertEqual(parameter.id_field, self.vc.EXPECTED_PARAMETER_FIELD_ID)
        self.assertEqual(parameter.name_field, self.vc.EXPECTED_PARAMETER_FIELD_NAME)
        self.assertEqual(parameter.type_field, self.vc.EXPECTED_PARAMETER_FIELD_TYPE)
        self.assertEqual(parameter.unit_field, self.vc.EXPECTED_PARAMETER_FIELD_UNIT)
        self.assertEqual(parameter.value_field, self.vc.EXPECTED_PARAMETER_FIELD_VALUE)
        self.assertEqual(
            parameter.supported_types,
            self.vc.SUPPORTED_EXPECTED_PARAMETER_TYPES,
        )
        self.assertEqual(
            parameter.supported_units,
            self.vc.SUPPORTED_EXPECTED_PARAMETER_UNITS,
        )

        self.assertEqual(metadata.fields, self.vc.EXPECTED_METADATA_FIELDS)
        self.assertEqual(metadata.id_field, self.vc.EXPECTED_METADATA_FIELD_ID)
        self.assertEqual(metadata.key_field, self.vc.EXPECTED_METADATA_FIELD_KEY)
        self.assertEqual(
            metadata.owner_id_field,
            self.vc.EXPECTED_METADATA_FIELD_OWNER_ID,
        )
        self.assertEqual(metadata.value_field, self.vc.EXPECTED_METADATA_FIELD_VALUE)
        self.assertEqual(
            metadata.value_kind_field,
            self.vc.EXPECTED_METADATA_FIELD_VALUE_KIND,
        )
        self.assertEqual(
            metadata.supported_value_kinds,
            self.vc.SUPPORTED_EXPECTED_METADATA_VALUE_KINDS,
        )

        self.assertEqual(reference.fields, self.vc.EXPECTED_REFERENCE_FIELDS)
        self.assertEqual(reference.kind_field, self.vc.EXPECTED_REFERENCE_FIELD_KIND)
        self.assertEqual(reference.name_field, self.vc.EXPECTED_REFERENCE_FIELD_NAME)

    def test_checks_contract_structure(self):
        contract = self.vc.CHECKS_CONTRACT
        check = self.vc.CHECK_CONTRACT

        self.assertEqual(contract.fields, self.vc.CHECKS_FIELDS)
        self.assertEqual(contract.components_field, self.vc.CHECKS_FIELD_COMPONENTS)
        self.assertEqual(contract.parameters_field, self.vc.CHECKS_FIELD_PARAMETERS)
        self.assertEqual(contract.metadata_field, self.vc.CHECKS_FIELD_METADATA)
        self.assertEqual(contract.references_field, self.vc.CHECKS_FIELD_REFERENCES)
        self.assertIs(contract.check, check)
        self.assertEqual(check.fields, self.vc.CHECK_FIELDS)
        self.assertEqual(check.enabled_field, self.vc.CHECK_FIELD_ENABLED)


class TestPublicApiSurface(_ContractTestCase):
    def test_all_includes_expected_public_symbols(self):
        expected_symbols = {
            "PARAMETRON_VERIFICATION_FILENAME",
            "PARAMETRON_VERIFICATION_SCHEMA_VERSION",
            "FIELD_SCHEMA_VERSION",
            "FIELD_OBSERVE",
            "FIELD_OBSERVATION_CONTEXT",
            "FIELD_EXPECTED",
            "FIELD_CHECKS",
            "TOP_LEVEL_FIELDS",
            "REQUIRED_TOP_LEVEL_FIELDS",
            "OPTIONAL_TOP_LEVEL_FIELDS",
            "OBSERVE_FIELDS",
            "OBSERVATION_CONTEXT_FIELDS",
            "OBSERVATION_PARAMETER_FIELDS",
            "EXPECTED_FIELDS",
            "EXPECTED_COMPONENT_FIELDS",
            "EXPECTED_PARAMETER_FIELDS",
            "EXPECTED_METADATA_FIELDS",
            "EXPECTED_REFERENCE_FIELDS",
            "CHECKS_FIELDS",
            "CHECK_FIELDS",
            "SUPPORTED_EXPECTED_COMPONENT_KINDS",
            "SUPPORTED_EXPECTED_PARAMETER_TYPES",
            "SUPPORTED_EXPECTED_PARAMETER_UNITS",
            "SUPPORTED_EXPECTED_METADATA_VALUE_KINDS",
            "ObservationParameterBindingContract",
            "ObservationContextContract",
            "ObserveContract",
            "ExpectedComponentContract",
            "ExpectedParameterContract",
            "ExpectedMetadataContract",
            "ExpectedReferenceContract",
            "ExpectedContract",
            "CheckContract",
            "ChecksContract",
            "VerificationContract",
            "OBSERVATION_PARAMETER_BINDING_CONTRACT",
            "OBSERVATION_CONTEXT_CONTRACT",
            "OBSERVE_CONTRACT",
            "EXPECTED_COMPONENT_CONTRACT",
            "EXPECTED_PARAMETER_CONTRACT",
            "EXPECTED_METADATA_CONTRACT",
            "EXPECTED_REFERENCE_CONTRACT",
            "EXPECTED_CONTRACT",
            "CHECK_CONTRACT",
            "CHECKS_CONTRACT",
            "PARAMETRON_VERIFICATION_CONTRACT",
            "supported_observation_categories",
            "supported_expected_component_kinds",
            "supported_expected_parameter_types",
            "supported_expected_parameter_units",
            "supported_expected_metadata_value_kinds",
        }

        self.assertLessEqual(expected_symbols, set(self.vc.__all__))

    def test_all_does_not_include_future_scope_apis(self):
        denied_names = {
            "load_parametron_verification",
            "load_verification_contract",
            "validate_parametron_verification",
            "validate_verification_contract",
            "observe_parameters",
            "observe_metadata",
            "observe_references",
            "write_observed_json",
            "verify_observed",
            "compare_observed",
        }

        self.assertTrue(denied_names.isdisjoint(set(self.vc.__all__)))

    def test_module_does_not_define_scope_creep_apis(self):
        denied_callable_names = (
            "load_parametron_verification",
            "load_verification_contract",
            "parse_parametron_verification",
            "parse_verification_contract",
            "validate_parametron_verification",
            "validate_verification_contract",
            "observe_components",
            "observe_parameters",
            "observe_metadata",
            "observe_references",
            "write_observed_json",
            "verify_observed",
            "compare_observed",
            "accept_observed",
            "reject_observed",
        )

        for name in denied_callable_names:
            with self.subTest(name=name):
                self.assertFalse(
                    callable(getattr(self.vc, name, None)),
                    f"Contract module must not define callable '{name}'",
                )


if __name__ == "__main__":
    unittest.main()
