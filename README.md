# Parametron FreeCAD

FreeCAD runtime integration for Parametron behind Engine-owned contracts.

The runtime opens a prepared working-copy document, applies exact property
assignments and requested target mutations, recomputes and saves the native
document, exports declared artifacts, and returns raw CAD evidence. Engine owns planning, request
construction, normalization, and verification decisions. Higher-level
orchestration and durable product storage/indexing are outside this repository.

## Runtime capabilities

- Installable `parametron-freecad` launcher with headless `smoke` and `execute`
  commands, structured argument forwarding, and deterministic process outcomes.
- Strict manifest loading and schema 1.0 execution with exact
  `<ObjectName>.<PropertyName>` parameter assignments.
- Native working-copy persistence through `document.save()` after recompute.
  Zero derived outputs (`outputs: []`) are supported; the native document is
  not added to the result's artifact list.
- Declared STEP, CSV, and PDF exports. STEP selects exactly one object through
  `document.getObject(outputs[].id)`, with no Label or whole-document fallback.
- Native mutation of existing metadata properties through exact
  `<ObjectName>.<PropertyName>` entries, a post-write read-back check, and raw
  post-mutation observation of the actual native state. Metadata is never
  created; a missing property fails deterministically.
- Optional observation of requested parameters, metadata, reference existence,
  and canonical request-scoped target-state suppression, visibility, and
  existence on the same live document, without evaluating verification checks.
- Optional non-recursive Link/XLink reference discovery for internal objects
  and Engine-mapped external targets, with deterministic rich schema-1 evidence,
  provenance, identity, deduplication, and controlled failures.
- Optional native occurrence evidence for the supported FreeCAD 1.1.4
  `Assembly::AssemblyObject.Group` direct-member mechanism, with the complete
  group inventory, per-member classification, explicit completeness, and
  declared-resource target binding.
- Optional bounded engineering-fact evidence for explicitly bound native
  properties, with typed values, explicit opaque unit tokens, and
  `observed`/`unavailable`/`unsupported` availability.
- Optional per-resource integrity evidence: pre-mutation baseline hashing for
  every declared resource and post-save persisted-result hashing for the primary
  configured result.
- Canonical success and handled-failure `prm.result.json` output, with path
  containment against the exact supplied working-copy root.

Normal `execute` consumes canonical Engine-produced schema 1.0 manifests
directly. Optional `assemblyMutations` and `partMutations` support mutation of
existing native metadata properties, suppression, visibility, and conservative
deletion. Mutation ordering is deterministic: parameter assignments first,
then Assembly before Part; within each section `metadata`, `suppression`,
`visibility`, and `deletion` run in that order, so a metadata write precedes a
deletion of the same object. Focused native tests also cover each capability
independently. Standalone validation and normal `execute` accept the canonical
schema 1.0 manifest and reject schema 2.0.

Metadata mutation supports exactly these `valueKind` and native property type
pairs:

- `string` -> `App::PropertyString`
- `boolean` -> `App::PropertyBool`
- `number` -> `App::PropertyFloat`, `App::PropertyFloatConstraint`
- `integer` -> `App::PropertyInteger`, `App::PropertyIntegerConstraint`

`App::PropertyLength`, `App::PropertyDistance`, `App::PropertyAngle`, and
`App::PropertyQuantity` are not native metadata mutation types. A missing,
unsupported, or read-only property, a `valueKind`/native-type mismatch, and a
post-write mismatch each produce a typed, deterministic metadata failure. A
metadata failure is reported at failure stage `metadata`, stops later
mutation stages, and leaves earlier successful writes applied.

Traversal requests require `schemaVersion: "1.0"` and `externalTargets` (an
empty array is valid). Raw traversal evidence retains object type, source
property, reference mechanism, endpoint identity, and resolution state under
schema 1.0.
Requested metadata and target-state observation reads live native state after
successful mutation and persistence and emits raw evidence, including the
actual native values and value kinds. Observation ordering is deterministic,
and the working-copy digest expectation is first. Engine owns expected-versus-
observed verification and normalized records. Mutation and lifecycle failures
use the existing structured failure boundary; cleanup is attempted and a
required-stage failure prevents a success result.
See the
[target-mutation contract](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/contracts/target-mutations.md).

The occurrence, bounded-fact, and integrity surfaces add no command-line
argument. Engine places `prm.occurrence-request.json` and
`prm.fact-request.json` at the working-copy root and publishes the integrity
request through `PARAMETRON_RUNTIME_INTEGRITY_REQUEST`. When any of them is
enabled, `--output-dir` is required and the runtime writes
`prm.occurrence-evidence.json`, `prm.fact-evidence.json`, and/or
`prm.integrity-evidence.json` there. Declared baselines are hashed before the
document is opened, the persisted configured result is hashed immediately after
save, and occurrence/fact inspection runs on the same open, mutated, recomputed,
and persisted document before close.

## Capture authoring

