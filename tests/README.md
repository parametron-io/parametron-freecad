# Tests

## Running the suite

Syntax and import check (from the repository root):

```
python -m compileall parametron_freecad scripts tests
```

Full test suite:

```
python -m pytest
```

These commands require a Python/FreeCAD environment providing this package
(see the "FreeCAD dependency" section below). This repository's `flake.nix`
provides one reproducible such environment (`nix develop`), but any equivalent
environment satisfying the same requirements works.

## FreeCAD dependency

Most tests run under ordinary Python and do not require a FreeCAD installation. Fake-FreeCAD module injection is used to test the document lifecycle, headless runtime, parameter assignment, document recompute, and artifact export boundaries without a real FreeCAD process.

The complete `tests/fixtures/reference_traversal/` directory is the portable
real reference-traversal fixture unit; `reference-root.FCStd` depends on its
`references/` sibling directory. The real fixture tests copy that complete
bundle to an arbitrary temporary location and use FreeCAD directly to verify
the persisted internal and external links without a traversal request or
`externalTargets` mappings. They run in the normal Nix suite when the repository
FreeCAD wrapper and `freecadcmd` are available. The same suite runs fresh bundle
copies through public `parametron-freecad execute` in independent flat and nested
working roots and compares the emitted canonical traversal bytes with frozen
evidence across runs. Maintain a semantic replacement bundle in a new directory with:

```
nix develop --command freecadcmd scripts/generate_reference_traversal_fixtures.py --pass=/absolute/new/output-directory
```

Generated `.FCStd` archive bytes need not match; the real fixture tests compare
their semantic traversal output. Tracked fixtures must remain byte-for-byte
unchanged during tests.

The committed `tests/fixtures/assembly_occurrence/` and
`tests/fixtures/fact_evidence/` bundles are real FreeCAD provenance fixtures
tracked with Git LFS. Regenerate them only through the Nix environment and the
FreeCAD host, writing to an absolute destination that does not yet exist:

```
nix develop --command freecadcmd scripts/generate_assembly_occurrence_fixtures.py --pass=/absolute/occurrence-fixtures
nix develop --command freecadcmd scripts/generate_fact_evidence_fixtures.py --pass=/absolute/fact-fixtures
```

Generation is semantically reproducible; `.FCStd` archive bytes are not
expected to be identical across runs. The real-FreeCAD evidence suites consume
their request sidecars at the working-copy root and their integrity request
through `PARAMETRON_RUNTIME_INTEGRITY_REQUEST`, and require an existing
`--output-dir` inside the attempt:

```
nix develop --command env PARAMETRON_FREECAD_STRICT_SMOKE=1 \
  python -m pytest \
  tests/test_occurrence_real_fixtures.py \
  tests/test_fact_real_fixtures.py \
  tests/test_integrity_real_fixtures.py \
  tests/test_evidence_lifecycle_real.py -q
```

`PARAMETRON_FREECAD_STRICT_SMOKE=1` makes a missing wrapper, host, or
LFS-fetched fixture bundle a failure instead of a skip.

Environment-gated real-FreeCAD rehearsals require a usable public
`parametron-freecad` wrapper and native host. They do not fall back to direct
Python entrypoint execution when the wrapper is unavailable:

- `PARAMETRON_FREECAD_BIN` selects the native host; when unset, the launcher and
  rehearsals use `freecadcmd` from `PATH`.
- In normal development mode, a missing or unusable wrapper or host skips the
  native rehearsal. A skip supplies no evidence that native behavior passed.
- `PARAMETRON_FREECAD_STRICT_SMOKE=1` requires usable native prerequisites;
  their absence or failure makes validation unsuccessful rather than skipped.

The Nix development environment supplies the intended wrapper and host for
strict native validation. The ordinary Python and fake-FreeCAD tests do not
require real FreeCAD.

The ordinary native execute rehearsal runs the public `parametron-freecad execute`
wrapper independently from fresh copies of the canonical lifecycle fixture in
flat and nested arbitrary working roots, with `outputs: []`. Each saved `.FCStd`
is reopened by a separate real-FreeCAD inspection process. The test compares
persisted parameter values and canonical result bytes across runs, checks that
the result contains no working-root or fixture paths, and confirms the committed
fixture hash is unchanged. This is native working-document persistence, not a
derived-output rehearsal; successful results contain `artifacts: []`. It does
not compare generated `.FCStd` archive bytes.

