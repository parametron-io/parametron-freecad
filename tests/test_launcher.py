from __future__ import annotations

import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from parametron_freecad.runtime import launcher


class LauncherResolutionTests(unittest.TestCase):
    def test_default_host_resolution_uses_freecadcmd_from_path(self) -> None:
        environment = {"PATH": "/controlled/bin", "UNRELATED": "ignored"}
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch.object(
                launcher.shutil,
                "which",
                return_value="/controlled/bin/freecadcmd",
            ) as which:
                resolved = launcher.resolve_freecad_host()

        self.assertEqual(resolved, "/controlled/bin/freecadcmd")
        which.assert_called_once_with("freecadcmd")

    def test_explicit_absolute_host_override_is_selected_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            host = Path(tmp_dir) / "custom-freecadcmd"
            host.touch(mode=0o755)
            with mock.patch.dict(
                os.environ,
                {"PARAMETRON_FREECAD_BIN": str(host)},
                clear=True,
            ):
                self.assertEqual(launcher.resolve_freecad_host(), str(host))

    def test_explicit_path_resolvable_host_name_is_selected(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"PARAMETRON_FREECAD_BIN": "custom-freecadcmd"},
            clear=True,
        ):
            with mock.patch.object(
                launcher.shutil,
                "which",
                return_value="/controlled/bin/custom-freecadcmd",
            ) as which:
                self.assertEqual(
                    launcher.resolve_freecad_host(),
                    "/controlled/bin/custom-freecadcmd",
                )
        which.assert_called_once_with("custom-freecadcmd")

    def test_explicit_host_surrounding_whitespace_is_trimmed(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"PARAMETRON_FREECAD_BIN": "  custom-freecadcmd  "},
            clear=True,
        ):
            with mock.patch.object(
                launcher.shutil,
                "which",
                return_value="/controlled/bin/custom-freecadcmd",
            ) as which:
                launcher.resolve_freecad_host()
        which.assert_called_once_with("custom-freecadcmd")

    def test_compound_host_configuration_is_not_split_or_run_in_a_shell(self) -> None:
        configured = "custom-freecadcmd --some-flag"
        with mock.patch.dict(
            os.environ,
            {"PARAMETRON_FREECAD_BIN": configured},
            clear=True,
        ):
            with mock.patch.object(launcher.shutil, "which", return_value=None) as which:
                with self.assertRaises(launcher.FreeCADHostResolutionError):
                    launcher.resolve_freecad_host()
        which.assert_called_once_with(configured)

    def test_blank_host_configuration_is_rejected_without_starting_child(self) -> None:
        for configured in ("", "   "):
            with self.subTest(configured=configured):
                with mock.patch.dict(
                    os.environ,
                    {"PARAMETRON_FREECAD_BIN": configured},
                    clear=True,
                ):
                    with mock.patch.object(launcher.subprocess, "run") as run:
                        with mock.patch("sys.stderr") as stderr:
                            exit_code = launcher.launch(["smoke"])
                self.assertEqual(exit_code, 127)
                run.assert_not_called()
                diagnostic = "".join(call.args[0] for call in stderr.write.call_args_list)
                self.assertIn("empty or whitespace-only", diagnostic)

    def test_recursive_wrapper_name_is_rejected_without_starting_child(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"PARAMETRON_FREECAD_BIN": "parametron-freecad"},
            clear=True,
        ):
            with mock.patch.object(
                launcher.shutil,
                "which",
                return_value="/controlled/bin/parametron-freecad",
            ):
                with mock.patch.object(launcher.subprocess, "run") as run:
                    with mock.patch("sys.stderr") as stderr:
                        exit_code = launcher.launch(["smoke"])
        self.assertEqual(exit_code, 127)
        run.assert_not_called()
        diagnostic = "".join(call.args[0] for call in stderr.write.call_args_list)
        self.assertIn("recursively", diagnostic)

    def test_absolute_recursive_wrapper_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            wrapper = Path(tmp_dir) / "parametron-freecad"
            wrapper.touch(mode=0o755)
            with mock.patch.dict(
                os.environ,
                {"PARAMETRON_FREECAD_BIN": str(wrapper)},
                clear=True,
            ):
                with self.assertRaisesRegex(
                    launcher.FreeCADHostResolutionError,
                    "recursively",
                ):
                    launcher.resolve_freecad_host()


