"""Production orchestration with real mutation consumers and instrumented CAD APIs.

Only export/traversal/observation adapters are injected. Assignment, suppression,
visibility, deletion (including its internal recompute/validity), save, close,
manifest loading/validation, and result serialization use production code.
"""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

CORPUS = Path(__file__).parent / 'fixtures' / 'engine_generated'


def mutations(prefix, families):
    values = {
        'suppression': [{'object': prefix + 'S2', 'suppressed': True}, {'object': prefix + 'S1', 'suppressed': False}],
        'visibility': [{'object': prefix + 'V2', 'visible': False}, {'object': prefix + 'V1', 'visible': True}],
        'deletion': [{'object': prefix + 'D2'}, {'object': prefix + 'D1'}],
    }
    # Reverse dictionary order deliberately; collection order must remain intact.
    return {family: values[family] for family in reversed(families)}


def payload(assembly=(), part=()):
    return {'schemaVersion': '1.0', 'sourceDocument': 'model.FCStd',
        'parameterAssignments': [{'target': 'Parameters.Length', 'value': 80, 'valueKind': 'float'}],
        'outputs': [], 'partMutations': mutations('P', part), 'assemblyMutations': mutations('A', assembly)}


class NativeObject:
    PropertiesList = ['Suppressed', 'Visibility', 'Length']
    InList = ()
    OutList = ()

    def __init__(self, name, event):
        self.Name = name
        self.event = event
        self.__dict__.update(Suppressed=False, Visibility=True, Length=1)

    def isDerivedFrom(self, type_name):
        return self.Name == 'Health' and type_name == 'PartDesign::Body'

    def getTypeIdOfProperty(self, name):
        return 'App::PropertyBool'

    def __setattr__(self, name, value):
        family = {'Suppressed': 'suppression', 'Visibility': 'visibility', 'Length': 'assignment'}.get(name)
        if family:
            self.event(f'{family}:{self.Name}')
        object.__setattr__(self, name, value)


class Harness:
    def __init__(self, root, data, fail=None, close_failure=False):
        from parametron_freecad.runtime import entrypoints as ep
        self.ep = ep
        self.root = root
        root.mkdir()
        (root / 'outputs').mkdir()
        (root / 'model.FCStd').write_bytes(b'pristine source')
        (root / 'prm.export-manifest.json').write_text(json.dumps(data))
        for name in ('prm.verification.json', 'prm.reference-traversal-request.json'):
            (root / name).write_bytes((CORPUS / name).read_bytes())
        self.events = []
        self.fail = fail
        self.original = RuntimeError('native original cause')
        self.close_failure = close_failure
        self.closed = False
        self.data = copy.deepcopy(data)
        names = ['Parameters', 'Health'] + [p + f + n for p in 'AP' for f in 'SVD' for n in '21']
        self.objects = {name: NativeObject(name, self.event) for name in names}
        self.objects['Health'].Shape = SimpleNamespace(
            isNull=lambda: (self.event('validity'), False)[1],
            isValid=lambda: True, Solids=[object()])
        # Live object inventory matters after deletion.
        class Document:
            @property
            def Objects(inner):
                return list(self.objects.values())
        Document.Name = 'Doc'
        Document.getObject = lambda inner, name: self.objects.get(name)
        Document.removeObject = lambda inner, name: self.remove(name)
        Document.recompute = lambda inner: self.event('recompute')
        Document.save = lambda inner: self.save()
        self.document = Document()
        self.module = SimpleNamespace(openDocument=self.open, closeDocument=self.close)
        self.dependencies = ep._ExecutionEntrypointDependencies(
            export_step_artifacts=self.export('step'), export_csv_artifacts=self.export('csv'),
            export_pdf_artifacts=self.export('pdf'), run_reference_traversal=self.traverse,
            run_observation_entrypoint=self.observe, write_success_result=self.success)

    def event(self, event):
        self.events.append(event)
        if event == self.fail:
            raise self.original

    def open(self, path):
        assert Path(path) == self.root / 'model.FCStd'
        self.event('open')
        return self.document

    def remove(self, name):
        self.event(f'deletion:{name}')
        del self.objects[name]

    def save(self):
        self.event('save')
        self.saved = {name: (obj.Length, obj.Suppressed, obj.Visibility) for name, obj in self.objects.items()}

    def close(self, name):
        assert name == 'Doc'
        self.event('close')
        if self.close_failure:
            raise RuntimeError('secondary close failure')
        self.closed = True

    def export(self, name):
        def run(document, outputs, *, working_copy):
            assert document is self.document and working_copy == self.root
            expected_length = 80 if self.data['parameterAssignments'] else 1
            assert self.saved['Parameters'][0] == expected_length
            self.event(name)
        return run

    def traverse(self, document, request, **kwargs):
        assert document is self.document
        self.event('traversal')
        return SimpleNamespace(status='succeeded', nodes=(), edges=(), diagnostics=())

    def observe(self, document, request, **kwargs):
        assert document is self.document
        assert self.saved == {name: (obj.Length, obj.Suppressed, obj.Visibility) for name, obj in self.objects.items()}
        assert not (self.root / 'prm.result.json').exists()
        try:
            self.event('observation')
        except RuntimeError as exc:
            raise self.ep.ObservationEntrypointError('observation failed') from exc

    def success(self, path, outputs):
        assert self.closed
        self.event('success')
        self.ep.write_success_result(path, outputs)

    def run(self):
        # A poison pill proves normal execute never invokes legacy translation.
        with mock.patch('parametron_freecad.execution.engine_manifest_compat.normalize_loaded_export_manifest_v1',
                        side_effect=AssertionError('legacy translation invoked')):
            self.ep.run_execution_entrypoint(working_copy=self.root,
                manifest_path=self.root / 'prm.export-manifest.json', result_path=self.root / 'prm.result.json',
                output_directory=self.root / 'outputs', observation_request_path=self.root / 'prm.verification.json',
                reference_traversal_request_path=self.root / 'prm.reference-traversal-request.json',
                freecad_module=self.module, _dependencies=self.dependencies)

    def result(self):
        return json.loads((self.root / 'prm.result.json').read_text())


