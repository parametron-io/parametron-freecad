"""Semantic-name and stable-ID policy tests for the GUI-free capture core."""

from __future__ import annotations

import copy
import unittest

from capture_support import valid_mapping

from parametron_freecad.capture import (
    CaptureIdPolicyError,
    CaptureNamePolicyError,
    generate_component_id,
    generate_feature_id,
    generate_group_owned_parameter_id,
    generate_metadata_id,
    generate_parameter_group_id,
    generate_parameter_id,
    generate_relationship_id,
    native_key_slug,
    semantic_name_slug,
    validate_capture_document,
    validate_explicit_id,
    validate_semantic_name,
)


class SemanticNameRulesTests(unittest.TestCase):
    def test_accepts_dsl_identifier_names(self) -> None:
        for name in ("Enclosure", "boxLength", "a1_B2", "Oz", "ölçü"):
            with self.subTest(name=name):
                self.assertEqual(validate_semantic_name(name), name)

    def test_rejects_blank_whitespace_and_nul(self) -> None:
        for name in (
            "",
            "   ",
            " Enclosure",
            "Enclosure ",
            "En\tclosure",
            "En\x00closure",
        ):
            with self.subTest(name=repr(name)):
                with self.assertRaises(CaptureNamePolicyError):
                    validate_semantic_name(
                        name, entity_path="entities.features[0].name"
                    )

    def test_rejects_names_not_matching_dsl_identifier_rules(self) -> None:
        for name in (
            "1Enclosure",
            "_Enclosure",
            "En-closure",
            "En closure",
            "En.closure",
        ):
            with self.subTest(name=name):
                with self.assertRaises(CaptureNamePolicyError):
                    validate_semantic_name(
                        name, entity_path="entities.features[0].name"
                    )

    def test_error_message_contains_entity_path(self) -> None:
        with self.assertRaises(CaptureNamePolicyError) as raised:
            validate_semantic_name("1Bad", entity_path="entities.components[2].name")
        self.assertIn("entities.components[2].name", str(raised.exception))
        self.assertIn("must start with a letter", str(raised.exception))

    def test_name_validation_is_case_sensitive_and_does_not_normalize(self) -> None:
        self.assertEqual(validate_semantic_name("Enclosure"), "Enclosure")
        self.assertEqual(validate_semantic_name("enclosure"), "enclosure")
        self.assertNotEqual(
            validate_semantic_name("Enclosure"),
            validate_semantic_name("enclosure"),
        )


class StableIdGenerationTests(unittest.TestCase):
    def test_name_slug_lowercases_only_the_first_character(self) -> None:
        self.assertEqual(semantic_name_slug("Enclosure"), "enclosure")
        self.assertEqual(semantic_name_slug("boxLength"), "boxLength")
        self.assertEqual(semantic_name_slug("VarSet"), "varSet")
        self.assertEqual(semantic_name_slug("A_B2"), "a_B2")

    def test_generated_ids_follow_the_documented_convention(self) -> None:
        self.assertEqual(generate_component_id("Enclosure"), "cmp.enclosure")
        self.assertEqual(
            generate_feature_id("cmp.enclosure", "Pad"),
            "fea.enclosure.pad",
        )
        self.assertEqual(
            generate_parameter_group_id("cmp.root", "VarSet"),
            "grp.root.varSet",
        )
        self.assertEqual(
            generate_parameter_id("cmp.enclosure", "length"),
            "par.enclosure.length",
        )
        self.assertEqual(
            generate_parameter_id("fea.enclosure.pad", "thickness"),
            "par.pad.thickness",
        )
        self.assertEqual(
            generate_group_owned_parameter_id(
                "cmp.root",
                "grp.root.varSet",
                "pilotValue",
            ),
            "par.root.varSet.pilotValue",
        )
        self.assertEqual(
            generate_metadata_id("cmp.enclosure", "material"),
            "meta.enclosure.material",
        )
        self.assertEqual(
            generate_metadata_id("fea.enclosure.pad", "tagged"),
            "meta.pad.tagged",
        )
        self.assertEqual(
            generate_relationship_id("cmp.root", "mount"),
            "rel.root.mount",
        )

    def test_metadata_key_slug_is_deterministic_for_native_keys(self) -> None:
        self.assertEqual(native_key_slug("material"), "material")
        self.assertEqual(native_key_slug("Tagged"), "tagged")
        self.assertEqual(native_key_slug("My Key"), "my_Key")
        self.assertEqual(native_key_slug("a.b"), "a_b")
        with self.assertRaises(CaptureIdPolicyError):
            native_key_slug(" material")
        with self.assertRaises(CaptureIdPolicyError):
            native_key_slug("material\x00")

    def test_ids_are_not_derived_from_native_refs(self) -> None:
        self.assertEqual(generate_component_id("Enclosure"), "cmp.enclosure")
        self.assertNotEqual(generate_component_id("Enclosure"), "cmp.Body")
        self.assertNotIn("MetadataBody", generate_component_id("Enclosure"))

    def test_explicit_override_is_validated_but_not_convention_bound(self) -> None:
        self.assertEqual(
            validate_explicit_id("cmp.root", entity_path="entities.components[0].id"),
            "cmp.root",
        )
        self.assertEqual(
            validate_explicit_id(
                "advanced.custom.id",
                entity_path="entities.components[0].id",
            ),
            "advanced.custom.id",
        )
        for invalid in ("", "   ", " id", "id ", "id\x00"):
            with self.subTest(identifier=repr(invalid)):
                with self.assertRaises(CaptureIdPolicyError):
                    validate_explicit_id(
                        invalid,
                        entity_path="entities.components[0].id",
                    )