class LauncherArgumentTransportTests(unittest.TestCase):
    def test_execute_request_builds_exact_structured_host_argv(self) -> None:
        protocol = [
            "execute",
            "--working-copy",
            "/tmp/work dir/_working/run",
            "--manifest",
            "/tmp/work dir/_working/run/export_manifest_v1.json",
            "--result",
            "/tmp/work dir/_working/run/result.json",
            "--output-dir",
            "/tmp/work dir/_working/run/outputs",
            "--observation-request",
            "/tmp/work dir/_working/run/parametron.verification.json",
        ]

        actual = launcher.build_host_argv("/bin/freecadcmd", protocol)

        self.assertEqual(
            actual,
            [
                "/bin/freecadcmd",
                "-P",
                str(launcher.package_root()),
                "-c",
                launcher.FREECAD_BOOTSTRAP_EXPRESSION,
                *(f"--pass={value}" for value in protocol),
            ],
        )

    def test_special_character_arguments_are_preserved_as_data(self) -> None:
        values = [
            "value with spaces",
            "unicodé/路径",
            "--starts-with-dash",
            "quotes'\"remain",
            "; $HOME & `touch never`",
            "key=value=again",
            "repeated",
            "repeated",
            "",
        ]

        actual = launcher.build_host_argv("freecadcmd", values)

        self.assertEqual(actual[5:], [f"--pass={value}" for value in values])
        self.assertEqual(len(actual[5:]), len(values))

    def test_bootstrap_is_fixed_and_never_contains_protocol_values(self) -> None:
        hostile_values = ["/tmp/path'); import os; #", "$(touch never); `id`"]
        first = launcher.build_host_argv("host", hostile_values)
        second = launcher.build_host_argv("host", ["entirely-different"])

        self.assertEqual(first[4], launcher.FREECAD_BOOTSTRAP_EXPRESSION)
        self.assertEqual(first[4], second[4])
        for value in hostile_values:
            self.assertNotIn(value, first[4])
            self.assertIn(f"--pass={value}", first[5:])
        self.assertNotIn("eval", first[4])

    def test_launch_uses_subprocess_list_without_shell_or_eval(self) -> None:
        with mock.patch.object(launcher, "resolve_freecad_host", return_value="host"):
            with mock.patch.object(launcher.subprocess, "run") as run:
                run.return_value.returncode = 0
                exit_code = launcher.launch(["smoke", "; echo never"])

        self.assertEqual(exit_code, 0)
        run.assert_called_once_with(
            launcher.build_host_argv("host", ["smoke", "; echo never"]),
            check=False,
        )


class LauncherProcessTests(unittest.TestCase):
    def _write_stub(self, directory: Path, body: str) -> Path:
        stub = directory / "freecad host stub"
        stub.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        return stub

    def _run_launcher(
        self,
        host: Path | str,
        protocol: list[str],
        cwd: Path,
        record_path: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["PARAMETRON_FREECAD_BIN"] = str(host)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        if record_path is not None:
            environment["LAUNCHER_STUB_RECORD"] = str(record_path)
        return subprocess.run(
            [sys.executable, "-m", "parametron_freecad.runtime.launcher", *protocol],
            cwd=cwd,
            env=environment,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )

    def test_stub_host_success_preserves_streams_and_exact_argv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir)
            record = directory / "argv.json"
            stub = self._write_stub(
                directory,
                "import json, os, sys\n"
                "open(os.environ['LAUNCHER_STUB_RECORD'], 'w', encoding='utf-8').write(json.dumps(sys.argv[1:]))\n"
                "print('stub stdout')\n"
                "print('stub stderr', file=sys.stderr)\n",
            )
            protocol = ["smoke", "value with spaces", "; $HOME & `id`"]
            result = self._run_launcher(stub, protocol, directory, record)

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "stub stdout\n")
            self.assertEqual(result.stderr, "stub stderr\n")
            self.assertEqual(
                json.loads(record.read_text(encoding="utf-8")),
                launcher.build_host_argv(str(stub), protocol)[1:],
            )

    def test_missing_host_returns_127_with_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing = Path(tmp_dir) / "missing-freecadcmd"
            result = self._run_launcher(missing, ["smoke"], Path(tmp_dir))

        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stdout, "")
        self.assertIn("FreeCAD host could not be started", result.stderr)
        self.assertIn("missing-freecadcmd", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_nonzero_host_exit_and_streams_are_propagated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir)
            stub = self._write_stub(
                directory,
                "import sys\n"
                "print('before exit')\n"
                "print('controlled failure', file=sys.stderr)\n"
                "raise SystemExit(23)\n",
            )
            result = self._run_launcher(stub, ["smoke"], directory)

        self.assertEqual(result.returncode, 23)
        self.assertEqual(result.stdout, "before exit\n")
        self.assertEqual(result.stderr, "controlled failure\n")

    @unittest.skipUnless(os.name == "posix", "signal propagation requires POSIX")
    def test_signal_termination_maps_to_128_plus_signal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir)
            stub = self._write_stub(
                directory,
                "import os, signal\n"
                "os.kill(os.getpid(), signal.SIGTERM)\n",
            )
            result = self._run_launcher(stub, ["smoke"], directory)

        self.assertEqual(result.returncode, 128 + signal.SIGTERM)

    def test_launcher_is_independent_of_caller_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            directory = Path(tmp_dir)
            record = directory / "argv.json"
            stub = self._write_stub(
                directory,
                "import json, os, sys\n"
                "open(os.environ['LAUNCHER_STUB_RECORD'], 'w', encoding='utf-8').write(json.dumps(sys.argv[1:]))\n",
            )
            result = self._run_launcher(stub, ["smoke"], directory, record)

            self.assertEqual(result.returncode, 0)
            recorded = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(recorded[1], str(launcher.package_root()))
            self.assertTrue(Path(recorded[1]).is_absolute())
            self.assertNotEqual(Path(recorded[1]), directory)


class NixWrapperContractTests(unittest.TestCase):
    def test_nix_wrapper_is_discoverable_and_executable(self) -> None:
        wrapper = shutil.which("parametron-freecad")
        if wrapper is None:
            self.skipTest("parametron-freecad is unavailable outside the Nix shell")

        self.assertTrue(os.path.isabs(wrapper))
        self.assertTrue(os.access(wrapper, os.X_OK))
        self.assertNotIn(str(Path.home()), wrapper)


if __name__ == "__main__":
    unittest.main()
