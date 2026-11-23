"""Deterministic ``prm.project.json`` context for capture orchestration.

This module is FreeCAD-free and GUI-free. It loads the Engine-owned project
mapping, validates its closed shape and path rules, and resolves the explicitly
selected model logical ID to a project-relative source path.

Capture never invents logical resource identity and never modifies the project
mapping. The mapping file is input-only. Model selection is explicit: resolving
by a coordinate-only path fails when more than one logical ID aliases it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parametron_freecad.capture.orchestration_errors import CaptureProjectError
from parametron_freecad.common.strict_json import StrictJsonError, loads_strict_json

PROJECT_MAPPING_FILENAME = "prm.project.json"
PROJECT_MAPPING_VERSION = "1.0"

_TOP_LEVEL_FIELDS = ("version", "projectId", "dsl", "resources", "tables")
_RESOURCES_FIELDS = ("models",)


@dataclass(frozen=True, slots=True)
class ProjectModel:
    """One declared model logical ID and its project-relative source path."""

    logical_id: str
    path: str

    def to_mapping(self) -> dict[str, str]:
        return {"logicalId": self.logical_id, "path": self.path}


@dataclass(frozen=True, slots=True)
class CaptureProjectContext:
    """Validated project mapping and its resolved project root."""

    root: Path
    mapping_path: Path
    project_id: str
    dsl: str
    models: tuple[ProjectModel, ...]
    tables: tuple[ProjectModel, ...] = ()

    def model(self, logical_id: str) -> ProjectModel:
        """Return the declared model for an exact logical ID."""

        return resolve_selected_model(self, logical_id)

    def source_path(self, model: ProjectModel) -> Path:
        """Return the confined absolute source path for a declared model."""

        return resolve_model_source_path(self, model)

    def model_by_path(self, relative_path: str) -> ProjectModel:
        """Return the single model declared for an exact relative path."""

        return resolve_model_by_path(self, relative_path)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "projectId": self.project_id,
            "dsl": self.dsl,
            "models": [model.to_mapping() for model in self.models],
            "tables": [table.to_mapping() for table in self.tables],
        }


def load_project_context(path: str | Path) -> CaptureProjectContext:
    """Load and validate ``prm.project.json`` from a directory or file path.

    A directory argument is resolved to ``prm.project.json`` inside it. The
    returned project root is the directory containing the mapping file.
    """

    candidate = Path(path)
    if candidate.is_dir():
        mapping_path = candidate / PROJECT_MAPPING_FILENAME
    elif candidate.name == PROJECT_MAPPING_FILENAME:
        mapping_path = candidate
    elif candidate.suffix == ".json":
        raise CaptureProjectError(
            [
                (
                    "project mapping file must be named "
                    f"{PROJECT_MAPPING_FILENAME!r}: {candidate}"
                )
            ]
        )
    else:
        # Treat a bare directory path as a project root even when it is absent
        # so the missing-mapping failure is reported consistently.
        mapping_path = candidate / PROJECT_MAPPING_FILENAME

    if not mapping_path.is_file():
        raise CaptureProjectError(
            [f"project mapping file does not exist: {mapping_path}"]
        )

    try:
        content = mapping_path.read_bytes()
    except OSError as exc:
        raise CaptureProjectError(
            [f"project mapping file could not be read: {mapping_path}: {exc}"]
        ) from exc

    try:
        decoded = loads_strict_json(content)
    except StrictJsonError as exc:
        raise CaptureProjectError(
            [f"invalid project mapping JSON at {mapping_path}: {exc}"]
        ) from exc

    return _context_from_mapping(mapping_path, decoded)


def _context_from_mapping(mapping_path: Path, decoded: Any) -> CaptureProjectContext:
    if not isinstance(decoded, Mapping):
        raise CaptureProjectError(["project mapping root must be an object"])

    problems: list[str] = []

    unknown = sorted(set(decoded) - set(_TOP_LEVEL_FIELDS))
    for field in unknown:
        problems.append(f'project mapping has unknown field "{field}"')

    version = _required_string(decoded, "version", problems)
    if version is not None:
        problems.extend(_version_problems(version))

    project_id = _required_string(decoded, "projectId", problems)
    if project_id is not None and project_id != project_id.strip():
        problems.append("projectId must not have leading or trailing whitespace")

    dsl = _required_string(decoded, "dsl", problems)
    normalized_dsl = (
        _normalize_relative_path(dsl, "dsl", problems) if dsl is not None else None
    )

    models: tuple[ProjectModel, ...] = ()
    resources = decoded.get("resources")
    if not isinstance(resources, Mapping):
        problems.append("resources is required and must be an object")
    else:
        unknown_resources = sorted(set(resources) - set(_RESOURCES_FIELDS))
        for field in unknown_resources:
            problems.append(f'resources has unknown field "{field}"')
        models_object = resources.get("models")
        if not isinstance(models_object, Mapping):
            problems.append("resources.models is required and must be an object")
        else:
            models = _parse_resource_map(models_object, "resources.models", problems)

    tables: tuple[ProjectModel, ...] = ()
    raw_tables = decoded.get("tables")
    if raw_tables is not None:
        if not isinstance(raw_tables, Mapping):
            problems.append("tables must be an object")
        else:
            tables = _parse_resource_map(raw_tables, "tables", problems)

    if problems:
        raise CaptureProjectError(problems)

    assert project_id is not None
    assert normalized_dsl is not None
    return CaptureProjectContext(
        root=mapping_path.parent,
        mapping_path=mapping_path,
        project_id=project_id,
        dsl=normalized_dsl,
        models=models,
        tables=tables,
    )


def _parse_resource_map(
    value: Mapping[Any, Any],
    context: str,
    problems: list[str],
) -> tuple[ProjectModel, ...]:
    entries: list[ProjectModel] = []
    for logical_id in sorted(value, key=str):
        if not isinstance(logical_id, str):
            problems.append(f"{context} logical ID must be a string")
            continue
        if logical_id == "" or logical_id.strip() == "":
            problems.append(f"{context} logical ID must not be empty")
            continue
        if logical_id != logical_id.strip():
            problems.append(
                f"{context} logical ID {logical_id!r} must not have leading or "
                "trailing whitespace"
            )
            continue
        raw_path = value[logical_id]
        if not isinstance(raw_path, str):
            problems.append(f"{context}[{logical_id!r}] path must be a string")
            continue
        normalized = _normalize_relative_path(
            raw_path, f"{context}[{logical_id!r}]", problems
        )
        if normalized is not None:
            entries.append(ProjectModel(logical_id=logical_id, path=normalized))
    return tuple(sorted(entries, key=lambda item: item.logical_id))


def _required_string(
    value: Mapping[str, Any],
    field: str,
    problems: list[str],
) -> str | None:
    if field not in value:
        problems.append(f"{field} is required")
        return None
    candidate = value[field]
    if not isinstance(candidate, str):
        problems.append(f"{field} must be a string")
        return None
    if candidate.strip() == "":
        problems.append(f"{field} is required")
        return None
    return candidate


def _version_problems(version: str) -> list[str]:
    problems: list[str] = []
    parts = version.split(".")
    if len(parts) != 2 or not all(_is_numeric_version_part(part) for part in parts):
        problems.append(
            'version must be a schema version in "major.minor" numeric form'
        )
        return problems
    if version != PROJECT_MAPPING_VERSION:
        problems.append(f"unsupported project mapping version {version!r}")
    return problems


def _is_numeric_version_part(part: str) -> bool:
    if part == "":
        return False
    if len(part) > 1 and part[0] == "0":
        return False
    return all("0" <= character <= "9" for character in part)


def _normalize_relative_path(
    raw: str,
    context: str,
    problems: list[str],
) -> str | None:
    if raw == "" or raw.strip() == "":
        problems.append(f"{context} path must not be empty")
        return None
    if raw != raw.strip():
        problems.append(
            f"{context} path {raw!r} must not have leading or trailing whitespace"
        )
        return None
    if "\x00" in raw:
        problems.append(f"{context} path {raw!r} must not contain a null byte")
        return None

    slash_path = raw.replace("\\", "/")
    if slash_path.startswith("/") or _is_windows_absolute(slash_path):
        problems.append(f"{context} path {raw!r} must be relative")
        return None

    parts: list[str] = []
    for segment in slash_path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not parts:
                problems.append(f"{context} path {raw!r} must stay within project root")
                return None
            parts.pop()
            continue
        parts.append(segment)

    if not parts:
        problems.append(f"{context} path {raw!r} must not resolve to current directory")
        return None
    return "/".join(parts)


def _is_windows_absolute(path: str) -> bool:
    if len(path) >= 2 and path[0].isalpha() and path[1] == ":":
        return True
    return path.startswith("//")


def resolve_selected_model(
    context: CaptureProjectContext,
    logical_id: str,
) -> ProjectModel:
    """Resolve one explicitly selected model logical ID."""

    if not isinstance(logical_id, str):
        raise CaptureProjectError(["selected model logical ID must be a string"])
    if logical_id == "" or logical_id.strip() == "":
        raise CaptureProjectError(["selected model logical ID must not be empty"])
    if logical_id != logical_id.strip():
        raise CaptureProjectError(
            ["selected model logical ID must not have leading or trailing whitespace"]
        )
    for model in context.models:
        if model.logical_id == logical_id:
            return model
    raise CaptureProjectError(
        [
            f"project mapping declares no model logical ID {logical_id!r}; "
            "declared models: " + ", ".join(m.logical_id for m in context.models)
        ]
    )


def resolve_model_by_path(
    context: CaptureProjectContext,
    relative_path: str,
) -> ProjectModel:
    """Resolve a model by exact project-relative path, failing on ambiguity."""

    problems: list[str] = []
    normalized = _normalize_relative_path(relative_path, "model", problems)
    if normalized is None or problems:
        raise CaptureProjectError(problems)

    matches = [model for model in context.models if model.path == normalized]
    if not matches:
        raise CaptureProjectError(
            [f"project mapping declares no model at path {normalized!r}"]
        )
    if len(matches) > 1:
        raise CaptureProjectError(
            [
                f"project mapping is ambiguous for path {normalized!r}: "
                + ", ".join(model.logical_id for model in matches)
            ]
        )
    return matches[0]


def resolve_model_source_path(
    context: CaptureProjectContext,
    model: ProjectModel,
) -> Path:
    """Return the confined absolute source path for a declared model.

    The declared path is validated as project-relative during context loading.
    This function rejoins it to the project root and rejects any escape.
    """

    candidate = (context.root / model.path).resolve(strict=False)
    root = context.root.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CaptureProjectError(
            [f"model {model.logical_id!r} path {model.path!r} escapes the project root"]
        ) from exc
    return candidate


__all__ = [
    "PROJECT_MAPPING_FILENAME",
    "PROJECT_MAPPING_VERSION",
    "CaptureProjectContext",
    "ProjectModel",
    "load_project_context",
    "resolve_model_by_path",
    "resolve_model_source_path",
    "resolve_selected_model",
]
