import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.native import (
    NativeInstanceInvalid,
    ensure_validated_sidecar,
    sidecar_is_current,
    validation_sidecar_path,
)


class NativeInstanceTests(unittest.TestCase):
    def test_ensure_validated_sidecar_writes_minimal_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.col"
            path.write_text("p edge 2 0\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"status":"ok","instance_id":"sample","family":"rc","n":2,"m":0,"num_colors":3}\n',
                stderr="",
            )

            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": "three_col_native"}), patch(
                "three_col_circle_code.instances.native.subprocess.run",
                return_value=completed,
            ) as run:
                summary = ensure_validated_sidecar(path)

            sidecar = json.loads(validation_sidecar_path(path).read_text(encoding="utf-8"))

        self.assertEqual(summary.instance_id, "sample")
        self.assertEqual(sidecar["instance_id"], "sample")
        self.assertEqual(sidecar["validated"], True)
        self.assertIn("sha256", sidecar)
        self.assertEqual(set(sidecar), {"instance_id", "sha256", "validated"})
        run.assert_called_once()

    def test_current_sidecar_skips_native_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.col"
            path.write_text("p edge 2 0\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"status":"ok","instance_id":"sample","n":2,"m":0}\n',
                stderr="",
            )
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": "three_col_native"}), patch(
                "three_col_circle_code.instances.native.subprocess.run",
                return_value=completed,
            ):
                ensure_validated_sidecar(path)

            with patch("three_col_circle_code.instances.native.subprocess.run") as run:
                self.assertTrue(sidecar_is_current(path))
                ensure_validated_sidecar(path)

        run.assert_not_called()

    def test_invalid_native_result_raises_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.col"
            path.write_text("p edge 2 0\n", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=2,
                stdout='{"status":"error","error":"bad instance"}\n',
                stderr="",
            )

            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": "three_col_native"}), patch(
                "three_col_circle_code.instances.native.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaisesRegex(NativeInstanceInvalid, "bad instance"):
                    ensure_validated_sidecar(path)


if __name__ == "__main__":
    unittest.main()