Capture is a separate GUI-free authoring path that turns an already-open, saved
FreeCAD project source into Engine-consumable project files. Capture does not
run Engine and does not execute engineering work.

The implemented capture surface lives in two places:

- `parametron_freecad/capture/` — the GUI-free capture core: the schema 1.0
  `prm.cad.json` record model, semantic-name and stable-ID policy, canonical
  serialization, an atomic writer, read-only native discovery, the versioned
  `prm.semantic-map.json` template/generator/validator/merge writer, project
  context loading, source fingerprinting, drift detection, deterministic
  previews, and project-root orchestration.
- `workbench/` — the FreeCAD add-on shell with a four-tab capture panel:
  Part/Assembly, Features, Parameters, and Metadata. The Qt panel is a frontend
  to the GUI-free core; importing the capture package and workbench state stays
  safe under headless FreeCAD and plain Python.

Capture behavior:

- Capture requires an existing `prm.project.json` and an explicitly selected
  declared model logical ID. It never invents project identity, creates a
  project mapping, or bootstraps a project.
- The active document must be the declared saved source. Capture verifies the
  saved file path, rejects unsaved documents, and records a deterministic
  `sha256:<hex>` fingerprint of the saved source bytes.
- Discovery is top-down and read-only. Components come from supported
  assembly/part containers, features from PartDesign features and sketches,
  parameter groups from `App::VarSet`, parameters from supported native scalar
  properties, and metadata from existing supported native properties. Links,
  joints, object groups, spreadsheets, technical drawings, and unknown native
  types produce diagnostics rather than invented capture entities.
- Semantic names are user-authored and validated as DSL identifiers. They are
  never derived from native object names, labels, CAD types, geometry, or
  `nativeRef`.
- Stable IDs are generated deterministically from semantic names and structural
  scope, or supplied as explicit exact overrides. Generated or explicit ID
  collisions are hard failures with no automatic suffixing.
- Capture is top-down: the root part/assembly must be captured and named before
  the Features, Parameters, and Metadata tabs become available, and each
  captured entity requires its captured owner. Uncaptured native objects are
  simply absent from the capture.
- Parameters are limited to supported native properties, not Sketcher
  constraints. Semantic parameter types and units come from the project
  semantic map, or a conservative default when none exists; the Parameters tab
  shows observable/writable state and lets the user choose among declared
  semantic types.
- Metadata must already exist. Capture selects existing `String`, `Bool`,
  `Float`, `FloatConstraint`, `Integer`, and `IntegerConstraint` metadata and
  never creates metadata.
- Feature target actions come from captured native capability and may be
  narrowed, never extended. Authorizing an uncaptured action fails.
- `prm.cad.json` and `prm.semantic-map.json` are written to the directory
  containing `prm.project.json`. Each file is written atomically, and existing
  differing files are never silently replaced: the caller must review the
  deterministic diff and pass an explicit confirmation decision.
- Drift fails closed before writing: a missing native selector, changed native
  type, changed ownership/hierarchy, or a semantic-name change that alters a
  generated ID requires rebind or review.
- Capture only reads native state. It does not save, recompute, or mutate the
  source document, and it does not modify `prm.project.json`.

Engine remains the semantic and schema authority. FreeCAD validates capture
invariants and produces contract-shaped raw files; Engine performs semantic
validation, planning, verification, and normalized-record generation, and may
run an optional Engine CLI validation preflight. An opt-in real-FreeCAD proof
regenerates a representative capture and proves the Engine CLI accepts it
through normal project-mode validation without structural repair; see
[docs/test-matrix.md](docs/test-matrix.md).

## Current limitations

- Supported occurrence scope is the direct `Assembly::AssemblyObject.Group`
  member mechanism only. Nested assemblies, `Assembly::AssemblyLink`,
  `LinkArray`/`ElementCount` arrays, and non-empty `Assembly::JointGroup` are
  unsupported or incomplete.
- Non-empty occurrence context is unsupported. Generic references are not
  occurrences and do not imply quantity.
- Facts are bounded to `bound_property`. There is no material database, unit
  algebra, unit conversion, or computed physical mass.
- A baseline mismatch fails before mutation. The runtime never reads, enforces,
  or rewrites `prm.project-lock.json`.
- Metadata must already exist in the source document. FreeCAD does not create
  missing metadata, property groups, aliases, or fallback properties, and
  metadata authoring policy remains Engine-owned. There is no template, BOM, or
  metadata-deletion capability.
- Capture authoring is v0-limited: it does not implement technical drawings,
  relationships/mates, external linked documents, a GUI execution trigger,
  project bootstrap, or the `parametron/` folder layout. Capture never creates
  metadata and never derives semantic names.
- Read-only native properties fail at the metadata stage. Unsupported
  Quantity-family native types (`App::PropertyLength`, `App::PropertyDistance`,
  `App::PropertyAngle`, `App::PropertyQuantity`) also fail deterministically.
- Parameter observation supports scalar boolean, integer, finite float, and
  string values. Native `Quantity` values are not observed.
