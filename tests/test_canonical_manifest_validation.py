"""Closed canonical schema-1 mutation contract, with one canonical version."""
import copy

import pytest

from parametron_freecad.execution.manifest_validation import validate_export_manifest_v1


def manifest(**sections):
    return dict(schemaVersion='1.0', sourceDocument='model.FCStd',
                parameterAssignments=[], outputs=[], **sections)


@pytest.mark.parametrize('scope', ['assemblyMutations', 'partMutations'])
@pytest.mark.parametrize('section', [{}, {'suppression': []}, {'visibility': []}, {'deletion': []},
    {'suppression': [{'object': 'Z', 'suppressed': True}, {'object': 'A', 'suppressed': False}],
     'visibility': [{'object': 'Z', 'visible': False}, {'object': 'A', 'visible': True}],
     'deletion': [{'object': 'Other'}]}])
def test_optional_empty_sparse_and_combined_sections(scope, section):
    payload = manifest(**{scope: section})
    original = copy.deepcopy(payload)
    assert validate_export_manifest_v1(payload).is_valid
    assert payload == original


def test_absent_and_coexisting_sections():
    assert validate_export_manifest_v1(manifest()).is_valid
    assert validate_export_manifest_v1(manifest(
        assemblyMutations={'suppression': [{'object': 'Asm', 'suppressed': True}]},
        partMutations={'visibility': [{'object': 'Part', 'visible': False}]})).is_valid


@pytest.mark.parametrize('scope', ['assemblyMutations', 'partMutations'])
@pytest.mark.parametrize('family', ['parameters', 'properties', 'actions', 'keep', 'force'])
def test_only_three_mutation_families(scope, family):
    result = validate_export_manifest_v1(manifest(**{scope: {family: []}}))
    assert [(d.code, d.path) for d in result.diagnostics] == [
        ('unknown_mutation_collection', f'{scope}.{family}')]


@pytest.mark.parametrize('family,field', [('suppression', 'suppressed'), ('visibility', 'visible')])
@pytest.mark.parametrize('value', [0, 1, 'true', 'false', None, [], {}])
def test_strict_json_boolean(family, field, value):
    result = validate_export_manifest_v1(manifest(partMutations={family: [{'object': 'A', field: value}]}))
    assert not result.is_valid
    assert [(d.code, d.path) for d in result.diagnostics] == [
        ('invalid_mutation_entry_field_type', f'partMutations.{family}[0].{field}')]


@pytest.mark.parametrize('family,entry', [
    ('suppression', {'object': 'A', 'suppressed': True}),
    ('visibility', {'object': 'A', 'visible': False}), ('deletion', {'object': 'A'})])
@pytest.mark.parametrize('extra', ['force', 'cascade', 'targetKind', 'action'])
def test_entry_shapes_are_closed(family, entry, extra):
    result = validate_export_manifest_v1(manifest(partMutations={family: [{**entry, extra: True}]}))
    assert not result.is_valid
    assert any(d.path == f'partMutations.{family}[0].{extra}' for d in result.diagnostics)


@pytest.mark.parametrize('family,entry', [
    ('suppression', {'object': 'A', 'suppressed': True}),
    ('visibility', {'object': 'A', 'visible': False}), ('deletion', {'object': 'A'})])
def test_duplicate_objects_rejected(family, entry):
    result = validate_export_manifest_v1(manifest(partMutations={family: [entry, dict(entry)]}))
    assert [d.code for d in result.diagnostics] == ['duplicate_mutation_object']


@pytest.mark.parametrize('family,entry', [
    ('suppression', {'object': 'A', 'suppressed': True}),
    ('visibility', {'object': 'A', 'visible': False})])
def test_deletion_conflicts_rejected(family, entry):
    result = validate_export_manifest_v1(manifest(partMutations={family: [entry], 'deletion': [{'object': 'A'}]}))
    assert [d.code for d in result.diagnostics] == ['mutation_family_conflict']


@pytest.mark.parametrize('assembly_family,assembly_entry', [
    ('suppression', {'object': 'A', 'suppressed': True}),
    ('visibility', {'object': 'A', 'visible': False}), ('deletion', {'object': 'A'})])
@pytest.mark.parametrize('part_family,part_entry', [
    ('suppression', {'object': 'A', 'suppressed': False}),
    ('visibility', {'object': 'A', 'visible': True}), ('deletion', {'object': 'A'})])
def test_cross_scope_conflicts(assembly_family, assembly_entry, part_family, part_entry):
    result = validate_export_manifest_v1(manifest(
        assemblyMutations={assembly_family: [assembly_entry]}, partMutations={part_family: [part_entry]}))
    assert [d.code for d in result.diagnostics] == ['cross_scope_mutation_object_conflict']


def test_diagnostics_follow_contract_order_without_mutating_input():
    # Reverse mapping insertion order and deliberately non-alphabetical arrays.
    section = {'deletion': [{'object': ''}], 'visibility': [{'object': 'Z', 'visible': 1}],
               'suppression': [{'object': 'Z', 'suppressed': 1}, {'object': 'A', 'suppressed': 0}]}
    payload = manifest(partMutations=copy.deepcopy(section), assemblyMutations=copy.deepcopy(section))
    original = copy.deepcopy(payload)
    first = validate_export_manifest_v1(payload)
    second = validate_export_manifest_v1(copy.deepcopy(original))
    assert first == second
    paths = [d.path for d in first.diagnostics]
    structural = [p for p in paths if p.endswith(('.suppressed', '.visible'))]
    assert structural == [f'{scope}.{suffix}' for scope in ('assemblyMutations', 'partMutations')
        for suffix in ('suppression[0].suppressed', 'suppression[1].suppressed', 'visibility[0].visible')]
    assert payload == original
