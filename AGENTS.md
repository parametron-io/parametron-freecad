# Parametron FreeCAD Agent Guide

## Parametron

Parametron is an early-stage engineering automation project.

The current public engineering system consists of:

- `parametron-engine` — deterministic engineering authoring, planning,
  execution contracts, verification, and normalized engineering records.
- `parametron-freecad` — FreeCAD-native execution and raw CAD evidence behind
  Engine-owned contracts.

Engine decides what engineering work should happen and how returned evidence is
interpreted. FreeCAD performs the CAD-native operations required by those
contracts.

## This repository

`parametron-freecad` is the FreeCAD runtime adapter for Parametron.

Its implemented capabilities include:

- headless FreeCAD execution
- working-copy document handling and native document persistence
- parameter mutation and recompute
- supported artifact export
- structured result and failure output
- requested runtime observation
- deterministic reference traversal and raw reference evidence
- versioned runtime, manifest, observation, and traversal contracts

FreeCAD owns CAD-native execution, document persistence, export behavior,
application-specific observation, reference traversal, and raw CAD evidence.

It does not own Engine planning, verification decisions, normalized engineering
records, or higher-level orchestration.

Before changing behavior, inspect the relevant source, tests, and permanent
documentation. Do not describe unsupported behavior as implemented.

## Repository boundaries

Keep FreeCAD-native behavior inside this repository and Engine-owned behavior
outside it.

The intended boundary is:

```text
parametron-engine
      |
      v
Engine-owned runtime contract
      |
      v
parametron-freecad
      |
      v
FreeCAD API / document execution
```

Important ownership rules:

- this repository owns actual FreeCAD API interaction
- this repository owns native document mutation, recompute, save, export, and
  runtime observation
- this repository owns raw reference traversal evidence
- Engine owns planning and runtime request construction
- Engine owns verification decisions
- Engine owns normalized record interpretation

Do not move Engine planning, normalized record generation, or verification
policy into this repository merely for convenience.

Do not implement Engine responsibilities locally to avoid an external dependency.
If a required change belongs to `parametron-engine`, report it as a repository
boundary instead.

## Workflow

Work is issue-driven and phase-oriented.

Keep every change bounded to the requested objective. Respect repository
ownership: work belonging to another repository is an external dependency, not
an excuse to implement that responsibility here.

Planning and actionable work live in GitHub Issues. Do not recreate
repository-local roadmap, checklist, progress-journal, or status-tracking files.

Prefer focused implementation, focused verification, documentation alignment,
and explicit closure over broad opportunistic cleanup.

Do not silently turn a documentation task into source refactoring, or a focused
runtime change into architecture redesign.

## Verification standard

Implementation alone is not completion.

A change is complete only when the relevant behavior is implemented, appropriate
tests pass, deterministic expectations are demonstrated where applicable, and
affected documentation is synchronized.

Use focused tests first and broader validation when the scope requires it.

Canonical repository validation commands are:

```bash
parametron-freecad smoke
```

```bash
python -m compileall parametron_freecad scripts tests
```

```bash
python -m pytest
```

Prefer the narrowest relevant test while iterating, then run broader validation
before closure when the change can affect shared runtime behavior.

The repository may provide optional development environments or wrappers, but
project-native commands are the canonical verification interface.

Real-FreeCAD tests may depend on an installed FreeCAD runtime and may remain
opt-in. Do not make real FreeCAD availability a requirement for the default test
suite unless a task explicitly changes that policy.

Failure behavior is part of the contract: invalid inputs should fail
deterministically, at the correct boundary, with stable classification where the
repository defines one.

Never claim determinism without repeatable evidence.

## Determinism

Determinism is part of the runtime contract.

When changing manifests, traversal, observation, result writing, path handling,
or structured runtime output:

- preserve canonical ordering where defined
- preserve stable serialization where defined
- avoid dependence on filesystem discovery order or incidental object iteration
- preserve exact contract-relative identities
- verify repeated equivalent execution when determinism is part of the claim

Raw runtime evidence may intentionally contain run-specific paths, timestamps,
or host details. Do not confuse raw evidence with Engine-owned normalized record
determinism.

## Phases

A phase is a repository-owned, bounded development objective.

A valid phase has:

- a clear goal
- explicit scope
- known dependencies
- verifiable exit criteria

Phases must be bounded, deterministic, independently understandable, and
objectively closable.

Phase identifiers belong to their owning repository. Do not redefine another
repository's phase or use phase numbers as global ordering.

