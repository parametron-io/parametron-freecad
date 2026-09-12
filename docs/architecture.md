# Parametron FreeCAD Architecture

This document describes the implemented runtime and module boundaries. Exact
file and schema details are documented in [contracts/](contracts/), and invocation
details are in [runtime.md](runtime.md).

## Role

`parametron-freecad` is the FreeCAD runtime adapter behind Engine-owned
contracts.

FreeCAD opens CAD documents, observes requested state, mutates requested
properties, recomputes documents, exports declared artifacts, and returns raw
runtime evidence. Engine normalizes that evidence into Engine-produced records.

## Runtime Boundary

FreeCAD owns CAD-runtime-specific behavior:

- runtime bootstrapping and the installable `parametron-freecad` launcher
  transport
- headless FreeCAD host execution
- document lifecycle
- requested mutation
- recompute
- persistence of the configured native working document (`document.save()`)
- requested observation
- export execution
- raw runtime results
- semantic raw-node identity contract/helper behavior
- raw reference traversal evidence
- structured runtime errors; trace payload metadata is a helper only

FreeCAD does not own Engine planning, verification decisions, normalization,
higher-level orchestration, or durable product storage and indexing.

## Runtime Model

The active runtime model is file-based contracts over derived working copies.

Engine and local callers invoke the installable
`parametron-freecad` executable with explicit working-copy, manifest, and result
paths. FreeCAD validates those paths, performs FreeCAD-specific execution or
observation, and returns raw runtime evidence through deterministic file-based
contracts. Engine owns planning, working-copy preparation, manifest projection,
verification, artifact handling,
normalization, and Engine failure reporting. FreeCAD owns CAD-native execution
and raw runtime evidence; it does not own durable records or verification
decisions.

Runtime-boundary flow:

```text
Engine or caller
  -> chooses one execution-instance root
  -> parametron-freecad
      -> validates that exact supplied root
      -> confines all CAD/runtime paths beneath it
      -> FreeCAD host executable
          -> parametron_freecad.runtime.headless.main
              -> CAD-native execution and observation
```

Launcher process flow:

```text
Engine / local caller
  -> parametron-freecad
      -> FreeCAD host
          -> headless.main
```

Responsibility separation:

- wrapper (`parametron-freecad`): process/bootstrap transport, host resolution,
  structured `--pass=` argument forwarding, exit/stdout/stderr propagation
- headless runtime: command semantics and validation
- execution/observation modules: CAD-native behavior
- Engine: orchestration and verification decisions

Wrapper arguments are transferred structurally as individual `--pass=<argument>`
elements. They are not interpolated into a shell command. The launcher removes
checkout/cwd knowledge from callers.

## Headless Execution

Implemented headless execution runs through the installable wrapper:

```text
parametron-freecad execute \
  --working-copy <working-copy-dir> \
  --manifest <manifest-path> \
  --result <result-path> \
  [--output-dir <output-dir>] \
  [--observation-request <request-path>] \
  [--reference-traversal-request <request-path>]
```

Traversal request schema `2.0` transports Engine-owned canonical external
target identities. FreeCAD matches resolved or missing XLink evidence only by
the complete approved runtime coordinate and emits raw schema-2 object/edge
evidence. FreeCAD does not derive identity from resolved document filenames,
open mapped external documents, normalize graph records, or persist them.

Smoke:

```text
parametron-freecad smoke
```

The launcher lives in `parametron_freecad/runtime/launcher.py`. The CLI adapter
lives in `parametron_freecad/runtime/headless.py` and delegates execution
orchestration to `parametron_freecad/runtime/entrypoints.py`.
`scripts/parametron_freecad_headless.py` remains a source/development
compatibility entrypoint and is not the installed production wrapper.

Canonical Engine-style layout:

```text
<product-dir>/
└── _working/
    └── <execution-id>/        authoritative supplied root
        ├── source/
        ├── export_manifest_v1.json
        ├── result.json
        └── outputs/
```

`_working` and `<execution-id>` names are caller conventions. FreeCAD does not
infer the parent layout. The supplied leaf is the isolation boundary; a sibling
leaf is outside scope. Passing the broad parent `_working` would create a
broader boundary. Callers are responsible for selecting the intended isolation
root.

Implemented execution behavior:

1. Validate CLI arguments before FreeCAD import.
2. Require `--working-copy` to resolve to an existing directory that becomes the
   authoritative execution-instance root (basename unrestricted; no nearest
   `_working` ancestor selection).
