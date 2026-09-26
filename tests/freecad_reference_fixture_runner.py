"""FreeCAD-host helper for real reference fixture tests."""

from __future__ import annotations

import sys
from pathlib import Path

import FreeCAD as App

from parametron_freecad.runtime.reference_traversal import run_reference_traversal
from parametron_freecad.runtime.reference_traversal_output_contract import (
    REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
    REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
)
from parametron_freecad.runtime.reference_traversal_output import (
    serialize_reference_traversal_output,
)
from parametron_freecad.runtime.reference_traversal_request import (
    load_reference_traversal_request,
)


PASS_PREFIX = "--pass="


def _arguments() -> tuple[Path, Path, Path]:
    values = [argument[len(PASS_PREFIX):] for argument in sys.argv if argument.startswith(PASS_PREFIX)]
    if len(values) != 3:
        raise RuntimeError("runner requires root, request, and output --pass arguments")
    return tuple(Path(value) for value in values)  # type: ignore[return-value]


def _validate_relocated_external_documents(document, root_path: Path) -> None:
    expected = {
        "ExternalSourceOne": root_path.parent / "references" / "reference-a.FCStd",
        "ExternalSourceTwo": root_path.parent / "references" / "reference-a.FCStd",
        "SecondExternalSource": root_path.parent / "references" / "reference-b.FCStd",
    }
    for source_name, expected_path in expected.items():
        target = document.getObject(source_name).getPropertyByName("ExternalLink")
        observed_path = Path(target.Document.FileName).resolve()
        if observed_path != expected_path.resolve():
            raise RuntimeError(
                f"relocated fixture target mismatch for {source_name}"
            )


def main() -> None:
    root_path, request_path, output_path = _arguments()
    document = App.openDocument(str(root_path))
    if document is None:
        raise RuntimeError("FreeCAD failed to open real reference fixture")
    try:
        # This test-only assertion proves relocation before traversal. The
        # runtime mapping and semantic output remain independent of FileName.
        _validate_relocated_external_documents(document, root_path)
        request = load_reference_traversal_request(request_path)
        result = run_reference_traversal(
            document,
            request,
            working_copy=root_path.parent,
            source_document="reference-root.FCStd",
            source_document_path=root_path,
        )
        output_path.write_bytes(serialize_reference_traversal_output(
            boundary=REFERENCE_TRAVERSAL_BOUNDARY_REFERENCE_TRAVERSAL_ENTRYPOINT,
            operation=REFERENCE_TRAVERSAL_OPERATION_REFERENCE_TRAVERSAL,
            status=result.status,
            source_document="reference-root.FCStd",
            nodes=result.nodes,
            edges=result.edges,
            diagnostics=result.diagnostics,
        ))
    finally:
        for name in sorted(tuple(App.listDocuments())):
            App.closeDocument(name)


main()
