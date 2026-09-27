"""Test-only inspection of a completed canonical lifecycle working document."""

import json
from pathlib import Path
import sys

import FreeCAD


PARAMETERS = ("boxLength", "boxWidth", "boxHeight", "holeDia", "boxChamfer")


def main() -> None:
    paths = [Path(arg[7:]) for arg in sys.argv if arg.startswith("--pass=")]
    if len(paths) != 2:
        raise ValueError("expected document and facts paths")
    document_path, facts_path = paths

    document = FreeCAD.openDocument(str(document_path))
    try:
        parameters = document.getObject("VarSet")
        if parameters is None:
            raise AssertionError("canonical VarSet object is missing")
        facts = {
            name: getattr(parameters, name).Value
            for name in PARAMETERS
        }
    finally:
        FreeCAD.closeDocument(document.Name)

    facts_path.write_text(json.dumps(facts, sort_keys=True) + "\n", encoding="utf-8")


main()
