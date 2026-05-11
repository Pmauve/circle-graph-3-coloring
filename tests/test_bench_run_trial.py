import json
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.plan_io import (
    InstancePlanRow,
    TrialPlanRow,
    instance_result_path,
    trial_result_path,
    write_instance_plan,
    write_plan_manifest,
    write_trial_plan,
)
from three_col_circle_code.bench.run_trial import main, run_trial
from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.solvers.common import SOLVER_STATUS_OK, SolverResult


ZYKOVCOLOR_TIMED_STDOUT = (
    "c Options : Encoding                = Assignment Encoding\n"
    "c Options : Strategy                = Single K\n"
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


class BenchRunTrialTests(unittest.TestCase):
    def test_run_trial_writes_solver_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ) as run_solver, patch(
                "three_col_circle_code.bench.run_trial.collect_environment_metadata",
                return_value={"hostname": "worker-2"},
            ):
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result_path, trial_result_path(work_root, 1))
        self.assertEqual(result["index"], 1)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["solver_target"], "sosa-3-col-exact")
        self.assertEqual(result["solver_label"], "SOSA exact")
        self.assertEqual(result["solver_params"], {"base_case_n": 8})
        self.assertEqual(result["num_colors"], 3)
        self.assertTrue(result["is_colorable"])
        self.assertTrue(result["validation_ok"])
        self.assertEqual(result["repetitions"], 1)
        self.assertEqual(result["warmup_repetitions"], 0)
        self.assertEqual(result["ok_repetitions"], 1)
        self.assertEqual(result["mean_wall_time_s"], 0.25)
        self.assertEqual(result["median_wall_time_s"], 0.25)
        self.assertEqual(result["mean_load_prepare_time_s"], 0.04)
        self.assertEqual(result["median_load_prepare_time_s"], 0.04)
        self.assertEqual(result["mean_solve_time_s"], 0.21)
        self.assertEqual(result["median_solve_time_s"], 0.21)
        self.assertEqual(result["mean_peak_rss_kb"], 1024)
        self.assertEqual(result["median_peak_rss_kb"], 1024)
        self.assertEqual(result["max_peak_rss_kb"], 1024)
        self.assertNotIn("wall_time_s", result)
        self.assertEqual(len(result["measurements"]), 1)
        self.assertEqual(result["environment"], {"hostname": "worker-2"})
        run_solver.assert_called_once()

    def test_run_trial_records_warmups_and_repeated_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(
                tmp_root,
                repetitions=3,
                warmup_repetitions=1,
            )
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                side_effect=[
                    _fake_solver_result(wall_time_s=9.0),
                    _fake_solver_result(wall_time_s=0.3),
                    _fake_solver_result(wall_time_s=0.1),
                    _fake_solver_result(wall_time_s=0.2),
                ],
            ) as run_solver:
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["warmup_repetitions"], 1)
        self.assertEqual(result["repetitions"], 3)
        self.assertEqual(result["ok_repetitions"], 3)
        self.assertEqual(result["mean_wall_time_s"], 0.2)
        self.assertEqual(result["median_wall_time_s"], 0.2)
        self.assertEqual(result["max_peak_rss_kb"], 3072)
        self.assertEqual([row["wall_time_s"] for row in result["warmup_measurements"]], [9.0])
        self.assertEqual([row["wall_time_s"] for row in result["measurements"]], [0.3, 0.1, 0.2])
        self.assertEqual([row["load_prepare_time_s"] for row in result["measurements"]], [0.04, 0.04, 0.04])
        self.assertEqual([row["solve_time_s"] for row in result["measurements"]], [0.21, 0.21, 0.21])
        self.assertEqual([row["peak_rss_kb"] for row in result["measurements"]], [3072, 1024, 2048])
        self.assertEqual(run_solver.call_count, 4)

    def test_run_trial_uses_planned_instance_id_for_legacy_instance_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(
                tmp_root,
                instance_id="rc_fast-k03-n0200-seed42",
                family="rc_fast",
            )
            save_instance(
                _build_record(instance_id="rc_fast-n0200-seed42", family="rc_fast", seed=1),
                instance_path,
            )

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ):
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["instance_id"], "rc_fast-k03-n0200-seed42")
        self.assertEqual(result["family"], "rc_fast")

    def test_run_trial_marks_inconsistent_repeated_answers_as_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(tmp_root, repetitions=2)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                side_effect=[
                    _fake_solver_result(is_colorable=True),
                    _fake_solver_result(is_colorable=False),
                ],
            ):
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["is_colorable"])
        self.assertIn("inconsistent", result["error"])

    def test_run_trial_records_solver_exception_as_error_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                side_effect=MemoryError("graph too large"),
            ):
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["ok_repetitions"], 0)
        self.assertIn("MemoryError", result["error"])
        self.assertEqual(result["details"]["error_type"], "MemoryError")

    def test_run_trial_records_invalid_missing_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, _instance_path = _write_plan(tmp_root)

            result_path = run_trial(plan_dir=plan_dir, index=1)
            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["solver_target"], "sosa-3-col-exact")
        self.assertFalse(result["validation_ok"])
        self.assertEqual(result["details"]["load_error_type"], "FileNotFoundError")

    def test_run_trial_skips_existing_result_unless_forced(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)
            result_path = trial_result_path(work_root, 1)
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "index": 1,
                        "status": "ok",
                        "instance_id": "rc-n0002-seed1",
                        "instance_path": str(instance_path),
                        "num_colors": 3,
                        "solver_target": "sosa-3-col-exact",
                        "solver": "sosa-3-col-exact",
                        "backend": None,
                        "solver_label": "SOSA exact",
                        "solver_params": {"base_case_n": 8},
                        "repetitions": 1,
                        "warmup_repetitions": 0,
                    }
                ),
                encoding="utf-8",
            )

            with patch("three_col_circle_code.bench.run_trial.run_solver") as run_solver:
                returned = run_trial(plan_dir=plan_dir, index=1)

        self.assertEqual(returned, result_path)
        run_solver.assert_not_called()

    def test_run_trial_reruns_stale_existing_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)
            result_path = trial_result_path(work_root, 1)
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "index": 1,
                        "status": "ok",
                        "instance_id": "old-instance",
                        "instance_path": str(instance_path),
                        "solver_target": "sosa-3-col-exact",
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ) as run_solver:
                run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["instance_id"], "rc-n0002-seed1")
        run_solver.assert_called_once()

    def test_run_trial_force_reruns_existing_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)
            result_path = trial_result_path(work_root, 1)
            result_path.parent.mkdir(parents=True)
            result_path.write_text('{"status": "old"}', encoding="utf-8")

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ) as run_solver:
                run_trial(plan_dir=plan_dir, index=1, force=True)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "ok")
        run_solver.assert_called_once()

    def test_run_trial_rejects_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir, _work_root, _instance_path = _write_plan(Path(tmpdir))

            with self.assertRaisesRegex(ValueError, "does not contain index"):
                run_trial(plan_dir=plan_dir, index=2)

    def test_run_trial_records_missing_instance_generation_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)
            instance_result_path(work_root, 1).unlink()

            result_path = run_trial(plan_dir=plan_dir, index=1)
            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["run_id"], "smoke")
        self.assertIn("run benchmark_generate_instance", result["error"])
        self.assertEqual(result["details"]["load_error_type"], "ValueError")

    def test_run_trial_records_failed_instance_generation_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, _instance_path = _write_plan(tmp_root)
            instance_result_path(work_root, 1).write_text(
                json.dumps(
                    {
                        "index": 1,
                        "kind": "instance",
                        "status": "error",
                        "instance_id": "rc-n0002-seed1",
                        "instance_path": str(tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"),
                        "validation_ok": False,
                        "validation_errors": [],
                        "error": "generator failed",
                    }
                ),
                encoding="utf-8",
            )

            result_path = run_trial(plan_dir=plan_dir, index=1)
            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "invalid")
        self.assertIn("generator failed", result["error"])

    def test_run_trial_uses_cached_validation_without_revalidating(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)

            with patch("three_col_circle_code.bench.run_trial.validate_instance", create=True) as validate_instance, patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ):
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertTrue(result["validation_ok"])
        self.assertEqual(result["validation_errors"], [])
        validate_instance.assert_not_called()

    def test_run_trial_does_not_load_graph_for_zykovcolor_path_solver(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(
                tmp_root,
                instance_id="rc-k03-n5000-seed1",
                solver="zykovcolor",
                solver_target="zykovcolor",
                solver_label="ZykovColor",
            )
            instance_path.parent.mkdir(parents=True, exist_ok=True)
            instance_path.write_text(
                "\n".join(
                    [
                        "c instance id rc-k03-n5000-seed1",
                        "c family rc",
                        "c seed 1",
                        "c n 5000",
                        "c m 10",
                        "c num colors 3",
                        "c source generated",
                        "p edge 5000 10",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            with patch("three_col_circle_code.bench.run_trial.load_instance") as load_instance, patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ) as run_solver:
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        load_instance.assert_not_called()
        run_solver.assert_called_once()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["solver_target"], "zykovcolor")
        self.assertEqual(result["n"], 5000)
        self.assertEqual(result["m"], 10)
        self.assertEqual(result["average_degree"], 0.004)

    def test_run_trial_aggregates_zykovcolor_native_timings(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            executable = _write_fake_zykovcolor_solver(tmp_root, stdout=ZYKOVCOLOR_TIMED_STDOUT)
            plan_dir, _work_root, instance_path = _write_plan(
                tmp_root,
                instance_id="rc-k03-n0002-seed1",
                solver="zykovcolor",
                solver_target="zykovcolor",
                solver_label="ZykovColor",
                solver_params={
                    "executable": str(executable),
                    "mode": "single-k",
                    "decision_num_colors": 3,
                },
                instance_suffix=".col",
            )
            save_instance(_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1), instance_path)

            with patch(
                "three_col_circle_code.bench.run_trial.collect_environment_metadata",
                return_value={"hostname": "worker-2"},
            ):
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "ok", result["error"])
        measurement = result["measurements"][0]
        self.assertEqual(measurement["total_native_time_s"], 12.469)
        self.assertEqual(measurement["load_prepare_time_s"], 2.012)
        self.assertEqual(measurement["solve_time_s"], 0.742)
        self.assertEqual(result["mean_total_native_time_s"], 12.469)
        self.assertEqual(result["median_total_native_time_s"], 12.469)
        self.assertEqual(result["mean_load_prepare_time_s"], 2.012)
        self.assertEqual(result["median_load_prepare_time_s"], 2.012)
        self.assertEqual(result["mean_solve_time_s"], 0.742)
        self.assertEqual(result["median_solve_time_s"], 0.742)
        self.assertEqual(result["details"]["native_time_source"], "zykovcolor_reported")
        self.assertEqual(result["details"]["zykovcolor_stats_total_time_s"], 2.754)
        self.assertEqual(result["details"]["zykovcolor_sat_solving_time_s"], 0.091)

    def test_run_trial_does_not_load_graph_for_native_sat_path_solver(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(
                tmp_root,
                instance_id="rc-k03-n5000-seed1",
                solver="sat-3-col-native",
                solver_target="sat-3-col-native",
                solver_label="Native SAT",
            )
            instance_path.parent.mkdir(parents=True, exist_ok=True)
            instance_path.write_text(
                "\n".join(
                    [
                        "c instance id rc-k03-n5000-seed1",
                        "c family rc",
                        "c seed 1",
                        "c n 5000",
                        "c m 10",
                        "c num colors 3",
                        "c source generated",
                        "p edge 5000 10",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            with patch("three_col_circle_code.bench.run_trial.load_instance") as load_instance, patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ) as run_solver:
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        load_instance.assert_not_called()
        run_solver.assert_called_once()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["solver_target"], "sat-3-col-native")
        self.assertEqual(result["n"], 5000)
        self.assertEqual(result["m"], 10)

    def test_cli_prints_result_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ):
                exit_code = main(["--plan-dir", str(plan_dir), "--index", "1"])

        self.assertEqual(exit_code, 0)


def _write_plan(
    tmp_root: Path,
    *,
    repetitions: int = 1,
    warmup_repetitions: int = 0,
    instance_id: str = "rc-n0002-seed1",
    family: str = "rc",
    solver: str = "sosa-3-col-exact",
    solver_target: str = "sosa-3-col-exact",
    solver_label: str = "SOSA exact",
    solver_params: dict[str, object] | None = None,
    instance_suffix: str = ".json",
) -> tuple[Path, Path, Path]:
    plan_dir = tmp_root / "plans" / "smoke"
    work_root = tmp_root / "work" / "smoke"
    instance_path = tmp_root / "instances" / family / "s" / f"{instance_id}{instance_suffix}"
    instances = (
        InstancePlanRow(
            index=1,
            instance_id=instance_id,
            family=family,
            n=2,
            seed=1,
            instance_path=instance_path,
        ),
    )
    trials = (
        TrialPlanRow(
            index=1,
            instance_id=instance_id,
            instance_path=instance_path,
            family=family,
            n=2,
            seed=1,
            solver=solver,
            backend=None,
            solver_target=solver_target,
            solver_params={"base_case_n": 8} if solver_params is None else solver_params,
            solver_label=solver_label,
            repetitions=repetitions,
            warmup_repetitions=warmup_repetitions,
        ),
    )
    write_instance_plan(plan_dir, instances)
    write_trial_plan(plan_dir, trials, instances=instances)
    write_plan_manifest(
        plan_dir,
        {
            "run_id": "smoke",
            "created_at": "2026-04-29T00:00:00+00:00",
            "work_root": work_root,
            "n_instances": 1,
            "n_trials": 1,
            "repetitions": repetitions,
            "warmup_repetitions": warmup_repetitions,
        },
    )
    _write_instance_result(work_root, instance_path)
    return plan_dir, work_root, instance_path


def _write_fake_zykovcolor_solver(tmpdir: Path, *, stdout: str) -> Path:
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


def _write_instance_result(work_root: Path, instance_path: Path) -> None:
    result_path = instance_result_path(work_root, 1)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "index": 1,
                "kind": "instance",
                "status": "ok",
                "instance_id": instance_path.stem,
                "instance_path": str(instance_path),
                "generated": False,
                "validation_ok": True,
                "validation_errors": [],
                "started_at": "2026-04-29T00:00:00+00:00",
                "finished_at": "2026-04-29T00:00:00+00:00",
                "error": None,
            }
        ),
        encoding="utf-8",
    )


