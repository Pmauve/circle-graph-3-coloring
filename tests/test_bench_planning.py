import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.planning import (
    expected_instance_path,
    iter_benchmark_trials,
    prepare_run_directory,
)
from three_col_circle_code.bench.specs import normalize_run_spec


class BenchPlanningTests(unittest.TestCase):
    def test_iter_benchmark_trials_is_deterministically_ordered(self) -> None:
        run_spec = normalize_run_spec(
            {
                "instance_pool_root": "eval/instances",
                "instances": [
                    {"family": "rcy_fast", "n_values": [8], "seeds": [2]},
                    {"family": "rc", "n_values": [4, 2], "seeds": [3, 1]},
                ],
                "solvers": [
                    {"target": "sat-baseline:pysat-cadical", "params": {"cutoff": 5}},
                    {"target": "sosa-3-col-exact", "params": {"base_case_n": 8}},
                ],
            }
        )
        instance_paths = {
            request.instance_id: Path("instances") / f"{request.instance_id}.json"
            for request in run_spec.instance_requests
        }

        trials = iter_benchmark_trials(run_spec, instance_paths)

        self.assertEqual(
            [
                (
                    trial.instance_request.family,
                    trial.instance_request.n,
                    trial.instance_request.seed,
                    trial.solver_config.target,
                    trial.solver_config.params,
                )
                for trial in trials
            ],
            [
                ("rc", 2, 1, "sat-baseline:pysat-cadical", {"cutoff": 5}),
                ("rc", 2, 1, "sosa-3-col-exact", {"base_case_n": 8}),
                ("rc", 2, 3, "sat-baseline:pysat-cadical", {"cutoff": 5}),
                ("rc", 2, 3, "sosa-3-col-exact", {"base_case_n": 8}),
                ("rc", 4, 1, "sat-baseline:pysat-cadical", {"cutoff": 5}),
                ("rc", 4, 1, "sosa-3-col-exact", {"base_case_n": 8}),
                ("rc", 4, 3, "sat-baseline:pysat-cadical", {"cutoff": 5}),
                ("rc", 4, 3, "sosa-3-col-exact", {"base_case_n": 8}),
                ("rcy_fast", 8, 2, "sat-baseline:pysat-cadical", {"cutoff": 5}),
                ("rcy_fast", 8, 2, "sosa-3-col-exact", {"base_case_n": 8}),
            ],
        )

    def test_expected_instance_path_uses_nested_pool_layout(self) -> None:
        run_spec = normalize_run_spec(
            {
                "instance_pool_root": "eval/instances",
                "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                "solvers": [{"target": "sosa-3-col-exact"}],
            }
        )

        path = expected_instance_path(
            instance_pool_root=run_spec.instance_pool_root,
            request=run_spec.instance_requests[0],
        )

        self.assertEqual(path, Path("eval/instances/rc/s/rc-n0002-seed1.json"))

    def test_prepare_run_directory_rejects_same_run_id_with_different_spec(self) -> None:
        with self.assertRaisesRegex(ValueError, "different benchmark spec"):
            with _temporary_run_dir() as output_root:
                prepare_run_directory(
                    output_root=output_root,
                    spec_source='{"instances": [], "solvers": []}',
                    run_id="same-run",
                )
                prepare_run_directory(
                    output_root=output_root,
                    spec_source='{"instances": [{"family": "rc"}], "solvers": []}',
                    run_id="same-run",
                )


class _temporary_run_dir:
    def __enter__(self) -> Path:
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        return Path(self._tmp.name)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
