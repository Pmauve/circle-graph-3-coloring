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
    _parse_reported_times,
    parse_zykovcolor_output,
    solve_zykovcolor,
)


ZYKOVCOLOR_TIMED_STDOUT = (
    "Result: Unsatisfiable for 3 colors at 12s 469ms and 441.309 mb memory.\n"
    "c Stats: Time \u250c Total: 2s 754ms\n"
    "c Stats: Time \u2502 \u250c Preprocessing: 2s 12ms\n"
    "c Stats: Time \u2502 \u250c Algorithm: 0s 742ms\n"
    "c Stats: Time \u2502 \u2502 - Building encoding: 0s 592ms\n"
    "c Stats: Time \u2502 \u2502 - Building at most k constraints: 0s 58ms\n"
    "c Stats: Time \u2502 \u2502 - CEGAR: 0s 0ms\n"
    "c Stats: Time \u2502 \u2502 \u250c Sat solving: 0s 91ms\n"
    "IncSatGC computed UNSAT for k = 3\n"
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

    def test_parse_preprocessing_chromatic_output_before_contradictory_single_k_footer(self) -> None:
        parsed = parse_zykovcolor_output(
            textwrap.dedent(
                """
                c Found lb 5 and ub 5 at 0s 186ms and 7.32 mb memory.
                Result: Chromatic number of 5 was determined in pre-processing.
                c Stats: Instance is UNSAT for K = 3
                IncSatGC computed SAT for k = 3
                """
            ),
            decision_num_colors=3,
        )

        self.assertEqual(parsed, (False, {"zykovcolor_mode": "chromatic_number", "chromatic_number": 5}))

    def test_parse_instance_k_stats_output(self) -> None:
        parsed = parse_zykovcolor_output("c Stats: Instance is UNSAT for K = 3\n")

        self.assertEqual(parsed, (False, {"zykovcolor_mode": "single_k", "k": 3, "raw_answer": "UNSAT"}))

    def test_parse_total_stats_time(self) -> None:
        self.assertEqual(_parse_core_time("c Stats: Time ┌ Total: 0s 10ms\n"), 0.01)

    def test_parse_result_time_preferred_over_total_stats_time(self) -> None:
        self.assertEqual(
            _parse_core_time("Result: Unsatisfiable for 3 colors at 9s 436ms\nc Stats: Time ┌ Total: 0s 136ms\n"),
            9.436,
        )

    def test_parse_reported_times_extracts_result_timestamp(self) -> None:
        self.assertEqual(_parse_reported_times(ZYKOVCOLOR_TIMED_STDOUT)["result_time_s"], 12.469)

    def test_parse_reported_times_extracts_stats_total(self) -> None:
        self.assertEqual(_parse_reported_times(ZYKOVCOLOR_TIMED_STDOUT)["stats_total_time_s"], 2.754)

    def test_parse_reported_times_extracts_preprocessing(self) -> None:
        self.assertEqual(_parse_reported_times(ZYKOVCOLOR_TIMED_STDOUT)["preprocessing_time_s"], 2.012)

    def test_parse_reported_times_extracts_algorithm(self) -> None:
        self.assertEqual(_parse_reported_times(ZYKOVCOLOR_TIMED_STDOUT)["algorithm_time_s"], 0.742)

    def test_parse_reported_times_extracts_sat_solving(self) -> None:
        self.assertEqual(_parse_reported_times(ZYKOVCOLOR_TIMED_STDOUT)["sat_solving_time_s"], 0.091)

    def test_parse_core_time_falls_back_to_stats_total_without_result_timestamp(self) -> None:
        stdout = "\n".join(line for line in ZYKOVCOLOR_TIMED_STDOUT.splitlines() if not line.startswith("Result:"))
        self.assertEqual(_parse_core_time(stdout), 2.754)

    def test_parse_core_time_prefers_zero_result_timestamp_over_stats_total(self) -> None:
        stdout = "Result: Satisfiable for 3 colors at 0s 0ms\nc Stats: Time \u250c Total: 2s 754ms\n"
        self.assertEqual(_parse_core_time(stdout), 0.0)

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

    def test_solve_zykovcolor_maps_reported_times_to_native_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(
                Path(tmpdir),
                stdout=(
                    "c Options : Encoding                = Assignment Encoding\n"
                    "c Options : Strategy                = Single K\n"
                    f"{ZYKOVCOLOR_TIMED_STDOUT}"
                ),
            )
            result = solve_zykovcolor(
                _sample_record(),
                params={"executable": str(executable), "mode": "single-k", "decision_num_colors": 3},
            )

        self.assertEqual(result.status, SOLVER_STATUS_OK, result.error)
        self.assertFalse(result.is_colorable)
        self.assertEqual(result.total_native_time_s, 12.469)
        self.assertEqual(result.core_time_s, 12.469)
        self.assertEqual(result.details["total_native_time_s"], 12.469)
        self.assertEqual(result.details["load_prepare_time_s"], 2.012)
        self.assertEqual(result.details["solve_time_s"], 0.742)
        self.assertEqual(result.details["zykovcolor_stats_total_time_s"], 2.754)
        self.assertEqual(result.details["zykovcolor_sat_solving_time_s"], 0.091)
        self.assertEqual(result.details["native_time_source"], "zykovcolor_reported")
        self.assertEqual(result.details["core_time_source"], "zykovcolor_reported")

    def test_solve_zykovcolor_prefers_zero_result_time_over_stats_total(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(
                Path(tmpdir),
                stdout=(
                    "c Options : Encoding                = Assignment Encoding\n"
                    "c Options : Strategy                = Single K\n"
                    "Result: Satisfiable for 3 colors at 0s 0ms\n"
                    "c Stats: Time \u250c Total: 2s 754ms\n"
                    "IncSatGC computed SAT for k = 3\n"
                ),
            )
            result = solve_zykovcolor(
                _sample_record(),
                params={"executable": str(executable), "mode": "single-k", "decision_num_colors": 3},
            )

        self.assertEqual(result.status, SOLVER_STATUS_OK, result.error)
        self.assertEqual(result.total_native_time_s, 0.0)
        self.assertEqual(result.core_time_s, 0.0)
        self.assertEqual(result.details["total_native_time_s"], 0.0)
        self.assertEqual(result.details["zykovcolor_stats_total_time_s"], 2.754)

    def test_solve_zykovcolor_error_keeps_parseable_reported_times_in_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(Path(tmpdir), stdout=ZYKOVCOLOR_TIMED_STDOUT, returncode=2)
            result = solve_zykovcolor(
                _sample_record(),
                params={"executable": str(executable), "mode": "single-k", "decision_num_colors": 3},
            )

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIsNone(result.total_native_time_s)
        self.assertIsNone(result.core_time_s)
        self.assertEqual(result.details["total_native_time_s"], 12.469)
        self.assertEqual(result.details["load_prepare_time_s"], 2.012)
        self.assertEqual(result.details["solve_time_s"], 0.742)

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

    def test_solve_zykovcolor_custom_single_k_uses_explicit_args(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(
                Path(tmpdir),
                stdout=(
                    "c Options : Encoding                = Zykov Encoding Propagator\n"
                    "c Options : Strategy                = Single K\n"
                    "IncSatGC computed UNSAT for k = 3\n"
                ),
            )
            result = solve_zykovcolor(
                _sample_record(),
                params={
                    "executable": str(executable),
                    "configuration": "custom",
                    "mode": "single-k",
                    "decision_num_colors": 3,
                    "solver": "cadical",
                    "extra_args": ["-e", "5"],
                },
            )

        command = result.details["command"]
        self.assertEqual(result.status, SOLVER_STATUS_OK, result.error)
        self.assertFalse(result.is_colorable)
        self.assertNotIn("--zykov-color", command)
        self.assertNotIn("--assignment", command)
        self.assertNotIn("--custom", command)
        self.assertEqual(command[-8:], ["--strategy", "2", "--num-colors", "3", "--solver", "1", "-e", "5"])

    def test_solve_zykovcolor_rejects_duplicate_solver_extra_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            executable = _write_fake_solver(Path(tmpdir), stdout="")
            result = solve_zykovcolor(
                _sample_record(),
                params={
                    "executable": str(executable),
                    "configuration": "custom",
                    "mode": "single-k",
                    "decision_num_colors": 3,
                    "solver": "cadical",
                    "extra_args": ["--solver", "1"],
                },
            )

        self.assertEqual(result.status, SOLVER_STATUS_ERROR)
        self.assertIn("params.solver", str(result.error))

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
            sys.stdout.buffer.write({stdout.encode("utf-8")!r})
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
