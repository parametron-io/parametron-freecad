"""Semantic-name and stable-ID policy for captured Parametron entities.

Semantic names are user-authored. The capture core never derives a semantic
name from a native object name, label, CAD type, geometry, or ``nativeRef``.
Names are exact and case-sensitive: no trimming, case folding, or Unicode
normalization is applied. A semantic name must be a DSL identifier:

* nonblank, with no leading/trailing whitespace and no NUL;
* the first character must be a letter;
* every remaining character must be a letter, a decimal digit, or ``_``.

The name is unique across captured components and features (the target
namespace) and unique across parameters (the parameter namespace). A collision
is a hard capture error. No automatic suffix is ever added.

Stable IDs are generated deterministically from the semantic name and the
structural scope. The identifier convention is:

=======================  =====================================================
Entity                   Identifier
=======================  =====================================================
Component                ``cmp.<nameSlug>``
Feature                  ``fea.<componentSlug>.<nameSlug>``
Parameter group          ``grp.<ownerSlug>.<nameSlug>``
Parameter                ``par.<ownerSlug>.<nameSlug>``
Group-owned parameter    ``par.<ownerSlug>.<groupSlug>.<nameSlug>``
Metadata                 ``meta.<ownerSlug>.<keySlug>``
Relationship             ``rel.<ownerSlug>.<nameSlug>``
Drawing                  ``drw.<nameSlug>``
Drawing sheet            ``sht.<drawingSlug>.<nameSlug>``
=======================  =====================================================

``nameSlug`` lowercases the first character of the semantic name and preserves
the remaining characters. ``ownerSlug`` and ``componentSlug`` are the final
dot-delimited segment of the owning entity ID (for example, ``cmp.root`` gives
``root``). ``groupSlug`` is the final segment of the parameter group ID.
``keySlug`` lowercases the first character of the exact native metadata key and
replaces every character outside letters, decimal digits, and ``_`` with ``_``.

Examples consistent with the committed capture fixtures:

* ``Enclosure`` -> ``cmp.enclosure``
* ``Pad`` in ``cmp.enclosure`` -> ``fea.enclosure.pad``
* ``VarSet`` owned by ``cmp.root`` -> ``grp.root.varSet``
* group-owned ``pilotValue`` -> ``par.root.varSet.pilotValue``
* ``material`` on ``cmp.enclosure`` -> ``meta.enclosure.material``
* ``Manufacturing`` drawing -> ``drw.manufacturing``
* ``Assembly`` sheet in ``drw.manufacturing`` -> ``sht.manufacturing.assembly``

An explicit advanced ID override is accepted instead of a generated ID. It must
be exact and unique, but it need not follow the generation convention; the
committed fixtures use overrides such as ``cmp.root`` and
``fea.targetObject.targetBody``. IDs are never derived from ``nativeRef``. A
generated or explicit ID collision is a hard error and is never repaired with a
suffix.
"""

from __future__ import annotations

from collections.abc import Mapping

from parametron_freecad.capture.errors import (
    CaptureIdPolicyError,
    CaptureNamePolicyError,
)

# Registries that participate in target-name and parameter-name uniqueness.
_TARGET_NAME_REGISTRIES = ("components", "features")
_NAMED_ENTITY_REGISTRIES = (
    "components",
    "features",
    "relationships",
    "parameterGroups",
    "parameters",
    "drawings",
)
_ALL_ID_REGISTRIES = (
    "components",
    "features",
    "relationships",
    "parameterGroups",
    "parameters",
    "metadata",
    "drawings",
)


def validate_semantic_name(name: str, *, entity_path: str = "name") -> str:
    """Validate one user-authored semantic name and return it unchanged."""

    if not isinstance(name, str):
        raise CaptureNamePolicyError(
            f"semantic name policy violation at {entity_path}: name must be a string"
        )
    if name == "" or name.strip() == "":
        raise CaptureNamePolicyError(
            f"semantic name policy violation at {entity_path}: name must be nonblank"
        )
    if name != name.strip():
        raise CaptureNamePolicyError(
            f"semantic name policy violation at {entity_path}: "
            "name must not have leading or trailing whitespace"
        )
    if "\x00" in name:
        raise CaptureNamePolicyError(
            f"semantic name policy violation at {entity_path}: "
            "name must not contain NUL"
        )

    first = name[0]
    if not first.isalpha():
        raise CaptureNamePolicyError(
            f"semantic name policy violation at {entity_path}: "
            "name must start with a letter"
        )
    for index, character in enumerate(name[1:], start=1):
        if not (character.isalpha() or character.isdecimal() or character == "_"):
            raise CaptureNamePolicyError(
                f"semantic name policy violation at {entity_path}: "
                f"name character at index {index} must be a letter, digit, "
                "or underscore"
            )
    return name