The same rehearsal also invokes the public wrapper twice with independent,
existing invalid `.FCStd` files and `outputs: []`. Real FreeCAD rejects each
native open, and the canonical failed `prm.result.json` retains the
`document_open` classification and native diagnostic. The test compares stable
failure semantics across the two working roots.
It also runs a schema-valid assignment to a missing native object against fresh
copies of the valid `.FCStd` fixture in two working roots. Each execution reaches
`parameter_assignment`, emits a failed canonical result with the target and
missing-object diagnostic, and preserves the committed fixture bytes.
These are representative native failures. Other controlled-failure stages have
separate lower-layer coverage; this rehearsal does not establish exhaustive
real-native failure conformance.

Run it with `python -m pytest
tests/test_execute_real_rehearsal.py`; set `PARAMETRON_FREECAD_STRICT_SMOKE=1`
to require the wrapper and real FreeCAD host.

## Engine evidence acceptance proof

The cross-repository occurrence, fact, and integrity acceptance proof is
Engine-owned. This repository supplies the production launcher and the real
Assembly/property fixtures; the proof delegates request composition, strict
evidence intake, normalization, quantity rollup, and integrity provenance to the
sibling `parametron-engine` proof harness. The final acceptance step uses Engine
validators and real FreeCAD 1.1.4, never a fake runtime.

From the repository root, with a sibling `parametron-engine` checkout and `nix`
available:

```bash
nix develop --command python scripts/run_engine_evidence_proof.py \
  --engine-repo ../parametron-engine \
  --workspace /tmp/parametron-evidence-proof \
  --report /tmp/parametron-evidence-proof/proof-report.json
```

The command prints a bounded accepted-evidence summary and exits non-zero if
Engine does not accept the evidence. The report records the Engine proof
scenarios, the accepted ten-occurrence quantity, explicit mixed/unavailable/
unsupported states, required-fact and baseline-mismatch stages, multi-outcome
evidence, and the documented FreeCAD executor-layout blocker.

Opt-in pytest rehearsal:

```bash
nix develop --command env PARAMETRON_RUN_ENGINE_EVIDENCE_PROOF=1 \
  python -m pytest tests/test_engine_evidence_proof.py -q
```

The proof requires the Engine 1.1.4 evidence harness and Git LFS fixtures. It is
deliberately opt-in because it builds and runs the Engine proof against real
FreeCAD. Complete occurrence acceptance is proven through the Engine
fixture-layout cadruntime path because FreeCAD resolves stored external link
targets relative to the source document while the normal executor materializes
the source at `source/<basename>`. The blocker is part of the Engine proof
report and is not hidden or replaced by a FreeCAD-only acceptance check.

## Test coverage areas

- Canonical JSON helpers (`test_canonical_json.py`)
- Path and working-copy boundary helpers (`test_paths.py`)
- Headless invocation and optional FreeCAD smoke (`test_headless_invocation.py`)
- Headless CLI argument surface and execute-mode integration (`test_headless_cli_arguments.py`)
- Process exit code taxonomy (`test_exit_codes.py`)
- FreeCAD document lifecycle context manager (`test_document_lifecycle.py`)
- Manifest contract definitions (`test_manifest_contract.py`)
- Strict manifest loader (`test_manifest_loader.py`)
- Structural manifest validation (`test_manifest_validation.py`)
- Deterministic parameter target resolver (`test_parameter_target_resolver.py`)
- Parameter assignment execution (`test_parameter_assignment.py`)
- Document recompute boundary (`test_document_recompute.py`)
- STEP artifact export (`test_step_export.py`)
- CSV artifact export (`test_csv_export.py`)
- PDF artifact export (`test_pdf_export.py`)
- Result writing (`test_result_writer.py`)
- Headless controlled-failure: malformed manifests (`test_headless_malformed_manifests.py`)
- Headless controlled-failure: missing working copies (`test_headless_missing_working_copies.py`)
- Headless deterministic repeated-run behavior (`test_headless_repeated_run.py`)
- Headless controlled-failure: unsupported artifact requests (`test_headless_unsupported_artifact_requests.py`)
- Engineering-evidence sidecar writing and containment (`test_evidence_sidecar.py`)
- Evidence lifecycle ordering and failure precedence (`test_evidence_lifecycle.py`)
- Occurrence request, evidence, and runtime (`test_occurrence_request.py`, `test_occurrence_evidence.py`, `test_occurrence_runtime.py`)
- Occurrence real-FreeCAD fixtures (`test_occurrence_real_fixtures.py`)
- Bounded fact request, evidence, and runtime (`test_fact_request.py`, `test_fact_evidence.py`, `test_fact_runtime.py`)
- Bounded fact real-FreeCAD fixtures (`test_fact_real_fixtures.py`)
- Integrity observation and runtime (`test_integrity_observation.py`, `test_integrity_runtime.py`)
- Integrity real-FreeCAD fixtures (`test_integrity_real_fixtures.py`)
- Full real-FreeCAD engineering-evidence lifecycle (`test_evidence_lifecycle_real.py`)
