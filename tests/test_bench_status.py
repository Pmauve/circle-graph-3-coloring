import json
import sys
import tempfile
import unittest
from pathlib import Path

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
from three_col_circle_code.bench.status import build_benchmark_status, main


class BenchStatusTests(unittest.TestCase):
    def test_build_benchmark_status_reports_missing_and_failed_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root)
            _write_result(instance_result_path(work_root, 1), "ok")
            _write_result(instance_result_path(work_root, 2), "error")
            _write_result(trial_result_path(work_root, 1), "ok")

            status = build_benchmark_status(plan_dir=plan_dir)

        self.assertEqual(status["run_id"], "smoke")
        self.assertTrue(status["ready_for_trials"])
        self.assertFalse(status["ready_for_merge"])
        self.assertFalse(status["all_instances_ok"])
        self.assertFalse(status["all_trials_ok"])
        self.assertFalse(status["all_ok"])
        self.assertEqual(status["instances"]["counts"], {"error": 1, "ok": 1})
        self.assertEqual(status["instances"]["failed_indices"], [2])
        self.assertEqual(status["trials"]["counts"], {"missing": 1, "ok": 1})
        self.assertEqual(status["trials"]["missing_indices"], [2])
        self.assertEqual(status["trials"]["failed_indices"], [])

    def test_build_benchmark_status_marks_ready_when_all_tasks_succeeded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root)
            _write_result(instance_result_path(work_root, 1), "skipped")
            _write_result(instance_result_path(work_root, 2), "ok")
            _write_result(trial_result_path(work_root, 1), "ok")
            _write_result(trial_result_path(work_root, 2), "ok")

            status = build_benchmark_status(plan_dir=plan_dir)

        self.assertTrue(status["ready_for_trials"])
        self.assertTrue(status["ready_for_merge"])
        self.assertTrue(status["all_instances_ok"])
        self.assertTrue(status["all_trials_ok"])
        self.assertTrue(status["all_ok"])
        self.assertEqual(status["instances"]["n_success"], 2)
        self.assertEqual(status["trials"]["n_success"], 2)

    def test_cli_fail_on_incomplete_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir, _work_root = _write_plan(Path(tmpdir))

            exit_code = main(["--plan-dir", str(plan_dir), "--fail-on-incomplete"])

        self.assertEqual(exit_code, 1)

    def test_cli_require_ready_for_trials_allows_complete_instance_stage_with_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root)
            _write_result(instance_result_path(work_root, 1), "ok")
            _write_result(instance_result_path(work_root, 2), "error")

            exit_code = main(["--plan-dir", str(plan_dir), "--require-ready-for-trials"])

        self.assertEqual(exit_code, 0)

    def test_cli_require_ready_for_trials_rejects_missing_instance_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root)
            _write_result(instance_result_path(work_root, 1), "ok")

            exit_code = main(["--plan-dir", str(plan_dir), "--require-ready-for-trials"])

        self.assertEqual(exit_code, 1)

    def test_cli_require_ready_for_merge_checks_trial_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root)
            _write_result(instance_result_path(work_root, 1), "ok")
            _write_result(instance_result_path(work_root, 2), "ok")
            _write_result(trial_result_path(work_root, 1), "ok")

            exit_code = main(["--plan-dir", str(plan_dir), "--require-ready-for-merge"])

        self.assertEqual(exit_code, 1)

    def test_cli_require_ready_for_merge_allows_complete_trial_stage_with_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root)
            _write_result(instance_result_path(work_root, 1), "ok")
            _write_result(instance_result_path(work_root, 2), "ok")
            _write_result(trial_result_path(work_root, 1), "ok")
            _write_result(trial_result_path(work_root, 2), "error")

            exit_code = main(["--plan-dir", str(plan_dir), "--require-ready-for-merge"])

        self.assertEqual(exit_code, 0)


def _write_plan(tmp_root: Path) -> tuple[Path, Path]:
    plan_dir = tmp_root / "plans" / "smoke"
    work_root = tmp_root / "work" / "smoke"
    instance_path_1 = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
    instance_path_2 = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed2.json"
    instances = (
        InstancePlanRow(1, "rc-n0002-seed1", "rc", 2, 1, instance_path_1),
        InstancePlanRow(2, "rc-n0002-seed2", "rc", 2, 2, instance_path_2),
    )
    trials = (
        TrialPlanRow(
            index=1,
            instance_id="rc-n0002-seed1",
            instance_path=instance_path_1,
            family="rc",
            n=2,
            seed=1,
            solver="sosa-3-col-exact",
            backend=None,
            solver_target="sosa-3-col-exact",
        ),
        TrialPlanRow(
            index=2,
            instance_id="rc-n0002-seed2",
            instance_path=instance_path_2,
            family="rc",
            n=2,
            seed=2,
            solver="sosa-3-col-exact",
            backend=None,
            solver_target="sosa-3-col-exact",
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
            "n_instances": 2,
            "n_trials": 2,
        },
    )
    return plan_dir, work_root


def _write_result(path: Path, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"status": status}), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
