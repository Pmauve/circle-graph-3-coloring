import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.plan import create_benchmark_plan, main
from three_col_circle_code.bench.plan_io import (
    INSTANCES_FILENAME,
    PLAN_MANIFEST_FILENAME,
    PLAN_SPEC_FILENAME,
    TRIALS_FILENAME,
    load_instance_plan,
    load_trial_plan,
)


class BenchPlanTests(unittest.TestCase):
    def test_create_benchmark_plan_writes_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "smoke.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1, 3]}],
                    "solvers": [
                        {
                            "target": "sat-baseline:pysat-cadical",
                            "label": "CaDiCaL",
                            "params": {"cutoff": 5},
                        },
                        {
                            "target": "sosa-3-col-exact",
                            "label": "SOSA exact",
                            "params": {"base_case_n": 8},
                        },
                    ],
                },
            )

            plan_dir = create_benchmark_plan(
                spec_path=spec_path,
                plan_root=tmp_root / "plans",
                work_root=tmp_root / "work",
            )

            manifest = json.loads((plan_dir / PLAN_MANIFEST_FILENAME).read_text(encoding="utf-8"))
            instances = load_instance_plan(plan_dir)
            trials = load_trial_plan(plan_dir, instances=instances)
            has_spec = (plan_dir / PLAN_SPEC_FILENAME).exists()
            has_instances = (plan_dir / INSTANCES_FILENAME).exists()
            has_trials = (plan_dir / TRIALS_FILENAME).exists()

        self.assertEqual(plan_dir.name, "smoke")
        self.assertTrue(has_spec)
        self.assertTrue(has_instances)
        self.assertTrue(has_trials)
        self.assertEqual(manifest["run_id"], "smoke")
        self.assertEqual(manifest["n_instances"], 2)
        self.assertEqual(manifest["n_trials"], 4)
        self.assertEqual(manifest["work_root"], str(tmp_root / "work" / "smoke"))
        self.assertEqual(set(manifest), {"created_at", "n_instances", "n_trials", "run_id", "work_root"})
        self.assertEqual([row.index for row in instances], [1, 2])
        self.assertEqual([row.index for row in trials], [1, 2, 3, 4])
        self.assertEqual({row.solver_label for row in trials}, {"CaDiCaL", "SOSA exact"})

    def test_create_benchmark_plan_uses_existing_flat_instance_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_pool = tmp_root / "instances"
            flat_path = instance_pool / "rc-n0002-seed1.json"
            flat_path.parent.mkdir(parents=True)
            flat_path.write_text("{}", encoding="utf-8")
            spec_path = _write_spec(
                tmp_root / "existing.json",
                {
                    "instance_pool_root": str(instance_pool),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                },
            )

            plan_dir = create_benchmark_plan(
                spec_path=spec_path,
                plan_root=tmp_root / "plans",
                work_root=tmp_root / "work",
            )
            instances = load_instance_plan(plan_dir)
            trials = load_trial_plan(plan_dir, instances=instances)

        self.assertEqual(instances[0].instance_path, flat_path)
        self.assertEqual(trials[0].instance_path, flat_path)

    def test_create_benchmark_plan_uses_expected_nested_path_for_missing_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_pool = tmp_root / "instances"
            spec_path = _write_spec(
                tmp_root / "missing.json",
                {
                    "instance_pool_root": str(instance_pool),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                },
            )

            plan_dir = create_benchmark_plan(
                spec_path=spec_path,
                plan_root=tmp_root / "plans",
                work_root=tmp_root / "work",
            )
            instances = load_instance_plan(plan_dir)
            trials = load_trial_plan(plan_dir, instances=instances)

        expected = instance_pool / "rc" / "s" / "rc-n0002-seed1.json"
        self.assertEqual(instances[0].instance_path, expected)
        self.assertEqual(trials[0].instance_path, expected)

    def test_create_benchmark_plan_rejects_existing_plan_with_different_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            first = _write_spec(
                tmp_root / "first.json",
                {
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                },
            )
            second = _write_spec(
                tmp_root / "second.json",
                {
                    "instances": [{"family": "rc", "n_values": [3], "seeds": [1]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                },
            )
            create_benchmark_plan(
                spec_path=first,
                plan_root=tmp_root / "plans",
                work_root=tmp_root / "work",
                run_id="same",
            )

            with self.assertRaisesRegex(ValueError, "different spec"):
                create_benchmark_plan(
                    spec_path=second,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                    run_id="same",
                )

    def test_create_benchmark_plan_force_replaces_existing_spec_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            first = _write_spec(
                tmp_root / "first.json",
                {
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                },
            )
            second = _write_spec(
                tmp_root / "second.json",
                {
                    "instances": [{"family": "rc", "n_values": [3], "seeds": [1]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                },
            )

            plan_dir = create_benchmark_plan(
                spec_path=first,
                plan_root=tmp_root / "plans",
                work_root=tmp_root / "work",
                run_id="same",
            )
            create_benchmark_plan(
                spec_path=second,
                plan_root=tmp_root / "plans",
                work_root=tmp_root / "work",
                run_id="same",
                force=True,
            )
            instances = load_instance_plan(plan_dir)

        self.assertEqual(instances[0].n, 3)

    def test_cli_prints_plan_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "cli.json",
                {
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                },
            )

            exit_code = main(
                [
                    "--spec",
                    str(spec_path),
                    "--plan-root",
                    str(tmp_root / "plans"),
                    "--work-root",
                    str(tmp_root / "work"),
                ]
            )
            has_plan_dir = (tmp_root / "plans" / "cli").exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(has_plan_dir)


def _write_spec(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


if __name__ == "__main__":
    unittest.main()
