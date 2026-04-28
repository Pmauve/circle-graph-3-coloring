import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.plan_io import (
    InstancePlanRow,
    TrialPlanRow,
    instance_result_path,
    load_instance_plan,
    load_plan_manifest,
    load_trial_plan,
    trial_result_path,
    validate_instance_plan,
    validate_trial_plan,
    write_instance_plan,
    write_plan_manifest,
    write_trial_plan,
)


class BenchPlanIoTests(unittest.TestCase):
    def test_instance_plan_round_trips_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "plan"
            rows = (
                InstancePlanRow(
                    index=1,
                    instance_id="rc-n0002-seed1",
                    family="rc",
                    n=2,
                    seed=1,
                    instance_path=Path("eval/instances/rc/s/rc-n0002-seed1.json"),
                ),
            )

            write_instance_plan(plan_dir, rows)
            loaded = load_instance_plan(plan_dir)

        self.assertEqual(loaded, rows)

    def test_trial_plan_round_trips_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "plan"
            instances = (
                InstancePlanRow(
                    index=1,
                    instance_id="rc-n0002-seed1",
                    family="rc",
                    n=2,
                    seed=1,
                    instance_path=Path("eval/instances/rc/s/rc-n0002-seed1.json"),
                ),
            )
            rows = (
                TrialPlanRow(
                    index=1,
                    instance_id="rc-n0002-seed1",
                    instance_path=Path("eval/instances/rc/s/rc-n0002-seed1.json"),
                    family="rc",
                    n=2,
                    seed=1,
                    solver="sosa-3-col-exact",
                    backend=None,
                    solver_target="sosa-3-col-exact",
                    solver_params={"base_case_n": 8},
                    solver_label="SOSA exact",
                ),
            )

            write_trial_plan(plan_dir, rows, instances=instances)
            loaded = load_trial_plan(plan_dir, instances=instances)

        self.assertEqual(loaded, rows)

    def test_plan_manifest_round_trips_json(self) -> None:
        self.maxDiff = None
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir) / "plan"
            manifest = {
                "run_id": "smoke",
                "created_at": "2026-04-29T00:00:00+00:00",
                "spec_filename": "spec.json",
                "instances_filename": "instances.jsonl",
                "trials_filename": "trials.jsonl",
                "instance_pool_root": Path("eval/instances"),
                "work_root": Path("eval/benchmark_work/smoke"),
                "n_instances": 1,
                "n_trials": 1,
                "solvers": [{"target": "sosa-3-col-exact", "params": {}}],
                "environment": {"python_version": "test"},
            }

            write_plan_manifest(plan_dir, manifest)
            loaded = load_plan_manifest(plan_dir)

        self.assertEqual(
            loaded,
            {
                **manifest,
                "instance_pool_root": str(Path("eval/instances")),
                "work_root": str(Path("eval/benchmark_work/smoke")),
            },
        )

    def test_instance_plan_rejects_non_contiguous_indices(self) -> None:
        rows = (
            InstancePlanRow(
                index=2,
                instance_id="rc-n0002-seed1",
                family="rc",
                n=2,
                seed=1,
                instance_path=Path("eval/instances/rc/s/rc-n0002-seed1.json"),
            ),
        )

        with self.assertRaisesRegex(ValueError, "contiguous"):
            validate_instance_plan(rows)

    def test_instance_plan_rejects_duplicate_instance_ids(self) -> None:
        rows = (
            InstancePlanRow(1, "same", "rc", 2, 1, Path("eval/instances/rc/s/same.json")),
            InstancePlanRow(2, "same", "rc", 2, 2, Path("eval/instances/rc/s/same-2.json")),
        )

        with self.assertRaisesRegex(ValueError, "duplicate instance id"):
            validate_instance_plan(rows)

    def test_instance_plan_rejects_benchmark_work_paths(self) -> None:
        rows = (
            InstancePlanRow(1, "bad", "rc", 2, 1, Path("eval/benchmark_work/run/instances/bad.json")),
        )

        with self.assertRaisesRegex(ValueError, "canonical instance pool"):
            validate_instance_plan(rows)

    def test_trial_plan_rejects_unknown_instance_id(self) -> None:
        rows = (
            TrialPlanRow(
                1,
                "missing",
                Path("eval/instances/rc/s/missing.json"),
                "rc",
                2,
                1,
                "sosa-3-col-exact",
                None,
                "sosa-3-col-exact",
                {},
                None,
            ),
        )

        with self.assertRaisesRegex(ValueError, "unknown instance id"):
            validate_trial_plan(rows, instances=())

    def test_trial_plan_rejects_instance_path_mismatch(self) -> None:
        instances = (
            InstancePlanRow(1, "rc-n0002-seed1", "rc", 2, 1, Path("eval/instances/rc/s/canonical.json")),
        )
        rows = (
            TrialPlanRow(
                1,
                "rc-n0002-seed1",
                Path("eval/instances/rc/s/other.json"),
                "rc",
                2,
                1,
                "sosa-3-col-exact",
                None,
                "sosa-3-col-exact",
                {},
                None,
            ),
        )

        with self.assertRaisesRegex(ValueError, "differs from instances.jsonl"):
            validate_trial_plan(rows, instances=instances)

    def test_trial_plan_rejects_duplicate_trial_keys(self) -> None:
        instances = (
            InstancePlanRow(1, "rc-n0002-seed1", "rc", 2, 1, Path("eval/instances/rc/s/rc-n0002-seed1.json")),
        )
        first = TrialPlanRow(
            1,
            "rc-n0002-seed1",
            Path("eval/instances/rc/s/rc-n0002-seed1.json"),
            "rc",
            2,
            1,
            "sosa-3-col-exact",
            None,
            "sosa-3-col-exact",
            {"base_case_n": 8},
            None,
        )
        second = TrialPlanRow(
            2,
            "rc-n0002-seed1",
            Path("eval/instances/rc/s/rc-n0002-seed1.json"),
            "rc",
            2,
            1,
            "sosa-3-col-exact",
            None,
            "sosa-3-col-exact",
            {"base_case_n": 8},
            None,
        )

        with self.assertRaisesRegex(ValueError, "duplicate trial"):
            validate_trial_plan((first, second), instances=instances)

    def test_result_paths_are_stable_and_indexed(self) -> None:
        self.assertEqual(
            instance_result_path(Path("eval/benchmark_work/run"), 7),
            Path("eval/benchmark_work/run/instances/000007/result.json"),
        )
        self.assertEqual(
            trial_result_path(Path("eval/benchmark_work/run"), 12),
            Path("eval/benchmark_work/run/trials/000012/result.json"),
        )


if __name__ == "__main__":
    unittest.main()
