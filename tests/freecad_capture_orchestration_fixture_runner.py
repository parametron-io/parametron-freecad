"""Test-only real-FreeCAD host for capture orchestration fixture tests.

Not production code. Copies nothing itself: the caller supplies a throwaway
project copy. The runner opens the declared saved source, verifies it is the
active document, discovers native candidates, applies explicit semantic
decisions, plans the two outputs, writes them atomically, and reports
deterministic evidence.

    nix develop --command freecadcmd \
      tests/freecad_capture_orchestration_fixture_runner.py \
      --pass=/absolute/path/to/project \
      --pass=<model logical id> \
      --pass=/absolute/path/to/output.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.capture import (
    CaptureDecisions,
    ComponentDecision,
    FeatureDecision,
    FreeCADSemanticMapSelection,
    MetadataDecision,
    ParameterDecision,
    ParameterGroupDecision,
    SemanticParameterTypeSelection,
    discover_capture_candidates,
    load_project_context,
    plan_capture_outputs,
    resolve_selected_model,
    verify_active_source,
    write_capture_outputs,
)

PASS_PREFIX = "--pass="

_SEMANTIC_TYPES = {
    "length": ("number", "mm", "number_to_length"),
    "dimensionless": ("number", "none", "number_to_dimensionless"),
    "count": ("integer", "count", "number_to_integer_exact"),
}
_NATIVE_TO_SEMANTIC = {
    "App::PropertyLength": "length",
    "App::PropertyDistance": "length",
    "App::PropertyFloat": "dimensionless",
    "App::PropertyFloatConstraint": "dimensionless",
    "App::PropertyInteger": "count",
    "App::PropertyIntegerConstraint": "count",
}


def _arguments() -> tuple[Path, str, Path]:
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 3:
        raise RuntimeError("runner requires project, model, and output arguments")
    return Path(values[0]), values[1], Path(values[2])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _decisions(discovery) -> CaptureDecisions:
    return CaptureDecisions(
        components=tuple(
            ComponentDecision(native_ref=item.native_ref, name=item.native_ref)
            for item in discovery.components
        ),
        features=tuple(
            FeatureDecision(native_ref=item.native_ref, name=item.native_ref)
            for item in discovery.features
        ),
        parameter_groups=tuple(
            ParameterGroupDecision(native_ref=item.native_ref, name=item.native_ref)
            for item in discovery.parameter_groups
        ),
        parameters=tuple(
            ParameterDecision(
                native_path=item.native_path, name=item.property.native_key
            )
            for item in discovery.parameters
            if item.property.supported
        ),
        metadata=tuple(
            MetadataDecision(native_path=item.native_path)
            for item in discovery.metadata
            if item.property.supported
        ),
    )


def _selection(discovery) -> FreeCADSemanticMapSelection:
    used: dict[str, str] = {}
    for item in discovery.parameters:
        if not item.property.supported:
            continue
        native_type = item.property.native_type_id
        semantic = _NATIVE_TO_SEMANTIC.get(native_type)
        if semantic is None:
            raise RuntimeError(f"no semantic type for native type {native_type!r}")
        used[native_type] = semantic
    semantic_names = sorted(set(used.values()))
    return FreeCADSemanticMapSelection(
        mapping_id="fixture-capture-v1",
        parameter_types=tuple(
            SemanticParameterTypeSelection(
                name,
                _SEMANTIC_TYPES[name][0],
                _SEMANTIC_TYPES[name][1],
                _SEMANTIC_TYPES[name][2],
            )
            for name in semantic_names
        ),
        native_type_to_semantic_type=used,
        cad_system_min_version="1.1.4",
    )


def main() -> None:
    project_root, logical_id, output_path = _arguments()
    context = load_project_context(project_root)
    model = resolve_selected_model(context, logical_id)
    source_path = context.source_path(model)
    source_hash = _sha256(source_path)
    mapping_hash = _sha256(context.mapping_path)

    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open orchestration fixture")

    try:
        evidence = verify_active_source(document, source_path)
        discovery = discover_capture_candidates(document)
        decisions = _decisions(discovery)
        selection = _selection(discovery)

        plan = plan_capture_outputs(
            context=context,
            model=model,
            discovery=discovery,
            decisions=decisions,
            semantic_selection=selection,
        )
        summary = write_capture_outputs(plan, confirm_replace=False)
        repeat = plan_capture_outputs(
            context=context,
            model=model,
            discovery=discovery,
            decisions=decisions,
            semantic_selection=selection,
        )
    finally:
        _close_all_documents()

    capture_bytes = (project_root / "prm.cad.json").read_bytes()
    semantic_bytes = (project_root / "prm.semantic-map.json").read_bytes()
    payload = {
        "source": {
            "path": str(source_path),
            "sha256": source_hash,
            "unchanged": _sha256(source_path) == source_hash,
        },
        "projectMapping": {
            "path": str(context.mapping_path),
            "unchanged": _sha256(context.mapping_path) == mapping_hash,
        },
        "sourceEvidence": evidence.to_mapping(),
        "plan": plan.to_mapping(),
        "write": summary.to_mapping(),
        "repeatStatus": repeat.status,
        "outputs": {
            "captureSha256": hashlib.sha256(capture_bytes).hexdigest(),
            "semanticSha256": hashlib.sha256(semantic_bytes).hexdigest(),
            "captureBytes": len(capture_bytes),
            "semanticBytes": len(semantic_bytes),
        },
        "counts": {
            "components": len(discovery.components),
            "features": len(discovery.features),
            "parameterGroups": len(discovery.parameter_groups),
            "parameters": len(discovery.parameters),
            "metadata": len(discovery.metadata),
            "selectedParameters": len(decisions.parameters),
            "selectedMetadata": len(decisions.metadata),
        },
    }
    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )


main()
