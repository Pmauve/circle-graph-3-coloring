import sys
import tempfile
import textwrap
import unittest
import os
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.solvers.common import SOLVER_STATUS_ERROR, SOLVER_STATUS_OK
from three_col_circle_code.solvers.registry import available_solver_names, run_solver
from three_col_circle_code.solvers.common import SolverConfig
from three_col_circle_code.solvers.zykovcolor import (
    ZYKOVCOLOR_SOLVER,
    _parse_core_time,
    parse_zykovcolor_output,
    solve_zykovcolor,
)


class ZykovColorSolverTests(unittest.TestCase):
    def test_parse_chromatic_number_output(self) -> None:
        parsed = parse_zykovcolor_output(
            "c log\nIncSatGC computed chromatic number of 3\n",
            decision_num_colors=3,
        )

        self.assertEqual(parsed, (True, {"zykovcolor_mode": "chromatic_number", "chromatic_number": 3}))

    def test_parse_chromatic_number_above_decision_palette(self) -> None:
        parsed = parse_zykovcolor_output(
            "IncSatGC computed chromatic number of 4\n",
            decision_num_colors=3,
        )

        self.assertEqual(parsed, (False, {"zykovcolor_mode": "chromatic_number", "chromatic_number": 4}))

    def test_parse_single_k_output(self) -> None:
        parsed = parse_zykovcolor_output("IncSatGC computed SAT for k = 3\n")

        self.assertEqual(parsed, (True, {"zykovcolor_mode": "single_k", "k": 3, "raw_answer": "SAT"}))

    def test_parse_total_stats_time(self) -> None:
        self.assertEqual(_parse_core_time("c Stats: Time ┌ Total: 0s 10ms\n"), 0.01)

    def test_parse_result_time_preferred_over_total_stats_time(self) -> None:
        self.assertEqual(
            _parse_core_time("Result: Unsatisfiable for 3 colors at 9s 436ms\nc Stats: Time ┌ Total: 0s 136ms\n"),
            9.436,
        )

    def test_solve_zykovcolor_runs_external_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(
                Path(tmpdir),
                stdout=(
                    "c Options : Encoding                = Assignment Encoding\n"
                    "c Options : Strategy                = Single K\n"
                    "IncSatGC computed SAT for k = 3\n"
                ),
            )
            result = solve_zykovcolor(
                _sample_record(),
                params={"executable": str(executable), "mode": "single-k", "decision_num_colors": 3},
            )

        self.assertEqual(result.status, SOLVER_STATUS_OK, result.error)
        self.assertTrue(result.is_colorable)
        self.assertEqual(result.details["zykovcolor_mode"], "single_k")
        self.assertEqual(result.details["effective_strategy"], "Single K")
        self.assertEqual(result.details["effective_encoding"], "Assignment Encoding")
        self.assertEqual(result.details["returncode"], 0)
        self.assertIn("--encoding", result.details["command"])
        self.assertIn("--strategy", result.details["command"])
        self.assertIn("2", result.details["command"])
        self.assertIn("--num-colors", result.details["command"])
        self.assertNotIn("--zykov-color", result.details["command"])

    def test_solve_zykovcolor_rejects_overridden_single_k_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(
                Path(tmpdir),
                stdout=(
                    "c Options : Encoding                = Zykov Encoding Propagator\n"
                    "c Options : Strategy                = Bottom-Up\n"
                    "IncSatGC computed chromatic number of 4\n"
                ),
            )
            result = solve_zykovcolor(
                _sample_record(),
                params={"executable": str(executable), "mode": "single-k", "decision_num_colors": 3},
            )

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("effective strategy", str(result.error))

    def test_solve_zykovcolor_reports_parse_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(Path(tmpdir), stdout="no result here\\n")
            result = solve_zykovcolor(
                _sample_record(),
                params={"executable": str(executable)},
            )

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("could not parse", str(result.error))

    def test_registry_exposes_zykovcolor(self) -> None:
        self.assertIn(ZYKOVCOLOR_SOLVER, available_solver_names())

    def test_registry_dispatches_zykovcolor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(
                Path(tmpdir),
                stdout="IncSatGC computed chromatic number of 3\\n",
            )
            result = run_solver(
                _sample_record(),
                SolverConfig(
                    solver=ZYKOVCOLOR_SOLVER,
                    params={"executable": str(executable)},
                ),
            )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertTrue(result.is_colorable)


def _write_fake_solver(tmpdir: Path, *, stdout: str, returncode: int = 0) -> Path:
    script = tmpdir / "fake_zykovcolor_impl.py"
    script.write_text(
        textwrap.dedent(
            f"""
            import sys
            from pathlib import Path

            dimacs_path = Path(sys.argv[1])
            if "p edge" not in dimacs_path.read_text(encoding="utf-8"):
                raise SystemExit(3)
            sys.stdout.write({stdout!r})
            raise SystemExit({returncode})
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    if os.name == "nt":
        command = tmpdir / "fake_zykovcolor.cmd"
        command.write_text(f'@echo off\n"{sys.executable}" "{script}" %*\n', encoding="utf-8")
        return command

    command = tmpdir / "fake_zykovcolor"
    command.write_text(f'#! /bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
    command.chmod(0o755)
    return command


def _sample_record() -> InstanceRecord:
    graph = nx.Graph()
    graph.add_node(0, label=0, l=0, r=2)
    graph.add_node(1, label=1, l=1, r=3)
    graph.add_edge(0, 1)
    metadata = InstanceMetadata(
        instance_id="sample",
        family="rcy",
        seed=1,
        generator="unit",
        n=2,
        m=1,
        bucket="s",
        source="generated",
        created_at="2026-05-04T00:00:00Z",
    )
    return InstanceRecord(metadata=metadata, graph=graph)


if __name__ == "__main__":
    unittest.main()
