"""Test-only real-FreeCAD host for the capture-to-Engine acceptance proof.

Not production code. The caller supplies a throwaway project copy. The runner
replays committed capture decisions against a fresh real-FreeCAD discovery,
regenerates both project-root outputs through the production orchestration path,
proves repeated capture is unchanged, exercises representative negative cases,
and reports deterministic evidence for the Engine CLI proof.

    nix develop --command freecadcmd \
      tests/freecad_capture_engine_acceptance_runner.py \
      --pass=/absolute/path/to/project \
      --pass=<model logical id> \
      --pass=/absolute/path/to/committed-prm.cad.json \
      --pass=/absolute/path/to/committed-prm.semantic-map.json \
      --pass=/absolute/path/to/evidence.json
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

import FreeCAD as App

_TESTS_DIRECTORY = Path(__file__).resolve().parent
if str(_TESTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIRECTORY))

from capture_engine_acceptance_support import (  # noqa: E402
    replay_decisions,
    selection_from_committed_map,
)

from parametron_freecad.capture import (  # noqa: E402
    CaptureContractError,
    CaptureDecisionError,
    CaptureDriftError,
    CaptureIdPolicyError,
    CaptureNamePolicyError,
    MetadataDecision,
    build_capture_document,
    discover_capture_candidates,
    load_project_context,
    plan_capture_outputs,
    resolve_selected_model,
    verify_active_source,
    write_capture_outputs,
)
from parametron_freecad.common.strict_json import loads_strict_json  # noqa: E402

PASS_PREFIX = "--pass="


def _arguments() -> tuple[Path, str, Path, Path, Path]:
    values = [
        argument[len(PASS_PREFIX) :]
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 5:
        raise RuntimeError("runner requires five --pass arguments")
    return (
        Path(values[0]),
        values[1],
        Path(values[2]),
        Path(values[3]),
        Path(values[4]),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close_all_documents() -> None:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)


def _read_json(path: Path) -> dict[str, Any]:
    decoded = loads_strict_json(path.read_bytes())
    if not isinstance(decoded, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return decoded


def _classify(action: Callable[[], Any]) -> str:
    try:
        action()
    except (
        CaptureNamePolicyError,
        CaptureIdPolicyError,
        CaptureContractError,
        CaptureDecisionError,
        CaptureDriftError,
    ) as exc:
        return type(exc).__name__
    return "no_error"


def _name_collision(decisions, context, model, discovery):
    included = [item for item in decisions.components]
    if len(included) < 2:
        return "not_applicable"
    renamed = dataclasses.replace(included[1], name=included[0].name, id="")
    mutated = dataclasses.replace(
        decisions,
        components=(included[0], renamed, *included[2:]),
    )
    return _classify(
        lambda: build_capture_document(
            context=context,
            model=model,
            discovery=discovery,
            decisions=mutated,
        )
    )


def _missing_parent(decisions, context, model, discovery):
    selected_components = {item.native_ref for item in decisions.components}
    owners = {
        candidate.component_native_ref
        for candidate in discovery.features
        if candidate.native_ref
        in {feature.native_ref for feature in decisions.features}
    }
    removable = sorted(
        ref
        for ref in selected_components - {discovery.root_component_native_ref}
        if ref in owners
    )
    if not removable:
        return "not_applicable"
    dropped = removable[0]
    mutated = dataclasses.replace(
        decisions,
        components=tuple(
            item for item in decisions.components if item.native_ref != dropped
        ),
    )
    return _classify(
        lambda: build_capture_document(
            context=context,
            model=model,
            discovery=discovery,
            decisions=mutated,
        )
    )


def _unsupported_metadata(decisions, context, model, discovery):
    unsupported = [
        candidate
        for candidate in discovery.metadata
        if not candidate.property.supported
    ]
    if not unsupported:
        return "not_applicable"
    candidate = unsupported[0]
    mutated = dataclasses.replace(
        decisions,
        metadata=(
            *decisions.metadata,
            MetadataDecision(native_path=candidate.native_path),
        ),
    )
    return _classify(
        lambda: build_capture_document(
            context=context,
            model=model,
            discovery=discovery,
            decisions=mutated,
        )
    )


def _stale_native_selector(
    capture_path: Path, context, model, discovery, decisions, selection
):
    original = capture_path.read_bytes()
    try:
        existing = _read_json(capture_path)
        features = existing["entities"]["features"]
        if not features:
            return "not_applicable"
        ghost = copy.deepcopy(features[0])
        ghost["id"] = "fea.ghost.staleSelector"
        ghost["name"] = "StaleSelector"
        ghost["displayName"] = "Stale Selector"
        ghost["identitySource"] = {
            "kind": "owner_scoped_key",
            "ownerScopedKey": "GhostNative",
            "nativeRef": "GhostNative",
        }
        ghost["targetability"] = {
            "suppress": False,
            "unsuppress": False,
            "hide": False,
            "unhide": False,
            "delete": False,
        }
        features.append(ghost)
        capture_path.write_bytes(
            (json.dumps(existing, ensure_ascii=False, sort_keys=True) + "\n").encode(
                "utf-8"
            )
        )
        return _classify(
            lambda: plan_capture_outputs(
                context=context,
                model=model,
                discovery=discovery,
                decisions=decisions,
                semantic_selection=selection,
            )
        )
    finally:
        capture_path.write_bytes(original)


def main() -> None:
    project_root, logical_id, committed_cad_path, committed_map_path, output_path = (
        _arguments()
    )
    committed_cad = _read_json(committed_cad_path)
    committed_map = _read_json(committed_map_path)

    context = load_project_context(project_root)
    model = resolve_selected_model(context, logical_id)
    source_path = context.source_path(model)
    source_hash = _sha256(source_path)
    mapping_hash = _sha256(context.mapping_path)

    _close_all_documents()
    document = App.openDocument(str(source_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open acceptance fixture")

    try:
        evidence = verify_active_source(document, source_path)
        discovery = discover_capture_candidates(document)
        decisions = replay_decisions(committed_cad, discovery)
        selection = selection_from_committed_map(committed_map)

        plan = plan_capture_outputs(
            context=context,
            model=model,
            discovery=discovery,
            decisions=decisions,
            semantic_selection=selection,
        )
        summary = write_capture_outputs(plan, confirm_replace=True)
        repeat = plan_capture_outputs(
            context=context,
            model=model,
            discovery=discovery,
            decisions=decisions,
            semantic_selection=selection,
        )

        negatives = {
            "name_collision": _name_collision(decisions, context, model, discovery),
            "missing_parent_capture": _missing_parent(
                decisions, context, model, discovery
            ),
            "unsupported_metadata_type": _unsupported_metadata(
                decisions, context, model, discovery
            ),
            "stale_native_selector": _stale_native_selector(
                plan.capture_path, context, model, discovery, decisions, selection
            ),
        }
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
        "plan": {
            "status": plan.status,
            "captureStatus": plan.capture_status,
            "semanticStatus": plan.semantic_status,
            "requiresConfirmation": plan.requires_confirmation,
        },
        "write": summary.to_mapping(),
        "repeatStatus": repeat.status,
        "negativeCases": negatives,
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
            "selectedComponents": len(decisions.components),
            "selectedFeatures": len(decisions.features),
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
