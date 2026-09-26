# Test Matrix

This matrix records current validation coverage for `parametron-freecad`.
It distinguishes contract/helper, fake-FreeCAD, and real-FreeCAD coverage,
including rejection of unsupported requests. It does not create new requirements.
Recorded counts in older sections are historical and must not be summed.
The current canonical schema-1 consolidation passed 3,714 full-suite tests
and 1,675 subtests in the Nix environment. Strict native fixture checks
passed on FreeCAD 1.1.1; compileall and the project smoke command passed.

## Command Rules

Current validation commands are ordinary Python/test commands, run inside a
Python/FreeCAD environment providing this package:

```bash
<command>
```

This repository's `flake.nix` provides one reproducible such environment
(`nix develop`); see [README.md](../README.md). Any equivalent environment
satisfying the documented runtime and verification requirements may be used.

## Recommended Validation Commands

Syntax/import check:

```bash
python -m compileall parametron_freecad scripts tests
```

Full suite (including real-FreeCAD tests when their environment is available):

```bash
python -m pytest
```

Focused headless/runtime checks:

```bash
python -m pytest tests/test_headless_cli_arguments.py
python -m pytest tests/test_headless_repeated_run.py
python -m pytest tests/test_runtime_entrypoints.py
python -m pytest tests/test_runtime_invocation.py
```

Focused manifest/result/artifact checks:

```bash
python -m pytest tests/test_manifest_contract.py tests/test_manifest_mutation_contract.py tests/test_manifest_loader.py tests/test_manifest_validation.py tests/test_manifest_mutation_validation.py
python -m pytest tests/test_result_writer.py
python -m pytest tests/test_failure_output_contract.py tests/test_failure_result_writer.py tests/test_trace_output_contract.py
python -m pytest tests/test_reference_traversal_output_contract.py
python -m pytest tests/test_reference_traversal_request.py tests/test_reference_traversal.py
python -m pytest tests/test_step_export.py tests/test_csv_export.py tests/test_pdf_export.py
python -m pytest tests/test_canonical_manifest_validation.py tests/test_canonical_runtime_lifecycle.py tests/test_canonical_lifecycle.py
```

Focused observation/reference-foundation checks:

```bash
python -m pytest tests/test_reference_access.py tests/test_reference_observation.py
python -m pytest tests/test_requested_scope_observation.py tests/test_observed_writer.py tests/test_observed_output_repeated_run.py
python -m pytest tests/test_observation_request.py
python -m pytest -q tests/test_verification_contract.py tests/test_observed_contract.py tests/test_target_state_observation.py tests/test_target_state_real_fixtures.py
```

Focused native suppression, visibility, and deletion checks:

```bash
python -m pytest tests/test_suppression.py
python -m pytest tests/test_suppression_real_fixtures.py
python -m pytest tests/test_visibility.py
python -m pytest tests/test_visibility_real_fixtures.py
python -m pytest tests/test_deletion.py
python -m pytest tests/test_deletion_real_fixtures.py
```

Focused post-mutation validity and native dependency evidence checks:

```bash
python -m pytest \
  tests/test_post_mutation_validity.py \
  tests/test_post_mutation_validity_real_fixtures.py
```

Production-execute real-FreeCAD target-mutation proof (requires an available
FreeCAD host; strict mode makes host unavailability a failure):

```bash
env PARAMETRON_FREECAD_STRICT_SMOKE=1 \
  python -m pytest tests/test_mutation_execute_real_fixtures.py
```

Focused aligned execute-plus-observation checks:

```bash
python -m pytest tests/test_headless_cli_arguments.py tests/test_runtime_entrypoints.py tests/test_observed_writer.py tests/test_observation_request.py
```

Focused launcher checks:

```bash
python -m pytest \
  tests/test_launcher.py \
  tests/test_headless_invocation.py \
  tests/test_environment_contract.py
```

Real FreeCAD smoke is environment-gated. Strict smoke exercises the installed
`parametron-freecad` wrapper:

```bash
PARAMETRON_FREECAD_BIN=/path/to/freecadcmd python -m pytest tests/test_headless_invocation.py
env PARAMETRON_FREECAD_STRICT_SMOKE=1 \
  python -m pytest tests/test_headless_invocation.py -k 'smoke'
```

`PARAMETRON_FREECAD_BIN` names the underlying FreeCAD host, not
`parametron-freecad`. `PARAMETRON_FREECAD_STRICT_SMOKE=1` turns unusable
configured FreeCAD smoke behavior into a test failure.

## Coverage Legend

| Label | Meaning |
| --- | --- |
| Covered | Directly tested. |
| Indirectly covered | Verified through integration or side-effect assertions. |

Real-FreeCAD coverage is proven only by an executed native PASS. A gated SKIP
means the host was unavailable and supplies no native proof; FAIL means the
native check did not pass. Fast/default tests cover contract validation,
serialization, orchestration, failure routing, and fake-FreeCAD behavior.
Native tests cover actual object mutation, recompute, validity, save/reopen,
observation, and native failure behavior.

## Current Coverage

The older pure `reference_traversal_output_contract` metadata helpers remain
for their non-runtime identity, diagnostic, and containment contracts. Their
narrow payload builder and serializer are historical helpers; the normal runtime
uses the rich `reference_traversal_output` serializer and one atomic writer.