3. Require manifest/result paths inside that exact supplied root.
4. When `--reference-traversal-request` is present, require an existing file
   inside the exact supplied root and require `--output-dir`; argument
   validation does not read request content.
5. Load and validate `export_manifest_v1.json` through the schema-1 validator.
   Schema-2 validation exists as a separate API; execution rejects schema 2.0.
6. Resolve `sourceDocument` inside the working copy.
7. When `--reference-traversal-request` is present, load it exactly once before
   FreeCAD resolution or document work. Malformed requests fail top-level
   `result.json` at stage `request_validation`.
8. When `--observation-request` is present, load the request and compute the
   source-document SHA-256 before document open.
9. Open the FreeCAD document.
10. Apply exact `<ObjectName>.<PropertyName>` parameter assignments.
11. Recompute once.
12. Persist the configured native working document with `document.save()`.
    Failures raise `DocumentSaveError` and short-circuit downstream stages with
    structured failure stage `document_save`.
13. Export declared STEP/CSV/PDF artifacts. If `outputs` is empty
    (`outputs: []`), zero derived exports are produced. For each STEP
    declaration, resolve `outputs[].id` through exact `document.getObject(id)`
    and export only `[selected_object]`. There is no `document.Objects` access,
    Label fallback, or heuristic selection. STEP declarations are processed in
    manifest order and fail fast on the first lookup/export error. CSV/PDF
    remain format-specific separate exporters.
14. When reference traversal is enabled, call the typed traversal boundary on
    the recomputed and persisted live document. `succeeded` and `partial`
    continue; `failed` fails top-level execution. `succeeded` and `partial`
    are atomically written to `<output-dir>/parametron.reference-traversal.json`.
    An execution or output-write exception fails top-level execution with
    preserved chaining. Either failure skips observation and does not roll back
    exports already completed.
15. When observation is enabled, observe the same open live document after
    persistence, exports, and traversal, before close, and write
    `<output-dir>/parametron.observed.json`.
16. Close the document.
17. Write deterministic success `result.json`.

Handled failures produce deterministic exit/stderr behavior without tracebacks.
Handled execute failures with a safe result path write failed `result.json`
through `parametron_freecad/runtime/failure_result_writer.py`, wired from
`parametron_freecad/runtime/entrypoints.py`. Argument/path failures without a
safe result path do not create `result.json`. Failure-result emission is
best-effort and does not mask the original failure. `ResultWriteError` does not
recurse into failure-result writing. Runtime trace output shape is implemented
as a contract helper only; trace file writer, path containment, and runtime
trace emission are not implemented yet.

## Package Boundaries

`parametron_freecad/common/`
: Deterministic shared helpers such as canonical JSON and path containment.

`parametron_freecad/execution/`
: Manifest contract metadata (schema 1.0 and schema 2.0 target-mutation contracts),
strict loading, validation (strict Schema 1.0 and Schema 2.0 validators, exact version dispatch, duplicate/conflict checking), parameter assignment,
document recompute, native document persistence (`execution/document_save.py`),
STEP/CSV/PDF export, Engine manifest compatibility, and success result writing.
`execution/step_export.py` performs exact selected-object STEP export through
`document.getObject(id)` and `Import.export([selected_object], path)`.

`parametron_freecad/runtime/`
: Headless CLI handling, installable `parametron-freecad` launcher transport,
runtime entrypoints, Engine invocation metadata, document lifecycle,
output/file/error contract metadata, structured failure result writing, runtime
trace output shape contract helper, raw reference traversal output shape
contract helper, semantic raw-node identity contract/helpers, integration
rehearsal, and deterministic artifact comparison helpers.

`parametron_freecad/observation/`
: Verification/observed contract metadata, requested parameter/metadata/reference
observation, observed output generation for injected document state, and Engine
verification compatibility helpers.

`scripts/`
: Source/development headless entrypoint and fixture maintenance generators.
The development entrypoint is not the installed production wrapper.

`tests/`
: Ordinary-Python, fake-FreeCAD, environment-gated smoke, and real fixture
coverage.

## Determinism and File Contracts

The headless execute path uses deterministic file-based contracts:

- `export_manifest_v1.json` declares source document, parameter assignments, and
  outputs
- `result.json` carries success or handled failure evidence
- when `--observation-request` is supplied, `<output-dir>/parametron.observed.json`
  carries canonical raw observed facts
- declared artifact outputs are confined to the working copy
- STEP selector resolution is deterministic and exact: `outputs[].id` is looked
  up through `document.getObject(id)` with no Label, iteration, or
  `document.Objects` fallback

