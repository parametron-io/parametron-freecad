# Parametron FreeCAD Agent Guide

## Parametron

Parametron is an early-stage engineering automation project.

The current public engineering system consists of:

- `parametron-engine` — deterministic engineering planning, execution contracts,
  verification, and normalized engineering records.
- `parametron-freecad` — FreeCAD-native execution and raw CAD evidence behind
  Engine-owned contracts.

Engine decides what engineering work should happen. FreeCAD performs the
CAD-native operations required by those contracts.

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

FreeCAD owns CAD-native execution and raw evidence.

It does not own Engine planning, verification decisions, normalized engineering
records, or higher-level orchestration.

Before changing behavior, inspect the relevant source, tests, and permanent
documentation. Do not describe unsupported behavior as implemented.

## Workflow

Work is issue-driven and phase-oriented.

Keep every change bounded to the requested objective. Respect repository
ownership: work belonging to another repository is an external dependency, not
an excuse to implement that responsibility here.

Planning and status live in GitHub Issues and the Parametron Engineering project.
Do not recreate repository-local roadmap, checklist, or status-tracking files.

Prefer focused implementation, focused verification, documentation alignment,
and explicit closure over broad opportunistic cleanup.

## Verification standard

Implementation alone is not completion.

A change is complete only when the relevant behavior is implemented, appropriate
tests pass, deterministic expectations are demonstrated where applicable, and
affected documentation is synchronized.

Use focused tests first and broader validation when the scope requires it.

Failure behavior is part of the contract: invalid inputs should fail
deterministically, at the correct boundary, with stable classification where the
repository defines one.

Never claim determinism without repeatable evidence.

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
- `reference traversal` means the FreeCAD-owned runtime process that discovers
  CAD references and emits raw traversal evidence.
- `reference records` are Engine-owned normalized representations derived from
  that raw evidence.
- Do not use `reference graph` as a synonym for FreeCAD reference traversal.
  Use it only when the surrounding contract explicitly describes graph-level
  relationships or structure.

Use lowercase hyphenated names for multi-word documentation files.

Versioned JSON contracts should follow established repository naming and schema
conventions; do not invent parallel formats casually.

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

## Agent behavior

Keep changes narrow. Do not modify unrelated files or silently expand scope.

Treat source and tests as authoritative for implemented behavior, and permanent
documentation as the public contract surface. If they disagree, investigate and
report the inconsistency instead of guessing.

Preserve backward compatibility and versioned contracts unless the task
explicitly requires a contract change.

Before finishing, review the resulting diff, report what changed, state what
was verified, and disclose remaining limitations or blockers.