| Area | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Installable `parametron-freecad` launcher | Covered | `tests/test_launcher.py`, `tests/test_headless_invocation.py`, `tests/test_environment_contract.py` | Host resolution, structured `--pass=` forwarding, process behavior, Nix wrapper discovery, real smoke. |
| Headless smoke mode | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_invocation.py`, `tests/test_launcher.py` | Real FreeCAD smoke exercises `parametron-freecad`, not direct script invocation. |
| Headless execute CLI | Covered | `tests/test_headless_cli_arguments.py` | `execute --working-copy --manifest --result [--output-dir] [--observation-request] [--reference-traversal-request]`. |
| Canonical schema-1 mapped traversal request and evidence | Covered | `tests/test_reference_traversal_request.py`, `tests/test_reference_traversal.py`, `tests/test_runtime_entrypoints.py` | Required `externalTargets`; strict five-field canonical mappings; canonical validation/order; resolved, missing, partial-list, unmatched, ambiguous, provenance, ID, relocation, and byte-stability behavior. |
| Real reference fixture bundle portability | Covered | `tests/test_reference_traversal_real_fixtures.py`, `tests/freecad_reference_fixture_relocation_runner.py` (test-only support) | Copies the complete committed `reference_traversal/` bundle to an arbitrary temporary location, opens the copied root directly with real FreeCAD, and verifies the internal target plus all three external targets and their copied-bundle document paths without a traversal request or `externalTargets` mappings. The root document alone is not the portable unit. |
| Aligned execute-plus-observation CLI | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_runtime_entrypoints.py` | Optional observation on `execute`; standalone `observe` remains rejected. |
| Observation request loading boundary | Covered | `tests/test_observation_request.py` | Strict JSON load, compatibility delegation, deterministic normalized data. |
| Live-document observation orchestration | Covered | `tests/test_runtime_entrypoints.py` | Same open document; post-mutation/export observation; internal source digest. |
| `_working` / supplied execution root | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_missing_working_copies.py`, `tests/test_file_argument_contract.py`, `tests/test_paths.py` | Supplied existing directory is authoritative; basename unrestricted; direct `_working` and nested `_working/<execution-id>` accepted; child containment preserved. |
| Manifest path containment | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_missing_working_copies.py` | Checked before FreeCAD import. |
| Result path containment | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_missing_working_copies.py` | Invalid result paths reject before file creation; safe path required for failed `prm.result.json`. |
| `sourceDocument` containment | Covered | `tests/test_document_lifecycle.py`, `tests/test_headless_missing_working_copies.py`, `tests/test_headless_cli_arguments.py` | Traversal and symlink escapes rejected against the supplied root. |
| FreeCAD-native manifest contract | Covered | `tests/test_manifest_contract.py` | Filename is `prm.export-manifest.json`. |
| Canonical manifest mutation metadata and strict validation | Covered | `tests/test_manifest_mutation_contract.py`, `tests/test_manifest_mutation_validation.py` | Canonical schema-1 metadata and strict validation cover mutation section shapes, version rejection, booleans, duplicates, conflicts, and deterministic diagnostics. Normal execute accepts canonical schema 1.0 with mutations and rejects schema 2.0 before document operations. |
| Canonical schema 1.0 mutation validation | Covered | `tests/test_canonical_manifest_validation.py`, `tests/test_canonical_lifecycle.py` | Four required core fields and optional `assemblyMutations`/`partMutations`; each section is closed to suppression, visibility, deletion. Strict booleans and entry shapes; duplicate, deletion, and cross-scope conflict rejection; suppression plus visibility coexistence; deterministic diagnostics without input mutation. Canonical Engine-generated manifest loads directly, and normal execute rejects schema 2.0. |
| Canonical runtime lifecycle and failure handling | Covered | `tests/test_canonical_runtime_lifecycle.py` | Parameter assignment → Assembly suppression, visibility, deletion → Part suppression, visibility, deletion → required final recompute/validity when applicable → save → STEP/CSV/PDF exports → traversal → observation → close → success. Each deletion includes internal recompute and supported Body validity inspection; a final pass follows later mutation state without redundant checking after final deletion. Mutation-free execution retains one recompute and no new target-mutation validity requirement. Structured stages cover suppression, visibility, deletion, recompute, post_mutation_validity, document_save, observation, and document_close; failures stop later work, attempt cleanup, preserve native causes and the primary execution failure even when cleanup/result emission fails, and prevent false success. Earlier completed mutations are not generally rolled back. |
| Canonical native lifecycle | Covered, real FreeCAD | `tests/test_canonical_lifecycle.py`, `tests/freecad_canonical_lifecycle_runner.py`, `tests/fixtures/canonical_lifecycle/` | Real normal execute persists large-variant parameters, suppression/unsuppression, hide/unhide, and conservative `Body002` deletion. No-delete regression proves `Body002` survives when deletion is omitted. Reopening proves persisted state equals live post-mutation observation; result/traversal emission, source-fixture integrity, and repeated-run semantic determinism are covered. |
| Production-execute target-mutation native proof | Covered, real FreeCAD | `tests/test_mutation_execute_real_fixtures.py`, `tests/freecad_mutation_execute_runner.py` (test-only host, not a production entrypoint), `tests/fixtures/partdesign_mutations/` | Canonical schema 1.0 `prm.export-manifest.json` and `prm.verification.json` enter production execute. Real FreeCAD proves suppress/unsuppress, hide/unhide, conservative safe deletion, post-mutation recompute and validity, working-copy save and independent reopen, and requested raw suppression/visibility/existence observation in `prm.observed.json`. Unsafe deletion and native validity failures yield failed `prm.result.json`, no observation or false success, and predictable document closure. Equivalent runs agree on native state, validity, result, target-state observation, and output names; the committed fixture hash stays unchanged. This does not prove arbitrary-object deletion, `.FCStd` archive byte identity, or the separate real Engine-to-FreeCAD rehearsal. |
| Canonical Engine-generated input corpus | Covered | `tests/test_canonical_lifecycle.py`, `tests/fixtures/engine_generated/prm.export-manifest.json`, `tests/fixtures/engine_generated/prm.verification.json`, `tests/fixtures/engine_generated/prm.reference-traversal-request.json` | Actual Engine production-materialized inputs for FreeCAD consumption, copied byte-for-byte; direct manifest and request loading. `prm.result.json` and `prm.observed.json` are FreeCAD outputs, not Engine-generated input fixtures. Engine retains verification and normalization ownership. |
| Strict manifest loading | Covered | `tests/test_manifest_loader.py`, `tests/test_headless_malformed_manifests.py` | Duplicate keys and non-standard JSON constants rejected. |
| Manifest structural validation | Covered | `tests/test_manifest_validation.py` | Exact field surfaces and supported formats. |
| Retired Engine dot-form compatibility regression | Covered | `tests/test_engine_manifest_compat.py` | Historical compatibility and rejection coverage; the current production execute path consumes canonical Engine-produced schema 1.0 inputs directly. |
| Engine name-only parameter rejection | Covered | `tests/test_engine_manifest_compat.py`, `tests/test_runtime_entrypoints.py` | Rejected before document open and side effects. |
| Exact parameter target resolver | Covered | `tests/test_parameter_target_resolver.py`, `tests/test_parameter_assignment.py` | `<ObjectName>.<PropertyName>` only. |
| Parameter assignment | Covered | `tests/test_parameter_assignment.py`, `tests/test_headless_cli_arguments.py` | Scalar assignment in manifest order. |
| Document recompute | Covered | `tests/test_document_recompute.py`, `tests/test_headless_cli_arguments.py`, `tests/test_canonical_runtime_lifecycle.py` | Mutation-free execution retains one recompute. Deletion includes post-removal recompute/validity; later mutation state may require a final pass. |
| Native document persistence | Covered | `tests/test_document_save.py`, `tests/test_runtime_entrypoints.py`, `tests/test_failure_output_contract.py`, `tests/test_reference_traversal_real_fixtures.py`, `tests/test_canonical_lifecycle.py`, `tests/test_mutation_execute_real_fixtures.py` | `document.save()` is called exactly once on the opened working copy after required recompute/validity and before exports/traversal/observation; `DocumentSaveError` maps to stage `document_save`; zero derived outputs persist native state with `artifacts: []`. Real FreeCAD close/reopen proof covers ordinary parameter and canonical target-mutation execution. Archive byte identity is not claimed. |
| STEP export | Covered | `tests/test_step_export.py`, `tests/test_headless_cli_arguments.py`, `tests/test_headless_repeated_run.py`, `tests/test_headless_unsupported_artifact_requests.py` | Exact `document.getObject(id)` lookup and one-object export; declared output path confined to working copy; no `document.Objects` fallback. |
| CSV export | Covered | `tests/test_csv_export.py`, `tests/test_headless_unsupported_artifact_requests.py` | Spreadsheet-backed CSV behavior. |
| PDF export | Covered | `tests/test_pdf_export.py`, `tests/test_headless_unsupported_artifact_requests.py` | TechDraw-backed PDF behavior. |
| Success `prm.result.json` | Covered | `tests/test_result_writer.py`, `tests/test_headless_repeated_run.py` | Structured success payloads only. |
| Structured failure output shape helper | Covered | `tests/test_failure_output_contract.py` | Payload shape, constants, validation, canonical JSON, immutability, import safety. |
| Structured failure result writer | Covered | `tests/test_failure_result_writer.py` | Canonical failed `prm.result.json` writes, immutability, write-error handling. |
| Structured failure emission / destination | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_malformed_manifests.py`, `tests/test_headless_unsupported_artifact_requests.py`, `tests/test_headless_missing_working_copies.py`, `tests/test_headless_repeated_run.py`, `tests/test_runtime_entrypoints.py`, `tests/test_runtime_invocation.py`, `tests/test_integration_rehearsal.py` | Safe result path + handled execute failure => failed `prm.result.json`; argument/path failure => no `prm.result.json`; repeated failure determinism; best-effort emission; `ResultWriteError` no-recursion. |
| Runtime trace output shape helper | Covered | `tests/test_trace_output_contract.py` | Payload/event shape, constants, validation, canonical JSON, immutability, import safety; no trace writer or runtime wiring. |
| Deterministic execute repeated runs | Covered | `tests/test_headless_repeated_run.py` | Fake-FreeCAD byte-stability for success and handled failure `prm.result.json`. |
| Controlled malformed manifest failures | Covered | `tests/test_headless_malformed_manifests.py` | Failed `prm.result.json` on handled execute failures; no artifact/document side effects. |
| Controlled missing working-copy failures | Covered | `tests/test_headless_missing_working_copies.py` | Argument failures produce no `prm.result.json`; execute failures with safe result path write failed `prm.result.json`. |
| Controlled unsupported artifact failures | Covered | `tests/test_headless_unsupported_artifact_requests.py` | Stop-on-first-failure behavior with failed `prm.result.json` when result path is safe. |
| Verification contract metadata | Covered | `tests/test_verification_contract.py` | Observation input contract foundation. |
| Verification loading | Covered | `tests/test_verification_loader.py`, `tests/test_malformed_verification_contracts.py` | Strict load behavior. |
| Observed output contract metadata | Covered | `tests/test_observed_contract.py` | `prm.observed.json` foundation. |
| Requested parameter observation | Covered | `tests/test_parameter_observation.py`, `tests/test_unavailable_requested_observations.py` | Exact `document.getObject` and property read. |
| Requested metadata observation | Covered | `tests/test_metadata_observation.py`, `tests/test_unavailable_requested_observations.py` | Exact owner/key reads. |
| Requested reference observation | Covered | `tests/test_reference_access.py`, `tests/test_reference_observation.py`, `tests/test_unavailable_requested_observations.py` | Existence check only; not traversal. |
| Canonical schema `1.0` target-state observation | Covered, including gated real FreeCAD | `tests/test_verification_contract.py`, `tests/test_observed_contract.py`, `tests/test_target_state_observation.py`, `tests/test_target_state_real_fixtures.py`, `tests/test_mutation_execute_real_fixtures.py` | Engine-defined request scope; exact native lookup and post-execution suppression, visibility, and existence evidence with `target_missing`/`unavailable` semantics. Production-execute proof compares raw `prm.observed.json` with independently reopened native state. FreeCAD does not decide verification success or produce normalized Engine records. |
| Observation ordering | Covered | `tests/test_observation_ordering.py`, `tests/test_requested_scope_observation.py` | Deterministic ordering for already-built payloads. |
| Observed JSON writing | Covered | `tests/test_observed_writer.py`, `tests/test_observed_output_repeated_run.py` | Canonical UTF-8 JSON with atomic destination replacement; no standalone CLI `observe`. |
| Engine invocation surface | Covered | `tests/test_runtime_invocation.py`, `tests/test_invocation_contract.py` | Execute and observe modes; execute failures preserve entrypoint-written failed `prm.result.json`. |
| Normal planner-generated Engine-to-FreeCAD invocation | Indirectly covered | `https://github.com/parametron-io/parametron-engine/blob/main/docs/test-matrix.md` | FreeCAD-local tests cover the runtime boundary; Engine planner/executor integration coverage belongs to the Engine repository. |
| File argument metadata | Covered | `tests/test_file_argument_contract.py`, `tests/test_invocation_contract.py` | Metadata only. |
| Output file metadata | Covered | `tests/test_output_file_contract.py`, `tests/test_invocation_contract.py` | Metadata only. |
| Engine-facing error classes | Covered | `tests/test_error_contract.py`, `tests/test_runtime_invocation.py` | In-process invocation errors. |
| Fixture-based integration rehearsal helper | Covered | `tests/test_integration_rehearsal.py` | Local/test helper; handled execution failures write failed `prm.result.json`. |
| Artifact byte comparison helper | Covered | `tests/test_artifact_comparison.py` | Exact byte comparison only. |
| Historical narrow traversal contract helper | Covered | `tests/test_reference_traversal_output_contract.py` | Contract/helper coverage includes semantic node/edge identity and identity-key deduplication; public total-order keys; item-level state metadata; aggregate-status metadata helper and exact public export; deterministic `succeeded`, `partial`, `failed` order and semantics; semantic completeness and item/aggregate separation; canonical JSON/repeated bytes, fresh nested structures, mutation isolation, blocked-FreeCAD import safety, caller-status and malformed-request compatibility, and unchanged schema/dataclasses. No actual runtime classification or status derivation, normalization, real traversal, diagnostics collection, runtime failure-path execution, or runtime wiring. Direct writer coverage is recorded separately. |
| Historical narrow traversal serialization helper | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_canonical_json.py` | Exact public export and keyword-only signature; payload-builder/canonical-helper byte equivalence; compact sorted-key UTF-8 bytes; no BOM or CRLF; exactly one trailing LF; direct non-ASCII, duplicate, and exact-string preservation; repeated and reordered-input byte equality under existing total orders; independent node/edge/diagnostic sequencing; validation propagation; mutation isolation; blocked-FreeCAD import safety; and no filesystem side effects. This covers pure bytes only, not writing or runtime emission. |
| Shared semantic traversal node identity helper | Covered | `tests/test_reference_traversal_output_contract.py` | Exact exports and ordered fields; four semantic tuple-key forms; exact exclusions; deterministic equality/distinction; no normalization or coercion; kind/path/object-name validation and deterministic errors; metadata completeness, freshness, mutation isolation, and canonical JSON compatibility; unchanged raw payload/arbitrary raw-kind behavior; import safety. This node-focused coverage does not prove `.FCStd` discovery, real FreeCAD traversal, writer/runtime wiring, node deduplication, or normalization; semantic edge helper coverage is recorded separately below. |
| Historical endpoint-only semantic edge helper | Covered | `tests/test_reference_traversal_output_contract.py` | Exact public API, immutable constants/metadata, directed nested keys across supported node/edge kinds, node-key and edge-kind validation, self-edges, reverse-edge distinction, duplicate elimination, deterministic sorting, permutation/repetition-count independence, shared-target and graph-relationship preservation, no normalization, no input mutation, raw payload compatibility, arbitrary raw edge-kind pass-through, duplicate raw-edge preservation, provenance limitation, and import safety. This is not real traversal, runtime cycle-guard, writer/wiring, `.FCStd` fixture, or property-sensitive identity coverage. |
| Historical reference discovery metadata helpers | Covered | `tests/test_reference_traversal_output_contract.py` | Exact seven exports with no private exports; immutable `objectType`/`sourceProperty`/`referenceMechanism` vocabulary and proposed locations; three metadata-only classifications; supported-runtime-evidence and no-guess policies; raw FreeCAD ownership; inactive schema `"1.0"` fields; canonical JSON, freshness, mutation isolation, compatibility, and import safety. No real discovery, runtime classification, provenance serialization, fixture-backed traversal, Engine normalization, or durable storage behavior. |
| Historical normalization metadata helper | Covered | `tests/test_reference_traversal_output_contract.py` | 86 focused tests cover exact public no-argument API, field categories, stable strings and exact raw evidence, inactive provenance, lexical contract-relative paths, filesystem/containment/Engine distinctions, destructive-canonicalization raw preservation, unchanged schema `"1.0"`, canonical JSON, deep freshness, blocked-FreeCAD imports, no filesystem side effects, and payload/identity/deduplication/ordering compatibility. No actual normalization, traversal, serialization, writer, or wiring. |
| Historical semantic exclusion metadata helper | Covered | `tests/test_reference_traversal_output_contract.py` | Exact eight exports; exact timestamp, request-ID, actor, process/runtime identity, temporary absolute path, and incidental enumeration-order aggregate order and semantics; operational placement and anti-overloading; canonical JSON and repeated metadata-byte equality; deep freshness/mutation isolation; guarded in-process/subprocess import safety; no filesystem/runtime side effects; unchanged payload/dataclasses, identity/deduplication, ordering/sequence, normalization/containment, and runtime behavior. This is metadata contract repeated-byte equality, not serialized traversal output-file repeated-run equality, and it does not cover real FreeCAD traversal. |
| Reference traversal output path containment | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_reference_traversal_output_writer.py`, `tests/test_runtime_entrypoints.py`, `tests/test_paths.py`, `tests/test_output_file_contract.py`, `tests/test_file_argument_contract.py` | Resolver coverage uses the exact supplied existing directory as authoritative, with unrestricted basename, arbitrary/direct/nested root acceptance, no ancestor widening, and lexical/resolved/symlink escape rejection. The runtime delegates canonical output emission to the atomic writer with that exact root. |
| Traversal authoritative execution-root reconciliation | Covered | `tests/test_reference_traversal_output_contract.py` | Focused accepted/rejected path coverage proves safe arbitrary, direct `_working`, and nested attempt roots while preserving exact-root containment and symlink-aware escape prevention. |
| Reference traversal request contract/loader | Covered | `tests/test_reference_traversal_request.py`, `tests/test_file_argument_contract.py` | Canonical schema `{"schemaVersion":"1.0","externalTargets":[]}`; immutable normalized model; canonical request/output filenames; optional CLI/file metadata; strict UTF-8, JSON, duplicate-key, non-standard-constant, root, field, and version validation; filesystem failures and all invalid inputs use one chained public error; no FreeCAD or write side effects. |
| Real FreeCAD reference graph traversal | Covered | `tests/test_reference_traversal_real_fixtures.py`, `tests/fixtures/reference_traversal/` | FreeCAD 1.1.1 opens the committed three-document bundle and produces an exact frozen rich schema-1 payload for internal, mapped resolved external, shared-target, and Engine-authorized missing evidence. IDs are independently derived from the public identity formula. |
| Deterministic direct traversal output writer | Covered | `tests/test_reference_traversal_output_writer.py` | Direct writing emits the rich canonical schema-1 payload with object and edge provenance. |
| Atomic traversal output replacement | Covered | `tests/test_reference_traversal_output_writer.py` | Canonical atomic writing covers exact rich bytes, repeated and reordered inputs, same-directory temporary files, replacement, containment, conflicting evidence, and cleanup after serialization or replacement failure. |
| Containment-integrated traversal writing | Covered | `tests/test_reference_traversal_output_writer.py`, `tests/test_reference_traversal_output_contract.py` | The atomic writer delegates exactly once to the existing resolver using the exact supplied authoritative `working_copy`; safe arbitrary, direct `_working`, and nested `_working/<execution-id>` roots are represented, the basename remains unrestricted, and no ancestor widening occurs. No traversal entrypoint/runtime wiring is implied. |
| Traversal request CLI path validation | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_file_argument_contract.py` | Optional invocation field and flag; empty/missing/directory/outside-root rejection; exact-root containment; `--output-dir` dependency; malformed/non-UTF-8 content is not read during argument validation. |
| Traversal request entrypoint loading | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal_request.py` | Optional path is forwarded; strict loader runs exactly once after manifest/source validation and before FreeCAD/document operations; absence skips loading; direct entrypoint output-directory dependency; malformed requests preserve cause, emit a canonical failed raw traversal payload before FreeCAD resolution, and fail top-level `prm.result.json` at `request_validation`; no CAD traversal runs. |
| Traversal request absence compatibility | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_runtime_invocation.py`, `tests/test_headless_cli_arguments.py`, `tests/test_step_export.py`, `tests/test_csv_export.py`, `tests/test_pdf_export.py` | Explicit regression proof preserves manifest load/validation, source resolution, document lifecycle, assignment, recompute, all export families, observation, success results, and exact Engine invocation fields/delegation when traversal is absent. |
| Traversal request execution wiring and emission | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_headless_cli_arguments.py`, `tests/test_reference_traversal_output_writer.py` | Traversal runs after recompute and all STEP/CSV/PDF exports and before observation; `succeeded`/`partial` are atomically emitted to the canonical filename beneath the existing output directory, then continue; the exact working copy is the sole containment root; runtime/writer create no directories; failed traversal and controlled containment/write errors skip observation while completed exports remain. Stable `runtime_failure` stages cover traversal and output containment/write failures; malformed-request raw output is covered separately. |
| Typed reference traversal callable boundary / discovery | Covered | `tests/test_reference_traversal.py` | Exact public signature; immutable four-field result; exact status vocabulary; representable partial/failed evidence; raw tuple type enforcement; chained public error; source-root and participating-object discovery; supported internal and Engine-mapped external relationships; unsupported-value-shape partial diagnostics; and FreeCAD-independent import. Serialization, writing, containment, Engine normalization, and durable storage behavior remain outside the callable. |
| Reference traversal fixtures | Covered | `tests/test_reference_traversal_real_fixtures.py`, `scripts/generate_reference_traversal_fixtures.py`, `tests/fixtures/reference_traversal/` | One root and two referenced documents cover internal, external, shared-target, and mapped missing evidence. The Nix/FreeCAD 1.1.1 maintenance generator guarantees semantic reproducibility; the small binary bundle is stored directly in Git without LFS. |
| Reference traversal ordering/deduplication/cycle guards | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_reference_traversal.py`, `tests/test_reference_traversal_output.py`, `tests/test_runtime_entrypoints.py` | Typed canonical results collapse equal resolved/missing/unresolved nodes and edges by complete identity before deterministic ordering/sequencing, at the same aligned canonicalization boundary for both; distinct identity components, shared targets, multiple outgoing edges, byte stability, permutation independence, and controlled conflict chaining (including node-only conflicts and no partial committed output) are covered. |
| Reference traversal writer repeated-run byte equality | Covered | `tests/test_reference_traversal_output_writer.py` | Repeated atomic writes and reordered inputs are byte-identical through the canonical rich serializer. Real traversal repeatability is covered by the native fixture tests. |
| Reference traversal runtime-emitted file | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal_real_fixtures.py` | Atomic writer integration proves the exact canonical destination and trailing newline. Production-entrypoint traversal of relocated real fixtures is byte-identical across repeated, arbitrary-basename, and nested working roots, with no absolute-path leakage or fixture mutation. |
| Reference traversal controlled failures | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_failure_output_contract.py`, `tests/test_reference_traversal_output_writer.py` | Malformed request raw output, document-open `runtime_failure` / `document_open`, typed/exception traversal `runtime_failure` / `reference_traversal`, containment `runtime_failure` / `reference_traversal_output_containment`, and serialization/write/replacement `runtime_failure` / `reference_traversal_output_write` are exact. Boundary/category/shape/messages and full exception chains are preserved. |
| Traversal diagnostic classification/deduplication/ordering | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_reference_traversal.py` | Unsupported allowlisted non-None value shapes return one schema-neutral warning at `reference_discovery`, status `partial`, and no inferred mapped-missing evidence. Exact diagnostic duplicates collapse by complete record before the canonical total order and sequence assignment. Typed results reject canonical Python traceback blocks through the existing chained execution error. |
| Traversal-present execute/export compatibility | Covered | `tests/test_runtime_entrypoints.py` | Declared output objects reach STEP, CSV, PDF, and success-result artifact handling unchanged and in the established pipeline order around traversal emission. |
| Real FreeCAD reference API inspection | Covered | `tests/test_reference_traversal.py`, bounded-unit command-host probe | FreeCAD 1.1.1 accepted the exact 21 private Link/XLink type-ID allowlist and exposed object/subelement/list value shapes. No heuristic string/path mechanism is included; supported internal discovery now applies this surface. |
| PartDesign mutation fixture foundation | Covered | `tests/test_partdesign_mutation_fixtures.py`, `tests/freecad_partdesign_mutation_fixture_runner.py`, `scripts/generate_partdesign_mutation_fixtures.py`, `tests/fixtures/partdesign_mutations/partdesign-mutations.FCStd` | Permanent fixture integrity (SHA-256 `7187abe9...`), native role/TypeId inventory, Body Tip and dependency chain, `Suppressed` and App-level `Visibility` preconditions, safe vs unsafe delete candidate roles, Body shape health, generator success, two-run semantic reproducibility, CLI argument/path/nix validations, `.FCBak` cleanup, and unmutated inspection. This is fixture-prerequisite coverage; actual suppression transitions are covered separately through the production consumer. |
| FreeCAD-native suppression / unsuppression consumer | Covered | `tests/test_suppression.py`, `tests/test_suppression_real_fixtures.py`, `tests/freecad_suppression_runner.py` (test-only support) | Exact `document.getObject(object)` resolution with no fallback; native `Suppressed` capability and `App::PropertyBool` requirement; both requested boolean states; controlled missing, unsupported, inspection, and write failures with native causes preserved where applicable; caller ordering, fail-fast behavior, and unchanged input ordering/content. Real FreeCAD coverage applies the production consumer to temporary copies of the committed PartDesign fixture, proves `TerminalChamfer` true -> false and intermediate features false -> true, preserves visibility, and leaves committed fixture bytes unchanged. Normal schema-1 execute composes this consumer; the test helper is not a production entrypoint. |
| FreeCAD-native visibility consumer | Covered | `tests/test_visibility.py`, `tests/test_visibility_real_fixtures.py`, `tests/freecad_visibility_runner.py` (test-only support) | Exact `document.getObject(object)` resolution with no fallback; native App-level `Visibility` capability and exact `App::PropertyBool` requirement; hide and unhide; controlled missing, unsupported, inspection, and write failures with native causes preserved where applicable; no `FreeCADGui` or `ViewObject` dependency; suppression independence; caller ordering, fail-fast/no-rollback behavior, unchanged input ordering/content, and empty collections. Real FreeCAD coverage applies the production consumer to temporary fixture copies, proves hide and unhide plus a controlled missing-target failure, preserves suppression, and leaves committed fixture bytes unchanged. Normal schema-1 execute composes this consumer; the test helper is not a production entrypoint. |
| FreeCAD-native deletion consumer | Covered | `tests/test_deletion.py`, `tests/test_deletion_real_fixtures.py`, `tests/freecad_deletion_runner.py` (test-only support) | Exact `document.getObject(object)` lookup with no fallback; deterministic dependency inspection; native `InList` dependent rejection without cascade, force, or repair policy; `document.removeObject`; exact post-removal absence verification; post-removal recompute; deterministic document-level supported `PartDesign::Body` validity inspection; fail-closed behavior on unavailable or invalid evidence; controlled missing-target, native-operation, and validity failures with preserved cause chains where applicable; caller ordering, fail-fast/no-rollback semantics, and unchanged caller input; import safety without FreeCAD. Real FreeCAD coverage applies the production consumer to temporary fixture copies and an in-memory test document, proves safe deletion of `SafeDeleteMarker`, rejection of `BaseSketch` with `IntermediatePad` dependency evidence, genuine invalid post-delete Body-state failure, repeated-process determinism, and committed-fixture immutability. Normal schema-1 execute composes this consumer; the test runner is not a production entrypoint. |
| FreeCAD-native post-mutation validity and dependency evidence | Covered | `tests/test_post_mutation_validity.py`, `tests/test_post_mutation_validity_real_fixtures.py`, `tests/freecad_post_mutation_validity_runner.py` (test-only support) | Read-only exact native lookup; bounded PartDesign Body shape-health evidence; distinct unavailable-evidence, native-inspection-failure, and proven-invalid-state classifications; null-state precedence; solid count as evidence rather than policy; deterministic `InList` dependents and `OutList` dependencies without deletion policy; deterministic document-level Body composition helper (`inspect_document_post_mutation_validity`) discovering surviving native `PartDesign::Body` objects in stable native-name order independent of `document.Objects` enumeration order, reusing bounded shape-health inspection, and failing closed when no supported Body evidence exists; real healthy and genuinely null Body evidence; repeated-process determinism; temporary fixture copies and committed-fixture immutability. The inspection helpers remain read-only; mutation, removal, and recompute are caller-owned. Normal schema-1 execute composes these inspections with structured failure mapping; schema-2 requests are rejected. |
| Supported internal object reference discovery | Covered | `tests/test_reference_traversal.py` | Root-only documents, unrelated-object and empty-link exclusion, participating source/target inclusion, multiple sources/targets/properties, LinkSub extraction, exact canonical IDs/type/property/mechanism provenance, complete endpoints, duplicate collapse, and object/property/value enumeration-order independence are covered. |
| Internal traversal raw-evidence preservation | Covered | `tests/test_reference_traversal.py` | Exact typed-result coverage preserves source path, document/object labels, stable names/types, complete endpoints, edge kind/state, source property, reference mechanism, and nullable diagnostics; empty unavailable optional values remain null. Mapped external missing evidence is covered separately; unresolved remains contract vocabulary. |
| Active traversal cycle prevention | Covered | `tests/test_reference_traversal.py` | Self-link and mutual internal-link coverage proves the one-pass non-recursive discovery boundary terminates with finite participating nodes and distinct edges. Recursive external-document traversal is not implemented. |
| Visited semantic object guard | Covered | `tests/test_reference_traversal.py` | Repeated document enumeration of one stable source object name is skipped before property access; call-count coverage proves one traversal and unchanged canonical evidence. |
| Internal relationship cardinality | Covered | `tests/test_reference_traversal.py` | Exact counts prove one shared semantic target node retains two incoming edges and one source retains two distinct outgoing edges. |
| External target approved-API probe and Engine mapping consumer | Covered | `tests/test_reference_traversal_request.py`, `tests/test_reference_traversal.py`, bounded-unit FreeCAD 1.1.1 command-host probes | The probe excludes relocation-dependent `Document.FileName`; canonical Engine mappings supply canonical identity for unique resolved and authorized missing evidence. Unmatched and absent source/property/mechanism cases do not fabricate evidence; ambiguity is controlled. |
| Rich raw traversal output schema 1.0 | Covered | `tests/test_reference_traversal_output.py`, `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal.py` | Exact payload fields/version, nullable provenance, empty rejection, ASCII/Unicode SHA-256 ID vectors and canonical preimage bytes, provenance-sensitive edge identity/order/deduplication, repeated reordered-input bytes, runtime success/failure schema-1 emission and typed rich evidence. |
| Canonical traversal result conflict handling | Covered | `tests/test_reference_traversal.py`, `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal_output_writer.py` | Canonical typed results reject invalid evidence items and conflicting identity before emission; single non-empty evidence tuples remain valid without placeholders; runtime entrypoint failures remain structured; conflicting raw evidence with one complete canonical identity fails deterministic controlled emission. |
| Supplied execution-root validation alignment | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_missing_working_copies.py`, `tests/test_file_argument_contract.py`, `tests/test_reference_traversal_output_contract.py` | Execute path and traversal containment helper treat the exact supplied directory as authoritative; basename unrestricted; sibling/parent/symlink escapes rejected. |
| Standalone headless `observe` rejection | Covered | negative coverage in `tests/test_headless_cli_arguments.py` | Currently rejected; observation is aligned onto `execute`. |
| Component observation exclusion | Covered | `tests/test_engine_verification_compat.py`, `tests/test_engine_verification_expectations.py` | Not implemented; compatibility validation rejects enabled components and non-empty component expectations, while the lower-level helper omits components. |
| Verification decision exclusion | Covered | negative coverage in `tests/test_engine_verification_compat.py`, `tests/test_observed_writer.py` | Engine-owned; FreeCAD emits raw observed facts only. |

Semantic-output-exclusion validation is recorded as separate overlapping runs:
82 focused tests passed with 644 deselected and 6 subtests; 726 complete
traversal contract tests and 415 subtests passed; 875 adjacent contract/path
tests and 724 subtests passed; 156 runtime regression tests and 22 subtests
passed; and 2920 full-suite tests and 1297 subtests passed, with 0 failed and 0
skipped. These runs are not summed.

## Focused Installable Launcher Coverage

Test files for the installable `parametron-freecad` launcher:

- `tests/test_launcher.py`
- `tests/test_headless_invocation.py`
- `tests/test_environment_contract.py`

### Host resolution and configuration

`tests/test_launcher.py`:

- `test_default_host_resolution_uses_freecadcmd_from_path`
- `test_explicit_absolute_host_override_is_selected_exactly`
- `test_explicit_path_resolvable_host_name_is_selected`
- `test_explicit_host_surrounding_whitespace_is_trimmed`
- `test_compound_host_configuration_is_not_split_or_run_in_a_shell`
- `test_blank_host_configuration_is_rejected_without_starting_child`
- `test_recursive_wrapper_name_is_rejected_without_starting_child`
- `test_absolute_recursive_wrapper_path_is_rejected`

Coverage:

- default `freecadcmd` host
- explicit `PARAMETRON_FREECAD_BIN` override
- surrounding whitespace trimming
- no shell splitting of compound host values
- blank/whitespace rejection without starting a child
- recursive wrapper-name and absolute-path rejection

### Structured argv and bootstrap

`tests/test_launcher.py`:

- `test_execute_request_builds_exact_structured_host_argv`
- `test_special_character_arguments_are_preserved_as_data`
- `test_bootstrap_is_fixed_and_never_contains_protocol_values`
- `test_launch_uses_subprocess_list_without_shell_or_eval`

Coverage:

- exact host argv construction
- one `--pass=` element per runtime protocol argument
- argument ordering preservation
- spaces, Unicode, quotes, and shell metacharacters as data
- fixed bootstrap expression
- no protocol-value interpolation into Python source
- no shell command or `eval`

### Process behavior

`tests/test_launcher.py`:

- `test_stub_host_success_preserves_streams_and_exact_argv`
- `test_missing_host_returns_127_with_diagnostic`
- `test_nonzero_host_exit_and_streams_are_propagated`
- `test_signal_termination_maps_to_128_plus_signal`
- `test_launcher_is_independent_of_caller_working_directory`

Coverage:

- success path
- inherited stdout/stderr
- host-start failure exit `127` with diagnostic
- nonzero child exit propagation
- POSIX signal termination as `128 + signal`
- caller working-directory independence

### Nix and real smoke

`tests/test_launcher.py` / `tests/test_headless_invocation.py` /
`tests/test_environment_contract.py`:

- `test_nix_wrapper_is_discoverable_and_executable`
- `test_nix_wrapper_smoke_from_unrelated_working_directory`
- `test_parametron_freecad_bin_names_the_underlying_host_not_wrapper`

Coverage:

- wrapper discovery on development-shell `PATH`
- executable Nix-store path
- real FreeCAD-backed smoke through `parametron-freecad`
- canonical smoke JSON
- unrelated working directory
- `PARAMETRON_FREECAD_BIN` names the underlying host, not the wrapper

Clarifications:

- real FreeCAD smoke now exercises `parametron-freecad`, not direct
  `freecadcmd scripts/parametron_freecad_headless.py` invocation
- no Engine dependency
- no network dependency
- no working-copy validation changes in the launcher stage
- these launcher tests do not prove real FCStd end-to-end execution
- supplied execution-root alignment is covered separately below

Recorded launcher validation:

```bash
nix develop --command python -m pytest \
  tests/test_launcher.py \
  tests/test_headless_invocation.py \
  tests/test_environment_contract.py