Do not preserve private development chronology in user-facing errors,
documentation, or public API names unless that chronology is itself part of a
stable contract.

Phase titles describe outcomes rather than vague activity.

## Naming

Use explicit, descriptive names and established Parametron terminology.

Prefer clarity over brevity. Do not introduce synonyms when a canonical term
already exists.

In this repository:

- `execution` means CAD-runtime execution
- `observation` means captured runtime state
- `verification` means Engine-owned expected-versus-observed decisions
- `validation` means syntax, schema, semantic, or contract checking
- `adapter` means runtime-specific CAD integration
- `raw evidence` means runtime-produced evidence that has not become an
  Engine-normalized record
- `reference traversal` means the FreeCAD-owned runtime process that discovers
  CAD references and emits raw traversal evidence
- `reference record` means an Engine-owned normalized representation derived
  from accepted traversal evidence

Do not use `reference graph` as a synonym for FreeCAD reference traversal. Use
it only when the surrounding contract explicitly describes graph-level
relationships or structure.

Use lowercase hyphenated names for multi-word documentation files.

Versioned JSON contracts should follow established repository naming and schema
conventions; do not invent parallel formats casually.

## Runtime contracts and evidence

This repository owns runtime-native behavior and raw evidence, not normalized
Engine records.

When changing runtime contracts:

- preserve versioned schema boundaries
- preserve working-copy confinement and path validation
- preserve structured success and failure behavior
- preserve atomic or deterministic file-writing guarantees where defined
- keep observation and traversal outputs as raw runtime evidence
- do not embed Engine verification decisions into runtime output

Existing runtime evidence should remain interpretable by Engine-owned contracts.
If a change would require a cross-repository contract update, make that boundary
explicit rather than silently changing one side.

## Compatibility and legacy surfaces

Do not preserve or expand compatibility behavior merely because tests exist for
it.

First determine whether the behavior is part of the current public contract.

Likewise, do not remove a runtime or contract boundary merely because it has few
callers.

When encountering apparently legacy code:

1. identify current callers
2. inspect tests
3. inspect current documentation
4. determine whether the behavior is contractual, transitional, or dead
5. report ambiguity before deleting or redesigning it

Do not reintroduce retired wrappers, parallel result formats, or obsolete
runtime paths without an explicit task requiring them.

## Documentation

Current public FreeCAD adapter architecture, runtime, and contract
documentation is maintained in `parametron-docs`; see the
[FreeCAD adapter documentation](https://github.com/parametron-io/parametron-docs/tree/main/docs/engine/adapters/freecad).
This repository documents implementation, schemas/validators, tests,
fixtures, and repository-local development/testing guidance.

Public documentation describes the current implemented FreeCAD runtime.

It must not be used as a private development journal.

Do not add repository-local roadmap, task-list, status-history, or private
planning documents.

Avoid private phase/task chronology in public prose unless it is necessary to
explain a stable compatibility contract.

Canonical documentation commands should be project-native. Optional Nix or
other environment tooling may be documented as contributor convenience, but
must not replace the underlying launcher, Python, or pytest command as the
public interface.

When source, tests, and documentation disagree, investigate the discrepancy
instead of choosing whichever version is convenient.

## Commits

Use structured Parametron commit messages:

`<type>(<scope>): <specific summary>`

Common types are `feat`, `fix`, `docs`, `test`, `refactor`, and `chore`.

Use one clear scope whenever possible. The subject should describe the concrete
effect of the change, not vague activity such as "update tests" or "fix stuff".

When a commit belongs to an issue, reference that issue. Use a closing keyword
only when the work is actually complete and its verification and documentation
requirements are satisfied.

Do not create commits unless explicitly requested.

Do not push unless explicitly requested.

## Agent behavior

Keep changes narrow. Do not modify unrelated files or silently expand scope.

Treat source and tests as authoritative evidence for implemented behavior, and
permanent documentation as the public contract surface. If they disagree,
investigate and report the inconsistency instead of guessing.

Do not infer that unused code is obsolete solely from caller count.

Preserve backward compatibility and versioned contracts when they are current
public contracts unless the task explicitly requires a breaking change.

Do not invent future architecture, product behavior, or roadmap commitments to
fill gaps in the current implementation.

Before finishing:

- review the complete diff
- confirm changed paths match the requested scope
- run relevant focused validation
- run broader validation when warranted
- report what changed
- report what was verified
- disclose remaining limitations, skipped validation, or blockers
- state whether any commit or push was performed
