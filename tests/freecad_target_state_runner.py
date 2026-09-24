"""Headless real-FreeCAD target-state observation probe."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.observation.requested_scope_observation import observe_requested_contract_scope


paths = [Path(arg[len("--pass="):]) for arg in sys.argv if arg.startswith("--pass=")]
if len(paths) != 2:
    raise RuntimeError("runner requires fixture and output --pass arguments")

for name in sorted(tuple(App.listDocuments())):
    App.closeDocument(name)
document = App.openDocument(str(paths[0]))
try:
    request = {
        "schemaVersion": "1.0",
        "observe": {"targetState": True},
        "observationContext": {"targetState": {
            "suppression": [
                {"destination": "part", "object": "TerminalChamfer"},
                {"destination": "part", "object": "IntermediatePad"},
            ],
            "visibility": [
                {"destination": "part", "object": "MutationBody"},
                {"destination": "part", "object": "BaseSketch"},
            ],
            "existence": [
                {"destination": "part", "object": "TerminalChamfer"},
                {"destination": "part", "object": "NoSuchTarget"},
            ],
        }},
    }
    evidence = observe_requested_contract_scope(document, request)["targetState"]
finally:
    for name in sorted(tuple(App.listDocuments())):
        App.closeDocument(name)

paths[1].write_text(json.dumps(evidence, sort_keys=True), encoding="utf-8")