# PASS, 48 passed
```

```text
focused preserved headless/runtime tests
# PASS, 108 passed
```

```bash
nix develop --command env \
  PARAMETRON_FREECAD_STRICT_SMOKE=1 \
  python -m pytest tests/test_headless_invocation.py -k 'smoke'
# PASS, 2 passed, 5 deselected
```

```bash
nix develop --command python -m pytest
# PASS, 2330 passed
```

```bash
nix develop --command python -m compileall \
  parametron_freecad scripts tests
# PASS
```

## Focused Supplied Execution-Root Coverage

Test files for the supplied execution-root contract:

- `tests/test_headless_cli_arguments.py`
- `tests/test_headless_missing_working_copies.py`
- `tests/test_file_argument_contract.py`

### Safe root acceptance

`tests/test_headless_cli_arguments.py` /
`tests/test_headless_missing_working_copies.py`:

- `test_execute_working_copy_arbitrary_safe_name_is_accepted`
- `test_execute_working_copy_arbitrary_safe_name_preserves_containment`
- `test_execute_working_copy_nested_execution_leaf_is_accepted`
- `test_execute_working_copy_nested_execution_leaf_is_authoritative_root`
- `test_execute_working_copy_direct_working_root_remains_accepted`

Coverage:

- arbitrary safe basename
- nested execution leaf
- direct `_working`
- exact normalized root
- no parent substitution
- no outside-root side effects

### Containment and isolation

- `test_execute_rejects_sibling_execution_paths`
- `test_execute_rejects_parent_working_root_paths`
- `test_execute_supplied_leaf_rejects_symlink_escapes`

Coverage:

- sibling manifest
- sibling result
- sibling output directory
- sibling observation request
- parent/shared paths
- symlink-resolved escapes

### Source, artifacts, and canonicalization

- `test_execute_nested_source_document_uses_supplied_leaf`
- `test_execute_rejects_artifact_path_in_sibling_execution_root`
- `test_execute_working_copy_root_symlink_is_canonicalized`

Coverage:

- source resolution against the supplied leaf
- artifact sibling rejection
- canonical root behavior

### Contract metadata

`tests/test_file_argument_contract.py`:

- `test_execute_cli_required_file_arguments_are_exact_and_ordered`

Coverage:

- updated supplied-root contract metadata

This test covers the FreeCAD supplied-root boundary without an Engine runtime
dependency; it does not prove cross-repository planner/executor integration.

Recorded supplied-root validation:

```bash
nix develop --command python -m pytest \
  tests/test_headless_cli_arguments.py \
  tests/test_file_argument_contract.py \
  tests/test_paths.py \
  tests/test_headless_missing_working_copies.py
