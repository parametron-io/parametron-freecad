# Test Matrix

This matrix records current validation coverage for `parametron-freecad`.
It distinguishes contract/helper, fake-FreeCAD, and real-FreeCAD coverage,
including rejection of unsupported requests. It does not create new requirements.
Recorded validation counts below are separate prior runs, not a claim that the
current suite was rerun or that overlapping counts should be summed.

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
python -m pytest tests/test_manifest_contract.py tests/test_manifest_v2_contract.py tests/test_manifest_loader.py tests/test_manifest_validation.py tests/test_manifest_v2_validation.py
python -m pytest tests/test_result_writer.py
python -m pytest tests/test_failure_output_contract.py tests/test_failure_result_writer.py tests/test_trace_output_contract.py
python -m pytest tests/test_reference_traversal_output_contract.py
python -m pytest tests/test_reference_traversal_request.py tests/test_reference_traversal.py
python -m pytest tests/test_step_export.py tests/test_csv_export.py tests/test_pdf_export.py
```

Focused observation/reference-foundation checks:

```bash
python -m pytest tests/test_reference_access.py tests/test_reference_observation.py
python -m pytest tests/test_requested_scope_observation.py tests/test_observed_writer.py tests/test_observed_output_repeated_run.py
python -m pytest tests/test_observation_request.py
```

Focused native suppression checks:

```bash
python -m pytest tests/test_suppression.py
python -m pytest tests/test_suppression_real_fixtures.py
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

## Current Coverage

