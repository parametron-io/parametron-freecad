# Observation Contract

Observation reads requested CAD-native state from an already-mutated,
recomputed, and persisted document. It never evaluates checks or makes
verification decisions — that is Engine's job.

## Request: `parametron.verification.json`

Contract: `parametron_freecad/observation/verification_contract.py`. Loaded
strictly through `parametron_freecad/runtime/observation_request.py`
(delegating first to `parametron_freecad/observation/verification_loader.py`
for strict JSON loading, then to
`parametron_freecad/observation/engine_verification_expectations.py` for
required expectation compatibility validation). Malformed JSON, duplicate
keys, non-JSON constants, and non-object roots are rejected; decoded requests
must also fit the supported observation scope. Loading and compatibility
failures become `ObservationRequestError` with the original cause preserved.
This validation does not evaluate checks or compare expected values.

Contract metadata defines top-level fields: `schemaVersion` (required), `observe` (required),
`observationContext` (optional — Engine defaults absent parameter bindings to
an empty list), `expected` (required), `checks` (required).

These metadata requirements are not all enforced by the current loading chain:
for example, `{"observe":{"metadata":true}}` is accepted without
`schemaVersion`, `expected`, or `checks` (covered by `tests/test_observation_request.py`).

`observe` is a set of boolean-ish enable flags per category:
`parameters`, `metadata`, `references`, `components`. `expected` carries the
per-category request data that a category needs to know what to look up
(e.g. `expected.references[]` entries with `kind`/`name`). `checks` is
recognized contract shape only; FreeCAD does not evaluate checks.

Of these four categories, `parameters`, `metadata`, and `references` have an
implemented observation helper. `components` is recognized contract shape
only. The external request compatibility check rejects enabled component
observation and non-empty component expectations. The lower-level
`observe_requested_contract_scope` helper skips components, but that does not
make component requests supported at the external loading boundary.

## Aligned external observation (`--observation-request` on `execute`)

`--observation-request` is a file-based input confined to the validated
working copy and requires `--output-dir`. The runtime:

1. loads the request and computes the source-document digest before the
   document is opened;
2. observes the same open, already-mutated, recomputed, and persisted
   document, after artifact export and reference traversal, before it is
   closed;
3. writes `<output-dir>/parametron.observed.json` atomically.

A standalone external `observe` command does not exist; observation is only
available aligned onto `execute`.

## Response: `parametron.observed.json`

Contract: `parametron_freecad/observation/observed_contract.py`.

```json
{
  "schemaVersion": "1.0",
  "workingCopy": { "path": "...", "sha256": "..." },
  "observation": {
    "parameters": [ { "id": "...", "name": "...", "groupId": "...", "value": 1.0, "valueKind": "number" } ],
    "metadata": [ { "id": "...", "key": "...", "ownerId": "...", "value": "...", "valueKind": "string" } ],
    "references": [ { "kind": "...", "name": "..." } ]
  }
}
```

- `workingCopy.sha256` is the lowercase SHA-256 of the source `.FCStd` file's
  bytes, computed before any in-memory mutation. The field name is
  `workingCopy.sha256` even though the hashed bytes are the source document's
  bytes, not a hash of the whole working-copy directory. Caller request data
  cannot override this digest, and unrelated output-directory contents do not
  participate in it.
- Only enabled, supported categories appear under `observation`; `components`
  is defined in the contract but not currently populated.
- Output is canonical UTF-8 JSON with deterministic requested-item ordering,
  canonical key ordering, and one trailing newline. Writing is atomic —
  `parametron_freecad/observation/observed_writer.py` never leaves a partial
  file after a failed write.

### Requested parameter and metadata observation

Implemented in `parametron_freecad/observation/parameter_observation.py` and
`metadata_observation.py`. Both resolve exact requested items only (owner/key
or object/property reads); neither infers, enumerates, or guesses values that
were not explicitly requested.

### Requested reference observation (not graph traversal)

Implemented in `parametron_freecad/observation/reference_observation.py`. For
each `expected.references[]` entry, it resolves the exact `name` through
`document.getObject(name)` to prove existence and echoes back the requested
`kind`/`name` in request order. It:

- does not traverse `document.Objects`
- does not infer `kind`
- does not discover dependencies
- does not preserve missing/unresolved external reference state

This is existence-checking of explicitly named objects, not the reference
graph traversal described in
[reference-traversal.md](reference-traversal.md).

## Failure behavior

Request loading, source hashing, observation generation, serialization, and
output-writing failures all use structured-failure stage `observation` (see
[result-and-failure.md](result-and-failure.md)). The document is still closed
through the normal lifecycle; no success `result.json` is written after an
observation failure; a failed `result.json` is written when its path is safe.

## Ownership

FreeCAD owns: document lifecycle, CAD-native mutation, recompute, native
persistence, export, and reading requested parameter/metadata/reference
facts into canonical raw observation output.

Engine owns: expected/observed comparison, tolerance evaluation, category and
overall verification outcomes, and acceptance/rejection decisions. FreeCAD's
observation output never contains comparison results, tolerances, category
outcomes, or normalized Engine records.
