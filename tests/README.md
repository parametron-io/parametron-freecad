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

The committed real reference-traversal fixtures run in the normal Nix suite
when the repository FreeCAD wrapper and `freecadcmd` are available. Maintain a
semantic replacement bundle in a new directory with:

```
nix develop --command freecadcmd scripts/generate_reference_traversal_fixtures.py --pass=/absolute/new/output-directory
```

Generated `.FCStd` archive bytes need not match; the real fixture tests compare
their semantic traversal output. Tracked fixtures must remain byte-for-byte
unchanged during tests.

Optional environment-gated smoke tests use a real `freecadcmd` binary:

- Set `PARAMETRON_FREECAD_BIN` to the path of a `freecadcmd` wrapper.
- Tests skip by default when the configured binary is unusable.
- Set `PARAMETRON_FREECAD_STRICT_SMOKE=1` to turn a skipped smoke test into a failure.

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
- Architecture documentation guards (`test_architecture_documentation.py`)