# PASS, 127 supplied-root focused tests passed
```

```bash
nix develop --command python -m pytest \
  tests/test_manifest_validation.py
# PASS, 129 manifest validation tests passed
```

```bash
nix develop --command python -m pytest \
  tests/test_runtime_entrypoints.py \
  tests/test_headless_repeated_run.py \
  tests/test_observation_request.py
# PASS, 58 runtime regression tests passed
```

```bash
nix develop --command python -m pytest \
  tests/test_launcher.py \
  tests/test_headless_invocation.py \
  tests/test_environment_contract.py
# PASS, 48 launcher regression tests passed
```

```bash
nix develop --command python -m pytest
# PASS, 2337 full-suite tests passed
```

```bash
nix develop --command python -m compileall \
  parametron_freecad scripts tests
# PASS
```

## Focused Structured Failure Output Contract Coverage

`tests/test_failure_output_contract.py` covers:

- exact structured failure payload shape (`schemaVersion`, `status`, `failure`)
- `stage=None` preserved in payload output
- exact top-level and nested failure detail field sets
- field-name and vocabulary constants
- invalid required string fields (`boundary`, `category`, `code`, `message`)
- invalid `stage` values (`""`, non-string)
- deterministic single-line `FailureOutputContractError` messages
- frozen `StructuredFailure` / no input mutation
- independent payload dict objects per `build_failure_output_payload` call
- canonical JSON compatibility through `dumps_canonical`
- import safety without FreeCAD module imports

## Focused Runtime Trace Output Contract Coverage

`tests/test_trace_output_contract.py` covers:

- trace output public API, constants, and `__all__` exports
- import safety without FreeCAD module imports
- exact trace payload shape (`schemaVersion`, `kind`, `boundary`, `operation`, `status`, `events`)
- exact event shape (`sequence`, `stage`, `state`, `message`)
- `message: null` when absent and message preservation when present
- deterministic zero-based event sequence assignment
- caller-provided event order preservation
- canonical JSON compatibility through `dumps_canonical`
- deterministic single-line `TraceOutputContractError` validation errors
- frozen `RuntimeTraceEvent` / no input mutation
- independent payload dict objects per `build_trace_output_payload` call
- guard against trace writer/runtime wiring surface creep

This coverage does not include trace file writer behavior, trace CLI behavior,
runtime trace emission, raw diagnostic file behavior, or reference graph
traversal.

## Focused Deterministic Traversal Output Writer Coverage

`tests/test_reference_traversal_output_writer.py` contains 59 tests: 17
direct-writer tests and 42 atomic-writer tests. The direct
writer coverage includes:

- exact public API, `OSError`-derived writer error, and import safety without
  FreeCAD
- exact equality with authoritative serializer bytes, including non-ASCII UTF-8
  and exactly one trailing LF
- exactly-once serializer delegation and unchanged distinctive-byte forwarding
- deterministic repeated ordinary overwrite and byte equality for
  representative equivalently reordered inputs
- caller sequence/dataclass non-mutation
- serialization/contract and file-write failure translation with the original
  exception preserved as `__cause__`
- missing-parent rejection without directory creation
- relative/caller-path pass-through and deliberate absence of a bound
  `resolve_reference_traversal_output_path(...)`

The atomic-writer coverage includes public API/import safety; exact resolver
delegation and exact-root authority for representative arbitrary/direct/nested
roots; no root widening; exactly-once serialization and exact bytes;
same-directory temporary placement; write/close-before-replace ordering;
missing-destination creation, existing-destination replacement, and repeated
deterministic writes; destination preservation across resolver, serializer,
temporary creation/wrapping, write, close, and replacement failures; temporary
cleanup, writer-error cause chaining, cleanup-failure precedence, input
non-mutation, and direct-writer independence.

Recorded validation evidence is: writer file `59 passed`; traversal-output
contract file `804 passed`, `422 subtests passed`; full suite `3057 passed`,
`1304 subtests passed`.

This coverage proves the separate writer-level atomic and containment-integrated
boundary. It does not prove runtime/headless/CLI traversal emission, real FreeCAD traversal, real `.FCStd`
fixture behavior, runtime item-state or aggregate-status application, controlled
output-write failure-stage integration, Engine normalization, or durable
storage/index/query behavior.

## Focused Raw Reference Traversal Output Contract Coverage

The in-memory serializer coverage adds 28 focused serializer/public-API tests
(723 deselected, 7 subtests) for the exact export/signature, authoritative
payload-builder and canonical-JSON equivalence, UTF-8 encoding, no BOM/CRLF,
exactly one trailing LF, compact formatting, direct non-ASCII, repeated and
reordered-input equality, independent sequencing, duplicate/exact-string
preservation, validation propagation, mutation isolation, blocked-FreeCAD
imports, and no filesystem side effects. Independently verified overlapping
runs: 751 complete traversal-contract tests, 10 canonical JSON tests, 120
adjacent writer/output-contract tests, 91 adjacent runtime tests, and 2945
full-suite tests; 0 failures. Compileall and `git diff --check` passed. No writer
or runtime traversal-file coverage is implied.

`tests/test_reference_traversal_output_contract.py` covers:

`ReferenceTraversalRuntimeStateSemanticsContractTests` contains 28 focused
methods covering:

- `test_helper_is_publicly_exported_and_callable`,
  `test_export_does_not_leak_a_private_helper_name`, and
  `test_task_introduces_no_new_public_state_constants`: exact public export and
  reuse of the existing state vocabulary without unnecessary constants
- `test_helper_signature_requires_no_arguments` and
  `test_helper_returns_plain_dict_with_no_arguments`: no-argument,
  metadata-only invocation
- `test_state_order_matches_defined_states_exactly`,
  `test_all_five_states_represented_exactly_once`,
  `test_no_competing_state_vocabulary_is_introduced`,
  `test_metadata_contains_documented_top_level_keys`,
  `test_item_state_fields_reference_node_and_edge_state_paths`, and
  `test_state_semantics_key_sets_are_exact_per_state`: canonical order and
  exact item-state metadata surface
- `test_resolved_semantics_distinguish_target_binding_from_verification_and_storage`,
  `test_missing_semantics_distinguish_established_absence_from_ambiguity`,
  `test_unresolved_semantics_require_ambiguous_or_insufficient_evidence`,
  `test_skipped_semantics_require_deliberate_non_attempt`,
  `test_skipped_does_not_map_to_specific_future_scenarios`,
  `test_failed_semantics_require_attempted_operation_failure`, and
  `test_failed_helper_itself_creates_no_diagnostics`: each state distinction,
  contract-defined explainable evidence boundaries, and absence of diagnostic creation
- `test_cross_state_distinctions`: missing versus unresolved, skipped versus
  failed, resolved versus Engine-verified, and item failed versus aggregate
  failed (4 subtests)
- `test_top_level_status_boundary_now_defines_aggregation_semantics`,
  `test_completeness_thresholds_are_semantic_not_numeric`, and
  `test_helper_behavior_discloses_metadata_only_exclusions`: aggregate policy
  metadata is present while runtime status derivation remains absent; no real
  discovery/classification, mechanism enumeration, schema mutation,
  serialization, Engine normalization, or durable storage behavior
- `test_metadata_is_plain_json_compatible_dict`,
  `test_repeated_calls_serialize_to_identical_canonical_bytes`, and
  `test_dumps_canonical_does_not_mutate_metadata`: JSON compatibility and
  canonical-byte stability
- `test_repeated_calls_are_value_equivalent_but_independent`,
  `test_deep_mutation_does_not_leak_to_a_later_call`, and
  `test_mutation_does_not_leak_to_module_level_constants`: fresh nested
  structures, mutation isolation, and module-constant protection
- `test_import_and_call_do_not_require_freecad`: FreeCAD-independent import and
  invocation

Recorded item-level semantics validation (overlapping runs are
reported separately, not summed):

- focused runtime-state semantics class: 28 passed, 4 subtests passed
- complete reference traversal contract file: 520 passed, 406 subtests passed
- adjacent runtime suite: 94 passed, 4 subtests passed
- full suite: 2714 passed, 1288 subtests passed
- failures: 0
- compileall: PASS
- `git diff --check`: PASS

Aggregate traversal status contract coverage adds two focused classes,
`ReferenceTraversalAggregateStatusSemanticsContractTests` and
`ReferenceTraversalAggregateStatusCompatibilityTests`, and updates the
item-state class boundary assertions. Coverage includes:

- exact public API/export and no-argument metadata-helper behavior for
  `build_reference_traversal_aggregate_status_semantics_contract()`
- deterministic `succeeded`, `partial`, `failed` order and the exact semantic
  requirements/exclusions for each status
- valid completed empty graphs; `missing`, `unresolved`, and contract-permitted
  `skipped` evidence not independently reducing status
- trustworthy independently reliable non-diagnostic graph evidence required
  for partial, with diagnostics-only evidence excluded
- malformed request, document-open, pre-evidence, systemic unreliable-evidence,
  containment, serialization, and output-write safe-emission failure boundaries
- item-level state versus aggregate-status separation, including one failed
  item not forcing aggregate `failed` and rejection of worst-item/severity-
  maximum aggregation
- semantic, contract-scope completeness without percentages, quotas, minimum
  node/edge counts, or diagnostic-count thresholds
- canonical JSON compatibility, repeated equivalent metadata bytes, fresh
  nested returns, deep mutation isolation, and import safety with FreeCAD-family
  imports blocked
- caller-supplied payload status preservation, malformed-request top-level
  `failed` compatibility, and unchanged schema `"1.0"`, payload shape, and
  dataclass fields

These tests validate metadata contract boundaries only. They do not exercise
real FreeCAD traversal, runtime classification or aggregate derivation,
diagnostics collection, containment/write/serialization failure execution,
writer behavior, request loading, or runtime wiring.

Recorded aggregate-status validation (overlapping runs
are reported separately, not summed):

- focused reference traversal contract file: 581 passed
- adjacent runtime suite: 179 passed
- full suite: 2775 passed, 1291 subtests passed
- failures: 0
- skips: 0
- compileall: PASS
- `git diff --check`: PASS

Normalization contract coverage adds 86 focused tests for
`build_reference_traversal_normalization_contract()`: exact public export and
no-argument signature; complete path, stable-string, exact-raw-evidence, and
inactive-provenance classification; string and lexical contract-relative path
rules; canonicalization versus filesystem resolution, containment, and Engine
normalization; separate raw preservation for destructive canonicalization;
schema `"1.0"` compatibility and no new serialized fields; deterministic
canonical JSON; deep freshness and mutation isolation; blocked-FreeCAD import
safety; no filesystem side effects; and unchanged payload, identity,
deduplication, and ordering behavior.

Verified normalization-stage evidence (overlapping runs are separate): 86
normalization-focused tests; 644 complete traversal contract tests; 112
adjacent path/contract tests; 87 adjacent runtime tests; and 2838 full-suite
tests with 1291 subtests, 0 failed, and 0 skipped. Compileall and
`git diff --check` passed. This does not cover actual runtime normalization,
real traversal, writer or traversal serialization behavior, trailing newlines,
repeated traversal-file bytes, or real `.FCStd` fixtures.

Ordering-extension contract coverage adds 54 focused tests across
`ReferenceTraversalOrderingExtensionFieldOrderTests`,
`ReferenceTraversalOrderingExtensionContractMetadataTests`,
`ReferenceTraversalOrderingExtensionFreshnessTests`,
`ReferenceTraversalOrderingExtensionCanonicalJsonTests`,
`ReferenceTraversalOrderingExtensionImportSafetyTests`,
`ReferenceTraversalOrderingExtensionSideEffectSafetyTests`, and
`ReferenceTraversalOrderingExtensionCompatibilityTests`, plus exact public API
expectation coverage. The tests cover:

- all five new public exports; exact immutable extension-only node and edge
  tuples; and exact complete extension orders
- schema-1 relative-order preservation and deliberate placement of `objectType`
  after `objectName` before `label`, and `sourceProperty` then
  `referenceMechanism` after edge `kind` before `state`
- exact metadata structure, zero-argument helper behavior, unknown-field and
  incidental-order policies, inactive activation flags, and fresh deeply
  mutation-isolated results
- canonical JSON determinism, blocked-FreeCAD import safety, and filesystem,
  time, process, environment, and random-identifier side-effect safety
- schema `"1.0"` and raw dataclass compatibility; unchanged payload shape,
  active schema-1 node/edge order keys, diagnostic and unresolved-entry order,
  serializer bytes, three-component semantic edge identity, and provenance-
  insensitive deduplication

Recorded validation evidence is 804 focused traversal contract tests with 422
subtests and 2998 full-suite tests with 1304 subtests, with 0 failures and 0
skips. This proves only the metadata/helper and inactive compatibility boundary;
it does not cover real FreeCAD traversal, runtime provenance application, a
traversal writer, runtime-emitted file equality, or real `.FCStd` fixtures.

- exact seven discovery/provenance public exports and no accidental private
  exports
- exact immutable provenance constants `objectType`, `sourceProperty`, and
  `referenceMechanism`; deterministic tuple order, no duplicates, and immutable
  tuple/mapping behavior
- document-internal, external-document, and external-file discovery semantics,
  existing scope/node/edge vocabulary reuse, and `documentPath` target evidence
- supported-runtime-evidence requirements; no inference from paths, extensions,
  suffixes, filesystem state, string shape, equal IDs, or missing paths; and
  rejection of ambiguous or unsupported mechanism guessing
- explicit metadata-only boundaries: no real discovery, runtime-value
  classification, diagnostic/failure creation, or schema change
- `objectType` association with object nodes and `sourceProperty`/
  `referenceMechanism` association with edge observations, including their
  distinction
- schema-1 inactive provenance locations `nodes[].objectType`,
  `edges[].sourceProperty`, and `edges[].referenceMechanism`; inactive schema
  status and existing-field overloading prohibitions
- raw FreeCAD/runtime ownership with Engine normalization and durable
  identity/storage explicitly unowned; these metadata helpers do not perform
  serialization, normalization, identity assignment, deduplication, or ordering
- deterministic canonical JSON and repeated canonical-byte equality, fresh
  nested structures, mutation isolation, and immutable module vocabulary
- unchanged schema `"1.0"`, dataclass fields, payload shape, semantic identity,
  deduplication, and ordering
- import safety with FreeCAD-family imports blocked
- raw reference traversal contract payload shape (`schemaVersion`, `kind`,
  `boundary`, `operation`, `status`, `sourceDocument`, `nodes`, `edges`,
  `diagnostics`)
- public constants and dataclass exports
- exact public ordering exports for node, edge, diagnostic, unresolved-entry,
  and total-ordering metadata constants/builders/helpers
- semantic node identity public API exports, exact global/per-kind field order,
  and exact excluded fields
- ordered tuple identity rules for `document`, `object`, `external_document`,
  and `external_file` nodes
- deterministic equality and semantic distinction across kind, path, and
  object-name components
- exact input preservation with no path/string normalization, trimming,
  case-folding, resolution, silent coercion, or filesystem dependency
- supported/unsupported kind, path, and required/forbidden object-name
  validation with deterministic single-line contract errors
- semantic identity metadata completeness, false capability flags, fresh
  independent return values, mutation isolation, and canonical JSON
  compatibility
- unchanged raw payload shape, arbitrary non-empty raw-kind pass-through,
  schema-1 ordering, state validation, and containment behavior
- exact node key priority: `documentPath` optional/`None`-first, `kind`, `id`,
  `objectName` optional/`None`-first, `label` optional/`None`-first, `state`,
  and `diagnostic` optional/`None`-first
- exact edge key priority: `source`, `target`, `kind`, `state`, and
  `diagnostic` optional/`None`-first
- exact diagnostic key priority: `stage` optional/`None`-first, `severity`,
  `code`, and `message`
- optional-string `None`-first behavior and ordinary lexicographic preservation
  of case, whitespace, Unicode, and path separators with no normalization
- immutable tuple output, input non-mutation, and duplicate preservation
  without ordering-time deduplication
- ordering before payload sequence assignment
- diagnostic sorting before zero-based sequencing, permutation-invariant
  payloads, and canonical byte equality across equivalent permutations
- unresolved-entry constants, exactly accepted `missing`/`unresolved` states,
  node-before-edge nested-key ordering, invalid state/type/container rejection,
  permutation invariance, duplicate preservation, and input non-mutation
- helper-only unresolved compatibility: no unresolved payload collection or
  unresolved-entry dataclass; unchanged schema and dataclass fields
- total-ordering metadata freshness, nested mutation isolation, JSON
  compatibility, and deterministic canonical serialization
- frozen `RawReferenceTraversalNode`, `RawReferenceTraversalEdge`, and
  `RawReferenceTraversalDiagnostic` dataclasses
- top-level, sequence-input, item-type, required-field, and optional-field
  validation errors
- deterministic zero-based `sequence` assignment for nodes, edges, and
  diagnostics independently
- canonical JSON compatibility through `dumps_canonical`
- import safety without FreeCAD module imports
- input non-mutation
- repeated-call determinism
- independent payload dict objects per `build_reference_traversal_output_payload`
  call

Recorded discovery/provenance validation evidence: 56 focused tests across the
four new contract test classes plus 2 public-API tests; 492 total tests in
`tests/test_reference_traversal_output_contract.py`; 179 adjacent runtime tests;
and 2686 full-suite tests. This coverage does not include fixture-backed or real
FreeCAD traversal.
- `REFERENCE_TRAVERSAL_STATE_RESOLVED`, `REFERENCE_TRAVERSAL_STATE_MISSING`,
  `REFERENCE_TRAVERSAL_STATE_UNRESOLVED`, `REFERENCE_TRAVERSAL_STATE_SKIPPED`,
  `REFERENCE_TRAVERSAL_STATE_FAILED`, and `REFERENCE_TRAVERSAL_DEFINED_STATES`
  constants and public exports through `__all__`
- deterministic five-state vocabulary order: `resolved`, then `missing`, then
  `unresolved`, then `skipped`, then `failed`
- node accepted-state validation for currently defined traversal states,
  including `"missing"`, `"unresolved"`, `"skipped"`, and `"failed"`
- edge accepted-state validation for currently defined traversal states,
  including `"missing"`, `"unresolved"`, `"skipped"`, and `"failed"`
- state vocabulary validation preservation
- canonical JSON compatibility for unresolved, skipped, and failed traversal
  payloads
- mixed resolved/missing/unresolved/skipped/failed payload ordering and
  contract-defined node/edge ordering before sequence assignment
- payload serialization for skipped and failed states
- unknown-state rejection through `ReferenceTraversalOutputContractError`
  for unknown strings
- intentional non-validation of graph semantics
- emitted raw evidence contract public API exports
- emitted path, identifier, object-name, label, inline diagnostic, and
  structured diagnostic field groups
- aggregate emitted-evidence metadata through
  `REFERENCE_TRAVERSAL_EMITTED_RAW_EVIDENCE_FIELDS` and
  `build_reference_traversal_emitted_raw_evidence_contract()`
- helper determinism, JSON compatibility, and independent return values
- unchanged normal traversal payload shape
- unchanged node/edge ordering behavior
- deterministic diagnostic total ordering behavior
- public API export coverage for reference distinction constants/helper
- reference scope vocabulary coverage (`document_internal`, `external_document`,
  `external_file`)
- node-kind and edge-kind vocabulary coverage
- internal/external edge-kind grouping coverage
- metadata helper determinism and canonical JSON compatibility through
  `build_reference_traversal_reference_distinction_contract()`
- helper result independence
- arbitrary raw `kind` pass-through on nodes and edges
- deterministic sequence assignment preservation
- diagnostic total ordering before sequencing
- malformed traversal request failure vocabulary constants
  (`REFERENCE_TRAVERSAL_DIAGNOSTIC_SEVERITY_ERROR`,
  `REFERENCE_TRAVERSAL_DIAGNOSTIC_CODE_MALFORMED_REQUEST`,
  `REFERENCE_TRAVERSAL_STAGE_REQUEST_VALIDATION`)
- malformed request failure contract helper through
  `build_reference_traversal_malformed_request_failure_contract()`
- malformed request failure contract out-of-scope disclaimers
- failed malformed request payload shape through
  `build_malformed_reference_traversal_request_payload(...)`
- caller-provided boundary/sourceDocument/diagnostic message values in failed
  malformed request payloads
- canonical JSON compatibility for malformed request contract and failed payload
- deterministic repeated-call behavior and independence/no mutation for
  malformed request contract and failed payload helpers
- invalid `sourceDocument` and `diagnosticMessage` input validation through
  `ReferenceTraversalOutputContractError`
- FreeCAD-free import safety for malformed request contract surface
- updated public API `__all__` export assertion for malformed request helpers and
  vocabulary constants
- traversal output path containment public API exports
  (`REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_ROOT`,
  `REFERENCE_TRAVERSAL_OUTPUT_PATH_CONTAINMENT_POLICY`,
  `REFERENCE_TRAVERSAL_OUTPUT_PATH_PARENT_POLICY`,
  `build_reference_traversal_output_containment_contract()`,
  `resolve_reference_traversal_output_path(...)`)
- containment contract metadata through
  `build_reference_traversal_output_containment_contract()`
- arbitrary safe basename, direct `_working`, and nested
  `_working/<execution-id>` root acceptance
- resolver positive cases for relative and absolute contained paths, nested
  parents, existing contained regular files, not-yet-created contained files, and
  `str`/`Path` inputs
- exact supplied-root authority with no widening to a parent or nearest
  `_working` ancestor
- parent, sibling, lexical traversal, canonical/resolved-path, absolute outside,
  and path-prefix-confusion rejection
- root symlink canonicalization and symlinked-parent/output-symlink escape
  rejection
- missing/non-directory root, missing/non-directory parent, and directory output
  target validation
- no-write/no-directory-creation coverage for
  `resolve_reference_traversal_output_path(...)`
- caller path-object non-mutation
- raw evidence path separation coverage confirming `sourceDocument` and
  `nodes[].documentPath` remain caller-provided raw evidence and are not
  containment-checked
- import safety without FreeCAD module imports

Focused validation command:

```bash
nix develop --command python -m pytest tests/test_reference_traversal_output_contract.py
# PASS, 434 passed, 402 subtests
```

Adjacent runtime validation:

```bash
nix develop --command python -m pytest tests/test_runtime_entrypoints.py tests/test_runtime_invocation.py tests/test_headless_invocation.py
# PASS, 94 passed, 4 subtests
```

Compile/import validation:

```bash
nix develop --command python -m compileall parametron_freecad scripts tests
# PASS
```

Full suite status:

```bash
nix develop --command python -m pytest
# PASS, 2628 passed, 1284 subtests, 0 failed, 0 skipped
```

Documentation-stage diff validation:

```bash
git diff --check
# PASS
```

The semantic edge/deduplication selection passed 91 tests and 63 subtests.
These are contract/helper tests. They do not prove real FreeCAD reference graph
traversal, actual reference discovery, runtime cycle guards, traversal output
writer behavior, CLI/runtime entrypoint wiring, real `.FCStd` reference
fixtures, property-sensitive identity, normalization, or Engine normalization.

## Focused Structured Failure Result Writer Coverage

`tests/test_failure_result_writer.py` covers:

- module import safety and public API surface (`write_failure_result`,
  `FailureResultWriteError`)
- canonical failed `prm.result.json` writes with structured failure payload shape
- repeated writes produce byte-stable output
- input `StructuredFailure` immutability
- `FailureResultWriteError` on invalid payload or write failures

## Focused Structured Failure Emission Coverage

Headless and runtime tests distinguish:

- safe result path + handled execute failure => failed `prm.result.json`
- no safe result path / argument failure => no `prm.result.json`

Evidence includes:

- `tests/test_headless_cli_arguments.py` — CLI execute failures with safe result
  path, invalid result path rejection, and `ResultWriteError` no-recursion
- `tests/test_headless_malformed_manifests.py` — malformed manifest failures write
  failed `prm.result.json`
- `tests/test_headless_unsupported_artifact_requests.py` — artifact export
  failures write failed `prm.result.json`
- `tests/test_headless_missing_working_copies.py` — argument vs execute failure
  split for `prm.result.json` creation
- `tests/test_headless_repeated_run.py` — repeated handled failure determinism
- `tests/test_runtime_entrypoints.py` — entrypoint stage attribution, best-effort
  emission, `ResultWriteError` no-recursion, failure-result write errors do not
  mask original failures
- `tests/test_runtime_invocation.py` — invocation preserves entrypoint-written
  failed `prm.result.json`
- `tests/test_integration_rehearsal.py` — rehearsal helper handled execution
  failures write failed `prm.result.json`

## Focused Aligned Execute-Plus-Observation Coverage

Test files for the aligned external live-document observation capability:

- `tests/test_headless_cli_arguments.py`
- `tests/test_runtime_entrypoints.py`
- `tests/test_observed_writer.py`
- `tests/test_observation_request.py`

### CLI contract tests

`tests/test_headless_cli_arguments.py`:

- `test_execute_observation_optional_argument_contract`
- `test_observation_request_requires_output_directory`
- `test_optional_paths_reject_empty_and_whitespace_values`
- `test_observation_paths_must_be_confined_and_have_required_types`

Coverage:

- accepted optional `--output-dir` / `--observation-request` arguments
- dependency between observation request and output directory
- empty/whitespace rejection
- path containment inside the validated working copy
- required path types (existing request file; output path not an existing
  regular file)
- standalone `observe` remains rejected
- unknown arguments remain rejected

### Observation request loader tests

`tests/test_observation_request.py`:

- `test_loads_valid_request`
- `test_malformed_json_is_wrapped_with_original_cause`
- `test_duplicate_keys_are_rejected`
- `test_non_standard_json_constants_are_rejected`
- `test_non_object_root_is_rejected`
- `test_unsupported_request_structure_is_rejected`
- `test_delegates_compatibility_and_does_not_mutate_loaded_data`
- `test_equivalent_json_inputs_load_to_equal_deterministic_data`

Coverage:

- strict JSON loading
- duplicate-key rejection
- non-standard constant rejection
- root shape validation
- compatibility delegation
- caller-data preservation
- deterministic normalized loading

### Live-document orchestration and digest tests

`tests/test_runtime_entrypoints.py`:

- `test_live_post_mutation_observation_phase_order_and_runtime_digest`
- `test_digest_changes_only_with_source_bytes_and_request_cannot_override_it`
- `test_execution_only_and_output_directory_alone_do_not_enable_observation`

Coverage:

- same open document instance
- post-mutation observation
- recompute/export/observation ordering
- observation before close
- post-persistence live observation (no reopen; working-copy document saved in place before observation)
- internally computed lowercase SHA-256 of source document bytes
- source-byte sensitivity
- output-directory independence
- request cannot override digest
- execution-only compatibility

### Failure behavior tests

`tests/test_runtime_entrypoints.py`:

- `test_observation_failures_close_document_write_structured_failure_and_preserve_cause`
- `test_request_loading_and_source_hash_failures_are_structured_observation_failures`

Coverage:

- stage `observation`
- structured failed `prm.result.json`
- no success result after failure
- guaranteed document cleanup
- original cause preservation
- pre-document-open request/hash failures
- no partial observed output

### Atomic observed writer tests

`tests/test_observed_writer.py`:

- `test_temporary_file_is_created_in_destination_and_atomically_replaces_target`
- `test_serialization_failure_preserves_existing_target_and_cleans_temporary`
- `test_replacement_failure_preserves_target_and_cleans_complete_temporary`

Coverage:

- destination-directory temporary file
- atomic replacement
- existing-target preservation on failure
- temporary-file cleanup
- no partial target output

### Native document persistence tests

`tests/test_document_save.py`:

- `test_module_import_does_not_require_freecad_or_export_modules`
- `test_save_document_calls_save_exactly_once_and_returns_none`
- `test_missing_and_non_callable_save_raise_deterministic_error`
- `test_save_exception_is_wrapped_and_preserves_original_cause`

`tests/test_runtime_entrypoints.py`:

- `test_zero_derived_outputs_still_save_and_observe_then_write_empty_artifacts`
- `test_save_failure_is_structured_and_short_circuits_all_later_work`
- `test_save_receives_exact_document_opened_from_validated_source`

`tests/test_reference_traversal_real_fixtures.py`:

- `test_runtime_native_save_persists_mutation_across_real_reopen`

Coverage:

- `save_document` helper imports safely without FreeCAD
- calls `document.save()` exactly once on the opened working-copy document
- missing or non-callable `save` raises deterministic `DocumentSaveError`
- save exceptions are wrapped in `DocumentSaveError` with original cause preserved
- lifecycle ordering: assign -> recompute -> save -> exports -> traversal -> observation -> close
- zero-derived-output execution (`outputs: []`) persists native document and produces `artifacts: []`
- save failure emits structured failed `prm.result.json` at stage `document_save` and short-circuits downstream stages
- observation uses the live persisted post-mutation document
- real FreeCAD 1.1.1 persistence round-trip: creates fixture, applies `Probe.Value = 42`, saves via runtime entrypoint, closes, reopens in real FreeCAD, and verifies `Probe.Value == 42`

### Verification-boundary tests that remain applicable

Existing tests that continue to prove FreeCAD emits raw observed facts and does
not perform Engine verification decisions:

- `test_output_contains_no_pass_fail_field`
- `test_checks_field_not_in_observation_output`
- `test_expected_value_ignored_observed_value_unconstrained`
- `test_checks_enabled_true_produces_no_output_field`
- `test_payload_contains_no_checks_or_comparison_fields`

### Validation results

Focused feature suite:

```bash
nix develop --command python -m pytest tests/test_headless_cli_arguments.py tests/test_runtime_entrypoints.py tests/test_observed_writer.py tests/test_observation_request.py
# PASS, 242 passed
```

Related runtime/observation suite:

```bash
nix develop --command python -m pytest tests/test_headless_cli_arguments.py tests/test_runtime_entrypoints.py tests/test_observed_writer.py tests/test_observation_request.py tests/test_runtime_invocation.py tests/test_engine_verification_compat.py
# PASS, 258 passed
```

Full suite:

```bash
nix develop --command python -m pytest
# PASS, 2310 passed, 1 skipped
```

The single skipped test is the existing environment-gated real headless
invocation coverage in `tests/test_headless_invocation.py`. It is not a failure
and leaves no unresolved or ambiguous failure status.

These counts are separate focused/related/full runs; overlapping focused
commands are not combined into a fictitious unique total.

## Focused Exact STEP Selector Coverage

Production:

```text
parametron_freecad/execution/step_export.py
```

FreeCAD tests:

```text
tests/test_step_export.py
tests/test_headless_cli_arguments.py
tests/test_headless_repeated_run.py
tests/test_headless_unsupported_artifact_requests.py
```

Sibling Engine surface:

```text
../parametron-engine/internal/engine/adapter/freecad_manifest_projection.go
../parametron-engine/internal/engine/adapter/freecad_manifest_projection_test.go
```

### Contract matrix

| Behavior                         | Expected                                  |
| -------------------------------- | ----------------------------------------- |
| Existing exact object name       | Selected object exported                  |
| Case mismatch                    | Missing-object failure                    |
| Label-only match                 | No fallback; failure                      |
| Different selectors              | Resolved/exported in order                |
| Repeated selector                | Exported once per declaration             |
| `document.Objects` access        | Forbidden                                 |
| Missing object                   | Deterministic failure                     |
| Lookup exception                 | Deterministic wrapped failure             |
| Missing/non-callable lookup      | Deterministic failure                     |
| CSV/PDF entries                  | Ignored by STEP helper                    |
| First selector failure           | Later declarations not processed          |
| Relative/absolute contained path | Existing acceptance preserved             |
| Escape/symlink/missing parent    | Existing rejection preserved              |
| Exporter exception               | Existing deterministic wrapping preserved |
| Injected exporter                | Lazy Import bypass preserved              |

### Focused STEP export methods

`tests/test_step_export.py`:

- `test_module_import_does_not_import_freecad_or_import_eagerly`
- `test_empty_outputs_are_accepted_and_do_nothing`
- `test_non_step_outputs_are_ignored`
- `test_step_outputs_are_exported_in_manifest_order`
- `test_relative_step_output_paths_resolve_against_working_copy`
- `test_absolute_step_output_path_inside_working_copy_is_accepted`
- `test_relative_traversal_outside_working_copy_is_rejected`
- `test_absolute_path_outside_working_copy_is_rejected`
- `test_symlink_escape_is_rejected`
- `test_missing_output_parent_directory_is_rejected`
- `test_output_parent_that_is_a_file_is_rejected`
- `test_injected_exporter_is_used_without_importing_import_module`
- `test_import_module_is_loaded_lazily_when_not_injected`
- `test_missing_import_module_becomes_deterministic_step_export_error`
- `test_missing_callable_export_function_becomes_deterministic_error`
- `test_exporter_exceptions_become_deterministic_step_export_errors`
- `test_export_step_artifacts_exports_exact_selected_object`
- `test_export_step_artifacts_allows_repeated_selectors`
- `test_export_step_artifacts_rejects_missing_selected_object_and_stops`
- `test_export_step_artifacts_wraps_get_object_exception`
- `test_export_step_artifacts_requires_callable_get_object`
- `test_export_step_artifacts_exact_name_has_no_case_or_label_fallback`

### Ownership

Engine owns:

- choosing and validating the selector
- projecting `Object` to `id`
- orchestration
- artifact acceptance
- verification and normalization

FreeCAD owns:

- exact `getObject(id)` lookup
- CAD-native selected-object export
- raw runtime result/failure evidence

### Selector coverage boundary

These are fake-FreeCAD tests, not real FreeCAD STEP geometry proof. They do not
exercise reference traversal or prove Engine invocation, artifact acceptance,
verification, or record generation. Those integration responsibilities remain
Engine-owned.

### Validation results

```bash
nix develop --command python -m pytest tests/test_step_export.py
# PASS, 22 focused STEP tests
```

```bash
nix develop --command python -m pytest \
  tests/test_headless_cli_arguments.py \
  tests/test_headless_repeated_run.py \
  tests/test_headless_unsupported_artifact_requests.py
