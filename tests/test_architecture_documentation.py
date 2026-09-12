from __future__ import annotations

import re
import unittest
from pathlib import Path


REQUIRED_HEADING_ALIASES = {
    "architecture boundary": {
        "architecture boundary",
        "runtime boundary",
    },
    "runtime model": {
        "runtime model",
    },
    "package/module boundaries": {
        "package/module boundaries",
        "package and module boundaries",
        "package boundaries",
        "module boundaries",
    },
    "headless execution": {
        "headless execution",
    },
    "observation boundary": {
        "observation boundary",
    },
    "gui and capture boundary": {
        "gui and capture boundary",
        "gui/capture boundary",
    },
    "engine integration boundary": {
        "engine integration boundary",
    },
    "determinism and file contracts": {
        "determinism and file contracts",
        "determinism & file contracts",
    },
    "c++ boundary / reserved native layer": {
        "c++ boundary / reserved native layer",
        "c++ boundary",
        "reserved native layer",
    },
}

REQUIRED_TERMS = [
    "parametron-freecad",
    "export_manifest_v1.json",
    "result.json",
    "parametron.verification.json",
    "parametron.observed.json",
    "parametron.cad.json",
    "parametron_freecad",
    "execution",
    "runtime",
    "observation",
    "gui",
    "Engine-owned",
    "derived working copies",
    "deterministic",
    "file-based contracts",
    "C++",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def architecture_doc_path() -> Path:
    return repo_root() / "docs" / "architecture.md"


def read_architecture_doc() -> str:
    path = architecture_doc_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Architecture documentation file is missing: {path}"
        )
    return path.read_text(encoding="utf-8")


def normalize_heading_text(text: str) -> str:
    text = re.sub(r"^#+", "", text)
    text = text.strip().lower()
    return re.sub(r"\s+", " ", text)


def normalized_markdown_headings(text: str) -> set[str]:
    headings: set[str] = set()
    for raw_heading in re.findall(r"(?m)^\s{0,3}#{1,6}\s+(.*?)\s*$", text):
        headings.add(normalize_heading_text(raw_heading))
    return headings


def missing_required_headings(headings: set[str]) -> list[str]:
    missing: list[str] = []
    for required_heading, aliases in REQUIRED_HEADING_ALIASES.items():
        normalized_aliases = {
            normalize_heading_text(alias) for alias in aliases
        }
        if headings.isdisjoint(normalized_aliases):
            missing.append(required_heading)
    return missing


def missing_required_terms(text: str) -> list[str]:
    normalized_text = text.casefold()
    return [
        term for term in REQUIRED_TERMS if term.casefold() not in normalized_text
    ]


class ArchitectureDocumentationTests(unittest.TestCase):
    def test_architecture_documentation_file_exists(self) -> None:
        path = architecture_doc_path()
        self.assertTrue(
            path.is_file(),
            f"Architecture documentation file is missing: {path}",
        )

    def test_architecture_documentation_has_required_sections(self) -> None:
        text = read_architecture_doc()
        headings = normalized_markdown_headings(text)
        missing_headings = missing_required_headings(headings)
        self.assertFalse(
            missing_headings,
            "docs/architecture.md is missing required architecture sections: "
            + ", ".join(missing_headings),
        )

    def test_architecture_documentation_mentions_required_boundaries(
        self,
    ) -> None:
        text = read_architecture_doc()
        missing_terms = missing_required_terms(text)
        self.assertFalse(
            missing_terms,
            "docs/architecture.md is missing required architecture terms: "
            + ", ".join(missing_terms),
        )


if __name__ == "__main__":
    unittest.main()
