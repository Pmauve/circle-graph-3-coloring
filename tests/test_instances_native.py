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
    generate_col_with_native,
    generate_col_sequence_with_native,
    materialize_circle_with_native,
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

    def test_ensure_validated_sidecar_accepts_compact_circle_without_native_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.circle"
            path.write_text(
                "\n".join(
                    [
                        "c instance id sample",
                        "c family rc",
                        "c n 2",
                        "c m 1",
                        "c num colors 3",
                        "c hord endpoint order START",
                        "c 1 2 1 2",
                        "c hord endpoint order END",
                        "p circle 2 1",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            with patch("three_col_circle_code.instances.native.subprocess.run") as run:
                summary = ensure_validated_sidecar(path)

            sidecar = json.loads(validation_sidecar_path(path).read_text(encoding="utf-8"))

        self.assertEqual(summary.instance_id, "sample")
        self.assertEqual(summary.n, 2)
        self.assertEqual(summary.m, 1)
        self.assertEqual(sidecar["validated"], True)
        run.assert_not_called()

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

    def test_generate_col_with_native_invokes_instance_generate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "sample.col"
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"status":"ok","instance_id":"sample","family":"rc_fast","n":8,"m":7,"num_colors":3,"path":"sample.col"}\n',
                stderr="",
            )

            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": "three_col_native"}), patch(
                "three_col_circle_code.instances.native.subprocess.run",
                return_value=completed,
            ) as run:
                summary = generate_col_with_native(
                    instance_path=path,
                    family="rc_fast",
                    n=8,
                    seed=17,
                )

        self.assertEqual(summary.instance_id, "sample")
        self.assertEqual(summary.family, "rc_fast")
        self.assertEqual(summary.n, 8)
        run.assert_called_once()
        self.assertEqual(
            run.call_args.args[0],
            [
                "three_col_native",
                "instance",
                "generate",
                "--family",
                "rc_fast",
                "--n",
                "8",
                "--seed",
                "17",
                "--num-colors",
                "3",
                "--max-attempts-per-node",
                "10000",
                "--output",
                str(path),
            ],
        )

    def test_generate_col_sequence_with_native_invokes_generate_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "instances"
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"status":"ok","count":2,"paths":["a.col","b.col"]}\n',
                stderr="",
            )

            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": "three_col_native"}), patch(
                "three_col_circle_code.instances.native.subprocess.run",
                return_value=completed,
            ) as run:
                paths = generate_col_sequence_with_native(
                    output_dir=output_dir,
                    family="rcy_fast",
                    start_n=100,
                    stop_n=300,
                    step_n=100,
                    seed=17,
                )

        self.assertEqual(paths, [Path("a.col"), Path("b.col")])
        self.assertEqual(
            run.call_args.args[0],
            [
                "three_col_native",
                "instance",
                "generate-sequence",
                "--family",
                "rcy_fast",
                "--start-n",
                "100",
                "--stop-n",
                "300",
                "--step-n",
                "100",
                "--seed",
                "17",
                "--num-colors",
                "3",
                "--max-attempts-per-node",
                "10000",
                "--output-dir",
                str(output_dir),
            ],
        )

    def test_materialize_circle_with_native_invokes_materialize_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            circle_path = Path(tmpdir) / "sample.circle"
            output_path = Path(tmpdir) / "sample.circle.col"
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"status":"ok","n":8,"m":7,"path":"sample.circle.col"}\n',
                stderr="",
            )

            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": "three_col_native"}), patch(
                "three_col_circle_code.instances.native.subprocess.run",
                return_value=completed,
            ) as run:
                summary = materialize_circle_with_native(circle_path=circle_path, output_path=output_path)

        self.assertEqual(summary.instance_id, "sample")
        self.assertEqual(summary.n, 8)
        self.assertEqual(summary.m, 7)
        self.assertEqual(
            run.call_args.args[0],
            [
                "three_col_native",
                "instance",
                "materialize-circle",
                str(circle_path),
                "--output",
                str(output_path),
            ],
        )


if __name__ == "__main__":
    unittest.main()
