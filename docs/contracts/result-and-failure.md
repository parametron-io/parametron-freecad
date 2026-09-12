# Result, Failure, and Trace Contracts

## Success `result.json`

Written once, after a successful `execute` call. Contract:
`parametron_freecad/execution/result_writer.py`.

```json
{
  "schemaVersion": "1.0",
  "status": "succeeded",
  "artifacts": [
    { "format": "step", "id": "Body", "path": "outputs/body.step" }
  ]
}
```

`artifacts` preserves the manifest's `outputs` declaration order and repeats
each declared output's `format`, `id`, and `path` as raw runtime evidence. An
empty `outputs: []` manifest produces `"artifacts": []`; the persisted native
document is never added to this list (see
[runtime.md](../runtime.md#native-persistence-vs-derived-artifacts)).

## Structured failure `result.json`

Handled `execute` failures write a failed `result.json` at the same path,
when a safe result path is available. Contract helper:
`parametron_freecad/runtime/failure_output_contract.py`; writer:
`parametron_freecad/runtime/failure_result_writer.py`.

```json
{
  "schemaVersion": "1.0",
  "status": "failed",
  "failure": {
    "boundary": "execution_entrypoint",
    "category": "execution",
    "code": "runtime_failure",
    "message": "deterministic single-line diagnostic",
    "stage": "parameter_assignment"
  }
}
```

`failure` always has `boundary`, `category`, `code`, `message`, and `stage`.
`stage` may be `null` only where the contract explicitly allows it.

Stage attribution for handled failures includes: `parameter_assignment`,
`recompute`, `document_save` (native persistence, `DocumentSaveError`),
`artifact_export`, `observation`, `reference_traversal`,
`reference_traversal_output_containment`,
`reference_traversal_output_write`, and `document_open`.

Behavior:

- argument/path failures without a safe result path do not create
  `result.json` at all
- success-path `result.json` behavior is unaffected by this contract
- CLI exit codes and single-line stderr are unaffected (see
  [runtime.md](../runtime.md#process-outcomes))
- failure-result emission is best-effort and never masks the original failure
- `ResultWriteError` does not recurse into failure-result writing

## Runtime trace contract (helper only — not wired into execution)

`parametron_freecad/runtime/trace_output_contract.py` defines a payload shape
for runtime trace evidence, but **no trace file is currently written**; there
is no CLI flag, path containment, or emission from `execute`, observation, or
reference traversal.

```json
{
  "schemaVersion": "1.0",
  "kind": "runtime_trace",
  "boundary": "execution_entrypoint",
  "operation": "execute",
  "status": "succeeded",
  "events": [
    { "sequence": 0, "stage": "manifest_loading", "state": "succeeded", "message": null }
  ]
}
```

Event `sequence` is zero-based and deterministic; caller-provided event order
is preserved; `message` is `null` when absent.

## Ownership

FreeCAD owns writing these files as raw runtime evidence. Engine owns
interpreting them for verification, acceptance, and normalized-record
generation; none of these payloads carry comparison results, tolerances, or
pass/fail decisions.
