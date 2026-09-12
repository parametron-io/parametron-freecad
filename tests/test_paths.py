from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from parametron_freecad.common.paths import (
    WORKING_COPY_DIR_NAME,
    find_working_copy_root,
    is_within_working_copy,
    require_child_path,
    require_existing_directory,
    require_existing_file,
    require_within_working_copy,
    require_working_copy_child,
    resolve_path,
)


class PathHelpersTests(unittest.TestCase):
    def create_symlink_or_skip(self, target: Path, link_path: Path) -> None:
        try:
            link_path.symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symlink creation is unavailable on this platform")

    def test_resolve_path_returns_resolved_absolute_path_for_absolute_input(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            path = root / "nested" / ".." / "file.txt"

            result = resolve_path(path)

            self.assertEqual(result, (root / "file.txt").resolve(strict=False))
            self.assertTrue(result.is_absolute())

    def test_resolve_path_resolves_relative_path_against_explicit_base(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir) / "base"
            expected = (base / "child" / "file.txt").resolve(strict=False)

            result = resolve_path("child/file.txt", base=base)

            self.assertEqual(result, expected)

    def test_resolve_path_without_base_resolves_against_current_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            previous_cwd = Path.cwd()
            os.chdir(tmp_dir)
            self.addCleanup(os.chdir, previous_cwd)

            result = resolve_path("child/file.txt")

            self.assertEqual(
                result,
                (Path(tmp_dir) / "child" / "file.txt").resolve(strict=False),
            )
            self.assertTrue(result.is_absolute())

    def test_resolve_path_expands_user_home(self) -> None:
        result = resolve_path("~/parametron-freecad-home-test")

        self.assertEqual(
            result,
            (Path.home() / "parametron-freecad-home-test").resolve(strict=False),
        )

    def test_require_existing_file_accepts_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "model.fcstd"
            path.write_text("content", encoding="utf-8")

            result = require_existing_file(path)

            self.assertEqual(result, path.resolve())

    def test_require_existing_file_rejects_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "missing.fcstd"

            with self.assertRaisesRegex(
                ValueError,
                rf"^expected existing file: {Path(path).resolve(strict=False)}$",
            ):
                require_existing_file(path)

    def test_require_existing_file_rejects_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir)

            with self.assertRaisesRegex(
                ValueError,
                rf"^expected existing file: {path.resolve()}$",
            ):
                require_existing_file(path)

    def test_require_existing_directory_accepts_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir)

            result = require_existing_directory(path)

            self.assertEqual(result, path.resolve())

    def test_require_existing_directory_rejects_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "missing"

            with self.assertRaisesRegex(
                ValueError,
                rf"^expected existing directory: {path.resolve(strict=False)}$",
            ):
                require_existing_directory(path)

    def test_require_existing_directory_rejects_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "result.json"
            path.write_text("{}", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                rf"^expected existing directory: {path.resolve()}$",
            ):
                require_existing_directory(path)

    def test_find_working_copy_root_accepts_working_copy_directory_itself(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_root = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            working_root.mkdir()

            result = find_working_copy_root(working_root)

            self.assertEqual(result, working_root.resolve())

    def test_find_working_copy_root_returns_nearest_working_ancestor(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_root = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            nested = working_root / "jobs" / "run"
            nested.mkdir(parents=True)

            result = find_working_copy_root(nested / "result.json")

            self.assertEqual(result, working_root.resolve())

    def test_find_working_copy_root_prefers_nearest_nested_working_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            outer = Path(tmp_dir) / WORKING_COPY_DIR_NAME
            inner = outer / "derived" / WORKING_COPY_DIR_NAME
            path = inner / "artifacts" / "step"
            path.mkdir(parents=True)

            result = find_working_copy_root(path)

            self.assertEqual(result, inner.resolve())

    def test_find_working_copy_root_returns_nearest_nested_working_root_for_file(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            outer_root = Path(tmp_dir) / "outer" / WORKING_COPY_DIR_NAME
            inner_root = outer_root / "a" / WORKING_COPY_DIR_NAME
            file_path = inner_root / "b" / "file.txt"
            file_path.parent.mkdir(parents=True)

            result = find_working_copy_root(file_path)

            self.assertEqual(result, inner_root.resolve())

    def test_find_working_copy_root_rejects_path_outside_working_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "project" / "model.fcstd"

            with self.assertRaisesRegex(
                ValueError,
                rf"^path is not within a {WORKING_COPY_DIR_NAME} working copy: "
                rf"{path.resolve(strict=False)}$",
            ):
                find_working_copy_root(path)

    def test_find_working_copy_root_does_not_match_near_miss_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for name in ("_working-copy", "working", ".working", "_Working"):
                candidate = root / name / "child"
                candidate.mkdir(parents=True)

                with self.assertRaisesRegex(
                    ValueError,
                    rf"^path is not within a {WORKING_COPY_DIR_NAME} working "
                    rf"copy: {candidate.resolve()}$",
                ):
                    find_working_copy_root(candidate)

    def test_is_within_working_copy_returns_true_inside_working_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / WORKING_COPY_DIR_NAME / "child"
            path.mkdir(parents=True)

            self.assertTrue(is_within_working_copy(path))

    def test_is_within_working_copy_returns_false_outside_working_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "project"

            self.assertFalse(is_within_working_copy(path))

    def test_require_within_working_copy_accepts_working_copy_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / WORKING_COPY_DIR_NAME / "child"
            path.mkdir(parents=True)

            result = require_within_working_copy(path)

            self.assertEqual(result, path.resolve())

    def test_require_within_working_copy_rejects_outside_path_with_stable_message(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "project"

            with self.assertRaisesRegex(
                ValueError,
                rf"^path is not within a {WORKING_COPY_DIR_NAME} working copy: "
                rf"{path.resolve(strict=False)}$",
            ):
                require_within_working_copy(path)

    def test_require_child_path_accepts_child_under_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "parent"
            child = parent / "child" / "file.txt"

            result = require_child_path(parent, child)

            self.assertEqual(result, child.resolve(strict=False))

    def test_require_child_path_accepts_equal_parent_and_child(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "parent"
            parent.mkdir()

            result = require_child_path(parent, parent)

            self.assertEqual(result, parent.resolve())

    def test_require_child_path_rejects_sibling_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parent = root / "parent"
            child = root / "sibling" / "file.txt"

            with self.assertRaisesRegex(
                ValueError,
                rf"^path escapes parent directory: "
                rf"{child.resolve(strict=False)} is not within {parent.resolve(strict=False)}$",
            ):
                require_child_path(parent, child)

    def test_require_child_path_rejects_traversal_outside_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parent = root / "parent"
            child = parent / ".." / "outside.txt"

            with self.assertRaisesRegex(
                ValueError,
                rf"^path escapes parent directory: "
                rf"{(root / 'outside.txt').resolve(strict=False)} is not within "
                rf"{parent.resolve(strict=False)}$",
            ):
                require_child_path(parent, child)

    def test_require_child_path_rejects_symlink_escape_from_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            parent = root / "parent"
            sibling = root / "sibling.txt"
            link_path = parent / "link_to_sibling"
            parent.mkdir()
            sibling.write_text("sibling", encoding="utf-8")
            self.create_symlink_or_skip(Path("..") / "sibling.txt", link_path)

            with self.assertRaisesRegex(
                ValueError,
                rf"^path escapes parent directory: "
                rf"{sibling.resolve()} is not within {parent.resolve()}$",
            ):
                require_child_path(parent, link_path)

    def test_require_child_path_accepts_missing_future_child_inside_parent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            parent = Path(tmp_dir) / "parent"
            child = parent / "results" / "result.json"
            parent.mkdir()

            result = require_child_path(parent, child)

            self.assertEqual(result, child.resolve(strict=False))

    def test_require_working_copy_child_accepts_path_inside_working_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / WORKING_COPY_DIR_NAME / "runs" / "result.json"

            result = require_working_copy_child(path)

            self.assertEqual(result, path.resolve(strict=False))

    def test_require_working_copy_child_rejects_path_outside_working_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "runs" / "result.json"

            with self.assertRaisesRegex(
                ValueError,
                rf"^path is not within a {WORKING_COPY_DIR_NAME} working copy: "
                rf"{path.resolve(strict=False)}$",
            ):
                require_working_copy_child(path)

    def test_require_working_copy_child_rejects_traversal_outside_working_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir) / WORKING_COPY_DIR_NAME / "jobs"
            outside = Path(tmp_dir) / "outside" / "result.json"

            with self.assertRaisesRegex(
                ValueError,
                rf"^path is not within a {WORKING_COPY_DIR_NAME} working copy: "
                rf"{outside.resolve(strict=False)}$",
            ):
                require_working_copy_child("../../outside/result.json", base=base)

    def test_require_working_copy_child_rejects_relative_traversal_with_base(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = Path(tmp_dir) / "project"
            nested = project / WORKING_COPY_DIR_NAME / "nested"
            source = project / "source.FCStd"
            nested.mkdir(parents=True)
            source.write_text("source", encoding="utf-8")

            with self.assertRaisesRegex(
                ValueError,
                rf"^path is not within a {WORKING_COPY_DIR_NAME} working copy: "
                rf"{source.resolve()}$",
            ):
                require_working_copy_child("../../source.FCStd", base=nested)

    def test_require_working_copy_child_rejects_symlink_escape_from_working_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = Path(tmp_dir) / "project"
            working_root = project / WORKING_COPY_DIR_NAME
            source = project / "source.FCStd"
            link_path = working_root / "link_to_source"
            working_root.mkdir(parents=True)
            source.write_text("source", encoding="utf-8")
            self.create_symlink_or_skip(Path("..") / "source.FCStd", link_path)

            with self.assertRaisesRegex(
                ValueError,
                rf"^path is not within a {WORKING_COPY_DIR_NAME} working copy: "
                rf"{source.resolve()}$",
            ):
                require_working_copy_child(link_path)

    def test_require_working_copy_child_accepts_missing_future_output_inside_working_copy(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            working_root = Path(tmp_dir) / "project" / WORKING_COPY_DIR_NAME
            future_output = working_root / "results" / "result.json"
            working_root.mkdir(parents=True)

            result = require_working_copy_child(future_output)

            self.assertEqual(result, future_output.resolve(strict=False))

    def test_repeated_calls_return_equal_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / WORKING_COPY_DIR_NAME / "child"

            first = require_within_working_copy(path)
            second = require_within_working_copy(path)

            self.assertEqual(first, second)

    def test_repeated_invalid_calls_have_same_error_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "outside"

            with self.assertRaises(ValueError) as first_error:
                require_within_working_copy(path)

            with self.assertRaises(ValueError) as second_error:
                require_within_working_copy(path)

            self.assertEqual(str(first_error.exception), str(second_error.exception))


if __name__ == "__main__":
    unittest.main()