# PASS, 78 updated headless tests
```

```text
296 adjacent contracts
46 runtime entrypoints
2343 full suite
compileall PASS
```

Engine focused/full regressions for aligned STEP selector projection also
passed in the sibling repository.

## Focused PartDesign Mutation Fixture Foundation Coverage

Production and test assets:

```text
scripts/generate_partdesign_mutation_fixtures.py
tests/fixtures/partdesign_mutations/partdesign-mutations.FCStd
tests/test_partdesign_mutation_fixtures.py
tests/freecad_partdesign_mutation_fixture_runner.py
```

### Contract matrix

| Tested Surface | Expected Behavior |
| --- | --- |
| Committed fixture existence | `tests/fixtures/partdesign_mutations/partdesign-mutations.FCStd` exists and is non-empty |
| Committed fixture SHA-256 integrity | Exactly matches locked digest `7187abe907ca6240bdc7cd07fb5ce7a52cf9192e3ba6d6153c581f18b328057a` |
| Inspection non-mutation | Committed fixture SHA-256 unchanged before and immediately after real FreeCAD inspection |
| Object and TypeId inventory | Exactly `MutationBody` (`PartDesign::Body`), `BaseSketch` (`Sketcher::SketchObject`), `IntermediatePad` (`PartDesign::Pad`), `PocketSketch` (`Sketcher::SketchObject`), `IntermediatePocket` (`PartDesign::Pocket`), `TerminalChamfer` (`PartDesign::Chamfer`), `SafeDeleteMarker` (`PartDesign::Feature`) |
| Body Tip | `MutationBody.Tip` resolves to `TerminalChamfer` |
| Feature dependency chain | `BaseSketch` -> `IntermediatePad` -> `IntermediatePocket` -> `TerminalChamfer` preserved |
| Suppression preconditions | `TerminalChamfer.Suppressed == True`; `IntermediatePad.Suppressed == False`; `IntermediatePocket.Suppressed == False` |
| App-level Visibility precondition | `MutationBody.Visibility == True` |
| Safe-delete candidate role | `SafeDeleteMarker` is unreferenced (`InList == []`, `OutList == []`) |
| Unsafe-delete candidate role | `BaseSketch` retains `IntermediatePad` in `InList` as a surviving dependent |
| Body shape health | Reopened `MutationBody.Shape` is non-null, valid, and contains exactly 1 solid |
| Generator success path | Generates valid fixture matching the full semantic contract, reports `reproducibility: "semantic"`, and cleans `.FCBak` files |
| Two-run semantic reproducibility | Two independent generator runs produce identical semantic inventory facts |
| Relative output rejection | Generator rejects non-absolute output path |
| Existing output protection | Generator rejects existing destination without modifying its contents or sentinel file |
| Missing output argument rejection | Generator rejects invocation without `--pass=` destination |
| Multiple output arguments rejection | Generator rejects invocation with multiple `--pass=` destinations |
| Nix-shell guard | Generator rejects execution outside `nix develop` environment |

### Focused test methods

`tests/test_partdesign_mutation_fixtures.py`:

- `CommittedPartDesignMutationFixtureTests`:
  - `test_committed_fixture_matches_full_semantic_contract`
  - `test_committed_fixture_unchanged_immediately_after_real_freecad_inspection`
- `PartDesignMutationGeneratorContractTests`:
  - `test_generator_success_path_matches_full_semantic_contract`
  - `test_generator_two_independent_runs_are_semantically_reproducible`
  - `test_generator_rejects_relative_output_path`
  - `test_generator_rejects_existing_destination_without_modifying_it`
  - `test_generator_rejects_missing_output_argument`
  - `test_generator_rejects_multiple_output_arguments`
  - `test_generator_rejects_execution_outside_nix_shell`

### Explicit distinctions and boundaries

- **Fixture prerequisite coverage documented:** Yes.
- **Fixture inspection claimed as mutation execution:** No.
- Canonical schema-1 mutation metadata and validation are covered in the current matrix above. Fixture inspection establishes starting native state only; focused real-FreeCAD suppression, visibility, and deletion coverage separately invokes the production consumers against temporary fixture copies and proves actual state transitions and removals. Deterministic post-mutation validity and native dependency inspection are implemented and covered separately below. Standalone conservative native deletion is implemented and covered separately below. This fixture-prerequisite run is historical. Current schema-1 execute integration and observation coverage are recorded in the table above; schema-2 requests are rejected.

### Validation results

Focused suite:

```bash
nix develop --command python -m pytest tests/test_partdesign_mutation_fixtures.py -q
# PASS, 11 passed in 4.56s
```

Full suite:

```bash
nix develop --command python -m pytest
# PASS, 3197 passed in 9.33s
```

Required real-FreeCAD skips: 0.

## Focused FreeCAD-Native Post-Mutation Validity Coverage

Production and test assets:

```text
parametron_freecad/execution/post_mutation_validity.py
tests/test_post_mutation_validity.py
tests/test_post_mutation_validity_real_fixtures.py
tests/freecad_post_mutation_validity_runner.py
```

`tests/freecad_post_mutation_validity_runner.py` is test-only FreeCAD
command-host support; it is not a production entrypoint.

### Focused fake/unit contract

| Tested Surface | Expected Behavior |
| --- | --- |
| Exact native lookup and supported type | Passes the requested name unchanged to `document.getObject()` and requires positive native `PartDesign::Body` type evidence; no Label or alias fallback |
| Healthy shape evidence | Reads `Shape.isNull()`, then `Shape.isValid()`, then observes `len(Shape.Solids)` and returns an immutable record with the exact requested object name |
| Failure classifications | `NativeValidityEvidenceUnavailableError` identifies absent, unsupported, or unusable required evidence; `NativeValidityInspectionError` identifies failures while invoking supported native inspection; `InvalidNativeCadStateError` identifies a native shape positively proven null or invalid |
| Cause preservation and diagnostics | Native lookup, predicate, solid inspection, and relationship-iteration failures preserve their underlying causes where applicable; messages and results are stable across repeated calls |
| Invalid-state precedence | Proven null state is classified before `isValid()` or solid evidence is required; proven `isValid() == False` is classified before solid evidence is required |
| Solid-count semantics | Zero, one, and multiple solids are retained as evidence; solid count is not a universal acceptance threshold |
| Native dependency mapping | `InList` maps to dependents and `OutList` maps to dependencies; related objects require stable native `Name` values |
| Dependency determinism | Duplicate names are removed, names are ordered lexically, input enumeration order does not affect immutable tuple results, and repeated calls agree |
| Document-level Body validity composition | `inspect_document_post_mutation_validity(document)` discovers surviving native `PartDesign::Body` objects in stable native-name order; results are deterministic and independent of `document.Objects` enumeration order; fails closed with `NativeValidityEvidenceUnavailableError` when no supported Body evidence exists; reuses bounded Body shape-health inspection; solid count remains evidence and not a universal acceptance threshold |
| Policy boundary | Dependency inspection reports native relationships only and makes no deletion-safety decision |
| Read-only and import-safe behavior | The inspection APIs do not mutate, recompute, save, close, or remove objects; importing the module does not require FreeCAD. |

### Permanent real-FreeCAD evidence

| Tested Surface | Established Fixture/Test Fact |
| --- | --- |
| Healthy native Body | Production inspection of `MutationBody` on temporary copies of the committed fixture reports non-null, valid native shape evidence with one solid |
| Solid-count scope | One solid is a locked fact about `MutationBody` in this fixture, not a general validity rule |
| Representative native dependencies | `SafeDeleteMarker` has no `InList` or `OutList` relationships under the locked fixture contract; `BaseSketch` reports `IntermediatePad` as a dependent; `IntermediatePad` reports `IntermediatePocket` as a dependent and `BaseSketch` as a dependency |
| Genuine invalid native state | A fresh test-owned empty `PartDesign::Body` has a genuinely null native shape. Real FreeCAD raises if `isValid()` is queried on that null shape, so production checks proven nullity first and deterministically raises `InvalidNativeCadStateError` |
| Independent-run determinism | Separate `freecadcmd` processes produce equal normalized healthy evidence, dependency evidence/order, and invalid-state diagnostics |
| Read-only fixture handling | Fixture-backed tests inspect temporary copies, before/after native state snapshots agree, and committed fixture hash/content remains unchanged; the empty-Body probe is in-memory and does not touch the fixture |

This coverage establishes the read-only native validity/dependency
infrastructure and permanent valid/invalid evidence originally introduced in
issue #3 and consumed by the standalone conservative native deletion
consumer in issue #4. Inspection helpers remain read-only; mutation, removal,
and recompute remain caller-owned. Canonical schema-1
execute composes these capabilities with ordered stages and structured failure
mapping, as recorded in the current coverage table. Engine continues to
own expected-versus-observed comparison, tolerance evaluation, engineering
verification decisions, and normalized durable records.

## Focused FreeCAD-Native Suppression / Unsuppression Coverage

Production and test assets:

```text
parametron_freecad/execution/suppression.py
tests/test_suppression.py
tests/test_suppression_real_fixtures.py
tests/freecad_suppression_runner.py
```

`tests/freecad_suppression_runner.py` is test-only FreeCAD command-host support;
it is not a production entrypoint.

| Tested Surface | Expected Behavior |
| --- | --- |
| Exact native target resolution | Passes the request's `object` string unchanged to `document.getObject`; missing, case-variant, alias, and Label values do not trigger fallback lookup |
| Native capability requirement | Requires an existing native `Suppressed` property whose type is exactly `App::PropertyBool`; does not synthesize unsupported properties |
| Requested states | `suppressed: true` writes native `True`; `suppressed: false` writes native `False` |
| Controlled failures | Missing and unsupported targets and native lookup, inspection, and write failures use the consumer's controlled error types; underlying native causes are preserved where applicable |
| Ordering and fail-fast | Applies entries in caller-provided order, stops at the first failure, retains earlier successful writes, and does not apply later entries |
| Request preservation | Does not rewrite mutation mappings or reorder the supplied sequence |
| Real `TerminalChamfer` transition | Production consumer changes native `Suppressed` from `True` to `False` on a temporary copy |
| Real intermediate-feature transitions | Production consumer changes native `Suppressed` from `False` to `True` for `IntermediatePad` and `IntermediatePocket`, each on an independent temporary copy |
| Visibility independence | Suppression and unsuppression leave native visibility unchanged |
| Fixture integrity | Committed PartDesign fixture bytes remain unchanged after real-FreeCAD mutation tests |

This historical section covers the standalone native consumer. Current
canonical schema-1 execute integration, recompute, save, and persistence are
covered by the production-execute fixture tests in the current matrix.

## Focused FreeCAD-Native Visibility Coverage

Production and test assets:

```text
parametron_freecad/execution/visibility.py
tests/test_visibility.py
tests/test_visibility_real_fixtures.py
tests/freecad_visibility_runner.py
```

`tests/freecad_visibility_runner.py` is test-only FreeCAD command-host support;
it is not a production entrypoint.

| Tested Surface | Expected Behavior |
| --- | --- |
| Exact native target resolution | Passes the request's `object` string unchanged to `document.getObject`; missing, case-variant, alias, and Label values do not trigger fallback lookup |
| Native App-level capability | Requires an existing native `Visibility` property whose type is exactly `App::PropertyBool`; does not synthesize unsupported properties |
| Hide and unhide | `visible: false` writes native `False`; `visible: true` writes native `True` |
| Controlled failures | Missing and unsupported targets and native lookup, inspection, and write failures use visibility-specific controlled error types; underlying native causes are preserved where applicable |
| App-level-only behavior | Does not import `FreeCADGui` or access `ViewObject` |
| Suppression independence | Visibility mutations do not call the suppression consumer or alter native `Suppressed` state |
| Ordering and fail-fast | Applies entries in caller-provided order, stops at the first failure, retains earlier successful writes without rollback, and does not apply later entries |
| Request preservation | Does not rewrite mutation mappings or reorder the supplied sequence |
| Empty collection | Performs no object lookup and succeeds without mutation |
| Real hide and unhide | Production consumer changes `MutationBody.Visibility` from `True` to `False` and `BaseSketch.Visibility` from `False` to `True`, each on a temporary fixture copy |
| Real missing target | Exact missing object name produces a controlled `VisibilityTargetNotFoundError` through real FreeCAD |
| Fixture integrity | Committed PartDesign fixture bytes remain unchanged after real-FreeCAD visibility tests |

This historical section covers the standalone visibility consumer. Current
canonical schema-1 execute integration and persistence are covered by the
production-execute fixture tests in the current matrix.

## Focused FreeCAD-Native Deletion Coverage

Production and test assets:

```text
parametron_freecad/execution/deletion.py
tests/test_deletion.py
tests/test_deletion_real_fixtures.py
tests/freecad_deletion_runner.py
```

`tests/freecad_deletion_runner.py` is test-only FreeCAD command-host support;
it is not a production entrypoint.

| Tested Surface | Expected Behavior |
| --- | --- |
| Exact native target resolution | Passes the request's `object` string unchanged to `document.getObject`; missing, case-variant, alias, and Label values do not trigger fallback lookup; missing target raises `DeletionTargetNotFoundError` |
| Native dependency inspection | Inspects native dependencies via `inspect_native_dependencies` before removal; missing or unusable required evidence raises `DeletionNativeOperationError` |
| Surviving-dependent rejection | Raises `UnsafeDeletionTargetError` when native `InList` reports surviving dependents; does not mutate document or remove targets; no cascade, recursive deletion, dependency repair, or force-delete policy |
| Native removal | Removes accepted targets through `document.removeObject` |
| Post-removal absence verification | Verifies requested exact object is absent (`document.getObject` returns `None`) after removal; raises `DeletionNativeOperationError` if still present or lookup fails |
| Post-removal recompute and Body validity | Recomputes document after removal via `recompute_document`; inspects document-level surviving `PartDesign::Body` validity via `inspect_document_post_mutation_validity`; recompute or validity failures raise `DeletionValidityError` |
| Fail-closed evidence semantics | Missing or unavailable required dependency or post-delete Body validity evidence fails closed; genuine invalid post-delete Body state (such as null shape) fails closed; solid count remains evidence, not a universal validity rule |
| Controlled failures and cause chains | Missing targets, native removal failures, dependent conflicts, and post-delete validity failures use deletion-specific controlled error types; underlying native causes are preserved where applicable |
| Ordering and fail-fast | Applies entries in caller-provided order, stops at the first failure, does not roll back earlier completed destructive deletions, and does not apply later entries |
| Request preservation | Does not rewrite mutation mappings or reorder the supplied sequence |
| Import safety | `parametron_freecad.execution.deletion` imports safely without FreeCAD modules present |
| Real `SafeDeleteMarker` removal | Production consumer safely deletes `SafeDeleteMarker` on a temporary fixture copy; `MutationBody` survives with valid shape evidence; committed fixture bytes remain unchanged |
| Real `BaseSketch` rejection | Production consumer rejects deletion of `BaseSketch` because real native `InList` evidence includes `IntermediatePad`; fixture object inventory remains unchanged |
| Real missing target | Nonexistent object name produces a controlled `DeletionTargetNotFoundError` through real FreeCAD |
| Genuine invalid post-delete Body state | Fresh test-owned in-memory document with empty Body fails post-delete validity with `DeletionValidityError` wrapping `InvalidNativeCadStateError` |
| Repeated-run determinism | Independent `freecadcmd` processes produce identical results, inventories, and diagnostics for safe, unsafe, and invalid-state scenarios |
| Fixture integrity | Committed PartDesign fixture bytes remain unchanged after real-FreeCAD deletion tests |

This historical section covers the standalone native deletion consumer.
Current canonical schema-1 execute lifecycle and structured failure mapping are
covered in the current matrix. Engine owns planning, semantic target resolution,
verification decisions, and normalized records.

### Validation results

Focused deletion suite:

```bash
nix develop --command python -m pytest tests/test_deletion.py -q
# PASS, 65 passed, 5 subtests passed
```

Real-FreeCAD deletion suite:

```bash
nix develop --command env PARAMETRON_FREECAD_STRICT_SMOKE=1 \
  python -m pytest tests/test_deletion_real_fixtures.py -q
