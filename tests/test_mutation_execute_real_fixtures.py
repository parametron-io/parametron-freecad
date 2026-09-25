"""Gated production execute proof against the committed native PartDesign fixture."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / 'fixtures/partdesign_mutations/partdesign-mutations.FCStd'
RUNNER = Path(__file__).parent / 'freecad_mutation_execute_runner.py'


def host():
    configured = os.environ.get('PARAMETRON_FREECAD_BIN', 'freecadcmd')
    found = shutil.which(configured)
    if found is None:
        if os.environ.get('PARAMETRON_FREECAD_STRICT_SMOKE') == '1':
            pytest.fail(f'real FreeCAD host unavailable: {configured}')
        pytest.skip(f'real FreeCAD host unavailable: {configured}')
    return found


def run_case(root, mutations, *, mode='normal'):
    executable = host()
    root.mkdir()
    (root / 'outputs').mkdir()
    shutil.copyfile(FIXTURE, root / FIXTURE.name)
    manifest = {'schemaVersion': '1.0', 'sourceDocument': FIXTURE.name,
                'parameterAssignments': [], 'partMutations': mutations, 'outputs': []}
    (root / 'prm.export-manifest.json').write_text(json.dumps(manifest))
    names = {'suppression': ('IntermediatePad', 'TerminalChamfer', 'BaseSketch'),
             'visibility': ('MutationBody', 'BaseSketch'),
             'existence': ('SafeDeleteMarker', 'BaseSketch')}
    request = {'schemaVersion': '1.0',
               'observe': {'components': False, 'parameters': False, 'metadata': False,
                           'references': False, 'targetState': True},
               'observationContext': {'parameters': [], 'targetState': {
                   family: [{'destination': 'part', 'object': name} for name in values]
                   for family, values in names.items()}},
               'expected': {'components': [], 'parameters': [], 'metadata': [], 'references': []},
               'checks': {family: {'enabled': False} for family in
                          ('components', 'parameters', 'metadata', 'references')}}
    (root / 'prm.verification.json').write_text(json.dumps(request))
    completed = subprocess.run([executable, '-P', str(ROOT), str(RUNNER),
                                f'--pass={root}', f'--pass={mode}'],
                               capture_output=True, text=True, timeout=90)
    assert 'Exception while processing file' not in completed.stderr, completed.stderr
    assert (root / 'native-facts.json').exists(), completed.stdout + completed.stderr
    facts = json.loads((root / 'native-facts.json').read_text())
    result = json.loads((root / 'prm.result.json').read_text())
    observed_path = root / 'outputs/prm.observed.json'
    observed = json.loads(observed_path.read_text()) if observed_path.exists() else None
    return facts, result, observed


def assert_observation_matches_native(facts, observed):
    assert observed['schemaVersion'] == '1.0'
    state = observed['observation']['targetState']
    native = facts['reopened']
    for family, property_name in (('suppression', 'suppressed'), ('visibility', 'visible')):
        for item in state[family]:
            target = native[item['object']]
            if target is None:
                assert item['status'] == 'target_missing'
            elif target[property_name] is None:
                assert item['status'] == 'unavailable'
            else:
                assert item['status'] == 'observed'
                assert item['value'] is target[property_name]
    for item in state['existence']:
        assert item['status'] == ('exists' if native[item['object']] else 'absent')


def test_production_suppress_unsuppress_hide_unhide_delete_and_repeat(tmp_path):
    source_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    mutations = {'suppression': [{'object': 'IntermediatePad', 'suppressed': True},
                                 {'object': 'TerminalChamfer', 'suppressed': False}],
                 'visibility': [{'object': 'MutationBody', 'visible': False},
                                {'object': 'BaseSketch', 'visible': True}],
                 'deletion': [{'object': 'SafeDeleteMarker'}]}
    outcomes = []
    for name in ('first', 'second'):
        facts, result, observed = run_case(tmp_path / name, mutations)
        assert facts['closed'] and facts['valid'], facts
        before, after = facts['before'], facts['reopened']
        assert before['IntermediatePad']['suppressed'] is False
        assert after['IntermediatePad']['suppressed'] is True
        assert before['TerminalChamfer']['suppressed'] is True
        assert after['TerminalChamfer']['suppressed'] is False
        assert before['MutationBody']['visible'] is True
        assert after['MutationBody']['visible'] is False
        assert before['BaseSketch']['visible'] is False
        assert after['BaseSketch']['visible'] is True
        assert after['BaseSketch']['visibilityType'] == 'App::PropertyBool'
        assert before['SafeDeleteMarker'] is not None
        assert after['SafeDeleteMarker'] is None
        assert result == {'schemaVersion': '1.0', 'status': 'succeeded', 'artifacts': []}
        assert_observation_matches_native(facts, observed)
        outcomes.append((after, facts['validity'], result, observed['observation']['targetState'],
                         sorted(path.name for path in (tmp_path / name / 'outputs').iterdir())))
    assert outcomes[0] == outcomes[1]
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == source_hash


def test_production_unsafe_deletion_rejected_with_native_dependency(tmp_path):
    source_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    outcomes = []
    for name in ('first', 'second'):
        facts, result, observed = run_case(tmp_path / name,
                                          {'deletion': [{'object': 'BaseSketch'}]})
        assert facts['closed'] and facts['valid']
        assert 'IntermediatePad' in facts['before']['BaseSketch']['dependents']
        assert facts['reopened'] == facts['before']
        assert facts['error']['cause'] == 'UnsafeDeletionTargetError'
        assert result['status'] == 'failed' and 'artifacts' not in result
        assert result['failure']['stage'] == 'deletion'
        assert 'IntermediatePad' in result['failure']['message']
        assert observed is None
        outcomes.append((facts['reopened'], result))
    assert outcomes[0] == outcomes[1]
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == source_hash


def test_production_native_validity_failure_stops_save_and_observation(tmp_path):
    source_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    facts, result, observed = run_case(tmp_path / 'invalid',
                                      {'visibility': [{'object': 'BaseSketch', 'visible': True}]},
                                      mode='invalid')
    assert facts['closed'] and not facts['valid']
    assert facts['validity']['type'] == 'InvalidNativeCadStateError'
    assert facts['before'] == facts['reopened']
    assert facts['error']['cause'] == 'InvalidNativeCadStateError'
    assert result['status'] == 'failed' and 'artifacts' not in result
    assert result['failure']['stage'] == 'post_mutation_validity'
    assert 'EmptyBody' in result['failure']['message']
    assert observed is None
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == source_hash
