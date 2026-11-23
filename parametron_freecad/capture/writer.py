"""Atomic canonical writer for ``prm.cad.json``.

The writer takes an explicit destination path. Project-root discovery and path
containment belong to the capture-orchestration layer, not this core. The
overwrite decision is mandatory: callers must pass ``overwrite=True`` to replace
an existing file, and a write without that decision never overwrites.

Writes are atomic. Content is serialized and validated before any file is
touched, written to a temporary file in the destination directory, flushed and
synced, then installed with an atomic rename (``overwrite=True``) or an atomic
no-replace hard link (``overwrite=False``). A failed write leaves no partial
destination file and removes its temporary file.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from parametron_freecad.capture.canonical import canonical_capture_bytes
from parametron_freecad.capture.errors import CaptureWriteError
from parametron_freecad.capture.model import CaptureDocument

CAPTURE_CONTRACT_FILENAME = "prm.cad.json"


def write_capture_document(
    path: str | os.PathLike[str],
    document: CaptureDocument,
    *,
    overwrite: bool,
) -> None:
    """Atomically write canonical capture JSON to ``path``.

    ``overwrite`` is a required explicit decision. ``overwrite=False`` fails if
    the destination already exists; it never silently replaces it.
    """

    if not isinstance(overwrite, bool):
        raise TypeError("overwrite must be an explicit bool decision")

    data = canonical_capture_bytes(document)
    target = Path(path)

    if not overwrite and target.exists():
        raise CaptureWriteError(
            f"capture write failed for {target}: target already exists"
        )
    if not target.parent.is_dir():
        raise CaptureWriteError(
            f"capture write failed for {target}: parent directory does not exist"
        )

    temporary_path: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        if overwrite:
            os.replace(temporary_path, target)
            temporary_path = None
        else:
            try:
                os.link(temporary_path, target)
            except FileExistsError as exc:
                raise CaptureWriteError(
                    f"capture write failed for {target}: target already exists"
                ) from exc
            os.unlink(temporary_path)
            temporary_path = None
    except CaptureWriteError:
        raise
    except OSError as exc:
        raise CaptureWriteError(f"capture write failed for {target}: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


__all__ = [
    "CAPTURE_CONTRACT_FILENAME",
    "write_capture_document",
]
