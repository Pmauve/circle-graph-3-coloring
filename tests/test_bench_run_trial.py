import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.plan_io import (
    InstancePlanRow,
    TrialPlanRow,
    trial_result_path,
    write_instance_plan,
    write_plan_manifest,
    write_trial_plan,
)
from three_col_circle_code.bench.run_trial import main, run_trial
from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.solvers.common import SOLVER_STATUS_OK, SolverResult


class BenchRunTrialTests(unittest.TestCase):
    def test_run_trial_writes_solver_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instance_path = _write_plan(tmp_root)
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)

            with patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(),
            ) as run_solver:
                result_path = run_trial(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result_path, trial_result_path(work_root, 1))
        self.assertEqual(result["index"], 1)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["solver_target"], "sosa-3-col-exact")
        self.assertEqual(result["solver_label"], "SOSA exact")
        self.assertEqual(result["solver_params"], {"base_case_n": 8})
        self.assertTrue(result["is_colorable"])
        self.assertTrue(result["validation_ok"])
        self.assertEqual(result["repetitions"], 1)
        self.assertEqual(result["warmup_repetitions"], 0)
        self.assertEqual(result["ok_repetitions"], 1)
        self.assertEqual(result["mean_wall_time_s"], 0.25)
        self.assertEqual(result["median_wall_time_s"], 0.25)
        self.assertNotIn("wall_time_s", result)
        self.assertEqual(len(result["measurements"]), 1)
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
        self.assertEqual([row["wall_time_s"] for row in result["warmup_measurements"]], [9.0])
        self.assertEqual([row["wall_time_s"] for row in result["measurements"]], [0.3, 0.1, 0.2])
        self.assertEqual(run_solver.call_count, 4)

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
            result_path.write_text('{"status": "ok"}', encoding="utf-8")

            with patch("three_col_circle_code.bench.run_trial.run_solver") as run_solver:
                returned = run_trial(plan_dir=plan_dir, index=1)

        self.assertEqual(returned, result_path)
        run_solver.assert_not_called()

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
) -> tuple[Path, Path, Path]:
    plan_dir = tmp_root / "plans" / "smoke"
    work_root = tmp_root / "work" / "smoke"
    instance_path = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
    instances = (
        InstancePlanRow(
            index=1,
            instance_id="rc-n0002-seed1",
            family="rc",
            n=2,
            seed=1,
            instance_path=instance_path,
        ),
    )
    trials = (
        TrialPlanRow(
            index=1,
            instance_id="rc-n0002-seed1",
            instance_path=instance_path,
            family="rc",
            n=2,
            seed=1,
            solver="sosa-3-col-exact",
            backend=None,
            solver_target="sosa-3-col-exact",
            solver_params={"base_case_n": 8},
            solver_label="SOSA exact",
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
    return plan_dir, work_root, instance_path


def _build_record(*, instance_id: str, family: str, seed: int, n: int = 2) -> InstanceRecord:
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
            bucket="s",
            source="generated",
            created_at="2026-04-29T00:00:00+00:00",
        ),
        graph=graph,
    )


def _fake_solver_result(*, wall_time_s: float = 0.25) -> SolverResult:
    return SolverResult(
        solver="sosa-3-col-exact",
        backend=None,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        is_colorable=True,
        n_vertices=2,
        m_edges=1,
        details={"stats": {}},
        error=None,
    )


if __name__ == "__main__":
    unittest.main()
