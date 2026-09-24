"""Gated real-FreeCAD proof for App-level target-state observation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "partdesign_mutations" / "partdesign-mutations.FCStd"
RUNNER = Path(__file__).parent / "freecad_target_state_runner.py"


class RealTargetStateObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        name = os.environ.get("PARAMETRON_FREECAD_BIN", "freecadcmd")
        cls.host = shutil.which(name)
        if cls.host is None:
            message = f"FreeCAD host {name!r} unavailable outside the Nix shell"
            if os.environ.get("PARAMETRON_FREECAD_STRICT_SMOKE") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)

    def test_exact_native_suppression_visibility_and_existence(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / FIXTURE.name
            shutil.copyfile(FIXTURE, fixture)
            output = Path(directory) / "evidence.json"
            completed = subprocess.run(
                [self.host, "-P", str(ROOT), str(RUNNER), f"--pass={fixture}", f"--pass={output}"],
                capture_output=True, text=True, timeout=60, check=False,
            )
            self.assertTrue(output.is_file(), completed.stderr + completed.stdout)
            evidence = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual([(x["object"], x["status"], x.get("value")) for x in evidence["suppression"]], [
            ("IntermediatePad", "observed", False), ("TerminalChamfer", "observed", True),
        ])
        self.assertEqual([(x["object"], x["status"], x.get("value")) for x in evidence["visibility"]], [
            ("BaseSketch", "observed", False), ("MutationBody", "observed", True),
        ])
        self.assertEqual([(x["object"], x["status"]) for x in evidence["existence"]], [
            ("NoSuchTarget", "absent"), ("TerminalChamfer", "exists"),
        ])


if __name__ == "__main__":
    unittest.main()
