"""Tests for deterministic artifact comparison runtime helper.

Coverage:
 1. Import safety and public API
 2. Empty input
 3. Exact byte comparison — matched, different (same/different size), binary, text, line endings, JSON, CSV
 4. Missing and non-file classifications
 5. Ordering and aggregation
 6. Error boundary — non-iterable input, invalid request, monkeypatched failures
 7. Input non-mutation
 8. Boundary regressions — no FreeCAD, no manifests, no verification, no side-effects
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest import mock

import parametron_freecad.runtime.artifact_comparison as _mod
from parametron_freecad.runtime.artifact_comparison import (
    ARTIFACT_COMPARISON_STATUS_DIFFERENT,
    ARTIFACT_COMPARISON_STATUS_MATCHED,
    ARTIFACT_COMPARISON_STATUS_MISSING_BOTH,
    ARTIFACT_COMPARISON_STATUS_MISSING_LEFT,
    ARTIFACT_COMPARISON_STATUS_MISSING_RIGHT,
    ARTIFACT_COMPARISON_STATUS_NOT_FILE_LEFT,
    ARTIFACT_COMPARISON_STATUS_NOT_FILE_RIGHT,
    ArtifactComparisonError,
    ArtifactComparisonReport,
    ArtifactComparisonRequest,
    ArtifactComparisonResult,
    compare_artifact_files,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _req(
    name: str = "artifact",
    role: str = "golden",
    left_path: Path | None = None,
    right_path: Path | None = None,
) -> ArtifactComparisonRequest:
    return ArtifactComparisonRequest(
        name=name,
        role=role,
        left_path=left_path or Path("/tmp/left"),
        right_path=right_path or Path("/tmp/right"),
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# 1. Import safety and public API
# ---------------------------------------------------------------------------


class TestImportSafety(unittest.TestCase):
    def test_module_importable_without_freecad(self) -> None:
        assert "FreeCAD" not in sys.modules

    def test_public_names_in_all(self) -> None:
        expected = {
            "ARTIFACT_COMPARISON_STATUS_DIFFERENT",
            "ARTIFACT_COMPARISON_STATUS_MATCHED",
            "ARTIFACT_COMPARISON_STATUS_MISSING_BOTH",
            "ARTIFACT_COMPARISON_STATUS_MISSING_LEFT",
            "ARTIFACT_COMPARISON_STATUS_MISSING_RIGHT",
            "ARTIFACT_COMPARISON_STATUS_NOT_FILE_LEFT",
            "ARTIFACT_COMPARISON_STATUS_NOT_FILE_RIGHT",
            "ArtifactComparisonError",
            "ArtifactComparisonReport",
            "ArtifactComparisonRequest",
            "ArtifactComparisonResult",
            "compare_artifact_files",
        }
        assert expected == set(_mod.__all__)

    def test_status_constants_are_strings(self) -> None:
        for name in _mod.__all__:
            if name.startswith("ARTIFACT_COMPARISON_STATUS_"):
                assert isinstance(getattr(_mod, name), str)

    def test_compare_artifact_files_is_callable(self) -> None:
        assert callable(compare_artifact_files)

    def test_artifact_comparison_error_is_value_error(self) -> None:
        assert issubclass(ArtifactComparisonError, ValueError)


class TestFrozenDataclasses(unittest.TestCase):
    def test_request_is_frozen(self) -> None:
        req = _req()
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            req.name = "mutated"  # type: ignore[misc]

    def test_result_is_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            left = Path(tmp) / "a.bin"
            right = Path(tmp) / "b.bin"
            left.write_bytes(b"x")
            right.write_bytes(b"x")
            report = compare_artifact_files([_req(left_path=left, right_path=right)])
            result = report.comparisons[0]
            with self.assertRaises((FrozenInstanceError, AttributeError)):
                result.status = "mutated"  # type: ignore[misc]

    def test_report_is_frozen(self) -> None:
        report = compare_artifact_files(())
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            report.all_matched = False  # type: ignore[misc]

    def test_report_comparisons_is_tuple(self) -> None:
        report = compare_artifact_files(())
        assert isinstance(report.comparisons, tuple)


# ---------------------------------------------------------------------------
# 2. Empty input
# ---------------------------------------------------------------------------


class TestEmptyInput(unittest.TestCase):
    def test_empty_tuple_returns_empty_comparisons(self) -> None:
        report = compare_artifact_files(())
        assert report.comparisons == ()

    def test_empty_list_returns_empty_comparisons(self) -> None:
        report = compare_artifact_files([])
        assert report.comparisons == ()

    def test_empty_tuple_all_matched_true(self) -> None:
        report = compare_artifact_files(())
        assert report.all_matched is True

    def test_empty_generator_all_matched_true(self) -> None:
        report = compare_artifact_files(x for x in [])
        assert report.all_matched is True

    def test_empty_input_returns_artifact_comparison_report(self) -> None:
        report = compare_artifact_files(())
        assert isinstance(report, ArtifactComparisonReport)


# ---------------------------------------------------------------------------
# 3. Exact byte comparison — matched
# ---------------------------------------------------------------------------


class TestMatchedFiles(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _compare(self, left: bytes, right: bytes) -> ArtifactComparisonResult:
        lp = self.tmp / "left"
        rp = self.tmp / "right"
        lp.write_bytes(left)
        rp.write_bytes(right)
        report = compare_artifact_files([_req(left_path=lp, right_path=rp)])
        return report.comparisons[0]

    def test_identical_files_status_matched(self) -> None:
        result = self._compare(b"hello", b"hello")
        assert result.status == ARTIFACT_COMPARISON_STATUS_MATCHED

    def test_identical_files_matches_true(self) -> None:
        result = self._compare(b"hello", b"hello")
        assert result.matches is True

    def test_identical_files_all_matched_true(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"hello")
        rp.write_bytes(b"hello")
        report = compare_artifact_files([_req(left_path=lp, right_path=rp)])
        assert report.all_matched is True

    def test_identical_files_sizes_equal(self) -> None:
        result = self._compare(b"hello", b"hello")
        assert result.left_size == result.right_size == 5

    def test_identical_files_sha256_equal(self) -> None:
        result = self._compare(b"hello", b"hello")
        expected = _sha256(b"hello")
        assert result.left_sha256 == result.right_sha256 == expected

    def test_empty_files_matched(self) -> None:
        result = self._compare(b"", b"")
        assert result.status == ARTIFACT_COMPARISON_STATUS_MATCHED
        assert result.matches is True
        assert result.left_size == 0
        assert result.right_size == 0


# ---------------------------------------------------------------------------
# 4. Exact byte comparison — different
# ---------------------------------------------------------------------------


class TestDifferentFiles(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _compare(self, left: bytes, right: bytes) -> ArtifactComparisonResult:
        lp = self.tmp / "left"
        rp = self.tmp / "right"
        lp.write_bytes(left)
        rp.write_bytes(right)
        report = compare_artifact_files([_req(left_path=lp, right_path=rp)])
        return report.comparisons[0]

    def test_different_same_size_status_different(self) -> None:
        result = self._compare(b"aaa", b"bbb")
        assert result.status == ARTIFACT_COMPARISON_STATUS_DIFFERENT

    def test_different_same_size_matches_false(self) -> None:
        result = self._compare(b"aaa", b"bbb")
        assert result.matches is False

    def test_different_same_size_all_matched_false(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"aaa")
        rp.write_bytes(b"bbb")
        report = compare_artifact_files([_req(left_path=lp, right_path=rp)])
        assert report.all_matched is False

    def test_different_same_size_sizes_equal(self) -> None:
        result = self._compare(b"aaa", b"bbb")
        assert result.left_size == result.right_size == 3

    def test_different_same_size_digests_differ(self) -> None:
        result = self._compare(b"aaa", b"bbb")
        assert result.left_sha256 != result.right_sha256

    def test_different_different_size_status_different(self) -> None:
        result = self._compare(b"short", b"longer content here")
        assert result.status == ARTIFACT_COMPARISON_STATUS_DIFFERENT

    def test_different_different_size_matches_false(self) -> None:
        result = self._compare(b"short", b"longer content here")
        assert result.matches is False

    def test_different_different_size_metadata(self) -> None:
        result = self._compare(b"short", b"longer content here")
        assert result.left_size == 5
        assert result.right_size == 19

    def test_binary_byte_for_byte_different(self) -> None:
        left = bytes(range(256))
        right = bytes(b ^ 0x01 for b in range(256))  # XOR lowest bit — guaranteed different
        result = self._compare(left, right)
        assert result.status == ARTIFACT_COMPARISON_STATUS_DIFFERENT

    def test_binary_byte_for_byte_matched(self) -> None:
        data = bytes(range(256))
        result = self._compare(data, data)
        assert result.status == ARTIFACT_COMPARISON_STATUS_MATCHED

    def test_text_not_normalized_different_encodings(self) -> None:
        # Same visual character encoded differently → different bytes
        left = "héllo".encode("utf-8")
        right = "h\xe9llo".encode("latin-1")
        result = self._compare(left, right)
        assert result.status == ARTIFACT_COMPARISON_STATUS_DIFFERENT

    def test_line_ending_difference_is_different(self) -> None:
        result = self._compare(b"line1\nline2\n", b"line1\r\nline2\r\n")
        assert result.status == ARTIFACT_COMPARISON_STATUS_DIFFERENT

    def test_json_semantic_equivalent_but_byte_different(self) -> None:
        left = b'{"a": 1, "b": 2}'
        right = b'{"b": 2, "a": 1}'
        result = self._compare(left, right)
        assert result.status == ARTIFACT_COMPARISON_STATUS_DIFFERENT

    def test_csv_byte_different_is_different(self) -> None:
        left = b"a,b,c\n1,2,3\n"
        right = b"a,b,c\r\n1,2,3\r\n"
        result = self._compare(left, right)
        assert result.status == ARTIFACT_COMPARISON_STATUS_DIFFERENT


# ---------------------------------------------------------------------------
# 5. Missing and non-file classifications
# ---------------------------------------------------------------------------


class TestMissingAndNonFile(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_left_status(self) -> None:
        rp = self.tmp / "right"
        rp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=self.tmp / "missing", right_path=rp)]
        ).comparisons[0]
        assert result.status == ARTIFACT_COMPARISON_STATUS_MISSING_LEFT

    def test_missing_left_matches_false(self) -> None:
        rp = self.tmp / "right"
        rp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=self.tmp / "missing", right_path=rp)]
        ).comparisons[0]
        assert result.matches is False

    def test_missing_left_all_matched_false(self) -> None:
        rp = self.tmp / "right"
        rp.write_bytes(b"data")
        report = compare_artifact_files(
            [_req(left_path=self.tmp / "missing", right_path=rp)]
        )
        assert report.all_matched is False

    def test_missing_right_status(self) -> None:
        lp = self.tmp / "left"
        lp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=lp, right_path=self.tmp / "missing")]
        ).comparisons[0]
        assert result.status == ARTIFACT_COMPARISON_STATUS_MISSING_RIGHT

    def test_missing_right_matches_false(self) -> None:
        lp = self.tmp / "left"
        lp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=lp, right_path=self.tmp / "missing")]
        ).comparisons[0]
        assert result.matches is False

    def test_missing_both_status(self) -> None:
        result = compare_artifact_files(
            [_req(left_path=self.tmp / "ml", right_path=self.tmp / "mr")]
        ).comparisons[0]
        assert result.status == ARTIFACT_COMPARISON_STATUS_MISSING_BOTH

    def test_missing_both_matches_false(self) -> None:
        result = compare_artifact_files(
            [_req(left_path=self.tmp / "ml", right_path=self.tmp / "mr")]
        ).comparisons[0]
        assert result.matches is False

    def test_missing_left_left_size_none(self) -> None:
        rp = self.tmp / "right"
        rp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=self.tmp / "missing", right_path=rp)]
        ).comparisons[0]
        assert result.left_size is None

    def test_missing_right_right_size_none(self) -> None:
        lp = self.tmp / "left"
        lp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=lp, right_path=self.tmp / "missing")]
        ).comparisons[0]
        assert result.right_size is None

    def test_missing_both_sizes_none(self) -> None:
        result = compare_artifact_files(
            [_req(left_path=self.tmp / "ml", right_path=self.tmp / "mr")]
        ).comparisons[0]
        assert result.left_size is None
        assert result.right_size is None

    def test_missing_both_digests_none(self) -> None:
        result = compare_artifact_files(
            [_req(left_path=self.tmp / "ml", right_path=self.tmp / "mr")]
        ).comparisons[0]
        assert result.left_sha256 is None
        assert result.right_sha256 is None

    def test_left_is_directory_not_file_left(self) -> None:
        d = self.tmp / "subdir"
        d.mkdir()
        rp = self.tmp / "right"
        rp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=d, right_path=rp)]
        ).comparisons[0]
        assert result.status == ARTIFACT_COMPARISON_STATUS_NOT_FILE_LEFT

    def test_left_is_directory_matches_false(self) -> None:
        d = self.tmp / "subdir"
        d.mkdir()
        rp = self.tmp / "right"
        rp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=d, right_path=rp)]
        ).comparisons[0]
        assert result.matches is False

    def test_right_is_directory_not_file_right(self) -> None:
        lp = self.tmp / "left"
        lp.write_bytes(b"data")
        d = self.tmp / "subdir"
        d.mkdir()
        result = compare_artifact_files(
            [_req(left_path=lp, right_path=d)]
        ).comparisons[0]
        assert result.status == ARTIFACT_COMPARISON_STATUS_NOT_FILE_RIGHT

    def test_right_is_directory_matches_false(self) -> None:
        lp = self.tmp / "left"
        lp.write_bytes(b"data")
        d = self.tmp / "subdir"
        d.mkdir()
        result = compare_artifact_files(
            [_req(left_path=lp, right_path=d)]
        ).comparisons[0]
        assert result.matches is False

    def test_not_file_left_left_size_none(self) -> None:
        d = self.tmp / "subdir"
        d.mkdir()
        rp = self.tmp / "right"
        rp.write_bytes(b"data")
        result = compare_artifact_files(
            [_req(left_path=d, right_path=rp)]
        ).comparisons[0]
        assert result.left_size is None

    def test_not_file_right_right_size_none(self) -> None:
        lp = self.tmp / "left"
        lp.write_bytes(b"data")
        d = self.tmp / "subdir"
        d.mkdir()
        result = compare_artifact_files(
            [_req(left_path=lp, right_path=d)]
        ).comparisons[0]
        assert result.right_size is None

    def test_missing_cases_no_exception_raised(self) -> None:
        # All missing/non-file cases return records, not exceptions.
        cases = [
            _req(left_path=self.tmp / "nx_l", right_path=self.tmp / "nx_r"),
        ]
        lp = self.tmp / "left"
        lp.write_bytes(b"x")
        d = self.tmp / "dir"
        d.mkdir()
        cases += [
            _req(left_path=self.tmp / "nx", right_path=lp),
            _req(left_path=lp, right_path=self.tmp / "nx"),
            _req(left_path=d, right_path=lp),
            _req(left_path=lp, right_path=d),
        ]
        for req in cases:
            report = compare_artifact_files([req])
            assert len(report.comparisons) == 1
            assert report.comparisons[0].matches is False


# ---------------------------------------------------------------------------
# 6. Ordering and aggregation
# ---------------------------------------------------------------------------


class TestOrderingAndAggregation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _file(self, name: str, data: bytes = b"x") -> Path:
        p = self.tmp / name
        p.write_bytes(data)
        return p

    def test_request_order_preserved(self) -> None:
        names = ["first", "second", "third"]
        reqs = [
            _req(name=n, left_path=self._file(f"l_{n}"), right_path=self._file(f"r_{n}"))
            for n in names
        ]
        report = compare_artifact_files(reqs)
        assert [r.name for r in report.comparisons] == names

    def test_mixed_results_order_preserved(self) -> None:
        lm = self._file("lm", b"same")
        rm = self._file("rm", b"same")
        ld = self._file("ld", b"aaa")
        rd = self._file("rd", b"bbb")
        lmiss = self.tmp / "lmiss_nonexistent"
        rmiss = self.tmp / "rmiss_nonexistent"
        reqs = [
            _req(name="match", left_path=lm, right_path=rm),
            _req(name="diff", left_path=ld, right_path=rd),
            _req(name="miss", left_path=lmiss, right_path=rmiss),
        ]
        report = compare_artifact_files(reqs)
        assert [r.name for r in report.comparisons] == ["match", "diff", "miss"]
        assert report.comparisons[0].status == ARTIFACT_COMPARISON_STATUS_MATCHED
        assert report.comparisons[1].status == ARTIFACT_COMPARISON_STATUS_DIFFERENT
        assert report.comparisons[2].status == ARTIFACT_COMPARISON_STATUS_MISSING_BOTH

    def test_all_matched_true_when_all_match(self) -> None:
        l1 = self._file("l1", b"x")
        r1 = self._file("r1", b"x")
        l2 = self._file("l2", b"x")
        r2 = self._file("r2", b"x")
        report = compare_artifact_files([
            _req(name="a", left_path=l1, right_path=r1),
            _req(name="b", left_path=l2, right_path=r2),
        ])
        assert report.all_matched is True

    def test_all_matched_false_when_one_differs(self) -> None:
        l1 = self._file("l1", b"x")
        r1 = self._file("r1", b"x")
        l2 = self._file("l2", b"aaa")
        r2 = self._file("r2", b"bbb")
        report = compare_artifact_files([
            _req(name="a", left_path=l1, right_path=r1),
            _req(name="b", left_path=l2, right_path=r2),
        ])
        assert report.all_matched is False

    def test_all_matched_false_when_one_missing(self) -> None:
        l1 = self._file("l1", b"x")
        r1 = self._file("r1", b"x")
        report = compare_artifact_files([
            _req(name="a", left_path=l1, right_path=r1),
            _req(name="b", left_path=self.tmp / "nx", right_path=self.tmp / "ny"),
        ])
        assert report.all_matched is False

    def test_name_preserved_in_result(self) -> None:
        lp = self._file("lp", b"data")
        rp = self._file("rp", b"data")
        result = compare_artifact_files(
            [_req(name="step_file", left_path=lp, right_path=rp)]
        ).comparisons[0]
        assert result.name == "step_file"

    def test_role_preserved_in_result(self) -> None:
        lp = self._file("lp", b"data")
        rp = self._file("rp", b"data")
        result = compare_artifact_files(
            [_req(role="geometry", left_path=lp, right_path=rp)]
        ).comparisons[0]
        assert result.role == "geometry"

    def test_resolved_paths_are_path_objects(self) -> None:
        lp = self._file("lp", b"x")
        rp = self._file("rp", b"x")
        result = compare_artifact_files(
            [_req(left_path=lp, right_path=rp)]
        ).comparisons[0]
        assert isinstance(result.left_path, Path)
        assert isinstance(result.right_path, Path)

    def test_single_different_makes_all_matched_false(self) -> None:
        lp = self._file("lp", b"a")
        rp = self._file("rp", b"b")
        report = compare_artifact_files([_req(left_path=lp, right_path=rp)])
        assert report.all_matched is False

    def test_generator_input_preserves_order(self) -> None:
        names = ["g1", "g2", "g3"]
        files = [(self._file(f"gl_{n}", b"x"), self._file(f"gr_{n}", b"x")) for n in names]
        report = compare_artifact_files(
            _req(name=n, left_path=l, right_path=r)
            for (n, (l, r)) in zip(names, files)
        )
        assert [c.name for c in report.comparisons] == names


# ---------------------------------------------------------------------------
# 7. Error boundary
# ---------------------------------------------------------------------------


class TestErrorBoundary(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_non_iterable_raises_artifact_comparison_error(self) -> None:
        with self.assertRaises(ArtifactComparisonError) as ctx:
            compare_artifact_files(42)  # type: ignore[arg-type]
        assert "iterable" in str(ctx.exception).lower()

    def test_non_iterable_cause_is_type_error(self) -> None:
        try:
            compare_artifact_files(42)  # type: ignore[arg-type]
        except ArtifactComparisonError as exc:
            assert isinstance(exc.__cause__, TypeError)
        else:
            self.fail("expected ArtifactComparisonError")

    def test_invalid_request_type_raises_error(self) -> None:
        with self.assertRaises(ArtifactComparisonError) as ctx:
            compare_artifact_files(["not_a_request"])  # type: ignore[list-item]
        assert "ArtifactComparisonRequest" in str(ctx.exception)

    def test_none_in_iterable_raises_error(self) -> None:
        with self.assertRaises(ArtifactComparisonError):
            compare_artifact_files([None])  # type: ignore[list-item]

    def test_empty_name_raises_error(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = ArtifactComparisonRequest(name="", role="r", left_path=lp, right_path=rp)
        with self.assertRaises(ArtifactComparisonError):
            compare_artifact_files([req])

    def test_empty_role_raises_error(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = ArtifactComparisonRequest(name="n", role="", left_path=lp, right_path=rp)
        with self.assertRaises(ArtifactComparisonError):
            compare_artifact_files([req])

    def test_read_failure_raises_artifact_comparison_error(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = _req(left_path=lp, right_path=rp)
        with mock.patch.object(Path, "read_bytes", side_effect=OSError("disk error")):
            with self.assertRaises(ArtifactComparisonError) as ctx:
                compare_artifact_files([req])
        assert "artifact" in str(ctx.exception).lower()

    def test_read_failure_cause_preserved(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = _req(left_path=lp, right_path=rp)
        with mock.patch.object(Path, "read_bytes", side_effect=OSError("disk error")):
            try:
                compare_artifact_files([req])
            except ArtifactComparisonError as exc:
                assert isinstance(exc.__cause__, OSError)
            else:
                self.fail("expected ArtifactComparisonError")

    def test_exists_oserror_raises_artifact_comparison_error(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = _req(left_path=lp, right_path=rp)
        with mock.patch.object(Path, "exists", side_effect=OSError("stat failure")):
            with self.assertRaises(ArtifactComparisonError):
                compare_artifact_files([req])

    def test_exists_oserror_cause_preserved(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = _req(left_path=lp, right_path=rp)
        with mock.patch.object(Path, "exists", side_effect=OSError("stat failure")):
            try:
                compare_artifact_files([req])
            except ArtifactComparisonError as exc:
                assert isinstance(exc.__cause__, OSError)
            else:
                self.fail("expected ArtifactComparisonError")


# ---------------------------------------------------------------------------
# 8. Input non-mutation
# ---------------------------------------------------------------------------


class TestInputNonMutation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_request_list_length_not_changed(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        reqs = [_req(left_path=lp, right_path=rp)]
        compare_artifact_files(reqs)
        assert len(reqs) == 1

    def test_request_object_identity_preserved(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = _req(left_path=lp, right_path=rp)
        reqs = [req]
        compare_artifact_files(reqs)
        assert reqs[0] is req

    def test_files_not_modified_by_comparison(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"original_left")
        rp.write_bytes(b"original_right")
        compare_artifact_files([_req(left_path=lp, right_path=rp)])
        assert lp.read_bytes() == b"original_left"
        assert rp.read_bytes() == b"original_right"

    def test_request_name_field_not_mutated(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = _req(name="original", left_path=lp, right_path=rp)
        compare_artifact_files([req])
        assert req.name == "original"

    def test_request_role_field_not_mutated(self) -> None:
        lp = self.tmp / "a"
        rp = self.tmp / "b"
        lp.write_bytes(b"x")
        rp.write_bytes(b"x")
        req = _req(role="my_role", left_path=lp, right_path=rp)
        compare_artifact_files([req])
        assert req.role == "my_role"


# ---------------------------------------------------------------------------
# 9. Boundary regressions — no scope creep
# ---------------------------------------------------------------------------


class TestBoundaryRegressions(unittest.TestCase):
    def test_does_not_import_freecad(self) -> None:
        # The module is already imported at top-level; verify no FreeCAD was pulled in.
        # Re-importing via import_module uses the cached module and does not reload,
        # so it cannot invalidate other tests' stale references.
        assert "parametron_freecad.runtime.artifact_comparison" in sys.modules
        assert "FreeCAD" not in sys.modules

    def test_module_namespace_does_not_expose_manifest_loader(self) -> None:
        # artifact_comparison must not import manifest_loader into its own namespace.
        for attr in vars(_mod).values():
            name = getattr(attr, "__name__", "") or ""
            module = getattr(attr, "__module__", "") or ""
            assert "manifest_loader" not in name
            assert "manifest_loader" not in module

    def test_module_namespace_does_not_expose_verification_loader(self) -> None:
        # artifact_comparison must not import verification_loader into its own namespace.
        for attr in vars(_mod).values():
            name = getattr(attr, "__name__", "") or ""
            module = getattr(attr, "__module__", "") or ""
            assert "verification_loader" not in name
            assert "verification_loader" not in module

    def test_module_namespace_does_not_expose_integration_rehearsal(self) -> None:
        # artifact_comparison must not import integration_rehearsal into its own namespace.
        for attr in vars(_mod).values():
            name = getattr(attr, "__name__", "") or ""
            module = getattr(attr, "__module__", "") or ""
            assert "integration_rehearsal" not in name
            assert "integration_rehearsal" not in module

    def test_no_result_json_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lp = Path(tmp) / "a"
            rp = Path(tmp) / "b"
            lp.write_bytes(b"x")
            rp.write_bytes(b"x")
            compare_artifact_files([_req(left_path=lp, right_path=rp)])
            assert not (Path(tmp) / "result.json").exists()

    def test_no_observed_json_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lp = Path(tmp) / "a"
            rp = Path(tmp) / "b"
            lp.write_bytes(b"x")
            rp.write_bytes(b"x")
            compare_artifact_files([_req(left_path=lp, right_path=rp)])
            assert not (Path(tmp) / "parametron.observed.json").exists()

    def test_no_extra_files_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lp = Path(tmp) / "left_input"
            rp = Path(tmp) / "right_input"
            lp.write_bytes(b"original")
            rp.write_bytes(b"original")
            before = set(Path(tmp).iterdir())
            compare_artifact_files([_req(left_path=lp, right_path=rp)])
            after = set(Path(tmp).iterdir())
            assert before == after, f"unexpected files written: {after - before}"

    def test_report_has_no_verdict_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lp = Path(tmp) / "a"
            rp = Path(tmp) / "b"
            lp.write_bytes(b"x")
            rp.write_bytes(b"y")
            report = compare_artifact_files([_req(left_path=lp, right_path=rp)])
        assert isinstance(report, ArtifactComparisonReport)
        assert not hasattr(report, "accepted")
        assert not hasattr(report, "rejected")
        assert not hasattr(report, "verdict")

    def test_module_has_no_cli_entrypoint(self) -> None:
        assert not hasattr(_mod, "main")
        assert not hasattr(_mod, "cli")


if __name__ == "__main__":
    unittest.main()