Emission of `parametron.cad.json` is not implemented.

Success `result.json` contains `schemaVersion`, `status`, and `artifacts`.
Handled failure `result.json` contains `schemaVersion`, `status: "failed"`, and
`failure` with `boundary`, `category`, `code`, `message`, and `stage`.
Deterministic exit codes and single-line stderr remain the process-oriented
failure surface alongside structured failure results.

For traversal-enabled execution, document-open failure retains the existing
top-level `execution_entrypoint` / `execution` / `runtime_failure` /
`document_open` classification and exception chaining. No separate raw
traversal diagnostic code is currently contracted for that failure.

Once traversal begins, a typed `failed` result and a chained
`ReferenceTraversalExecutionError` both retain the top-level execution failure
shape and `runtime_failure` code, with stable stage `reference_traversal`.
Top-level classification is separate from raw traversal evidence.

Atomic traversal-output failures retain code `runtime_failure`. Resolver
containment rejection uses stage `reference_traversal_output_containment`;
serialization and all later emission phases use
`reference_traversal_output_write`. Private writer phase metadata resolves the
otherwise ambiguous shared contract-error type without changing public
exceptions or raw payloads.

The raw payload builder applies the contract diagnostic total order before
sequence assignment. The typed traversal boundary rejects diagnostics carrying
the canonical Python traceback header, preventing uncontracted stack traces
from entering semantic output without rewriting raw evidence.

Traversal is additive to the execute pipeline: declared output data is passed
unchanged through STEP, CSV, PDF, and success-result artifact handling.

### Native Document Persistence vs. Derived Artifacts

The runtime execution lifecycle distinguishes the configured native document
from derived exported artifacts:

```text
configured native CAD document != derived exported artifact
```

Native document persistence is part of aligned CAD execution and runs
unconditionally after recompute, persisting the already-opened working-copy
document in place with `document.save()`. Derived artifact exports (such as STEP,
CSV, and PDF) are separate format-specific operations.

The runtime supports execution with zero derived exports (`outputs: []`). In
such runs, the configured native working document is persisted and the runtime
succeeds with `artifacts: []` in `result.json`. The persisted native working
document is NOT automatically added to `result.json.artifacts`.

Parametron FreeCAD consumes concrete manifest exports; it does not parse Engine
DSL authoring syntax or resolve logical export profiles.

## Reference Discovery and Serialization

Real API inspection uses the FreeCAD command host. Supported mechanisms are the
21 probed concrete Link/XLink property type IDs, enumerated through an exact
private allowlist and observed via `PropertiesList`, `getTypeIdOfProperty`, and
`getPropertyByName`. String/path shape alone never establishes a reference.

The typed traversal implementation now establishes the opened source document
as one resolved schema-2 graph root. It preserves the canonical contract-relative
manifest source path and a non-empty runtime document label when available.
Relationship-driven object and supported link-property discovery run on that
opened document.

The typed boundary rejects schema generation mismatches across non-empty node
and edge tuples before runtime emission adaptation. Empty tuples do not create
placeholder evidence or assert a generation. Legacy adapter validation and
schema-2 equal-identity/conflicting-evidence failures remain controlled and
chained.

Object discovery is relationship-driven. The runtime may enumerate all document
objects, but object nodes represent participating sources, deterministic internal
targets, and Engine-mapped external targets of supported Link/XLink properties.
Both endpoints
exist for every emitted edge; unrelated objects and empty link properties do
not affect output. Semantic nodes and edges are deduplicated and sorted after
discovery, independent of runtime enumeration order.

For emitted internal relationships, the runtime preserves available document
and object identity evidence, labels, types, complete endpoints, property and
mechanism provenance, edge kind/state, and diagnostics. Unavailable optional
strings remain null rather than being guessed.

The active internal object discovery pass is non-recursive. Self-links and
mutual object cycles remain ordinary finite edges and cannot re-enter traversal.
Recursive external-document traversal is not implemented.

Real traversal verification uses the committed
`tests/fixtures/reference_traversal/` bundle: one root document, two referenced
documents, one internal link, three mapped resolved external XLinks (including
a shared target), and one Engine-authorized missing target from an empty XLink.
The bundle is copied intact to arbitrary and nested working roots before the
production entrypoint is invoked. Canonical traversal bytes remain identical;
relocation-dependent `Document.FileName` values never participate in matching
or semantic output. The maintenance generator promises semantic equivalence,
not identical FreeCAD archive bytes.