# Expectations explicitly enumerate native calls, including BOTH checks for
# two deletions. No expected event list is derived from the runtime helper.
CASES = [
    ((), (), ['recompute']),
    ((), ('suppression',), ['suppression:PS2', 'suppression:PS1', 'recompute', 'validity']),
    ((), ('visibility',), ['visibility:PV2', 'visibility:PV1', 'recompute', 'validity']),
    ((), ('deletion',), ['deletion:PD2', 'recompute', 'validity', 'deletion:PD1', 'recompute', 'validity']),
    ((), ('suppression', 'visibility', 'deletion'), ['suppression:PS2', 'suppression:PS1',
        'visibility:PV2', 'visibility:PV1', 'deletion:PD2', 'recompute', 'validity',
        'deletion:PD1', 'recompute', 'validity']),
    (('deletion',), ('visibility',), ['deletion:AD2', 'recompute', 'validity',
        'deletion:AD1', 'recompute', 'validity', 'visibility:PV2', 'visibility:PV1', 'recompute', 'validity']),
    (('deletion',), ('suppression',), ['deletion:AD2', 'recompute', 'validity',
        'deletion:AD1', 'recompute', 'validity', 'suppression:PS2', 'suppression:PS1', 'recompute', 'validity']),
    (('suppression', 'visibility', 'deletion'), ('suppression', 'visibility', 'deletion'),
        ['suppression:AS2', 'suppression:AS1', 'visibility:AV2', 'visibility:AV1',
         'deletion:AD2', 'recompute', 'validity', 'deletion:AD1', 'recompute', 'validity',
         'suppression:PS2', 'suppression:PS1', 'visibility:PV2', 'visibility:PV1',
         'deletion:PD2', 'recompute', 'validity', 'deletion:PD1', 'recompute', 'validity']),
]


@pytest.mark.parametrize('assembly,part,expected', CASES)
def test_exact_lifecycle_order_and_repeatability(tmp_path, assembly, part, expected):
    outcomes = []
    for run in ('first', 'second'):
        harness = Harness(tmp_path / run, payload(assembly, part))
        harness.run()
        assert harness.events == ['open', 'assignment:Parameters', *expected,
            'save', 'step', 'csv', 'pdf', 'traversal', 'observation', 'close', 'success']
        assert harness.result() == {'schemaVersion': '1.0', 'status': 'succeeded', 'artifacts': []}
        outcomes.append((harness.events, harness.result()))
    assert outcomes[0] == outcomes[1]


FAILURES = [
    ('assignment:Parameters', 'parameter_assignment'), ('suppression:PS2', 'suppression'),
    ('visibility:PV2', 'visibility'), ('deletion:PD2', 'deletion'),
    ('recompute', 'recompute'), ('validity', 'post_mutation_validity'),
    ('save', 'document_save'), ('observation', 'observation'), ('close', 'document_close')]