def semantic_name_slug(name: str, *, entity_path: str = "name") -> str:
    """Return the deterministic lowerCamel identifier slug for a semantic name."""

    validated = validate_semantic_name(name, entity_path=entity_path)
    return validated[:1].lower() + validated[1:]


def validate_explicit_id(identifier: str, *, entity_path: str = "id") -> str:
    """Validate one explicit stable ID and return it unchanged."""

    if not isinstance(identifier, str):
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: id must be a string"
        )
    if identifier == "" or identifier.strip() == "":
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: id must be nonblank"
        )
    if identifier != identifier.strip():
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: "
            "id must not have leading or trailing whitespace"
        )
    if "\x00" in identifier:
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: id must not contain NUL"
        )
    return identifier


def _scope_slug(identifier: str, *, entity_path: str) -> str:
    validate_explicit_id(identifier, entity_path=entity_path)
    return identifier.rsplit(".", 1)[-1]


def _require_exact_native_key(key: str, *, entity_path: str) -> str:
    if not isinstance(key, str):
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: "
            "metadata key must be a string"
        )
    if key == "" or key.strip() == "":
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: "
            "metadata key must be nonblank"
        )
    if key != key.strip():
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: "
            "metadata key must not have leading or trailing whitespace"
        )
    if "\x00" in key:
        raise CaptureIdPolicyError(
            f"stable ID policy violation at {entity_path}: "
            "metadata key must not contain NUL"
        )
    return key


def native_key_slug(key: str, *, entity_path: str = "key") -> str:
    """Return the deterministic identifier slug for an exact native metadata key."""

    validated = _require_exact_native_key(key, entity_path=entity_path)
    parts: list[str] = []
    for index, character in enumerate(validated):
        if character.isalpha() or character.isdecimal() or character == "_":
            parts.append(character[:1].lower() if index == 0 else character)
        else:
            parts.append("_")
    return "".join(parts)


