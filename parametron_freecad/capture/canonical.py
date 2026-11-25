"""Canonical serialization for capture documents.

Canonicalization matches the Engine contract's normalization semantics:

* all seven entity registries are sorted by ``id``;
* drawing ``componentIds`` are sorted lexicographically;
* drawing sheets are sorted by ``order`` then ``id``;
* structure nodes are sorted by ``componentId``;
* child lists are sorted lexicographically;
* relationship endpoint order is preserved;
* object keys use the repository's deterministic sorted-key canonical JSON;
* output is UTF-8 with exactly one trailing newline.

The input record or mapping is never mutated. A fresh deep copy is ordered and
serialized.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from parametron_freecad.capture.model import CaptureDocument
from parametron_freecad.capture.validation import validate_capture_document
from parametron_freecad.common.canonical_json import dumps_canonical

_ENTITY_REGISTRIES = (
    "components",
    "features",
    "relationships",
    "parameterGroups",
    "parameters",
    "metadata",
    "drawings",
)


def canonical_capture_bytes(
    value: CaptureDocument | Mapping[str, Any],
) -> bytes:
    """Return canonical UTF-8 bytes for a capture record or mapping."""

    if isinstance(value, CaptureDocument):
        mapping = value.to_mapping()
    elif isinstance(value, Mapping):
        mapping = value
    else:
        raise TypeError("canonical_capture_bytes requires a CaptureDocument or mapping")

    validate_capture_document(mapping)
    ordered = _order_capture_mapping(mapping)
    return dumps_canonical(ordered).encode("utf-8")


def canonical_capture_text(
    value: CaptureDocument | Mapping[str, Any],
) -> str:
    """Return canonical capture JSON text with one trailing newline."""

    return canonical_capture_bytes(value).decode("utf-8")


def _order_capture_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    ordered = copy.deepcopy(value)
    entities = ordered["entities"]

    for registry in _ENTITY_REGISTRIES:
        entities[registry].sort(key=lambda item: item["id"])

    for drawing in entities["drawings"]:
        drawing["componentIds"].sort()
        drawing["sheets"].sort(key=lambda sheet: (sheet["order"], sheet["id"]))

    nodes = ordered["structure"]["nodes"]
    nodes.sort(key=lambda node: node["componentId"])
    for node in nodes:
        node["children"].sort()

    return ordered


__all__ = [
    "canonical_capture_bytes",
    "canonical_capture_text",
]