def _build_record(
    *,
    instance_id: str,
    family: str,
    seed: int,
    n: int = 2,
    num_colors: int = 3,
) -> InstanceRecord:
    graph = nx.Graph()
    for node in range(n):
        graph.add_node(node, label=node, l=node, r=node + n)
    for node in range(n - 1):
        graph.add_edge(node, node + 1)
    return InstanceRecord(
        metadata=InstanceMetadata(
            instance_id=instance_id,
            family=family,
            seed=seed,
            generator="test_fixture",
            n=graph.number_of_nodes(),
            m=graph.number_of_edges(),
            num_colors=num_colors,
            bucket="s",
            source="generated",
            created_at="2026-04-29T00:00:00+00:00",
        ),
        graph=graph,
    )


def _fake_solver_result(
    *,
    wall_time_s: float = 0.25,
    is_colorable: bool = True,
) -> SolverResult:
    return SolverResult(
        solver="sosa-3-col-exact",
        backend=None,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        is_colorable=is_colorable,
        n_vertices=2,
        m_edges=1,
        details={
            "stats": {},
            "load_prepare_time_s": 0.04,
            "solve_time_s": 0.21,
            "total_native_time_s": 0.25,
        },
        total_native_time_s=0.25,
        error=None,
        peak_rss_kb=int(round(wall_time_s * 10240)) if wall_time_s != 0.25 else 1024,
    )


if __name__ == "__main__":
    unittest.main()
