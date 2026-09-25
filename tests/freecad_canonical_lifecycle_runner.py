"""Test-only host proving pristine, live, closed, and reopened native states."""
from dataclasses import replace
import json
import sys
from pathlib import Path

import FreeCAD

from parametron_freecad.runtime import entrypoints

PARAMETERS = ('boxLength', 'boxWidth', 'boxHeight', 'holeDia', 'boxChamfer')


def snapshot(document):
    return {
        'parameters': {name: getattr(document.getObject('VarSet'), name).Value for name in PARAMETERS},
        'suppression': {name: document.getObject(name).Suppressed for name in ('Fillet', 'Pocket001')},
        'visibility': {name: document.getObject(name).Visibility for name in
                       ('Body', 'Body001', 'Chamfer', 'Pad002', 'Body003')},
        'Body002_exists': document.getObject('Body002') is not None,
    }


def main():
    root = Path(next(arg[7:] for arg in sys.argv if arg.startswith('--pass=')))
    manifest = json.loads((root / 'prm.export-manifest.json').read_text())
    source = root / manifest['sourceDocument']
    document = FreeCAD.openDocument(str(source))
    try:
        for name in ('Body', 'Body001', 'Body002', 'Body003', 'Chamfer', 'Fillet', 'Pocket001', 'Pad002', 'VarSet'):
            assert document.getObject(name).Name == name
        for name in ('Body002', 'Body003'):
            body = document.getObject(name)
            assert body.TypeId == 'PartDesign::Body'
            assert not body.Shape.isNull() and body.Shape.isValid()
            assert body.Tip is not None
        assert document.getObject('Body002').InList == []
        before = snapshot(document)
        assert before['parameters'] == dict(zip(PARAMETERS, (50, 30, 40, 12, 3)))
        assert before['suppression'] == {'Fillet': False, 'Pocket001': True}
        assert before['visibility']['Body003'] is True
        assert before['Body002_exists'] is True
    finally:
        FreeCAD.closeDocument(document.Name)

    live = []

    def observe(document, request, **kwargs):
        live.append(snapshot(document))
        assert not (root / 'prm.result.json').exists()
        entrypoints.run_observation_entrypoint(document, request, **kwargs)

    def success(path, outputs):
        assert not FreeCAD.listDocuments(), 'document must be closed before success emission'
        assert not Path(path).exists()
        entrypoints.write_success_result(path, outputs)

    entrypoints.run_execution_entrypoint(
        working_copy=root, manifest_path=root / 'prm.export-manifest.json',
        result_path=root / 'prm.result.json', output_directory=root / 'outputs',
        observation_request_path=root / 'prm.verification.json',
        reference_traversal_request_path=root / 'prm.reference-traversal-request.json',
        freecad_module=FreeCAD,
        _dependencies=replace(entrypoints._ExecutionEntrypointDependencies(),
                              run_observation_entrypoint=observe, write_success_result=success),
    )
    assert not FreeCAD.listDocuments()
    assert json.loads((root / 'prm.result.json').read_text())['status'] == 'succeeded'
    document = FreeCAD.openDocument(str(source))
    try:
        persisted = snapshot(document)
        assert live == [persisted], 'persisted state must equal the live observation state'
    finally:
        FreeCAD.closeDocument(document.Name)
    (root / 'native-facts.json').write_text(json.dumps(persisted, sort_keys=True))


try:
    main()
except Exception:
    import traceback
    traceback.print_exc()
    raise