# PASS, 12 passed, 0 skipped
```

Document-level validity and fixture regressions:

```bash
nix develop --command python -m pytest tests/test_post_mutation_validity.py -q
# PASS, 83 passed, 9 subtests passed
```

```bash
nix develop --command env PARAMETRON_FREECAD_STRICT_SMOKE=1 \
  python -m pytest tests/test_post_mutation_validity_real_fixtures.py tests/test_partdesign_mutation_fixtures.py -q
# PASS, 22 passed
```

Aggregate suite status:

```bash
nix develop --command python -m pytest
# PASS, 3682 passed, 1609 subtests passed
```

## Canonical Manifest Mutation Validation

`tests/test_manifest_mutation_contract.py` checks canonical schema-1 contract
metadata. `tests/test_manifest_mutation_validation.py` checks standalone
schema-1 validation of sparse and combined suppression, visibility, and
deletion mutations. It covers exact field shapes, strict booleans, duplicate
and cross-scope conflict rejection, deterministic diagnostic order, and input
immutability. Schema 2.0 is rejected by both standalone validation and normal
execution before FreeCAD document operations.

```bash
python -m pytest tests/test_manifest_mutation_contract.py tests/test_manifest_mutation_validation.py tests/test_canonical_manifest_validation.py
```

## Documentation-Only Validation

For documentation-only changes, review the diff for current implementation and
contract accuracy, and check links and stale references.

```bash
git diff --check
git status --short --branch
git diff -- README.md AGENTS.md docs/test-matrix.md
git status --short
```

Implementation tests are not required for documentation-only edits unless local
instructions or review scope explicitly ask for them.
