# Target Mutations

"Target mutation" means suppressing/unsuppressing, changing visibility of, or
deleting a named CAD feature or object, as opposed to the scalar property
writes already handled by `parameterAssignments` (see
[manifest.md](manifest.md)).

Three layers exist for this capability, at different levels of completeness:

```text
Layer 1 — Contract/Type Metadata:  implemented
Layer 2 — Manifest Validation:     implemented
Layer 3 — Runtime Execution:       not implemented
```

## Layer 1 — Contract metadata (implemented)

`parametron_freecad/execution/manifest_contract.py` defines manifest schema
`2.0`'s optional `assemblyMutations`/`partMutations` sections and their
`suppression`/`visibility`/`deletion` entry shapes. See
[manifest.md](manifest.md#schema-20-contract-metadata-and-validation-implemented-runtime-execution-not-implemented)
for the exact field surface. This metadata is frozen, tuple-based,
import-safe, and free of FreeCAD dependencies or filesystem/runtime side
effects.

## Layer 2 — Manifest validation (implemented)

`parametron_freecad/execution/manifest_validation.py` strictly validates
schema `2.0` manifests: exact version dispatch, closed mutation collections,
strict entry shapes and JSON-boolean typing, duplicate-target rejection,
within-scope and cross-scope conflict rejection, and deterministic diagnostic
ordering. This validator can accept and cleanly reject a schema `2.0`
manifest today — but validating a manifest is not the same as executing its
mutations.

## Layer 3 — Runtime execution (not implemented)

`parametron_freecad/runtime/entrypoints.py` still loads and validates every
manifest exclusively through the schema `1.0` path
(`validate_export_manifest_v1`). A schema `2.0` manifest — mutation-bearing or
not — is rejected before document opening, parameter assignment, recompute,
save, export, or success-result writing. Handled validation failures still
attempt a failed `result.json` when a safe destination is supplied. There is no native suppression,
unsuppression, visibility, or deletion execution, and no post-mutation
validity or target-observation behavior.

## PartDesign mutation fixture foundation (implemented test infrastructure)

A permanent real-FreeCAD fixture provides tested native object structure and
mutation preconditions:

- fixture: `tests/fixtures/partdesign_mutations/partdesign-mutations.FCStd`
- generator: `scripts/generate_partdesign_mutation_fixtures.py`
- tests: `tests/test_partdesign_mutation_fixtures.py`

It provides a native `PartDesign::Body` (`MutationBody`) with a dependency
chain `BaseSketch -> IntermediatePad -> IntermediatePocket -> TerminalChamfer`,
`Tip` resolving to `TerminalChamfer`, `TerminalChamfer` persisted with native
`Suppressed = True` (the other two features `False`), App-level
`MutationBody.Visibility = True`, an unreferenced `SafeDeleteMarker` feature
(safe-delete candidate), and `BaseSketch` retained in `IntermediatePad`'s
`InList` (dependency-sensitive unsafe-delete candidate). The reopened body's
shape is valid and contains exactly one solid. The generator is
semantically, not byte-for-byte, reproducible; the committed fixture's
SHA-256 digest is checked before and after inspection to lock the committed
asset.

This fixture proves the fixture's own structure and preconditions against
real FreeCAD. It does not itself implement or exercise any mutation
execution.

## Ownership

FreeCAD owns the CAD-native runtime boundary. Engine owns semantic intent,
planning, verification decisions, and normalization. Current work and status are
tracked in GitHub Issues and the `Parametron Engineering` project.