| Area | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Installable `parametron-freecad` launcher | Covered | `tests/test_launcher.py`, `tests/test_headless_invocation.py`, `tests/test_environment_contract.py` | Host resolution, structured `--pass=` forwarding, process behavior, Nix wrapper discovery, real smoke. |
| Headless smoke mode | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_invocation.py`, `tests/test_launcher.py` | Real FreeCAD smoke exercises `parametron-freecad`, not direct script invocation. |
| Headless execute CLI | Covered | `tests/test_headless_cli_arguments.py` | `execute --working-copy --manifest --result [--output-dir] [--observation-request] [--reference-traversal-request]`. |
| Traversal request schema 2 / mapped external evidence | Covered | `tests/test_reference_traversal_request.py`, `tests/test_reference_traversal.py`, `tests/test_runtime_entrypoints.py` | Closed schema-1 compatibility; strict five-field schema-2 mappings; canonical validation/order; resolved, missing, partial-list, unmatched, ambiguous, provenance, ID, relocation, and byte-stability behavior. |
| Aligned execute-plus-observation CLI | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_runtime_entrypoints.py` | Optional observation on `execute`; standalone `observe` remains rejected. |
| Observation request loading boundary | Covered | `tests/test_observation_request.py` | Strict JSON load, compatibility delegation, deterministic normalized data. |
| Live-document observation orchestration | Covered | `tests/test_runtime_entrypoints.py` | Same open document; post-mutation/export observation; internal source digest. |
| `_working` / supplied execution root | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_missing_working_copies.py`, `tests/test_file_argument_contract.py`, `tests/test_paths.py` | Supplied existing directory is authoritative; basename unrestricted; direct `_working` and nested `_working/<execution-id>` accepted; child containment preserved. |
| Manifest path containment | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_missing_working_copies.py` | Checked before FreeCAD import. |
| Result path containment | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_headless_missing_working_copies.py` | Invalid result paths reject before file creation; safe path required for failed `prm.result.json`. |
| `sourceDocument` containment | Covered | `tests/test_document_lifecycle.py`, `tests/test_headless_missing_working_copies.py`, `tests/test_headless_cli_arguments.py` | Traversal and symlink escapes rejected against the supplied root. |
| FreeCAD-native manifest contract | Covered | `tests/test_manifest_contract.py` | Filename is `prm.export-manifest.json`. |
| Manifest schema 2.0 contract metadata & strict validation | Covered | `tests/test_manifest_v2_contract.py`, `tests/test_manifest_v2_validation.py` | Schema 2.0 metadata defined; required core fields and optional `assemblyMutations`/`partMutations`; `{object, suppressed}`, `{object, visible}`, `{object}` shapes; shared section contract; parameter/output reuse; transport filename remains `prm.export-manifest.json`; immutability, import safety, and frozen tuples; strict Schema 2.0 validation implemented (`validate_export_manifest_v2`, `validate_export_manifest`); exact version dispatch (`"1.0"` vs `"2.0"`); strict JSON booleans; duplicate object rejection; suppression/visibility vs deletion conflict rejection; suppression + visibility allowed; cross-scope object conflict rejection; deterministic diagnostics. The execute entrypoint remains V1-only and rejects schema 2.0 before document operations. The standalone native suppression/unsuppression consumer is implemented and tested but is not wired to execute; native visibility and deletion execution remain unimplemented. |
| Strict manifest loading | Covered | `tests/test_manifest_loader.py`, `tests/test_headless_malformed_manifests.py` | Duplicate keys and non-standard JSON constants rejected. |
| Manifest structural validation | Covered | `tests/test_manifest_validation.py` | Exact field surfaces and supported formats. |
| Engine dot-form manifest compatibility | Covered | `tests/test_engine_manifest_compat.py`, `tests/test_runtime_entrypoints.py`, `tests/fixtures/engine_generated/export_manifest.v1.json` | Transitional compatibility only. |
| Engine name-only parameter rejection | Covered | `tests/test_engine_manifest_compat.py`, `tests/test_runtime_entrypoints.py` | Rejected before document open and side effects. |
| Exact parameter target resolver | Covered | `tests/test_parameter_target_resolver.py`, `tests/test_parameter_assignment.py` | `<ObjectName>.<PropertyName>` only. |
| Parameter assignment | Covered | `tests/test_parameter_assignment.py`, `tests/test_headless_cli_arguments.py` | Scalar assignment in manifest order. |
| Document recompute | Covered | `tests/test_document_recompute.py`, `tests/test_headless_cli_arguments.py` | Recompute called once. |
| Native document persistence | Covered | `tests/test_document_save.py`, `tests/test_runtime_entrypoints.py`, `tests/test_failure_output_contract.py`, `tests/test_reference_traversal_real_fixtures.py` | `document.save()` is called exactly once on the opened working copy after recompute and before exports/traversal/observation; `DocumentSaveError` wraps save failures and maps to stage `document_save`; zero derived outputs (`outputs: []`) persist native document and yield `artifacts: []`; real FreeCAD close/reopen semantic round trip proves `Probe.Value` persists across real reopens. |
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
| Observation ordering | Covered | `tests/test_observation_ordering.py`, `tests/test_requested_scope_observation.py` | Deterministic ordering for already-built payloads. |
| Observed JSON writing | Covered | `tests/test_observed_writer.py`, `tests/test_observed_output_repeated_run.py` | Canonical UTF-8 JSON with atomic destination replacement; no standalone CLI `observe`. |
| Engine invocation surface | Covered | `tests/test_runtime_invocation.py`, `tests/test_invocation_contract.py` | Execute and observe modes; execute failures preserve entrypoint-written failed `prm.result.json`. |
| Normal planner-generated Engine-to-FreeCAD invocation | Indirectly covered | `https://github.com/parametron-io/parametron-engine/blob/main/docs/test-matrix.md` | FreeCAD-local tests cover the runtime boundary; Engine planner/executor integration coverage belongs to the Engine repository. |
| File argument metadata | Covered | `tests/test_file_argument_contract.py`, `tests/test_invocation_contract.py` | Metadata only. |
| Output file metadata | Covered | `tests/test_output_file_contract.py`, `tests/test_invocation_contract.py` | Metadata only. |
| Engine-facing error classes | Covered | `tests/test_error_contract.py`, `tests/test_runtime_invocation.py` | In-process invocation errors. |
| Fixture-based integration rehearsal helper | Covered | `tests/test_integration_rehearsal.py` | Local/test helper; handled execution failures write failed `prm.result.json`. |
| Artifact byte comparison helper | Covered | `tests/test_artifact_comparison.py` | Exact byte comparison only. |
| Raw reference traversal contract helper | Covered | `tests/test_reference_traversal_output_contract.py` | Contract/helper coverage includes semantic node/edge identity and identity-key deduplication; public total-order keys; item-level state metadata; aggregate-status metadata helper and exact public export; deterministic `succeeded`, `partial`, `failed` order and semantics; semantic completeness and item/aggregate separation; canonical JSON/repeated bytes, fresh nested structures, mutation isolation, blocked-FreeCAD import safety, caller-status and malformed-request compatibility, and unchanged schema/dataclasses. No actual runtime classification or status derivation, normalization, real traversal, diagnostics collection, runtime failure-path execution, or runtime wiring. Direct writer coverage is recorded separately. |
| Reference traversal in-memory canonical serialization | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_canonical_json.py` | Exact public export and keyword-only signature; payload-builder/canonical-helper byte equivalence; compact sorted-key UTF-8 bytes; no BOM or CRLF; exactly one trailing LF; direct non-ASCII, duplicate, and exact-string preservation; repeated and reordered-input byte equality under existing total orders; independent node/edge/diagnostic sequencing; validation propagation; mutation isolation; blocked-FreeCAD import safety; and no filesystem side effects. This covers pure bytes only, not writing or runtime emission. |
| Semantic traversal node identity contract/helper | Covered | `tests/test_reference_traversal_output_contract.py` | Exact exports and ordered fields; four semantic tuple-key forms; exact exclusions; deterministic equality/distinction; no normalization or coercion; kind/path/object-name validation and deterministic errors; metadata completeness, freshness, mutation isolation, and canonical JSON compatibility; unchanged raw payload/arbitrary raw-kind behavior; import safety. This node-focused coverage does not prove `.FCStd` discovery, real FreeCAD traversal, writer/runtime wiring, node deduplication, or normalization; semantic edge helper coverage is recorded separately below. |
| Semantic traversal edge identity/deduplication contract/helper | Covered | `tests/test_reference_traversal_output_contract.py` | Exact public API, immutable constants/metadata, directed nested keys across supported node/edge kinds, node-key and edge-kind validation, self-edges, reverse-edge distinction, duplicate elimination, deterministic sorting, permutation/repetition-count independence, shared-target and graph-relationship preservation, no normalization, no input mutation, raw payload compatibility, arbitrary raw edge-kind pass-through, duplicate raw-edge preservation, provenance limitation, and import safety. This is not real traversal, runtime cycle-guard, writer/wiring, `.FCStd` fixture, or property-sensitive identity coverage. |
| Reference discovery-semantics and provenance-requirements contract/helpers | Covered | `tests/test_reference_traversal_output_contract.py` | Exact seven exports with no private exports; immutable `objectType`/`sourceProperty`/`referenceMechanism` vocabulary and proposed locations; three metadata-only classifications; supported-runtime-evidence and no-guess policies; raw FreeCAD ownership; inactive schema `"1.0"` fields; canonical JSON, freshness, mutation isolation, compatibility, and import safety. No real discovery, runtime classification, provenance serialization, fixture-backed traversal, Engine normalization, or durable storage behavior. |
| Reference traversal normalization metadata contract/helper | Covered | `tests/test_reference_traversal_output_contract.py` | 86 focused tests cover exact public no-argument API, field categories, stable strings and exact raw evidence, inactive provenance, lexical contract-relative paths, filesystem/containment/Engine distinctions, destructive-canonicalization raw preservation, unchanged schema `"1.0"`, canonical JSON, deep freshness, blocked-FreeCAD imports, no filesystem side effects, and payload/identity/deduplication/ordering compatibility. No actual normalization, traversal, serialization, writer, or wiring. |
| Reference traversal semantic output exclusion metadata contract/helper | Covered | `tests/test_reference_traversal_output_contract.py` | Exact eight exports; exact timestamp, request-ID, actor, process/runtime identity, temporary absolute path, and incidental enumeration-order aggregate order and semantics; operational placement and anti-overloading; canonical JSON and repeated metadata-byte equality; deep freshness/mutation isolation; guarded in-process/subprocess import safety; no filesystem/runtime side effects; unchanged payload/dataclasses, identity/deduplication, ordering/sequence, normalization/containment, and runtime behavior. This is metadata contract repeated-byte equality, not serialized traversal output-file repeated-run equality, and it does not cover real FreeCAD traversal. |
| Reference traversal output path containment | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_reference_traversal_output_writer.py`, `tests/test_runtime_entrypoints.py`, `tests/test_paths.py`, `tests/test_output_file_contract.py`, `tests/test_file_argument_contract.py` | Resolver coverage uses the exact supplied existing directory as authoritative, with unrestricted basename, arbitrary/direct/nested root acceptance, no ancestor widening, and lexical/resolved/symlink escape rejection. The runtime delegates canonical output emission to the atomic writer with that exact root. |
| Traversal authoritative execution-root reconciliation | Covered | `tests/test_reference_traversal_output_contract.py` | Focused accepted/rejected path coverage proves safe arbitrary, direct `_working`, and nested attempt roots while preserving exact-root containment and symlink-aware escape prevention. |
| Reference traversal request contract/loader | Covered | `tests/test_reference_traversal_request.py`, `tests/test_file_argument_contract.py` | Exact closed schema `{"schemaVersion":"1.0"}`; immutable normalized model; canonical request/output filenames; optional CLI/file metadata; strict UTF-8, JSON, duplicate-key, non-standard-constant, root, field, and version validation; filesystem failures and all invalid inputs use one chained public error; no FreeCAD or write side effects. |
| Real FreeCAD reference graph traversal | Covered | `tests/test_reference_traversal_real_fixtures.py`, `tests/fixtures/reference_traversal/` | FreeCAD 1.1.1 opens the committed three-document bundle and produces an exact frozen schema-2 payload for internal, mapped resolved external, shared-target, and Engine-authorized missing evidence. IDs are independently derived from the public identity formula. |
| Deterministic direct traversal output writer | Covered | `tests/test_reference_traversal_output_writer.py` | The 17 direct-writer tests cover the public `write_reference_traversal_output(...)` API and FreeCAD-independent import, exact serializer-byte equality, exactly-once delegation, unchanged distinctive-byte forwarding, repeated ordinary overwrite determinism, representative reordered-input byte equality, input non-mutation, chained serialization and file-write error translation, missing-parent non-creation, and caller/relative-path pass-through. This compatibility writer is deliberately direct, non-atomic, and independent of containment resolution. |
| Atomic traversal output replacement | Covered | `tests/test_reference_traversal_output_writer.py` | The 42 atomic-writer tests cover the public/import-safe `write_reference_traversal_output_atomically(...)` API; serializer exactly-once delegation and unchanged bytes; same-directory unique temporary files; write/close-before-`os.replace(...)` ordering; missing-target creation and existing-target replacement; repeated deterministic writes; preservation across resolver, serializer, temporary-file creation/wrapping, write, close, and replacement failures; cleanup and cleanup-failure precedence; chained writer errors; input non-mutation; and direct-writer independence. This is writer-unit, not runtime traversal, coverage. |
| Containment-integrated traversal writing | Covered | `tests/test_reference_traversal_output_writer.py`, `tests/test_reference_traversal_output_contract.py` | The atomic writer delegates exactly once to the existing resolver using the exact supplied authoritative `working_copy`; safe arbitrary, direct `_working`, and nested `_working/<execution-id>` roots are represented, the basename remains unrestricted, and no ancestor widening occurs. No traversal entrypoint/runtime wiring is implied. |
| Traversal request CLI path validation | Covered | `tests/test_headless_cli_arguments.py`, `tests/test_file_argument_contract.py` | Optional invocation field and flag; empty/missing/directory/outside-root rejection; exact-root containment; `--output-dir` dependency; malformed/non-UTF-8 content is not read during argument validation. |
| Traversal request entrypoint loading | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal_request.py` | Optional path is forwarded; strict loader runs exactly once after manifest/source validation and before FreeCAD/document operations; absence skips loading; direct entrypoint output-directory dependency; malformed requests preserve cause, emit a canonical failed raw traversal payload before FreeCAD resolution, and fail top-level `prm.result.json` at `request_validation`; no CAD traversal runs. |
| Traversal request absence compatibility | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_runtime_invocation.py`, `tests/test_headless_cli_arguments.py`, `tests/test_step_export.py`, `tests/test_csv_export.py`, `tests/test_pdf_export.py` | Explicit regression proof preserves manifest load/validation, source resolution, document lifecycle, assignment, recompute, all export families, observation, success results, and exact Engine invocation fields/delegation when traversal is absent. |
| Traversal request execution wiring and emission | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_headless_cli_arguments.py`, `tests/test_reference_traversal_output_writer.py` | Traversal runs after recompute and all STEP/CSV/PDF exports and before observation; `succeeded`/`partial` are atomically emitted to the canonical filename beneath the existing output directory, then continue; the exact working copy is the sole containment root; runtime/writer create no directories; failed traversal and controlled containment/write errors skip observation while completed exports remain. Stable `runtime_failure` stages cover traversal and output containment/write failures; malformed-request raw output is covered separately. |
| Typed reference traversal callable boundary / discovery | Covered | `tests/test_reference_traversal.py` | Exact public signature; immutable four-field result; exact status vocabulary; representable partial/failed evidence; raw tuple type enforcement; chained public error; source-root and participating-object discovery; supported internal and Engine-mapped external relationships; unsupported-value-shape partial diagnostics; and FreeCAD-independent import. Serialization, writing, containment, Engine normalization, and durable storage behavior remain outside the callable. |
| Reference traversal fixtures | Covered | `tests/test_reference_traversal_real_fixtures.py`, `scripts/generate_reference_traversal_fixtures.py`, `tests/fixtures/reference_traversal/` | One root and two referenced documents cover internal, external, shared-target, and mapped missing evidence. The Nix/FreeCAD 1.1.1 maintenance generator guarantees semantic reproducibility; the small binary bundle is stored directly in Git without LFS. |
| Reference traversal ordering/deduplication/cycle guards | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_reference_traversal.py`, `tests/test_reference_traversal_output_v2.py`, `tests/test_runtime_entrypoints.py` | Typed schema-2 results collapse equal resolved/missing/unresolved nodes and edges by complete identity before deterministic ordering/sequencing, at the same aligned canonicalization boundary for both; distinct identity components, shared targets, multiple outgoing edges, schema-1 multiplicity, byte stability, permutation independence, and controlled conflict chaining (including node-only conflicts and no partial committed output) are covered. |
| Reference traversal direct-writer repeated-run byte equality | Covered | `tests/test_reference_traversal_output_writer.py` | Repeated direct writes and representative reordered inputs are byte-identical through the authoritative serializer contract. This is writer unit coverage, not real traversal or runtime-emitted output. |
| Reference traversal runtime-emitted file | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal_real_fixtures.py` | Atomic writer integration proves the exact canonical destination and trailing newline. Production-entrypoint traversal of relocated real fixtures is byte-identical across repeated, arbitrary-basename, and nested working roots, with no absolute-path leakage or fixture mutation. |
| Reference traversal controlled failures | Covered | `tests/test_runtime_entrypoints.py`, `tests/test_failure_output_contract.py`, `tests/test_reference_traversal_output_writer.py` | Malformed request raw output, document-open `runtime_failure` / `document_open`, typed/exception traversal `runtime_failure` / `reference_traversal`, containment `runtime_failure` / `reference_traversal_output_containment`, and serialization/write/replacement `runtime_failure` / `reference_traversal_output_write` are exact. Boundary/category/shape/messages and full exception chains are preserved. |
| Traversal diagnostic classification/deduplication/ordering | Covered | `tests/test_reference_traversal_output_contract.py`, `tests/test_reference_traversal.py` | Unsupported allowlisted non-None value shapes return one schema-neutral warning at `reference_discovery`, status `partial`, and no inferred mapped-missing evidence. Schema-2 exact diagnostic duplicates collapse by complete record before the existing total order and sequence assignment; schema-1 multiplicity is unchanged. Typed results reject canonical Python traceback blocks through the existing chained execution error. |
| Traversal-present execute/export compatibility | Covered | `tests/test_runtime_entrypoints.py` | Declared output objects reach STEP, CSV, PDF, and success-result artifact handling unchanged and in the established pipeline order around traversal emission. |
| Real FreeCAD reference API inspection | Covered | `tests/test_reference_traversal.py`, bounded-unit command-host probe | FreeCAD 1.1.1 accepted the exact 21 private Link/XLink type-ID allowlist and exposed object/subelement/list value shapes. No heuristic string/path mechanism is included; supported internal discovery now applies this surface. |
| PartDesign mutation fixture foundation | Covered | `tests/test_partdesign_mutation_fixtures.py`, `tests/freecad_partdesign_mutation_fixture_runner.py`, `scripts/generate_partdesign_mutation_fixtures.py`, `tests/fixtures/partdesign_mutations/partdesign-mutations.FCStd` | Permanent fixture integrity (SHA-256 `7187abe9...`), native role/TypeId inventory, Body Tip and dependency chain, `Suppressed` and App-level `Visibility` preconditions, safe vs unsafe delete candidate roles, Body shape health, generator success, two-run semantic reproducibility, CLI argument/path/nix validations, `.FCBak` cleanup, and unmutated inspection. This is fixture-prerequisite coverage; actual suppression transitions are covered separately through the production consumer. |
| FreeCAD-native suppression / unsuppression consumer | Covered | `tests/test_suppression.py`, `tests/test_suppression_real_fixtures.py`, `tests/freecad_suppression_runner.py` (test-only support) | Exact `document.getObject(object)` resolution with no fallback; native `Suppressed` capability and `App::PropertyBool` requirement; both requested boolean states; controlled missing, unsupported, inspection, and write failures with native causes preserved where applicable; caller ordering, fail-fast behavior, and unchanged input ordering/content. Real FreeCAD coverage applies the production consumer to temporary copies of the committed PartDesign fixture, proves `TerminalChamfer` true -> false and intermediate features false -> true, preserves visibility, and leaves committed fixture bytes unchanged. This consumer is not wired to the schema-2 execute boundary and the helper is not a production entrypoint. |
| Supported internal object reference discovery | Covered | `tests/test_reference_traversal.py` | Root-only documents, unrelated-object and empty-link exclusion, participating source/target inclusion, multiple sources/targets/properties, LinkSub extraction, exact schema-2 IDs/type/property/mechanism provenance, complete endpoints, duplicate collapse, and object/property/value enumeration-order independence are covered. |
| Internal traversal raw-evidence preservation | Covered | `tests/test_reference_traversal.py` | Exact typed-result coverage preserves source path, document/object labels, stable names/types, complete endpoints, edge kind/state, source property, reference mechanism, and nullable diagnostics; empty unavailable optional values remain null. Mapped external missing evidence is covered separately; unresolved remains contract vocabulary. |
| Active traversal cycle prevention | Covered | `tests/test_reference_traversal.py` | Self-link and mutual internal-link coverage proves the one-pass non-recursive discovery boundary terminates with finite participating nodes and distinct edges. Recursive external-document traversal is not implemented. |
| Visited semantic object guard | Covered | `tests/test_reference_traversal.py` | Repeated document enumeration of one stable source object name is skipped before property access; call-count coverage proves one traversal and unchanged canonical evidence. |
| Internal relationship cardinality | Covered | `tests/test_reference_traversal.py` | Exact counts prove one shared semantic target node retains two incoming edges and one source retains two distinct outgoing edges. |
| External target approved-API probe and Engine mapping consumer | Covered | `tests/test_reference_traversal_request.py`, `tests/test_reference_traversal.py`, bounded-unit FreeCAD 1.1.1 command-host probes | The probe excludes relocation-dependent `Document.FileName`; schema-2 Engine mappings supply canonical identity for unique resolved and authorized missing evidence. Unmatched and absent source/property/mechanism cases do not fabricate evidence; ambiguity is controlled. |
| Raw traversal output schema 2.0 | Covered | `tests/test_reference_traversal_output_v2.py`, `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal.py` | Exact payload fields/version, nullable provenance, empty rejection, ASCII/Unicode SHA-256 ID vectors and canonical preimage bytes, provenance-sensitive edge identity/order/deduplication, repeated reordered-input bytes, runtime success/failure v2 emission, typed v2 evidence, and unchanged schema-1 fields/bytes. |
| Traversal schema-generation compatibility hardening | Covered | `tests/test_reference_traversal.py`, `tests/test_runtime_entrypoints.py`, `tests/test_reference_traversal_output_writer.py` | Cross-field schema-1/schema-2 mixtures are rejected through the chained typed error before adaptation; single non-empty evidence tuples remain valid without placeholders; direct legacy adaptation covers success, missing paths, and dangling endpoints; runtime entrypoint handling cannot leak adapter implementation exceptions; conflicting raw evidence with one complete schema-2 identity fails deterministic controlled emission. |
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
- Schema 2.0 metadata and strict manifest validation are implemented and covered separately below. Fixture inspection establishes starting native state only; focused real-FreeCAD suppression coverage separately invokes the production suppression consumer against temporary fixture copies and proves actual state transitions. Native visibility, deletion, post-mutation validity, and target observation remain unimplemented.

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

This coverage proves the standalone native consumer. The execute entrypoint
still rejects schema-2 manifests before document operations, so it does not
prove schema-2 execute integration, recompute, save, or persistence through the
normal execute flow. Visibility and deletion consumers remain unimplemented.

## Focused Aligned Manifest Schema 2.0 Metadata and Strict Validation Coverage

Production and test assets:

```text
parametron_freecad/execution/manifest_contract.py
parametron_freecad/execution/manifest_validation.py
tests/test_manifest_v2_contract.py
tests/test_manifest_v2_validation.py
```

### Contract and validation matrix

| Tested Surface | Expected Behavior |
| --- | --- |
| Schema version dispatch | Exact dispatch: `"1.0"` -> `validate_export_manifest_v1`, `"2.0"` -> `validate_export_manifest_v2`; missing version, non-string, whitespace-padded (`" 2.0 "`), numeric (`2.0`), unvetted (`"3.0"`, `"v2"`), and empty strings fail deterministically with `invalid_schema_version`; no trimming, case folding, numeric coercion, or fallback |
| Schema 1.0 closure | Filename remains `prm.export-manifest.json`; schema version remains `"1.0"`; exact four top-level fields (`schemaVersion`, `sourceDocument`, `parameterAssignments`, `outputs`); `assemblyMutations` and `partMutations` rejected as unknown fields; existing V1 public surface and runtime execution preserved |
| Schema 2.0 metadata exactness | Schema version is exactly `"2.0"`; required top-level fields match V1 core; optional top-level fields (`assemblyMutations`, `partMutations`) are exact; all-fields tuple preserves deterministic ordering |
| Schema 2.0 positive cases | Minimal valid manifest (core fields with no mutation sections); empty mutation sections (`{}`); sparse mutation sections (e.g. suppression only, deletion only); full multi-scope and multi-family manifests; coexisting suppression and visibility on the same object |
| Mutation section structure | Mutation sections must be JSON objects; allowed collections are strictly `suppression`, `visibility`, `deletion`; unknown collections (e.g. `parameters`, `properties`, `keep`, `actions`, `targets`) rejected with `unknown_mutation_collection`; non-array collections rejected with `invalid_mutation_collection_type` |
| Entry shape validation | Suppression entries require `{object, suppressed}`; visibility entries require `{object, visible}`; deletion entries require `{object}`; missing required fields, non-dict entries, and unknown fields (e.g. `force`, `cascade`, `action`, `targetKind`) rejected |
| Strict JSON booleans | `suppressed` and `visible` entry values must be strict JSON booleans (`type(val) is bool`); integers (`0`, `1`), strings (`"true"`, `"false"`), and non-booleans rejected with `invalid_mutation_entry_field_type` |
| Duplicate object rejection | Duplicate target object within the same scope and family (e.g. `Pad` twice in `partMutations.suppression`) rejected with `duplicate_mutation_object`; comparison is exact string equality (no trim, no case fold) |
| Intra-scope conflict rejection | Within the same scope, suppression + deletion on the same object rejected with `mutation_family_conflict`; visibility + deletion on the same object rejected with `mutation_family_conflict` |
| Suppression + visibility allowed | Within the same scope, suppression and visibility targeting the same object is explicitly valid (independent semantic axes) |
| Cross-scope conflict rejection | The same object name occurring in both `assemblyMutations` and `partMutations` across any family is rejected with `cross_scope_mutation_object_conflict`; Engine must resolve scope before handoff |
| Diagnostic determinism | Diagnostics sort deterministically: assembly mutations before part mutations; family order suppression -> visibility -> deletion; entries in caller-supplied array order; input mappings are immutable |
| Runtime V1-only safety boundary | Runtime entrypoint uses `validate_export_manifest_v1`; Schema 2.0 mutation-bearing manifests are rejected before CAD document open, parameter assignment, recompute, save, export, or success-result writing; runtime V2 acceptance and mutation-consumer wiring remain unimplemented. The standalone native suppression/unsuppression consumer is covered separately; native visibility and deletion consumers remain unimplemented |

### Focused test methods

`tests/test_manifest_v2_contract.py`:

- `TestSchema10ClosureAndCompatibility`:
  - `test_export_manifest_v1_filename_unchanged`
  - `test_export_manifest_schema_version_v1_constant`
  - `test_v1_top_level_fields_unchanged`
  - `test_export_manifest_v1_contract_object_fields_unchanged`
  - `test_v1_contract_has_no_mutation_fields`
  - `test_existing_all_exports_present`
- `TestSchema20Metadata`:
  - `test_export_manifest_schema_version_v2_constant`
  - `test_v2_required_top_level_fields_matches_v1_core`
  - `test_v2_optional_top_level_fields`
  - `test_v2_top_level_fields_order_and_contents`
  - `test_v2_contract_dataclass_fields`
  - `test_v2_contract_singleton_instance_attributes`
- `TestTargetMutationSectionContract`:
  - `test_mutation_collection_constants`
  - `test_target_mutation_section_fields_tuple`
  - `test_mutation_entry_field_constants`
  - `test_suppression_entry_fields_and_contract`
  - `test_visibility_entry_fields_and_contract`
  - `test_deletion_entry_fields_and_contract`
  - `test_target_mutation_section_contract_singleton`
  - `test_part_and_assembly_share_exact_same_mutation_section_contract`
- `TestSharedContractsAndTransportFilename`:
  - `test_v1_and_v2_share_exact_same_parameter_assignment_contract`
  - `test_v1_and_v2_share_exact_same_output_contract`
  - `test_v1_and_v2_share_exact_same_manifest_filename`
  - `test_no_v2_filename_constant_introduced`
- `TestForbiddenMutationSurfacesAbsent`:
  - `test_no_parameters_or_properties_in_mutation_metadata`
  - `test_no_action_or_keep_in_mutation_metadata`
  - `test_no_target_kind_or_semantic_id_in_mutation_metadata`
  - `test_no_force_cascade_or_dependency_policy_in_mutation_metadata`
- `TestImmutabilityAndImportSafety`:
  - `test_manifest_contract_import_safe_without_freecad`
  - `test_manifest_contract_import_safe_without_freecad_gui`
  - `test_manifest_v2_contract_rejects_attribute_assignment`
  - `test_target_mutation_section_contract_rejects_attribute_assignment`
  - `test_all_new_field_collections_are_tuples`
- `TestTask2Task3Boundary`:
  - `test_v1_validator_does_not_accept_schema_2_0`
  - `test_v1_validator_flags_schema_2_0_as_invalid_schema_version`
  - `test_v1_validator_flags_assembly_mutations_as_unknown_field`
  - `test_v2_validator_is_exposed_in_manifest_validation_module`
  - `test_generic_manifest_validator_is_exposed_in_manifest_validation_module`
  - `test_loader_does_not_expose_mutation_parsing`
  - `test_engine_manifest_compat_module_has_no_mutation_normalization`
  - `test_runtime_entrypoints_module_source_has_no_v2_symbols`
  - `test_manifest_contract_module_itself_exposes_no_validation_function`
- `TestNoRuntimeBehaviorExposedOnV2Surface`:
  - `test_no_apply_suppression`, `test_no_apply_visibility`, `test_no_apply_deletion`
  - `test_no_execute_mutations`, `test_no_parse_mutations`

`tests/test_manifest_v2_validation.py`:

- `TestSchemaVersionDispatch`:
  - `test_validate_export_manifest_dispatches_v1`
  - `test_validate_export_manifest_dispatches_v2`
  - `test_missing_schema_version_rejected`
  - `test_non_string_schema_version_rejected`
  - `test_unsupported_string_schema_version_rejected`
  - `test_schema_version_whitespace_not_trimmed`
  - `test_schema_version_no_case_folding`
  - `test_schema_version_no_numeric_coercion`
- `TestSchema10Closure`:
  - `test_v1_validator_rejects_assembly_mutations`
  - `test_v1_validator_rejects_part_mutations`
  - `test_v1_validator_rejects_schema_20_even_without_mutations`
  - `test_v1_validator_accepts_clean_v1_manifest`
- `TestSchema20PositiveCases`:
  - `test_minimal_v2_manifest_valid`
  - `test_empty_assembly_and_part_mutations_valid`
  - `test_sparse_mutation_sections_valid`
  - `test_full_v2_manifest_with_all_mutation_families_valid`
  - `test_suppression_and_visibility_on_same_object_is_valid`
  - `test_multiple_distinct_objects_in_same_family_valid`
- `TestSchema20StructuralValidation`:
  - `test_non_mapping_mutation_section_rejected`
  - `test_unknown_mutation_collection_rejected`
  - `test_forbidden_collection_names_rejected`
  - `test_non_list_mutation_collection_rejected`
  - `test_non_mapping_mutation_entry_rejected`
  - `test_missing_required_entry_fields`
  - `test_unknown_entry_fields_rejected`
  - `test_invalid_object_field_type`
  - `test_empty_object_field_rejected`
- `TestSchema20StrictBooleans`:
  - `test_suppressed_field_requires_strict_bool`
  - `test_visible_field_requires_strict_bool`
  - `test_boolean_fields_reject_integers_0_and_1`
  - `test_boolean_fields_reject_strings_true_and_false`
- `TestSchema20DuplicateRejection`:
  - `test_duplicate_suppression_object_rejected`
  - `test_duplicate_visibility_object_rejected`
  - `test_duplicate_deletion_object_rejected`
  - `test_duplicate_object_matching_is_exact_string`
- `TestSchema20ConflictRejection`:
  - `test_suppression_and_deletion_conflict_rejected`
  - `test_visibility_and_deletion_conflict_rejected`
- `TestSchema20CrossScopeConflicts`:
  - `test_same_object_in_assembly_and_part_mutations_rejected`
  - `test_cross_scope_conflict_across_different_families_rejected`
- `TestSchema20DiagnosticDeterminism`:
  - `test_mutation_arrays_not_reordered`
  - `test_object_strings_not_normalized`
  - `test_diagnostic_order_assembly_before_part`
  - `test_diagnostic_order_suppression_visibility_deletion`
  - `test_input_mapping_not_mutated`
- `TestSharedCoreValidationBehavior`:
  - `test_missing_required_core_fields_rejected_same_as_v1`
  - `test_unknown_top_level_fields_rejected_same_as_v1`
  - `test_empty_source_document_rejected_same_as_v1`
  - `test_non_list_parameter_assignments_rejected_same_as_v1`
  - `test_unsupported_output_format_rejected_same_as_v1`
  - `test_supported_output_formats_unchanged`
- `TestRuntimeRemainsV1Only`:
  - `test_entrypoints_module_imports_only_v1_validator`
  - `test_entrypoints_source_has_no_v2_symbols`
  - `test_real_v1_validator_rejects_v2_mutation_bearing_manifest_before_freecad_open`
- `TestImportIsolation`:
  - `test_module_imports_without_freecad`
  - `test_validate_export_manifest_v2_is_callable_without_freecad_module_present`
- `TestLoaderBoundaryIntegration`:
  - `test_loader_rejects_duplicate_json_object_keys_before_mutation_validation`
  - `test_duplicate_mutation_object_value_is_a_separate_validator_level_contract`

### Explicit distinctions and boundaries

- **V2 validation coverage documented:** Yes.
- **V1 closure coverage documented:** Yes.
- **Duplicate/conflict coverage documented:** Yes.
- **Strict bool coverage documented:** Yes.
- **Diagnostic determinism documented:** Yes.
- **Runtime V1-only safety proof documented:** Yes.
- **Schema 2.0 execute integration claimed implemented:** No.
- The standalone native suppression/unsuppression consumer is implemented and tested, but Schema 2.0 runtime manifest acceptance and consumer wiring are not implemented. Native visibility, native safe deletion, post-mutation validity infrastructure, target observation, and Engine emission are not implemented.

### Validation results

Focused suite:

```bash
nix develop --command python -m pytest tests/test_manifest_v2_validation.py tests/test_manifest_v2_contract.py -q
# PASS, 221 passed, 210 subtests passed in 0.16s
```

Full suite:

```bash
nix develop --command python -m pytest
# PASS, 3418 passed, 1587 subtests passed in 9.38s
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