def generate_component_id(
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``cmp.<nameSlug>`` for a component semantic name."""

    return f"cmp.{semantic_name_slug(name, entity_path=entity_path)}"


def generate_feature_id(
    component_id: str,
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``fea.<componentSlug>.<nameSlug>`` for a feature."""

    component_slug = _scope_slug(component_id, entity_path="componentId")
    return f"fea.{component_slug}.{semantic_name_slug(name, entity_path=entity_path)}"


def generate_parameter_group_id(
    owner_component_id: str,
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``grp.<ownerSlug>.<nameSlug>`` for a parameter group."""

    owner_slug = _scope_slug(owner_component_id, entity_path="ownerComponentId")
    return f"grp.{owner_slug}.{semantic_name_slug(name, entity_path=entity_path)}"


def generate_parameter_id(
    owner_id: str,
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``par.<ownerSlug>.<nameSlug>`` for a component/feature parameter."""

    owner_slug = _scope_slug(owner_id, entity_path="ownerId")
    return f"par.{owner_slug}.{semantic_name_slug(name, entity_path=entity_path)}"


def generate_group_owned_parameter_id(
    owner_component_id: str,
    group_id: str,
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``par.<ownerSlug>.<groupSlug>.<nameSlug>`` for a group parameter."""

    owner_slug = _scope_slug(owner_component_id, entity_path="componentId")
    group_slug = _scope_slug(group_id, entity_path="ownerId")
    return (
        f"par.{owner_slug}.{group_slug}."
        f"{semantic_name_slug(name, entity_path=entity_path)}"
    )


def generate_metadata_id(
    owner_id: str,
    key: str,
    *,
    entity_path: str = "key",
) -> str:
    """Return ``meta.<ownerSlug>.<keySlug>`` for metadata."""

    owner_slug = _scope_slug(owner_id, entity_path="ownerId")
    return f"meta.{owner_slug}.{native_key_slug(key, entity_path=entity_path)}"


def generate_relationship_id(
    owner_component_id: str,
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``rel.<ownerSlug>.<nameSlug>`` for a relationship."""

    owner_slug = _scope_slug(owner_component_id, entity_path="componentId")
    return f"rel.{owner_slug}.{semantic_name_slug(name, entity_path=entity_path)}"


def generate_drawing_id(
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``drw.<nameSlug>`` for a drawing semantic name."""

    return f"drw.{semantic_name_slug(name, entity_path=entity_path)}"


def generate_drawing_sheet_id(
    drawing_id: str,
    name: str,
    *,
    entity_path: str = "name",
) -> str:
    """Return ``sht.<drawingSlug>.<nameSlug>`` for a drawing sheet."""

    drawing_slug = _scope_slug(drawing_id, entity_path="drawingId")
    return f"sht.{drawing_slug}.{semantic_name_slug(name, entity_path=entity_path)}"


def validate_capture_policy(value: object) -> None:
    """Apply semantic-name and stable-ID policy to a shape-valid capture draft."""

    if not isinstance(value, Mapping):
        raise CaptureNamePolicyError(
            "semantic name policy violation at root: capture draft must be an object"
        )

    _validate_names(value)
    _validate_ids(value)


def _validate_names(value: Mapping) -> None:
    entities = value["entities"]

    for registry in _NAMED_ENTITY_REGISTRIES:
        for index, entity in enumerate(entities[registry]):
            path = f"entities.{registry}[{index}].name"
            validate_semantic_name(entity["name"], entity_path=path)

    target_names: dict[str, str] = {}
    for registry in _TARGET_NAME_REGISTRIES:
        for index, entity in enumerate(entities[registry]):
            path = f"entities.{registry}[{index}].name"
            name = entity["name"]
            previous = target_names.get(name)
            if previous is not None:
                raise CaptureNamePolicyError(
                    f"semantic name policy violation at {path}: "
                    f'name "{name}" collides with {previous}'
                )
            target_names[name] = path

    parameter_names: dict[str, str] = {}
    for index, parameter in enumerate(entities["parameters"]):
        path = f"entities.parameters[{index}].name"
        name = parameter["name"]
        previous = parameter_names.get(name)
        if previous is not None:
            raise CaptureNamePolicyError(
                f"semantic name policy violation at {path}: "
                f'name "{name}" collides with {previous}'
            )
        parameter_names[name] = path

    drawing_names: dict[str, str] = {}
    for index, drawing in enumerate(entities["drawings"]):
        path = f"entities.drawings[{index}].name"
        name = drawing["name"]
        previous = drawing_names.get(name)
        if previous is not None:
            raise CaptureNamePolicyError(
                f"semantic name policy violation at {path}: "
                f'name "{name}" collides with {previous}'
            )
        drawing_names[name] = path

        sheet_names: dict[str, str] = {}
        for sheet_index, sheet in enumerate(drawing["sheets"]):
            sheet_path = f"entities.drawings[{index}].sheets[{sheet_index}].name"
            sheet_name = sheet["name"]
            validate_semantic_name(sheet_name, entity_path=sheet_path)
            previous = sheet_names.get(sheet_name)
            if previous is not None:
                raise CaptureNamePolicyError(
                    f"semantic name policy violation at {sheet_path}: "
                    f'name "{sheet_name}" collides with {previous}'
                )
            sheet_names[sheet_name] = sheet_path


def _validate_ids(value: Mapping) -> None:
    entities = value["entities"]
    seen: dict[str, str] = {}

    for registry in _ALL_ID_REGISTRIES:
        for index, entity in enumerate(entities[registry]):
            path = f"entities.{registry}[{index}].id"
            identifier = validate_explicit_id(entity["id"], entity_path=path)
            previous = seen.get(identifier)
            if previous is not None:
                raise CaptureIdPolicyError(
                    f"stable ID policy violation at {path}: "
                    f'id "{identifier}" collides with {previous}'
                )
            seen[identifier] = path

    for drawing_index, drawing in enumerate(entities["drawings"]):
        for sheet_index, sheet in enumerate(drawing["sheets"]):
            path = f"entities.drawings[{drawing_index}].sheets[{sheet_index}].id"
            identifier = validate_explicit_id(sheet["id"], entity_path=path)
            previous = seen.get(identifier)
            if previous is not None:
                raise CaptureIdPolicyError(
                    f"stable ID policy violation at {path}: "
                    f'id "{identifier}" collides with {previous}'
                )
            seen[identifier] = path


__all__ = [
    "generate_component_id",
    "generate_drawing_id",
    "generate_drawing_sheet_id",
    "generate_feature_id",
    "generate_group_owned_parameter_id",
    "generate_metadata_id",
    "generate_parameter_group_id",
    "generate_parameter_id",
    "generate_relationship_id",
    "native_key_slug",
    "semantic_name_slug",
    "validate_capture_policy",
    "validate_explicit_id",
    "validate_semantic_name",
]