@pytest.mark.parametrize('failure,stage', FAILURES)
@pytest.mark.parametrize('with_deletion', [False, True])
def test_required_failure_stops_later_stages_and_preserves_cause(tmp_path, failure, stage, with_deletion):
    # Include deletion when it is the failing stage; otherwise exercise validity
    # both through final recompute and through deletion's internal safety check.
    families = ('suppression', 'visibility', 'deletion') if with_deletion or stage == 'deletion' else ('suppression', 'visibility')
    results = []
    for run in ('first', 'second'):
        harness = Harness(tmp_path / run, payload(part=families), fail=failure)
        with pytest.raises(harness.ep.ExecutionEntrypointError) as caught:
            harness.run()
        cause = caught.value
        chain = []
        while cause is not None:
            chain.append(cause)
            cause = cause.__cause__
        assert harness.original in chain
        index = harness.events.index(failure)
        assert harness.events[index + 1:] == ([] if failure == 'close' else ['close'])
        assert 'success' not in harness.events
        result = harness.result()
        assert result['status'] == 'failed' and 'artifacts' not in result
        assert result['failure']['stage'] == stage
        assert result['failure']['boundary'] == 'execution_entrypoint'
        assert result['failure']['code'] == 'runtime_failure'
        results.append((harness.events, result))
    assert results[0] == results[1]


def test_execution_failure_remains_primary_when_cleanup_and_result_emission_fail(tmp_path):
    from parametron_freecad.execution.result_writer import ResultWriteError
    harness = Harness(tmp_path / 'run', payload(part=('suppression',)),
                      fail='suppression:PS2', close_failure=True)
    with mock.patch.object(harness.ep, 'write_failure_result',
                           side_effect=ResultWriteError('disk unavailable')) as writer:
        with pytest.raises(harness.ep.ExecutionEntrypointError) as caught:
            harness.run()
    writer.assert_called_once()
    assert writer.call_args.args[1].stage == 'suppression'
    primary = caught.value.__cause__
    assert primary.__cause__ is harness.original
    assert any('cleanup also failed' in note for note in primary.__notes__)
    assert harness.events == ['open', 'assignment:Parameters', 'suppression:PS2', 'close']
    assert not (harness.root / 'prm.result.json').exists()


def test_execution_failure_stage_survives_close_failure(tmp_path):
    harness = Harness(tmp_path / 'run', payload(part=('visibility',)),
                      fail='visibility:PV2', close_failure=True)
    with pytest.raises(harness.ep.ExecutionEntrypointError) as caught:
        harness.run()
    assert caught.value.__cause__.__cause__ is harness.original
    assert harness.result()['failure']['stage'] == 'visibility'
    assert harness.events == ['open', 'assignment:Parameters', 'visibility:PV2', 'close']


@pytest.mark.parametrize('change,stage', [
    ({'schemaVersion': '2.0'}, 'manifest_validation'),
    ({'partMutations': {'visibility': [{'object': 'PV2', 'visible': 1}]}}, 'manifest_validation'),
    ({'sourceDocument': '../outside.FCStd'}, 'source_document_resolution')])
def test_invalid_contract_and_containment_fail_before_native_open(tmp_path, change, stage):
    harness = Harness(tmp_path / 'run', {**payload(part=('suppression',)), **change})
    with pytest.raises(harness.ep.ExecutionEntrypointError):
        harness.run()
    assert harness.events == []
    assert harness.result()['failure']['stage'] == stage


def test_empty_ordinary_request_has_one_recompute_and_no_validity_requirement(tmp_path):
    data = payload()
    data['parameterAssignments'] = []
    del data['assemblyMutations'], data['partMutations']
    harness = Harness(tmp_path / 'run', data)
    # Ordinary execution must not acquire the target-mutation validity policy.
    harness.objects['Health'].Shape.isNull = lambda: True
    harness.run()
    assert harness.events == ['open', 'recompute', 'save', 'step', 'csv', 'pdf',
                              'traversal', 'observation', 'close', 'success']


@pytest.mark.parametrize('with_deletion', [False, True])
def test_invalid_native_shape_stops_persistence(tmp_path, with_deletion):
    families = ('deletion',) if with_deletion else ('visibility',)
    harness = Harness(tmp_path / 'run', payload(part=families))
    harness.objects['Health'].Shape.isValid = lambda: False
    with pytest.raises(harness.ep.ExecutionEntrypointError):
        harness.run()
    assert harness.result()['failure']['stage'] == 'post_mutation_validity'
    assert harness.events[-2:] == ['validity', 'close']
    assert 'save' not in harness.events and 'success' not in harness.events


def test_unsafe_deletion_rejects_surviving_dependents_before_removal(tmp_path):
    harness = Harness(tmp_path / 'run', payload(part=('deletion',)))
    harness.objects['PD2'].InList = [harness.objects['Health']]
    with pytest.raises(harness.ep.ExecutionEntrypointError):
        harness.run()
    assert harness.result()['failure']['stage'] == 'deletion'
    assert harness.events == ['open', 'assignment:Parameters', 'close']
    assert harness.document.getObject('PD2') is not None
    assert harness.document.getObject('PD1') is not None
