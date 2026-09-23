"""FreeCAD-host helper for fixture-native reference relocation tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import FreeCAD as App


PASS_PREFIX = "--pass="


def _arguments() -> tuple[Path, Path]:
    values = [
        Path(argument[len(PASS_PREFIX):])
        for argument in sys.argv
        if argument.startswith(PASS_PREFIX)
    ]
    if len(values) != 2:
        raise RuntimeError("runner requires root and output --pass arguments")
    return values[0], values[1]


def main() -> None:
    root_path, output_path = _arguments()
    document = App.openDocument(str(root_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open relocated reference fixture")

    expected = {
        ("InternalSource", "InternalLink"): (
            "InternalTarget",
            root_path,
        ),
        ("ExternalSourceOne", "ExternalLink"): (
            "SharedTarget",
            root_path.parent / "references" / "reference-a.FCStd",
        ),
        ("ExternalSourceTwo", "ExternalLink"): (
            "SharedTarget",
            root_path.parent / "references" / "reference-a.FCStd",
        ),
        ("SecondExternalSource", "ExternalLink"): (
            "SecondTarget",
            root_path.parent / "references" / "reference-b.FCStd",
        ),
    }
    observed = {}
    try:
        for (source_name, property_name), (target_name, target_path) in expected.items():
            source = document.getObject(source_name)
            if source is None:
                raise RuntimeError(f"relocated fixture lacks object {source_name!r}")
            target = source.getPropertyByName(property_name)
            if target is None or target.Name != target_name:
                raise RuntimeError(
                    f"relocated fixture target mismatch at {source_name}.{property_name}"
                )
            observed_path = Path(target.Document.FileName).resolve()
            if observed_path != target_path.resolve():
                raise RuntimeError(
                    f"relocated fixture document mismatch at {source_name}.{property_name}"
                )
            observed[f"{source_name}.{property_name}"] = {
                "target": target.Name,
                "document": str(observed_path),
            }
        output_path.write_text(
            json.dumps(observed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n",
            encoding="utf-8",
        )
    finally:
        for name in sorted(tuple(App.listDocuments())):
            App.closeDocument(name)


main()