class CapturePolicyCollisionTests(unittest.TestCase):
    def test_component_and_feature_name_collision_is_hard_error(self) -> None:
        payload = valid_mapping()
        payload["entities"]["features"][0]["name"] = "Enclosure"

        with self.assertRaises(CaptureNamePolicyError) as raised:
            validate_capture_document(payload)

        message = str(raised.exception)
        self.assertIn("entities.features[0].name", message)
        self.assertIn("entities.components[1].name", message)
        self.assertIn('"Enclosure"', message)
        self.assertNotIn("-2", message)

    def test_parameter_name_collision_is_hard_error(self) -> None:
        payload = valid_mapping()
        second = copy.deepcopy(payload["entities"]["parameters"][0])
        second["id"] = "par.root.parameters.length2"
        second["identitySource"]["ownerScopedKey"] = "length2"
        second["identitySource"]["groupScopedKey"] = "length2"
        payload["entities"]["parameters"].append(second)

        with self.assertRaises(CaptureNamePolicyError) as raised:
            validate_capture_document(payload)

        message = str(raised.exception)
        self.assertIn("entities.parameters[1].name", message)
        self.assertIn("entities.parameters[0].name", message)
        self.assertIn('"length"', message)

    def test_names_in_different_namespaces_do_not_collide(self) -> None:
        payload = valid_mapping()
        payload["entities"]["parameters"][0]["name"] = "Enclosure"
        payload["entities"]["parameters"][0]["id"] = "par.root.parameters.Enclosure"

        validate_capture_document(payload)

    def test_generated_id_collision_from_case_differing_names_is_hard_error(
        self,
    ) -> None:
        payload = valid_mapping()
        # Names are unique because the target namespace is case-sensitive.
        payload["entities"]["components"][0]["name"] = "Enclosure"
        payload["entities"]["components"][1]["name"] = "enclosure"
        payload["entities"]["components"][0]["id"] = generate_component_id("Enclosure")
        payload["entities"]["components"][1]["id"] = generate_component_id("enclosure")

        with self.assertRaises(CaptureIdPolicyError) as raised:
            validate_capture_document(payload)

        message = str(raised.exception)
        self.assertIn("entities.components[0].id", message)
        self.assertIn("entities.components[1].id", message)
        self.assertIn('"cmp.enclosure"', message)
        self.assertNotIn("-2", message)

    def test_duplicate_id_across_registries_is_hard_error(self) -> None:
        payload = valid_mapping()
        payload["entities"]["features"][0]["id"] = "cmp.part"

        with self.assertRaises(CaptureIdPolicyError) as raised:
            validate_capture_document(payload)

        message = str(raised.exception)
        self.assertIn("entities.features[0].id", message)
        self.assertIn("entities.components[1].id", message)
        self.assertIn('"cmp.part"', message)

    def test_explicit_id_with_surrounding_whitespace_is_hard_error(self) -> None:
        payload = valid_mapping()
        payload["entities"]["components"][1]["id"] = " cmp.part"

        with self.assertRaises(CaptureIdPolicyError) as raised:
            validate_capture_document(payload)

        self.assertIn("entities.components[1].id", str(raised.exception))
        self.assertIn("leading or trailing whitespace", str(raised.exception))

    def test_policy_failure_is_deterministic(self) -> None:
        payload = valid_mapping()
        payload["entities"]["features"][0]["id"] = "cmp.part"

        messages = []
        for _ in range(2):
            with self.assertRaises(CaptureIdPolicyError) as raised:
                validate_capture_document(copy.deepcopy(payload))
            messages.append(str(raised.exception))
        self.assertEqual(messages[0], messages[1])


if __name__ == "__main__":
    unittest.main()
