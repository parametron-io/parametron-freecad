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
- Optional observation of requested parameters, metadata, reference existence,
  and canonical request-scoped target-state suppression, visibility, and
  existence on the same live document, without evaluating verification checks.
- Optional non-recursive Link/XLink reference discovery for internal objects
  and Engine-mapped external targets, with deterministic rich schema-1 evidence,
  provenance, identity, deduplication, and controlled failures.
- Canonical success and handled-failure `prm.result.json` output, with path
  containment against the exact supplied working-copy root.

Normal `execute` consumes canonical Engine-produced schema 1.0 manifests
directly. Optional `assemblyMutations` and `partMutations` support suppression,
visibility, and conservative deletion. Assembly precedes Part; within each
section, suppression precedes visibility and deletion. Focused native tests
also cover each capability independently. Standalone validation and normal
`execute` accept the canonical schema 1.0 manifest and reject schema 2.0.
Traversal requests require `schemaVersion: "1.0"` and `externalTargets` (an
empty array is valid). Raw traversal evidence retains object type, source
property, reference mechanism, endpoint identity, and resolution state under
schema 1.0.
Requested target-state observation reads live native state after successful
mutation and persistence and emits raw evidence. Engine owns expected-versus-
observed verification and normalized records. Mutation and lifecycle failures
use the existing structured failure boundary; cleanup is attempted and a
required-stage failure prevents a success result.
See the
[target-mutation contract](https://github.com/parametron-io/parametron-docs/blob/main/docs/engine/adapters/freecad/contracts/target-mutations.md).

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
  and error boundaries
- `parametron_freecad/observation/`: requested CAD facts and observed output
- `scripts/`: development entrypoint and fixture maintenance generators
- `tests/`: ordinary Python, fake-FreeCAD, and real-FreeCAD coverage

## Development and Validation

Once a Python/FreeCAD environment providing this package is available, the
ordinary validation commands are:

```bash
parametron-freecad smoke
python -m compileall parametron_freecad scripts tests
python -m pytest
```

See [tests/README.md](tests/README.md) for FreeCAD dependency notes and
environment variables (`PARAMETRON_FREECAD_BIN`,
`PARAMETRON_FREECAD_STRICT_SMOKE`), and [docs/test-matrix.md](docs/test-matrix.md)
for current validation coverage.

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
- [FreeCAD contracts](https://github.com/parametron-io/parametron-docs/tree/main/docs/engine/adapters/freecad/contracts)

Repository-local validation coverage is tracked in
[docs/test-matrix.md](docs/test-matrix.md).

Current work and status are tracked in GitHub Issues and the
`Parametron Engineering` project.

## License

This project is licensed under the [GNU Affero General Public License v3.0 (AGPL-3.0)](LICENSE) and is part of the Parametron ecosystem.

If you use this software over a network, you must make the source code available under the same license.
