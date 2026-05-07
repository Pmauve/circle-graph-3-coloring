import os
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.common import SOLVER_STATUS_ERROR, SOLVER_STATUS_OK
from three_col_circle_code.solvers.sat_native import (
    SAT_3_COL_NATIVE_SOLVER,
    solve_sat_3_col_native_from_path,
)


class NativeSatSolverTests(unittest.TestCase):
    def test_missing_binary_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_col(Path(tmpdir) / "triangle.col")
            missing_binary = str(Path(tmpdir) / "missing-three-col-native")
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": missing_binary}):
                result = solve_sat_3_col_native_from_path(
                    path,
                    params={"solver_bin": "kissat"},
                )

        self.assertEqual(result.solver, SAT_3_COL_NATIVE_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("THREE_COL_NATIVE_BIN", result.error or "")
        self.assertEqual(result.n_vertices, 3)
        self.assertEqual(result.m_edges, 3)

    def test_missing_solver_bin_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "three_col_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": str(binary)}):
                result = solve_sat_3_col_native_from_path(path)

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("solver_bin", result.error or "")

    def test_runs_binary_and_parses_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "three_col_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=0,
                stdout=(
                    '{"status":"ok","solver_status":"COLORABLE",'
                    '"core_time_s":0.030}\n'
                ),
                stderr="",
            )
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sat_native.subprocess.run",
                return_value=completed,
            ) as run:
                result = solve_sat_3_col_native_from_path(
                    path,
                    params={
                        "backend": "dimacs-pipe",
                        "solver_bin": "kissat",
                        "timeout_s": 12,
                    },
                )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_colorable)
        self.assertEqual(result.core_time_s, 0.03)
        self.assertNotIn("parse_encode_time_s", result.details)
        self.assertNotIn("solve_time_s", result.details)
        command = run.call_args.args[0]
        self.assertEqual(command[:4], [str(binary), "sat", "solve", str(path)])
        self.assertIn("--solver-bin", command)
        self.assertIn("kissat", command)
        self.assertEqual(run.call_args.kwargs["timeout"], 42.0)

    def test_native_embedded_backends_do_not_require_solver_bin(self) -> None:
        for backend in ("cadical-direct", "cadical-rustsat", "kissat-rustsat"):
            with self.subTest(backend=backend):
                self._assert_embedded_backend_does_not_require_solver_bin(backend)

    def _assert_embedded_backend_does_not_require_solver_bin(self, backend: str) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "three_col_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=0,
                stdout=(
                    '{"status":"ok","solver_status":"COLORABLE",'
                    '"core_time_s":0.020}\n'
                ),
                stderr="",
            )
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sat_native.subprocess.run",
                return_value=completed,
            ) as run:
                result = solve_sat_3_col_native_from_path(
                    path,
                    params={"backend": backend, "timeout_s": 12},
                )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_colorable)
        self.assertEqual(result.core_time_s, 0.02)
        command = run.call_args.args[0]
        self.assertIn(backend, command)
        self.assertNotIn("--solver-bin", command)
        self.assertNotIn("solver_bin", result.details)

    def test_parses_not_colorable_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "three_col_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=0,
                stdout="s NOT_COLORABLE\nt core_time_s 0.456\n",
                stderr="",
            )
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sat_native.subprocess.run",
                return_value=completed,
            ):
                result = solve_sat_3_col_native_from_path(
                    path,
                    params={"solver_bin": "kissat"},
                )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertFalse(result.is_colorable)
        self.assertEqual(result.core_time_s, 0.456)

    def test_accepts_unknown_status_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "three_col_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=3,
                stdout="s UNKNOWN\nt core_time_s 1.25\n",
                stderr="",
            )
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sat_native.subprocess.run",
                return_value=completed,
            ):
                result = solve_sat_3_col_native_from_path(
                    path,
                    params={"solver_bin": "kissat"},
                )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertIsNone(result.is_colorable)
        self.assertEqual(result.core_time_s, 1.25)

    def test_nonzero_exit_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "three_col_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=2,
                stdout="s ERROR\ne bad input\n",
                stderr="",
            )
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sat_native.subprocess.run",
                return_value=completed,
            ):
                result = solve_sat_3_col_native_from_path(
                    path,
                    params={"solver_bin": "kissat"},
                )

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("code 2", result.error or "")

    def test_timeout_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "three_col_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            with patch.dict(os.environ, {"THREE_COL_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sat_native.subprocess.run",
                side_effect=TimeoutExpired(cmd=["three_col_native"], timeout=0.01),
            ):
                result = solve_sat_3_col_native_from_path(
                    path,
                    params={"solver_bin": "kissat", "timeout_s": 0.01},
                )

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("timed out", result.error or "")


def _write_col(path: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "c ircle representation START",
                "c 1 2 3 1 2 3",
                "c ircle representation END",
                "p edge 3 3",
                "e 1 2",
                "e 1 3",
                "e 2 3",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
