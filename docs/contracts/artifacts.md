# Artifact Output Contract

Manifest `outputs[]` declares derived artifact exports, distinct from native
document persistence (see
[runtime.md](../runtime.md#native-persistence-vs-derived-artifacts)).
The execution pipeline runs STEP, then CSV, then PDF exporters. Each exporter
processes its declarations in manifest order; the first lookup/export failure
stops execution, including subsequent export formats.

Every artifact output path is resolved relative to the working copy when
relative, must remain contained inside it, and requires an existing parent
directory — the same containment failure modes (traversal escape, absolute
outside path, symlink escape, missing/non-directory parent) are rejected
deterministically across all three exporters.

## STEP (`parametron_freecad/execution/step_export.py`)

`outputs[].id` is the exact, case-sensitive FreeCAD internal object name. It
is a runtime CAD selector — not an Engine artifact hash, normalized record
ID, or durable product identity.

```text
document.getObject(id)
Import.export([selected_object], path)
```

- exact lookup only: no Label fallback, no object iteration, no
  `document.Objects` access, no first/active/visible-object fallback, no case
  normalization
- exactly one selected object exported per STEP declaration
- a repeated selector across distinct declared paths is exported once per
  declaration (not deduplicated across declarations)
- deterministic errors on: missing/non-callable `getObject`, a lookup
  exception, a lookup returning no object, or an exporter error after a
  successful lookup

Engine and FreeCAD agree on this selector projection:

```text
Engine outputs[].object -> aligned outputs[].id -> document.getObject(id) -> one-object export
```

Engine owns selector choice/validation and artifact acceptance; FreeCAD owns
exact CAD-native lookup and export of the selected object. FreeCAD invents no
durable artifact or record identity from the selector; `result.json`
preserves the declared `id` as raw runtime evidence only (see
[result-and-failure.md](result-and-failure.md)).

## CSV (`parametron_freecad/execution/csv_export.py`)

`outputs[].id` names a FreeCAD `Spreadsheet` object, resolved through
`document.getObject(id)`. Cell data comes from the spreadsheet's `Content`
mapping; cell addresses (e.g. `B12`) are parsed to build a rectangular
row-major grid bounded by the maximum populated row/column, with unoccupied
cells emitted as empty strings. Output is written as UTF-8 CSV with `\n` line
endings.

## PDF (`parametron_freecad/execution/pdf_export.py`)

`outputs[].id` names a FreeCAD TechDraw page object, resolved through
`document.getObject(id)`. Export goes through the `TechDrawGui` module,
trying `exportPageAsPdf(page, path)` first and falling back to
`export([page], path)` if that function is not present.

## Artifact byte comparison (test/tooling helper only)

`parametron_freecad/runtime/artifact_comparison.py` compares two
caller-provided files by exact raw bytes. It is not a verification decision,
semantic artifact comparison, golden-baseline manager, or Engine acceptance
policy — those remain Engine-owned.
