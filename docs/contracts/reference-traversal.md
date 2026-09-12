# Reference Traversal Contract

FreeCAD reports raw reference-graph evidence for a document. The canonical
model is a directed dependency graph — not a folder tree — supporting shared
targets, multiple incoming/outgoing edges, cycles, and unresolved targets.
FreeCAD does not normalize this into CAD-independent records; that is a
downstream (Engine) responsibility.

Real, FreeCAD-backed discovery is implemented for internal object references
and Engine-mapped external targets (see "Supported discovery" below). This is
distinct from requested reference *observation*, which only checks existence
of explicitly named objects — see
[observation.md](observation.md#requested-reference-observation-not-graph-traversal).

## Traversal request

Loaded strictly by `parametron_freecad/runtime/reference_traversal_request.py`
via `--reference-traversal-request <path>` on `execute` (requires
`--output-dir`; the path must be an existing file inside the working copy).
CLI validation does not read the file's JSON content; the runtime loads it
exactly once, before FreeCAD/document work. A malformed request fails
top-level `result.json` at stage `request_validation` (see
[result-and-failure.md](result-and-failure.md)) and also emits the canonical
failed raw traversal payload described below.

Canonical filenames:

```text
request:  parametron.reference-traversal-request.json
output:   parametron.reference-traversal.json
```

**Schema `1.0`** (closed): `{"schemaVersion": "1.0"}` only.

**Schema `2.0`**: `schemaVersion` plus `externalTargets[]`, where each entry
supplies Engine-owned canonical external-target identity:
`sourceObjectName`, `sourceProperty`, `referenceMechanism`,
`targetObjectName`, `targetDocumentPath`. FreeCAD never opens mapped
documents and never reads `Document.FileName` for matching or output — an
approved-API probe found no mechanism that exposes stable, relocation-
independent original target spelling (Link variants reject cross-document
targets; XLink variants expose only a relocation-dependent absolute
`Document.FileName`). Schema-2 external identity therefore always comes from
the Engine-supplied mapping, never from runtime path inspection.

## Supported discovery

Discovery inspects only the FreeCAD 1.1.1-confirmed private allowlist of 21
concrete `App::PropertyLink*`/`App::PropertyXLink*` type IDs, read through
`PropertiesList`, `getTypeIdOfProperty(name)`, and `getPropertyByName(name)`.
No string/path heuristic is a supported mechanism.

- **Internal**: object-node inclusion is relationship-driven, not an
  inventory — an object node is emitted only as the source or a
  deterministically identified target of an actually-observed supported
  relationship. Discovery is one-pass and non-recursive: a visited set keyed
  by stable source-object name prevents repeat reads, and self-links/mutual
  link cycles terminate as finite evidence rather than being recursed into.
  Shared targets deduplicate to one node without losing distinct incoming
  edges; one source keeps each distinct outgoing edge.
- **External (mapped)**: runtime matching uses only
  `(sourceObjectName, sourceProperty, referenceMechanism, targetObjectName)`
  against the schema-2 mapping. A unique resolved observation emits a mapped
  external `object` node and a resolved `external_document_reference` edge.
  `None`/empty/partially-observed values against a mapped target emit missing
  evidence. Multiple same-name candidates for one mapped coordinate are fatal
  (`ambiguous_reference_target`, via chained
  `ReferenceTraversalExecutionError`) rather than guessed.
- Allowlisted properties with an unsupported non-`None` value shape produce a
  `partial` status and one `unsupported_reference_value_shape` warning
  diagnostic at stage `reference_discovery`, with no inferred target
  evidence. Non-allowlisted properties are ignored before their value is even
  read.

Recursive traversal into mapped external documents is **not implemented**.
The current object/property-mechanism raw contract also cannot distinguish
two same-source/same-target/same-kind observations that arose through
different `sourceProperty`/`referenceMechanism` under schema 1.0 output; only
schema 2.0 output carries that provenance (see below). This is a known
current contract limitation, not a bug.

## Output schema

Runtime emission uses schema `2.0`. Schema `1.0`'s public models, ordering,
and bytes remain unchanged and closed for compatibility.

Schema 2.0 example (the top-level shape is shared by both schemas):

```json
{
  "schemaVersion": "2.0",
  "kind": "raw_reference_traversal",
  "boundary": "reference_traversal_entrypoint",
  "operation": "reference_traversal",
  "status": "succeeded",
  "sourceDocument": "assembly.FCStd",
  "nodes": [ { "sequence": 0, "id": "...", "kind": "document", "state": "resolved", "documentPath": "...", "objectName": null, "objectType": null, "label": "...", "diagnostic": null } ],
  "edges": [ { "sequence": 0, "source": "...", "target": "...", "kind": "external_document_reference", "sourceProperty": "XLink", "referenceMechanism": "App::PropertyXLink", "state": "resolved", "diagnostic": null } ],
  "diagnostics": []
}
```

Schema 2.0 adds nullable `objectType` on nodes (after `objectName`, before
`label`) and nullable `sourceProperty`/`referenceMechanism` on edges (after
`kind`, before `state`). Observed values are non-empty strings; unavailable
values are `null`; empty strings are rejected.

Contract-defined kinds: `document`, `object`, `external_document`, `external_file`
(nodes); `document_internal_reference`, `external_document_reference`,
`external_file_reference` (edges). States: `resolved`, `missing`,
`unresolved`, `skipped`, `failed`.

Real discovery in `parametron_freecad/runtime/reference_traversal.py` currently
emits only `document` and `object` nodes, and `document_internal_reference`
and `external_document_reference` edges. Mapped external targets are `object`
nodes with the mapped `documentPath`; discovery does not emit
`external_document` or `external_file` nodes, or `external_file_reference`
edges. Those additional kinds are contract vocabulary, not implemented
discovery output.

### Per-item state semantics

The vocabulary for `nodes[].state` and `edges[].state` is:

- `resolved`: an observed supported relationship was deterministically bound
  to concrete target evidence sufficient for the raw traversal contract. This
  does not imply Engine verification, storage existence, durable identity,
  filesystem-containment validation of evidence paths, or recursive completeness.
- `missing`: an observed reference identifies an expected target or location,
  and runtime evidence establishes its absence or unavailability at traversal
  time. Incomplete evidence, ambiguity, unsupported mechanisms, and operation
  exceptions do not establish this state.
- `unresolved`: a relationship or candidate target was observed, but evidence
  was insufficient or ambiguous for deterministic target binding. This proves
  no absence; the runtime must not guess the target, reference scope,
  document/file kind, or normalized identity. It does not mean an operation
  exception or an intentional non-attempt.
- `skipped`: resolution or traversal was deliberately not attempted under an
  explicit, deterministic, contract-approved runtime boundary or rule. It is
  not a generic fallback for ambiguity, established absence, or attempted
  failure. The contract requires evidence explaining the non-attempt; the contract assigns
  no specific runtime cases to this state.
- `failed`: an item operation was attempted, but an exception, runtime error,
  invalid runtime response, or equivalent failure prevented a reliable result.
  This is distinct from absence, ambiguous or insufficient evidence, and a
  deliberate non-attempt. The contract requires explainable diagnostic
  evidence for the failure.

Item states do not determine aggregate `status` (`succeeded`, `partial`, or
`failed`); one failed item does not automatically make the traversal failed.
Aggregate outcomes follow the separate [status semantics](#status-semantics).

### Identity

Node identity is a tuple keyed by kind plus canonical contract-relative path
(and, for `object`, the stable object name):

```text
document          -> ("document", documentPath)
object            -> ("object", documentPath, objectName)
external_document -> ("external_document", documentPath)
external_file     -> ("external_file", documentPath)
```

The serialized `id` is `<node-kind>:<lowercase-sha256>` over the exact UTF-8
bytes of `dumps_canonical(identity_key)` (including its trailing LF). Edge
identity is `(source_key, target_key, kind, sourceProperty,
referenceMechanism)` under schema 2.0 — both provenance values participate,
so `null` differs from every observed value. Equal complete identities with
equal complete raw evidence collapse to one; equal identities with
*unequal* raw evidence are a contract conflict and cause a controlled,
chained `ReferenceTraversalExecutionError` rather than a silent merge.

### Ordering

For schema 2.0, deterministic total order is applied before zero-based sequence assignment,
independently for nodes, edges, and diagnostics:

```text
node:       documentPath, kind, id, objectName, objectType, label, state, diagnostic
edge:       source, target, kind, sourceProperty, referenceMechanism, state, diagnostic
diagnostic: stage, severity, code, message
```

These are the schema-2 keys implemented in
`parametron_freecad/runtime/reference_traversal_output_v2.py`. The separate
schema-1 node/edge ordering omits `objectType`, `sourceProperty`, and
`referenceMechanism`; it is not the ordering used for runtime schema-2 emission.

`None` sorts before any provided string; ordinary case-sensitive
lexicographic comparison is used with no trimming, case folding, or path
normalization. This makes output independent of FreeCAD API enumeration
order, document/filesystem enumeration order, or map iteration order.

### Diagnostics

| Condition | Code | Severity | Stage | Outcome |
| --- | --- | --- | --- | --- |
| Allowlisted mechanism, unsupported value shape | `unsupported_reference_value_shape` | `warning` | `reference_discovery` | `partial`; no target evidence |
| Malformed traversal request | `malformed_traversal_request` | `error` | `request_validation` | Failed raw payload, empty graph |
| Multiple candidates for one mapped coordinate | `ambiguous_reference_target` (message token) | — | — | Fatal, chained execution failure; no raw diagnostic |

Exact-duplicate diagnostics `(stage, severity, code, message)` collapse
before ordering. A typed result rejects any diagnostic containing the
canonical Python traceback header — raw stack traces cannot reach semantic
output.

### Status semantics

- `succeeded`: required traversal work completed and reliable evidence was
  produced. `missing`/`unresolved`/`skipped` items alone do not reduce
  status, and an empty graph can still succeed.
- `partial`: the source document opened and some trustworthy graph evidence
  was retained, but required work is explicitly incomplete. Diagnostics alone
  are not sufficient evidence for `partial`.
- `failed`: no safely usable result exists (malformed request, document-open
  failure, or a failure before reliable evidence exists). One failed item
  does not automatically force aggregate `failed`.

## Output containment and emission

`<output-dir>/parametron.reference-traversal.json` is written atomically
(`parametron_freecad/runtime/reference_traversal_output_writer.py`) using the
exact supplied `--working-copy` as the sole containment root — the same exact
containment model as the rest of the runtime (see
[runtime.md](../runtime.md#working-copy--execution-root-contract)). The
runtime creates no directories; `--output-dir` must already exist. `succeeded`
and `partial` results are emitted before observation runs; `failed` skips
emission and skips observation, while already-completed exports remain in
place.

## Real fixture verification

A committed real `.FCStd` bundle at `tests/fixtures/reference_traversal/`
(one root document plus two referenced documents) exercises internal, mapped
external, shared-target, and Engine-authorized-missing evidence end to end
through FreeCAD 1.1.1, including relocation to arbitrary and nested working
roots with byte-identical canonical output. The maintenance generator
(`scripts/generate_reference_traversal_fixtures.py`) guarantees semantic
reproducibility, not byte-identical archive contents. No real cyclic `.FCStd`
fixture is committed, because FreeCAD 1.1.1 save/reopen produced unstable
DAG/dependent-document repair behavior; the self-link and mutual-link tests
are the deliberate finite non-recursive cycle guard instead.

## Ownership

FreeCAD owns raw discovery and evidence capture. Engine owns normalizing raw
evidence into CAD-independent reference records. Durable graph storage, indexing,
where-used, and impact-query behavior are outside this repository's scope.