- Verification decisions and normalized engineering records remain
  Engine-owned.

## Headless usage

Supported local invocation:

```bash
parametron-freecad smoke
```

Execute shape:

```text
parametron-freecad execute \
  --working-copy /run/product/_working/execution-a \
  --manifest /run/product/_working/execution-a/prm.export-manifest.json \
  --result /run/product/_working/execution-a/prm.result.json \
  [--output-dir /run/product/_working/execution-a/outputs] \
  [--observation-request /run/product/_working/execution-a/prm.verification.json] \
  [--reference-traversal-request /run/product/_working/execution-a/prm.reference-traversal-request.json]
```

The supplied `--working-copy` directory is the runtime root. Its basename is not
prescribed. All request and manifest-resolved paths must stay below it. Direct
`_working` roots and nested `_working/<execution-id>` roots are both supported.
Normal planner-generated Engine execution selects and invokes this executable
through Engine-owned runtime capability contracts.

The launcher selects `PARAMETRON_FREECAD_BIN` when configured, otherwise
`freecadcmd` from `PATH`. It works independently of the caller's working
directory. Optional observation and traversal requests require `--output-dir`.
The caller prepares the working copy and output directories.

Occurrence and fact request sidecars are discovered only as plain files at the
working-copy root; the integrity request is read only from
`PARAMETRON_RUNTIME_INTEGRITY_REQUEST`. There is no CLI flag for any of them,
and an invocation without an enabled surface writes none of their evidence.

Execution validates the canonical manifest and supplied requests before native
execution, opens the prepared source document, applies parameter assignments
and target mutations, performs required recompute and supported post-mutation
validity checks, saves the native document, then runs exports, optional
traversal, and optional observation. It closes the document before writing the
success result. Deletion performs its own post-removal recompute and validity
check; a final pass runs when later mutation state requires it. Mutation-free
execution retains its established recompute behavior. A standalone external
`observe` command is unsupported; a separate
in-process observation callable accepts injected document state.

See [runtime.md](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/runtime.md)
for lifecycle, containment, launcher, and failure behavior, and
[contracts/](https://github.com/parametron-io/parametron-docs/tree/main/docs/engine/adapters/freecad/contracts)
for exact schema semantics.

## Repository layout

- `parametron_freecad/common/`: canonical JSON and path helpers
- `parametron_freecad/execution/`: manifests, assignments, persistence, exports,
  and results
- `parametron_freecad/runtime/`: launcher, CLI, lifecycle, invocation, traversal,
  occurrence/fact/integrity evidence sidecars, and error boundaries
- `parametron_freecad/observation/`: requested CAD facts and observed output
- `parametron_freecad/capture/`: GUI-free capture contract core, native
  discovery, semantic-map generation, project context, drift, and orchestration
- `workbench/`: FreeCAD add-on shell and four-tab capture UI
- `scripts/`: development entrypoint and fixture maintenance generators
- `tests/`: ordinary Python, fake-FreeCAD, and real-FreeCAD coverage

## Development and Validation

Once a Python/FreeCAD environment providing this package is available, the
ordinary validation commands are:

```bash
parametron-freecad smoke
python -m compileall parametron_freecad scripts tests workbench
python -m pytest
```

See [tests/README.md](tests/README.md) for FreeCAD dependency notes and
environment variables (`PARAMETRON_FREECAD_BIN`,
`PARAMETRON_FREECAD_STRICT_SMOKE`, `PARAMETRON_ENGINE_ACCEPTANCE`), and
[docs/test-matrix.md](docs/test-matrix.md) for current validation coverage.

This repository includes a Nix flake that provides the reproducible
development environment used by maintainers and CI:

```bash
nix develop
```

Nix is optional for contributors. The current Nix environment targets
`x86_64-linux`; equivalent environments may be used on other platforms as long
as the documented runtime and verification requirements are satisfied.
Multi-platform Nix support is outside the current scope.

## Documentation

Current public FreeCAD adapter architecture, runtime, and contract
documentation is maintained in `parametron-docs`:

- [FreeCAD adapter architecture](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/architecture.md)
- [FreeCAD runtime](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/runtime.md)
- [FreeCAD capture authoring](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/authoring-capture.md)
- [FreeCAD contracts](https://github.com/parametron-io/parametron-docs/tree/main/docs/engine/adapters/freecad/contracts)
- [Occurrence evidence](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/contracts/occurrence-evidence.md)
- [Bounded fact evidence](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/contracts/fact-evidence.md)
- [Integrity request](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/contracts/integrity-request.md)
  and [integrity evidence](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/contracts/integrity-evidence.md)

Repository-local validation coverage is tracked in
[docs/test-matrix.md](docs/test-matrix.md).

Current work and status are tracked in GitHub Issues and the
`Parametron Engineering` project.

## License

This project is licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) and is part of the Parametron ecosystem.

If you use this software over a network, you must make the source code available under the same license.