A real document-cycle fixture is intentionally absent because FreeCAD 1.1.1
save/reopen behavior introduced unstable DAG/dependent-document repair effects.
The focused self-link and mutual-link tests remain the cycle guard for this
non-recursive traversal boundary.

Within the active document, visited source semantic identity is the stable
object name. Repeated runtime enumeration is skipped before property reads.

Node deduplication does not erase relationship cardinality: shared targets have
one node and distinct incoming edges; sources retain distinct outgoing edges.

External path probing is restricted to the approved property inspection API.
It found no stable original spelling: XLink target objects expose only resolved
absolute `Document.FileName` values that change on relocation, while missing or
unresolved values expose no target identity. Those values cannot enter semantic
output or be lossily relativized.

Runtime raw traversal emission is schema `2.0`. Its parallel contract module
keeps v1 untouched, activates nullable node `objectType` and edge
`sourceProperty`/`referenceMechanism`, generates kind-prefixed SHA-256 IDs from
the exact canonical semantic-key UTF-8 bytes (including LF), and includes both
provenance values in edge identity/deduplication/order. Null is explicit
unavailable evidence and empty strings are invalid. Request schemas `1.0` and
`2.0` coexist; schema 2 carries Engine-owned external target mappings. No Engine
normalization or durable product identity enters this boundary.

Runtime trace output shape is implemented as a contract helper in
`parametron_freecad/runtime/trace_output_contract.py`. Runtime trace file
writer, path containment, and trace emission from execute/observe/reference
traversal are not implemented yet. Raw reference traversal output shape, public
node/edge total-order keys, deterministic diagnostic sorting before sequencing,
helper-only mixed ordering of existing missing/unresolved node/edge evidence,
emitted raw evidence field contract, and internal/external reference distinction
vocabulary/helper are implemented as contract helpers in
`parametron_freecad/runtime/reference_traversal_output_contract.py`.
The same module defines metadata-only aggregate `succeeded`, `partial`, and
`failed` semantics, semantic completeness, and trustworthy retained-evidence
boundaries. The payload builder remains caller-status-driven; active traversal
applies resolved/missing evidence and partial unsupported-shape classification.
The module also exposes pure `serialize_reference_traversal_output(...)`, which
delegates to the payload builder and canonical JSON helper and returns
deterministic UTF-8 bytes with exactly one trailing LF. It performs no
filesystem access and writes no file. The separate
`reference_traversal_output_writer.py` implements direct, non-atomic binary
emission of those exact bytes with ordinary overwrite and chained writer errors.
It accepts the caller path directly and does not call the containment resolver.
The same module exposes a separate atomic writer that uses the exact supplied
authoritative root and the existing containment resolver, writes through a
same-directory temporary file, and atomically replaces the destination. Real
supported internal and Engine-mapped external traversal is implemented; runtime
emission uses the atomic writer. The writers do not create parent directories
or themselves perform FreeCAD traversal.
Separate raw runtime diagnostic files are not implemented yet.

## Observation Boundary

Observation foundations exist for already-decoded verification data and injected
or lifecycle-opened document state:

- requested parameters
- requested metadata
- requested references
- deterministic observed output ordering
- `parametron.observed.json` writing with atomic destination replacement

Aligned external observation is available on the headless `execute` path through
`--observation-request` and `--output-dir`. Observation uses the same open
document after mutation, recompute, and artifact export, and runs before
document close. Standalone external `observe` remains unsupported. Observation
input contract metadata is `parametron.verification.json`. FreeCAD does not
evaluate checks or make verification decisions.

## Reference Traversal Boundary

Requested reference observation exists, but it is not reference graph traversal.

Current requested reference observation resolves exact names through
`document.getObject(name)` and returns requested `kind`/`name` entries. It does
not discover CAD dependencies, traverse document objects, infer reference kinds,
or preserve missing external reference states.

Schema 1.0 contract helpers in
`parametron_freecad/runtime/reference_traversal_output_contract.py` also define
malformed traversal request failure behavior at the contract/helper level.
Malformed requests fail at request validation with `status: "failed"`, empty
`nodes` and `edges`, and one structured diagnostic through
`build_malformed_reference_traversal_request_payload(...)`. Runtime request
loading now emits that canonical failed shape atomically before FreeCAD
resolution, then preserves the chained request error in top-level `result.json`.
The raw diagnostic excludes the request-local absolute path. Traversal output
file path containment is implemented as a
contract helper through `resolve_reference_traversal_output_path(...)` and
`build_reference_traversal_output_containment_contract()`. Raw evidence path
fields such as `sourceDocument` and `nodes[].documentPath` remain caller-provided
raw evidence and are not filesystem containment decisions.

