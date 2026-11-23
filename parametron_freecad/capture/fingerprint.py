"""Deterministic source-document fingerprint for capture orchestration.

The captured ``sourceDocument.fingerprint`` is a descriptive input string. This
module produces a stable ``sha256:<hex>`` fingerprint of the saved native
document bytes. It reads the on-disk file only; it never touches an open
document and never imports FreeCAD.

Because the fingerprint covers saved bytes, an unsaved native change cannot be
silently captured: orchestration verifies the active document is saved before
computing the fingerprint.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

FINGERPRINT_PREFIX = "sha256:"


class CaptureFingerprintError(OSError):
    """Raised when a source document cannot be read for fingerprinting."""


def document_fingerprint(path: str | Path) -> str:
    """Return ``sha256:<hex>`` for the saved source document bytes."""

    source = Path(path)
    digest = hashlib.sha256()
    try:
        with source.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CaptureFingerprintError(
            f"source document fingerprint failed for {source}: {exc}"
        ) from exc
    return FINGERPRINT_PREFIX + digest.hexdigest()


__all__ = ["FINGERPRINT_PREFIX", "CaptureFingerprintError", "document_fingerprint"]
