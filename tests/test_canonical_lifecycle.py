"""Canonical Engine inputs and integrated native lifecycle proof.

Input provenance (all three engine_generated JSON files):
Engine e261458a34014caff64802bf2467e07a0532f906; source is the committed
fixtures/canonical_lifecycle/parametron.project.json and cube.project.dsl.
Source cube.FCStd SHA-256:
9376277c131ac3f361f05412b3a6b455f8574eabf99f1e02d1fa75d3fca82250
Generated SHA-256 (copied bytes were compared with the materialized files):
prm.export-manifest.json: 7937493ef734357210cde34fb0ec93c6c1c0535049e9f2f56414e29b0d5efc1f
prm.verification.json: a528a6e95f9d6f7b443699929efb60bb0b12c11cd8182d31fa96628c0fb0f6f3
prm.reference-traversal-request.json: 98d84dbf3bcd5d5175f4e7e8f4bb0cfa49b2449e815b861eb1890b9bd8ca596c
From Engine's fresh Nix shell:
  go build -o /tmp/freecad-issue6-repaired/parametron ./cmd/parametron
  cd /tmp/freecad-issue6-repaired
  PARAMETRON_FREECAD_RUNTIME=/tmp/freecad-issue6-capture/runtime ./parametron \
    --project /home/emreg/Documents/Work/parametron-freecad/tests/fixtures/canonical_lifecycle \
    --out /tmp/freecad-issue6-repaired/output
The temporary executable logs argv and exits 23, deliberately without CAD or
result/evidence output. Normal orchestration first calls
cadruntime.WriteFreeCADRuntimeObservationRequest -> freecad.WriteFreeCADRuntimeManifest
-> ComposeFreeCADRuntimeManifest, and cadruntime.WriteFreeCADReferenceTraversalRequest materializes traversal input.
The three files passed to the runtime were copied byte-for-byte, unchanged.
The observation reference retains Engine's absolute materialization path;
FreeCAD observes the supplied working-copy root, not Engine verification policy.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path(__file__).parent / 'fixtures' / 'engine_generated'
SOURCE = Path(__file__).parent / 'fixtures' / 'canonical_lifecycle' / 'input' / 'cube.FCStd'


def test_engine_inputs_load_directly():
    from parametron_freecad.execution.manifest_loader import load_export_manifest_v1
    from parametron_freecad.execution.manifest_validation import validate_export_manifest_v1
    from parametron_freecad.runtime.entrypoints import load_observation_request, load_reference_traversal_request
    loaded = load_export_manifest_v1(CORPUS / 'prm.export-manifest.json')
    assert validate_export_manifest_v1(loaded.data).is_valid
    assert loaded.data['schemaVersion'] == '1.0'
    assert loaded.data['sourceDocument'] == 'source/cube.FCStd'
    assert loaded.data['outputs'] == []
    assert set(loaded.data) == {'schemaVersion', 'sourceDocument', 'outputs', 'parameterAssignments', 'partMutations'}
    assert [x['target'] for x in loaded.data['parameterAssignments']] == [
        'VarSet.boxChamfer', 'VarSet.boxHeight', 'VarSet.boxLength', 'VarSet.boxWidth', 'VarSet.holeDia']
    request = load_observation_request(CORPUS / 'prm.verification.json')
    assert request['observe']['targetState'] is True
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert request['expected']['metadata'] == [
        {'key': 'working_copy_sha256', 'value': source_hash}]
    capture = json.loads((SOURCE.parent.parent / 'parametron.cad.json').read_text())
    assert capture['sourceDocument']['fingerprint'] == 'sha256:' + source_hash
    load_reference_traversal_request(CORPUS / 'prm.reference-traversal-request.json')
    assert sorted(p.name for p in CORPUS.iterdir()) == [
        'prm.export-manifest.json', 'prm.reference-traversal-request.json', 'prm.verification.json']


def run_native(root, delete, ordinary=False):
    host = shutil.which(os.environ.get('PARAMETRON_FREECAD_BIN', 'freecadcmd'))
    if host is None:
        if os.environ.get('PARAMETRON_FREECAD_STRICT_SMOKE') == '1':
            pytest.fail('FreeCAD host unavailable')
        pytest.skip('FreeCAD host unavailable')
    root.mkdir()
    (root / 'source').mkdir()
    (root / 'outputs').mkdir()
    shutil.copyfile(SOURCE, root / 'source/cube.FCStd')
    for path in CORPUS.iterdir():
        shutil.copyfile(path, root / path.name)
    if not delete:
        path = root / 'prm.export-manifest.json'
        data = json.loads(path.read_text())
        del data['partMutations']['deletion']
        path.write_text(json.dumps(data))
    if ordinary:
        path = root / 'prm.export-manifest.json'
        data = json.loads(path.read_text())
        del data['partMutations']
        path.write_text(json.dumps(data))
        path = root / 'prm.verification.json'
        request = json.loads(path.read_text())
        request['observe']['targetState'] = False
        del request['observationContext']['targetState']
        # The existing parameter observer supports scalars, not native Quantity.
        # Geometry-driving lengths are independently inspected via .Value.
        request['observe']['parameters'] = True
        request['observationContext']['parameters'] = [
            {'id': 'varset-label', 'name': 'Label', 'groupName': 'VarSet'}]
        path.write_text(json.dumps(request))
    process = subprocess.run([host, '-P', str(ROOT),
        str(ROOT / 'tests/freecad_canonical_lifecycle_runner.py'), f'--pass={root}'],
        capture_output=True, text=True, timeout=90)
    assert (root / 'native-facts.json').exists(), process.stdout + process.stderr
    assert 'Exception while processing file' not in process.stderr
    facts = json.loads((root / 'native-facts.json').read_text())
    assert facts == {
        'parameters': {'boxLength': 80, 'boxWidth': 50, 'boxHeight': 60, 'holeDia': 18, 'boxChamfer': 5},
        'suppression': {'Fillet': not ordinary, 'Pocket001': ordinary},
        'visibility': {'Body': True, 'Body001': True, 'Chamfer': True, 'Pad002': True, 'Body003': ordinary},
        'Body002_exists': not delete,
    }
    result = json.loads((root / 'prm.result.json').read_text())
    assert result == {'schemaVersion': '1.0', 'status': 'succeeded', 'artifacts': []}
    observed = json.loads((root / 'outputs/prm.observed.json').read_text())
    assert observed['schemaVersion'] == '1.0'
    assert observed['workingCopy'] == {
        'path': str(root), 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest()}
    observation = observed['observation']
    assert observation['references'] == [{'kind': 'working_copy_path', 'name': str(root)}]
    assert observation['metadata'][0]['value'] == observed['workingCopy']['sha256']
    if ordinary:
        assert 'targetState' not in observation
        assert observation['parameters'][0]['id'] == 'varset-label'
        assert observation['parameters'][0]['value'] == 'box_body'
    else:
        assert observation['targetState'] == {
            'suppression': [
                {'destination': 'part', 'object': 'Fillet', 'status': 'observed', 'value': True},
                {'destination': 'part', 'object': 'Pocket001', 'status': 'observed', 'value': False}],
            'visibility': [
                {'destination': 'part', 'object': name, 'status': 'observed', 'value': visible}
                for name, visible in [('Body', True), ('Body001', True), ('Body003', False),
                                      ('Chamfer', True), ('Pad002', True)]],
            'existence': [{'destination': 'part', 'object': 'Body002',
                           'status': 'absent' if delete else 'exists'}],
        }
    from parametron_freecad.runtime.reference_traversal_request import REFERENCE_TRAVERSAL_OUTPUT_FILENAME
    traversal = json.loads((root / 'outputs' / REFERENCE_TRAVERSAL_OUTPUT_FILENAME).read_text())
    assert traversal['status'] == 'succeeded'
    return facts, result, observed


@pytest.mark.parametrize('delete', [True, False], ids=['canonical', 'Body002-no-delete'])
def test_native_lifecycle_persistence_and_repeatability(tmp_path, delete):
    before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    try:
        first = run_native(tmp_path / 'first', delete)
        second = run_native(tmp_path / 'second', delete)
        assert first[:2] == second[:2]
        assert first[2]['observation']['targetState'] == second[2]['observation']['targetState']
    finally:
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == before


def test_native_ordinary_execution_and_non_target_observation(tmp_path):
    before = SOURCE.read_bytes()
    try:
        run_native(tmp_path / 'ordinary', delete=False, ordinary=True)
    finally:
        assert SOURCE.read_bytes() == before