The same module now implements deterministic semantic raw-node identity at the
contract/helper boundary for document, object, external-document, and
external-file nodes. It returns ordered keys from caller-provided canonical
contract-relative path evidence and stable object name where applicable. It
does not normalize or resolve strings, inspect the filesystem, generate a
serialized node ID, perform traversal, or change raw payload behavior.

It also implements directed semantic edge identity and deterministic
identity-key deduplication at the helper boundary. The key is source semantic
node key + target semantic node key + documented edge kind. Equal keys collapse
in deterministic lexicographic order; reversed relationships remain distinct.
This does not deduplicate raw payload edges or merge state/diagnostic evidence.
This schema-1 helper is not property-sensitive. The separate schema-2 contract
includes source-property and reference-mechanism provenance in edge identity.

The same module defines metadata-only discovery classification semantics:
document-internal relationships remain within one FreeCAD document identity,
external-document relationships cross to a distinct FreeCAD document, and
external-file relationships target a non-FreeCAD file or file-backed resource.
Supported runtime relationship evidence is required; ambiguous or unsupported
mechanisms are not guessed from paths, extensions, filesystem state, string
shape, equal IDs, or missing paths.

It also defines immutable raw adapter provenance requirements for `objectType`,
`sourceProperty`, and `referenceMechanism`. Schema `1.0` does not serialize these
fields. Its ordering-extension metadata describes node order as `documentPath`,
`kind`, `id`, `objectName`, `objectType`, `label`, `state`, `diagnostic`, and edge
order as `source`, `target`, `kind`, `sourceProperty`, `referenceMechanism`,
`state`, `diagnostic`. This metadata does not alter schema-1 ordering or bytes.
The separate schema-2 implementation activates these fields and orders for
runtime emission.

The same boundary exposes total-order helpers for raw nodes, edges, and
structured diagnostics. Optional strings place `None` before provided strings;
provided values use ordinary lexicographic ordering without trimming, case
folding, Unicode/separator rewriting, path normalization/resolution, filesystem
inspection, or semantic inference. Diagnostics sort before zero-based sequence
assignment. Sorting preserves duplicate raw evidence and performs no raw
payload deduplication.

“Unresolved entries” are helper-only existing
`RawReferenceTraversalNode`/`RawReferenceTraversalEdge` evidence in exactly the
`missing` or `unresolved` states. Nodes order before edges and then reuse their
respective keys. There is no separate unresolved payload collection or
unresolved-entry dataclass; the raw schema remains `nodes`, `edges`, and
`diagnostics`. These helpers do not discover references or implement traversal,
writing, output emission, runtime diagnostic policy, or runtime wiring.

The module also defines metadata-only item-level semantics for the existing
`resolved`, `missing`, `unresolved`, `skipped`, and `failed` node/edge evidence
states through `build_reference_traversal_runtime_state_semantics_contract()`.
It describes `nodes[].state` and `edges[].state`; it does not classify real
FreeCAD runtime values, enumerate supported mechanisms, or create diagnostics.
`build_reference_traversal_aggregate_status_semantics_contract()` separately
defines metadata-only top-level `succeeded`/`partial`/`failed` meanings and
partial-versus-failed boundaries without deriving a status. Active discovery produces resolved
and mapped-missing evidence and classifies unsupported value shapes as partial.
Schema `"1.0"`, its node/edge/diagnostic fields, and its serialized payload shape
are unchanged.

The same module defines applicable string and contract-relative path rules
through metadata-only `build_reference_traversal_normalization_contract()`.
It separates canonical semantic/path inputs from exact raw label and diagnostic
evidence and requires a separately approved raw-evidence location whenever
canonicalization would change observed spelling. It performs no normalization,
validation, serialization, filesystem resolution, containment, traversal, or
runtime wiring. Schema `"1.0"` has no active general-purpose raw-original field
and no provenance or raw-original field was activated. FreeCAD retains raw
runtime evidence ownership, Engine retains final CAD-independent normalization,
and durable product storage and graph queries remain outside this repository.

