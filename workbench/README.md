# Parametron FreeCAD workbench

FreeCAD add-on shell and top-down capture UI for Parametron. The GUI is
a frontend to the GUI-free `parametron_freecad.capture` core. It does not
duplicate document lifecycle, target lookup, property access, discovery,
serialization, or Engine planning logic.

## Layout

- `Init.py` — headless-safe startup; makes the repository and workbench packages
  importable. Never imports `FreeCADGui` or Qt.
- `InitGui.py` — GUI startup; registers the Parametron workbench.
- `parametron_workbench/state.py` — GUI-free top-down state model (gating,
  validation, ID previews, collisions).
- `parametron_workbench/session.py` — GUI-free capture session tying panel state
  to orchestration preview and atomic writes.
- `parametron_workbench/selection.py` — GUI-free semantic-map selection loading.
- `parametron_workbench/panel.py`, `commands.py`, `workbench.py`, `qt.py` —
  FreeCAD/Qt GUI layer.
- `resources/parametron.svg` — workbench icon.
- `package.xml` — FreeCAD add-on metadata (SPDX `AGPL-3.0-or-later`).

## Loading the add-on

FreeCAD must be able to import both `parametron_freecad` and
`parametron_workbench`. `Init.py` adds the repository root (the parent of this
`workbench/` directory) and this directory to `sys.path`, so linking this
directory into FreeCAD's `Mod` directory is enough when the repository is intact:

```text
<FreeCAD user data>/Mod/Parametron -> /path/to/parametron-freecad/workbench
```

Use a symbolic link so `Init.py` resolves the real repository path. Restart
FreeCAD after linking. The `Parametron` workbench and its `Capture Project…`
command appear in the workbench selector and menu.

## Capture flow

1. Open the project source document (`resources.models[...]` in
   `prm.project.json`) and save it.
2. Run `Parametron → Capture Project…` and select the project's
   `prm.project.json`.
3. Name the root part/assembly. The Features, Parameters, Metadata, and Drawings
   tabs stay disabled until a part/assembly is captured and named.
4. Select and name features, select native-property parameters (semantic types
   come from the project's semantic map, or a conservative default), select
   existing supported metadata, and group discovered drawing pages into named
   drawings with explicit sheet order.
5. Review the deterministic diff, confirm replacement when required, and write
   `prm.cad.json` and `prm.semantic-map.json` atomically to the project root.

Semantic names are always user-authored. Capture never derives a name from a
native label. The source document and project mapping are never modified.

## Boundaries

- No GUI execution trigger for Engine runs.
- No drawing layout automation, PDF/SVG/PNG export, relationships/mates,
  separate `.FCStd` drawing resources, or external linked documents.
- No project bootstrap and no `parametron/` folder.
- Metadata must already exist; only the supported String/Bool/Float/Integer
  native metadata types are authorable.

## Testing

The GUI-free state and session are covered by the standard test suite:

```bash
python -m pytest tests/test_workbench_panel_state.py
python -m pytest
```

GUI registration is validated statically and by import-safety tests. Interactive
workbench loading is a manual/opt-in check in a real FreeCAD GUI session.
