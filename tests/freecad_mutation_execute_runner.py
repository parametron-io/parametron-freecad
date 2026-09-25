"""Real FreeCAD host for production execute and independent native inspection."""
import json
import sys
from pathlib import Path

import FreeCAD

from parametron_freecad.execution.post_mutation_validity import inspect_document_post_mutation_validity
from parametron_freecad.runtime.entrypoints import run_execution_entrypoint

passed = [arg[7:] for arg in sys.argv if arg.startswith('--pass=')]
root = Path(passed[0])
mode = passed[1]
source = root / 'partdesign-mutations.FCStd'


def inspect(document):
    names = ('IntermediatePad', 'TerminalChamfer', 'MutationBody', 'BaseSketch', 'SafeDeleteMarker')
    state = {}
    for name in names:
        target = document.getObject(name)
        state[name] = None if target is None else {
            'suppressed': target.Suppressed if 'Suppressed' in target.PropertiesList else None,
            'visible': target.Visibility if 'Visibility' in target.PropertiesList else None,
            'visibilityType': target.getTypeIdOfProperty('Visibility') if 'Visibility' in target.PropertiesList else None,
            'dependents': sorted(item.Name for item in target.InList),
        }
    return state


def read_source():
    document = FreeCAD.openDocument(str(source))
    try:
        return inspect(document)
    finally:
        FreeCAD.closeDocument(document.Name)

before = read_source()
if mode == 'invalid':
    document = FreeCAD.openDocument(str(source))
    try:
        document.addObject('PartDesign::Body', 'EmptyBody')
        document.recompute()
        document.save()
    finally:
        FreeCAD.closeDocument(document.Name)
    before = read_source()

error = None
try:
    run_execution_entrypoint(
        working_copy=root,
        manifest_path=root / 'prm.export-manifest.json',
        result_path=root / 'prm.result.json',
        output_directory=root / 'outputs',
        observation_request_path=root / 'prm.verification.json',
        freecad_module=FreeCAD,
    )
except Exception as exc:
    error = {'type': type(exc).__name__, 'message': str(exc),
             'cause': type(exc.__cause__).__name__ if exc.__cause__ else None,
             'causeMessage': str(exc.__cause__) if exc.__cause__ else None}

closed = not FreeCAD.listDocuments()
reopened = read_source()
document = FreeCAD.openDocument(str(source))
try:
    try:
        validity = [item.__dict__ if hasattr(item, '__dict__') else str(item)
                    for item in inspect_document_post_mutation_validity(document)]
        valid = True
    except Exception as exc:
        validity = {'type': type(exc).__name__, 'message': str(exc)}
        valid = False
finally:
    FreeCAD.closeDocument(document.Name)
assert not FreeCAD.listDocuments()
(root / 'native-facts.json').write_text(json.dumps({
    'before': before, 'reopened': reopened, 'closed': closed, 'error': error,
    'valid': valid, 'validity': validity, 'freecadVersion': FreeCAD.Version(),
}, sort_keys=True))
