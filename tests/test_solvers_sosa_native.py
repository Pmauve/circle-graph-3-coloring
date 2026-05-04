import os
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess, TimeoutExpired
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.solvers.common import SOLVER_STATUS_ERROR, SOLVER_STATUS_OK
from three_col_circle_code.solvers.sosa.native import (
    SOSA_3_COL_NATIVE_SOLVER,
    solve_sosa_3_col_native_from_path,
)


class NativeSosaSolverTests(unittest.TestCase):
    def test_missing_binary_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_col(Path(tmpdir) / "triangle.col")
            missing_binary = str(Path(tmpdir) / "missing-sosa-native")
            with patch.dict(os.environ, {"SOSA_NATIVE_BIN": missing_binary}):
                result = solve_sosa_3_col_native_from_path(path)

        self.assertEqual(result.solver, SOSA_3_COL_NATIVE_SOLVER)
        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("SOSA_NATIVE_BIN", result.error or "")
        self.assertEqual(result.n_vertices, 3)
        self.assertEqual(result.m_edges, 3)

    def test_runs_binary_with_skip_graph_validation_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "sosa_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=0,
                stdout="s COLORABLE\nt core_time_s 0.123\n",
                stderr="",
            )
            with patch.dict(os.environ, {"SOSA_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sosa.native.subprocess.run",
                return_value=completed,
            ) as run:
                result = solve_sosa_3_col_native_from_path(
                    path,
                    params={"base_case_n": 8, "timeout_s": 12},
                )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_colorable)
        self.assertEqual(result.core_time_s, 0.123)
        command = run.call_args.args[0]
        self.assertEqual(command[:2], [str(binary), "solve"])
        self.assertIn("--base-case-n", command)
        self.assertIn("8", command)
        self.assertIn("--skip-graph-validation", command)
        self.assertEqual(run.call_args.kwargs["timeout"], 12.0)

    def test_validate_instance_artifact_omits_skip_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "sosa_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=0,
                stdout="s NOT_COLORABLE\nt core_time_s 0.456\n",
                stderr="",
            )
            with patch.dict(os.environ, {"SOSA_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sosa.native.subprocess.run",
                return_value=completed,
            ) as run:
                result = solve_sosa_3_col_native_from_path(
                    path,
                    validate_instance_artifact=True,
                )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertFalse(result.is_colorable)
        self.assertEqual(result.core_time_s, 0.456)
        self.assertNotIn("--skip-graph-validation", run.call_args.args[0])

    def test_nonzero_exit_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "sosa_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(
                args=[],
                returncode=2,
                stdout="s ERROR\ne bad input\n",
                stderr="",
            )
            with patch.dict(os.environ, {"SOSA_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sosa.native.subprocess.run",
                return_value=completed,
            ):
                result = solve_sosa_3_col_native_from_path(path)

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("code 2", result.error or "")

    def test_timeout_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "sosa_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            with patch.dict(os.environ, {"SOSA_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sosa.native.subprocess.run",
                side_effect=TimeoutExpired(cmd=["sosa_native"], timeout=0.01),
            ):
                result = solve_sosa_3_col_native_from_path(path, params={"timeout_s": 0.01})

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("timed out", result.error or "")

    def test_json_input_is_exported_to_temp_col_for_native_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "sosa_native"
            binary.write_text("", encoding="utf-8")
            path = _write_json_instance(Path(tmpdir) / "triangle.json")
            completed = CompletedProcess(
                args=[],
                returncode=0,
                stdout="s COLORABLE\nt core_time_s 0.123\n",
                stderr="",
            )
            with patch.dict(os.environ, {"SOSA_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sosa.native.subprocess.run",
                return_value=completed,
            ) as run:
                result = solve_sosa_3_col_native_from_path(path)

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        native_path = Path(run.call_args.args[0][2])
        self.assertEqual(native_path.suffix, ".col")
        self.assertEqual(result.n_vertices, 3)
        self.assertEqual(result.m_edges, 3)

    def test_missing_core_time_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            binary = Path(tmpdir) / "sosa_native"
            binary.write_text("", encoding="utf-8")
            path = _write_col(Path(tmpdir) / "triangle.col")
            completed = CompletedProcess(args=[], returncode=0, stdout="s COLORABLE\n", stderr="")
            with patch.dict(os.environ, {"SOSA_NATIVE_BIN": str(binary)}), patch(
                "three_col_circle_code.solvers.sosa.native.subprocess.run",
                return_value=completed,
            ):
                result = solve_sosa_3_col_native_from_path(path)

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertIsNone(result.core_time_s)
        self.assertEqual(result.details["core_time_source"], "missing")


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


def _write_json_instance(path: Path) -> Path:
    graph = nx.Graph()
    graph.add_node(0, label=0, l=0, r=3)
    graph.add_node(1, label=1, l=1, r=4)
    graph.add_node(2, label=2, l=2, r=5)
    graph.add_edges_from([(0, 1), (0, 2), (1, 2)])
    record = InstanceRecord(
        metadata=InstanceMetadata(
            instance_id="triangle",
            family="manual",
            seed=None,
            generator="test",
            n=3,
            m=3,
            bucket="s",
            source="test",
            created_at="2026-05-04T00:00:00+00:00",
        ),
        graph=graph,
    )
    save_instance(record, path)
    return path


if __name__ == "__main__":
    unittest.main()
