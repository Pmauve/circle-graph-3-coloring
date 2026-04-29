import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.merge import main, merge_benchmark_results
from three_col_circle_code.bench.plan_io import (
    PLAN_SPEC_FILENAME,
    InstancePlanRow,
    TrialPlanRow,
    trial_result_path,
    write_instance_plan,
    write_plan_manifest,
    write_trial_plan,
)
from three_col_circle_code.bench.report_data import (
    SUMMARY_BY_BUCKET_FILENAME,
    SUMMARY_BY_N_FILENAME,
    SUMMARY_OVERALL_FILENAME,
)
from three_col_circle_code.bench.results import MANIFEST_FILENAME, RESULTS_FILENAME


class BenchMergeTests(unittest.TestCase):
    def test_merge_benchmark_results_writes_standard_run_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root, n_trials=2)
            _write_trial_result(work_root, 2, solver_params={"base_case_n": 16}, solver_label="SOSA 16")
            _write_trial_result(work_root, 1, solver_params={"base_case_n": 8}, solver_label="SOSA 8")

            run_dir = merge_benchmark_results(
                plan_dir=plan_dir,
                output_root=tmp_root / "runs",
            )
            manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            rows = [
                json.loads(line)
                for line in (run_dir / RESULTS_FILENAME).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            has_summary_by_n = (run_dir / SUMMARY_BY_N_FILENAME).exists()
            has_summary_by_bucket = (run_dir / SUMMARY_BY_BUCKET_FILENAME).exists()
            has_summary_overall = (run_dir / SUMMARY_OVERALL_FILENAME).exists()
            has_report = (run_dir / "report.html").exists()

        self.assertEqual(run_dir.name, "smoke")
        self.assertEqual([row["index"] for row in rows], [1, 2])
        self.assertEqual(manifest["execution_mode"], "merged_trial_outputs")
        self.assertEqual(manifest["n_expected_trials"], 2)
        self.assertEqual(manifest["n_merged_trials"], 2)
        self.assertEqual(manifest["missing_trial_indices"], [])
        self.assertTrue(has_summary_by_n)
        self.assertTrue(has_summary_by_bucket)
        self.assertTrue(has_summary_overall)
        self.assertTrue(has_report)

    def test_merge_benchmark_results_fails_on_missing_trials_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root = _write_plan(tmp_root, n_trials=2)

            with self.assertRaisesRegex(ValueError, "missing trial"):
                merge_benchmark_results(plan_dir=plan_dir, output_root=tmp_root / "runs")

    def test_merge_benchmark_results_allows_missing_trials_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root, n_trials=2)
            _write_trial_result(work_root, 1, solver_params={"base_case_n": 8}, solver_label="SOSA 8")

            run_dir = merge_benchmark_results(
                plan_dir=plan_dir,
                output_root=tmp_root / "runs",
                allow_missing=True,
            )
            manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            rows = (run_dir / RESULTS_FILENAME).read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(len(rows), 1)
        self.assertEqual(manifest["missing_trial_indices"], [2])
        self.assertEqual(manifest["n_merged_trials"], 1)

    def test_merge_benchmark_results_rejects_mismatched_trial_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root, n_trials=1)
            _write_trial_result(work_root, 1, solver_params={"base_case_n": 8}, solver_label="SOSA 8")
            result_path = trial_result_path(work_root, 1)
            row = json.loads(result_path.read_text(encoding="utf-8"))
            row["solver_target"] = "other"
            result_path.write_text(json.dumps(row), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "does not match plan"):
                merge_benchmark_results(plan_dir=plan_dir, output_root=tmp_root / "runs")

    def test_merge_benchmark_results_rejects_existing_results_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root, n_trials=1)
            _write_trial_result(work_root, 1, solver_params={"base_case_n": 8}, solver_label="SOSA 8")
            run_dir = merge_benchmark_results(plan_dir=plan_dir, output_root=tmp_root / "runs")

            with self.assertRaisesRegex(ValueError, "use --force"):
                merge_benchmark_results(plan_dir=plan_dir, output_root=tmp_root / "runs")
            rebuilt = merge_benchmark_results(plan_dir=plan_dir, output_root=tmp_root / "runs", force=True)

        self.assertEqual(rebuilt, run_dir)

    def test_cli_prints_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root = _write_plan(tmp_root, n_trials=1)
            _write_trial_result(work_root, 1, solver_params={"base_case_n": 8}, solver_label="SOSA 8")

            exit_code = main(
                [
                    "--plan-dir",
                    str(plan_dir),
                    "--output-root",
                    str(tmp_root / "runs"),
                ]
            )
            run_exists = (tmp_root / "runs" / "smoke").exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(run_exists)


def _write_plan(tmp_root: Path, *, n_trials: int) -> tuple[Path, Path]:
    plan_dir = tmp_root / "plans" / "smoke"
    work_root = tmp_root / "work" / "smoke"
    spec = {
        "instance_pool_root": str(tmp_root / "instances"),
        "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
        "solvers": [
            {"target": "sosa-3-col-exact", "label": "SOSA 8", "params": {"base_case_n": 8}},
            {"target": "sosa-3-col-exact", "label": "SOSA 16", "params": {"base_case_n": 16}},
        ][:n_trials],
        "repetitions": 1,
        "warmup_repetitions": 0,
    }
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / PLAN_SPEC_FILENAME).write_text(json.dumps(spec), encoding="utf-8")
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
    trials = tuple(
        TrialPlanRow(
            index=index,
            instance_id="rc-n0002-seed1",
            instance_path=instance_path,
            family="rc",
            n=2,
            seed=1,
            solver="sosa-3-col-exact",
            backend=None,
            solver_target="sosa-3-col-exact",
            solver_params={"base_case_n": 8 if index == 1 else 16},
            solver_label="SOSA 8" if index == 1 else "SOSA 16",
            repetitions=1,
            warmup_repetitions=0,
        )
        for index in range(1, n_trials + 1)
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
            "n_trials": n_trials,
            "repetitions": 1,
            "warmup_repetitions": 0,
        },
    )
    return plan_dir, work_root


def _write_trial_result(work_root: Path, index: int, *, solver_params: dict, solver_label: str) -> None:
    path = trial_result_path(work_root, index)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "index": index,
        "run_id": "smoke",
        "instance_id": "rc-n0002-seed1",
        "instance_path": str(work_root.parent.parent / "instances" / "rc" / "s" / "rc-n0002-seed1.json"),
        "family": "rc",
        "bucket": "s",
        "n": 2,
        "m": 1,
        "seed": 1,
        "source": "generated",
        "solver_target": "sosa-3-col-exact",
        "solver": "sosa-3-col-exact",
        "backend": None,
        "solver_params": solver_params,
        "solver_label": solver_label,
        "status": "ok",
        "repetitions": 1,
        "warmup_repetitions": 0,
        "ok_repetitions": 1,
        "mean_wall_time_s": 0.1 * index,
        "median_wall_time_s": 0.1 * index,
        "is_colorable": True,
        "validation_ok": True,
        "validation_errors": [],
        "details": {},
        "warmup_measurements": [],
        "measurements": [
            {
                "repetition": 1,
                "status": "ok",
                "wall_time_s": 0.1 * index,
                "is_colorable": True,
                "error": None,
            }
        ],
        "error": None,
    }
    path.write_text(json.dumps(row), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
