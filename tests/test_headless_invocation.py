from __future__ import annotations

import importlib
import io
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.runtime import headless


class FakeFreeCAD:
    def Version(self) -> list[str]:
        return ["1", "0", "0", "fake"]


class HeadlessInvocationTests(unittest.TestCase):
    def _repo_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _script_path(self) -> Path:
        return self._repo_root() / "scripts" / "parametron_freecad_headless.py"

    def _import_with_freecad_blocked(self, module_name: str):
        original_import = __import__

        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "FreeCAD":
                raise AssertionError("FreeCAD should not be imported")
            return original_import(name, globals, locals, fromlist, level)

        sys.modules.pop(module_name, None)
        with mock.patch("builtins.__import__", side_effect=guarded_import):
            return importlib.import_module(module_name)

    def _run_freecad_command(
        self,
        command: list[str],
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=self._repo_root(),
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )

    def _meaningful_excerpt(self, result: subprocess.CompletedProcess[str]) -> str:
        for stream_name, stream_value in (
            ("stderr", result.stderr),
            ("stdout", result.stdout),
        ):
            for line in stream_value.splitlines():
                stripped = line.strip()
                if stripped:
                    return f"{stream_name}: {stripped[:240]}"
        return "stdout/stderr were both empty"

    def _evaluate_freecad_smoke_result(
        self,
        result: subprocess.CompletedProcess[str],
    ) -> tuple[bool, str]:
        if result.returncode != 0:
            return False, f"return code was {result.returncode}"
        if "Traceback" in result.stderr:
            return False, "stderr contained a Python traceback"

        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            return False, f"stdout was not valid JSON: {exc}"

        if payload.get("status") != "ok":
            return False, f"status was {payload.get('status')!r}"
        if payload.get("host") != "freecadcmd":
            return False, f"host was {payload.get('host')!r}"
        if "freecadVersion" not in payload:
            return False, "freecadVersion was missing"
        return True, "ok"

    def _format_smoke_diagnostic(
        self,
        label: str,
        command: list[str],
        result: subprocess.CompletedProcess[str],
        outcome: str,
    ) -> str:
        return (
            f"{label}: command={shlex.join(command)}; "
            f"returncode={result.returncode}; "
            f"outcome={outcome}; "
            f"excerpt={self._meaningful_excerpt(result)}"
        )

    def test_run_headless_smoke_with_fake_freecad_writes_stable_json(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        exit_code = headless.run_headless_smoke(FakeFreeCAD(), stdout, stderr)

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            stdout.getvalue(),
            '{"freecadVersion":["1","0","0","fake"],"host":"freecadcmd","status":"ok"}\n',
        )
        self.assertEqual(stderr.getvalue(), "")

    def test_main_returns_deterministic_failure_when_freecad_is_unavailable(
        self,
    ) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch(
            "parametron_freecad.runtime.headless.import_module",
            side_effect=ImportError("No module named FreeCAD"),
        ):
            exit_code = headless.main(stdout=stdout, stderr=stderr)

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            "parametron-freecad: FreeCAD module is not available\n",
        )

    def test_repeated_success_calls_produce_identical_output(self) -> None:
        first_stdout = io.StringIO()
        second_stdout = io.StringIO()

        first_exit_code = headless.main(
            stdout=first_stdout,
            stderr=io.StringIO(),
            freecad_module=FakeFreeCAD(),
        )
        second_exit_code = headless.main(
            stdout=second_stdout,
            stderr=io.StringIO(),
            freecad_module=FakeFreeCAD(),
        )

        self.assertEqual(first_exit_code, 0)
        self.assertEqual(second_exit_code, 0)
        self.assertEqual(first_stdout.getvalue(), second_stdout.getvalue())

    def test_runtime_module_import_does_not_require_freecad(self) -> None:
        module = self._import_with_freecad_blocked(
            "parametron_freecad.runtime.headless"
        )
        self.assertIsNotNone(module)
        self.assertEqual(
            module.FREECAD_UNAVAILABLE_MESSAGE,
            "parametron-freecad: FreeCAD module is not available",
        )

    def test_script_module_import_does_not_require_freecad(self) -> None:
        module = self._import_with_freecad_blocked(
            "scripts.parametron_freecad_headless"
        )
        self.assertEqual(module.main.__module__, "parametron_freecad.runtime.headless")
        self.assertEqual(module.main.__name__, "main")

    def test_direct_script_execution_without_freecad_is_deterministic(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self._script_path())],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            result.stderr,
            "parametron-freecad: FreeCAD module is not available\n",
        )

    def test_nix_wrapper_smoke_from_unrelated_working_directory(self) -> None:
        wrapper = shutil.which("parametron-freecad")
        strict_smoke = os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1"
        if wrapper is None:
            message = "parametron-freecad wrapper is unavailable on PATH"
            if strict_smoke:
                self.fail(message)
            self.skipTest(message)

        with tempfile.TemporaryDirectory() as tmp_dir:
            command = [wrapper, "smoke"]
            result = subprocess.run(
                command,
                cwd=tmp_dir,
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )

        ok, outcome = self._evaluate_freecad_smoke_result(result)
        diagnostic = self._format_smoke_diagnostic(
            "Nix wrapper smoke",
            command,
            result,
            outcome,
        )
        self.assertTrue(ok, diagnostic)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["host"], "freecadcmd")
        self.assertIn("freecadVersion", payload)


if __name__ == "__main__":
    unittest.main()