It also defines metadata-only semantic output exclusion rules through
`build_reference_traversal_semantic_output_exclusion_contract()`. Timestamps,
request IDs, actors, process/runtime-local identities, temporary absolute
paths, and incidental enumeration order are excluded from semantic graph
evidence, identity, semantic hashes/fingerprints, deduplication, ordering, and
sequence assignment. Operational values belong in execution, trace, audit, or
request/invocation surfaces. This adds no payload field, semantic hash or node-
ID formula, serialization, writer, runtime enforcement, or real traversal.

Runtime identity assignment and property/reference-mechanism-sensitive edge
identity are active for participating internal objects and Engine-mapped
external objects. Traversal emits raw schema-2 evidence; normalization and
durable graph storage remain outside this boundary.

The runtime request contract supports closed compatible schema `1.0` and strict
schema `2.0` with Engine-owned external-target mappings. The strict loader
normalizes either into an immutable model and has no FreeCAD or file-write side
effects. Canonical request/output
filenames, optional execute-CLI path validation, and exactly-once entrypoint
loading, runtime invocation, and output emission are implemented.
The optional path is non-invasive: absence preserves the full execute/export/
observation pipeline and the existing Engine invocation contract.

The typed CAD traversal boundary accepts the live document, normalized request,
authoritative working-copy path, manifest-relative source document, and resolved
source path. It returns only immutable raw status/node/edge/diagnostic evidence.
The result boundary canonicalizes both schema generations and diagnostics using
the approved contract keys, so caller and FreeCAD enumeration order cannot
affect the returned evidence tuples. Missing/unresolved evidence remains normal
node/edge evidence rather than a separate payload collection.
For schema 2 only, repeated equal node and edge evidence is collapsed by the
complete semantic identity before ordering and independent sequence
assignment, using the same duplicate-versus-conflict rule and the same
canonicalization boundary for both. Conflicting raw evidence at one identity
is rejected; no state or diagnostic aggregation occurs.
Representable partial and failed evidence are results, not exceptions. A single
chained execution error is reserved for failures preventing a valid result.
Serialization, writing, and containment are separate runtime modules; Engine
normalization and durable storage are outside the callable.

The execute entrypoint invokes this boundary after recompute and all declared
exports, before observation. Both `succeeded` and `partial` preserve their typed
raw evidence in the execution flow and continue normally. `failed` and
`ReferenceTraversalExecutionError` fail top-level execution and prevent
observation, while completed export side effects remain. Traversal output is
emitted for `succeeded` and `partial` through the atomic writer before
observation. `--output-dir` must already exist and supplies only the destination
parent; the exact working copy remains the sole containment root. Runtime and
writer create no directories. Malformed-request, document-open, traversal, and
output-containment/write failures use stable stages
(`request_validation`, `document_open`, `reference_traversal`,
`reference_traversal_output_containment`,
`reference_traversal_output_write`) and deterministic messages through the
existing top-level failure boundary.

The reference model is a directed dependency graph. Shared targets, multiple
incoming and outgoing edges, and finite internal cycles retain their graph
relationships; the runtime does not impose a folder tree or recursively open
external documents.

## Engine Integration Boundary

FreeCAD exposes an installable external executable (`parametron-freecad`) and
Engine-callable runtime surfaces in `parametron_freecad/runtime/` without owning
Engine planning, normalization, or durable records.

Engine invokes eligible normal planner-generated execution through the installed
wrapper and Engine-owned runtime capability contracts. FreeCAD returns raw
runtime evidence through file-based contracts and typed runtime errors. Engine
normalizes that evidence into Engine-produced records.

Engine and FreeCAD now agree on STEP selector projection:

```text
outputs[].object -> outputs[].id -> getObject(id) -> one-object export
```

That semantic mapping and normal aligned invocation are implemented. Engine owns
selector choice/validation and artifact acceptance; FreeCAD owns exact
CAD-native lookup and selected-object export.

Transitional Engine manifest and verification compatibility helpers exist, but
FreeCAD does not implement verification decisions or durable product storage.

## GUI and Capture Boundary

GUI/capture functionality is not implemented in this repository today.

## C++ Boundary

There is no active C++ runtime, native extension, or C++ build integration.

## Validation Boundary

Project validation commands are ordinary Python/test commands, run inside a
Python/FreeCAD environment providing this package:

```bash
python -m compileall parametron_freecad scripts tests
python -m pytest
```

Real FreeCAD smoke tests are environment-gated. Supported local smoke uses the
installed wrapper:

```bash
parametron-freecad smoke
```

`PARAMETRON_FREECAD_BIN` overrides the underlying FreeCAD host when needed. See
[README.md](../README.md) for the optional Nix development shell that provides
a reproducible environment satisfying these requirements.
