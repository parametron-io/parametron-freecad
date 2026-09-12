# Manifest Contract

The manifest is the file-based description of one execution: source document,
parameter assignments, and declared exports. Contract metadata lives in
`parametron_freecad/execution/manifest_contract.py`; validation lives in
`parametron_freecad/execution/manifest_validation.py`.

Transport filename (both schema versions):

```text
export_manifest_v1.json
```

The transport filename and the schema version are separate concepts; there is
no `export_manifest_v2.json` filename.

## Schema 1.0 (implemented and active at runtime)

Runtime execution (`parametron_freecad/runtime/entrypoints.py`) loads and
validates manifests exclusively through the schema 1.0 path
(`validate_export_manifest_v1`). This is the only schema version currently
accepted for real execution.

Closed top-level fields:

- `schemaVersion`
- `sourceDocument`
- `parameterAssignments`
- `outputs`

Parameter assignment entry fields: `target`, `value`, `valueKind`.

Output declaration entry fields: `id`, `format`, `path`. Supported formats:
`csv`, `pdf`, `step`. See [artifacts.md](artifacts.md) for export behavior.

`outputs: []` is valid and produces zero derived exports; see
[runtime.md](../runtime.md#native-persistence-vs-derived-artifacts).

`sourceDocument` is resolved inside the working copy; relative and absolute
paths are accepted only when they resolve inside it. Missing files and
traversal/symlink escapes are rejected before the FreeCAD document is opened.

Parameter mutation targets are exact `<ObjectName>.<PropertyName>` strings,
resolved only through `document.getObject(name)`. There is no Label lookup,
`document.Objects` fallback, unit conversion, spreadsheet cell semantics,
constraint/expression target support, or capture-backed target projection.

A transitional Engine-shaped compatibility path
(`parametron_freecad/execution/engine_manifest_compat.py`) adapts
Engine-authored dot-form data (`export_manifest.v1.json` shape) into this
schema, e.g. `inputs.sourceModel -> sourceDocument`,
`outputs[].type -> format`, `outputs[].filename -> path`,
`outputs[].object -> id`. It intentionally rejects Engine name-only parameter
assignments that lack explicit FreeCAD target data.

## Schema 2.0 (contract metadata and validation implemented; runtime execution not implemented)

Schema 2.0 adds optional target-mutation sections on top of the same core
fields. Its contract metadata and strict validator are implemented and
tested, but **the runtime does not yet accept or execute schema 2.0
manifests** — see [target-mutations.md](target-mutations.md) for the exact
boundary between what is validated and what is executed.

Required top-level fields: `schemaVersion`, `sourceDocument`,
`parameterAssignments`, `outputs` (the same `ParameterAssignmentContract` and
`OutputContract` objects as schema 1.0).

Optional top-level fields: `assemblyMutations`, `partMutations` — each using
the same `TargetMutationSectionContract`, with collections `suppression`,
`visibility`, `deletion`:

- `suppression[]` → `{object, suppressed}`
- `visibility[]` → `{object, visible}`
- `deletion[]` → `{object}`

Mutation sections never contain `parameters` or `properties`; scalar property
writes remain exclusively the job of `parameterAssignments`.

### Validation rules (`validate_export_manifest`, `validate_export_manifest_v1`, `validate_export_manifest_v2`)

- **Exact version dispatch** — `"1.0"` and `"2.0"` are matched by exact string
  equality; no trimming, case folding, or numeric coercion.
- **Schema 1.0 stays closed** — `assemblyMutations`/`partMutations` are
  rejected as unknown fields under schema 1.0.
- **Optional mutation sections** — absent, `{}`, or sparse valid collections
  under schema 2.0 are all accepted.
- **Closed mutation collections** — only `suppression`, `visibility`,
  `deletion` are recognized; anything else (`parameters`, `keep`, `actions`,
  `targets`, …) is rejected.
- **Strict entry shape** — unknown/extra entry fields (`force`, `cascade`,
  `action`, `targetKind`, …) are rejected.
- **Strict JSON booleans** — `suppressed`/`visible` must satisfy
  `type(value) is bool`; numeric or string coercions (`0`, `1`, `"true"`) are
  rejected.
- **Duplicate rejection** — the same object twice within one scope/family
  (e.g. `Pad` twice in `partMutations.suppression`) is rejected.
- **Deletion conflicts** — suppression+deletion or visibility+deletion on the
  same object within one scope is rejected.
- **Suppression+visibility is valid** — these are independent semantic axes
  and may coexist on the same object within one scope.
- **Cross-scope conflict rejection** — the same object may not appear in both
  `assemblyMutations` and `partMutations` across any family.
- **No string normalization** — object-name comparisons are exact string
  equality; no trimming, case folding, or CAD lookup.
- **Deterministic diagnostics** — diagnostics sort assembly before part, then
  suppression → visibility → deletion, preserving array order; input is never
  mutated.

## Ownership

FreeCAD owns manifest loading, strict validation, and (for schema 1.0)
execution. Engine owns manifest authoring/projection and, for schema 2.0,
the semantic intent behind requested mutations. Neither the manifest nor its
validator performs CAD-native mutation, recompute, or persistence by
themselves — see [runtime.md](../runtime.md) for the execution lifecycle.
