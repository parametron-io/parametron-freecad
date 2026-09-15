# Parametron FreeCAD

FreeCAD runtime integration for Parametron behind Engine-owned contracts.

The runtime opens a prepared working-copy document, applies exact property
assignments, recomputes and saves the native document, exports declared
artifacts, and returns raw CAD evidence. Engine owns planning, request
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
- Optional observation of requested parameters, metadata, and reference
  existence on the same live document, without evaluating verification checks.
- Optional non-recursive Link/XLink reference discovery for internal objects
  and Engine-mapped external targets, with deterministic raw schema-2 evidence,
  provenance, identity, deduplication, and controlled failures.
- Canonical success and handled-failure `result.json` output, with path
  containment against the exact supplied working-copy root.

Manifest schema 2.0 metadata and strict validation are implemented separately;
execution rejects schema 2.0 manifests. Native suppression, visibility, and
deletion execution are not currently implemented. See the
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
  --manifest /run/product/_working/execution-a/export_manifest_v1.json \
  --result /run/product/_working/execution-a/result.json \
  [--output-dir /run/product/_working/execution-a/outputs] \
  [--observation-request /run/product/_working/execution-a/parametron.verification.json] \
  [--reference-traversal-request /run/product/_working/execution-a/parametron.reference-traversal-request.json]
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

Execution proceeds through assignment, recompute, native save, exports,
optional traversal, optional observation, document close, and success-result
writing. A standalone external `observe` command is unsupported; a separate
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

Nix is optional for contributors. Equivalent environments may be used as long
as the documented runtime and verification requirements are satisfied.

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

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) and is part of the Parametron ecosystem.

If you use this software over a network, you must make the source code available under the same license.
