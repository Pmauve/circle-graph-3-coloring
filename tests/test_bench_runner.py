import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.report_data import (
    SUMMARY_BY_BUCKET_FILENAME,
    SUMMARY_BY_N_FILENAME,
    SUMMARY_OVERALL_FILENAME,
)
from three_col_circle_code.bench.results import MANIFEST_FILENAME, RESULTS_FILENAME
from three_col_circle_code.bench.runner import BenchmarkTask, _execute_benchmark_task, main, run_benchmark
from three_col_circle_code.bench.specs import InstanceRequest
from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.solvers.common import SOLVER_STATUS_OK, SolverConfig, SolverResult
from three_col_circle_code.solvers.sat import SAT_BASELINE_SOLVER


class BenchRunnerTests(unittest.TestCase):
    def test_run_benchmark_writes_manifest_results_and_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "sat-smoke.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:legacy-pysmt-msat", "params": {"cutoff": 5}}],
                },
            )
            first = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={"python_version": "test"},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ), patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="legacy-pysmt-msat", wall_time_s=0.25),
            ) as run_solver:
                run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                )

            manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            lines = (run_dir / RESULTS_FILENAME).read_text(encoding="utf-8").strip().splitlines()
            has_summary_by_n = (run_dir / SUMMARY_BY_N_FILENAME).exists()
            has_summary_by_bucket = (run_dir / SUMMARY_BY_BUCKET_FILENAME).exists()
            has_summary_overall = (run_dir / SUMMARY_OVERALL_FILENAME).exists()
            has_report = (run_dir / "report.html").exists()

        self.assertEqual(run_dir.name, "sat-smoke")
        self.assertEqual(manifest["run_id"], run_dir.name)
        self.assertEqual(manifest["n_instances"], 1)
        self.assertEqual(manifest["n_tasks"], 1)
        self.assertEqual(
            manifest["solvers"],
            [
                {
                    "solver": "sat-baseline",
                    "backend": "legacy-pysmt-msat",
                    "target": "sat-baseline:legacy-pysmt-msat",
                    "params": {"cutoff": 5},
                }
            ],
        )
        self.assertEqual(
            manifest["instance_requests"],
            [{"instance_id": "rc-n0002-seed1", "family": "rc", "n": 2, "seed": 1}],
        )
        self.assertEqual(manifest["environment"], {"python_version": "test"})
        self.assertEqual(len(lines), 1)
        result = json.loads(lines[0])
        self.assertEqual(result["instance_id"], "rc-n0002-seed1")
        self.assertEqual(result["solver_target"], "sat-baseline:legacy-pysmt-msat")
        self.assertEqual(result["solver_params"], {"cutoff": 5})
        self.assertEqual(result["solver"], SAT_BASELINE_SOLVER)
        self.assertEqual(result["backend"], "legacy-pysmt-msat")
        self.assertTrue(result["validation_ok"])
        self.assertIn(str(first), result["instance_path"])
        self.assertTrue(has_summary_by_n)
        self.assertTrue(has_summary_by_bucket)
        self.assertTrue(has_summary_overall)
        self.assertTrue(has_report)
        run_solver.assert_called_once()

    def test_run_benchmark_emits_progress_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "progress-run.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {"cutoff": 5}}],
                },
            )
            progress = io.StringIO()

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ), patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.25),
            ):
                run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                    progress_stream=progress,
                )

        rendered = progress.getvalue()
        self.assertIn("Starting benchmark run 'progress-run'", rendered)
        self.assertIn("Resolving 1 requested instances...", rendered)
        self.assertIn("Generating missing instances (1 total)...", rendered)
        self.assertIn("Generated 1/1 missing instances", rendered)
        self.assertIn("Planned tasks: 1 across 1 instances and 1 solver configs", rendered)
        self.assertIn("[1/1] rc-n0002-seed1 | sat-baseline:pysat-cadical", rendered)
        self.assertIn("-> ok in 0.2500s", rendered)
        self.assertIn("Completed run 'progress-run': ok=1, error=0, invalid=0", rendered)

    def test_run_benchmark_limits_generation_progress_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "generation-progress-run.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n": {"start": 2, "stop": 12, "step": 1}, "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {}}],
                },
            )
            progress = io.StringIO()

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                side_effect=lambda family, n, seed: _build_record(
                    instance_id=f"{family}-n{n:04d}-seed{seed}",
                    family=family,
                    seed=seed,
                    n=n,
                ),
            ), patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                    progress_stream=progress,
                )

        rendered = progress.getvalue()
        self.assertIn("Resolving 11 requested instances...", rendered)
        self.assertIn("Generating missing instances (11 total)...", rendered)
        self.assertIn("Generated 1/11 missing instances", rendered)
        self.assertIn("Generated 10/11 missing instances", rendered)
        self.assertIn("Generated 11/11 missing instances", rendered)
        self.assertNotIn("Generated 2/11 missing instances", rendered)
        self.assertNotIn("Generated 9/11 missing instances", rendered)

    def test_execute_benchmark_task_records_invalid_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            run_dir = tmp_root / "run"
            run_dir.mkdir()
            invalid_path = tmp_root / "broken.json"
            invalid_path.write_text("{not json", encoding="utf-8")

            _execute_benchmark_task(
                run_dir=run_dir,
                run_id="run-1",
                task=BenchmarkTask(
                    instance_request=InstanceRequest(
                        instance_id="rc-n0002-seed1",
                        family="rc",
                        n=2,
                        seed=1,
                    ),
                    instance_path=invalid_path,
                    solver_config=SolverConfig(solver=SAT_BASELINE_SOLVER, backend="pysat-cadical"),
                ),
            )

            result = json.loads((run_dir / RESULTS_FILENAME).read_text(encoding="utf-8").strip())

        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["solver_target"], "sat-baseline:pysat-cadical")
        self.assertEqual(result["solver_params"], {})
        self.assertFalse(result["validation_ok"])
        self.assertEqual(result["family"], "rc")
        self.assertEqual(result["n"], 2)
        self.assertEqual(result["seed"], 1)

    def test_run_benchmark_reuses_existing_pooled_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_pool_root = tmp_root / "instances"
            _write_instance(
                instance_pool_root / "rc" / "s" / "rc-n0002-seed1.json",
                instance_id="rc-n0002-seed1",
                family="rc",
                seed=1,
            )
            spec_path = _write_spec(
                tmp_root / "reuse-pool.json",
                {
                    "instance_pool_root": str(instance_pool_root),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {}}],
                },
            )

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
            ) as generate_instance_mock, patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                run_dir = run_benchmark(output_root=tmp_root / "runs", spec_path=spec_path)

            manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))

        self.assertEqual(manifest["run_id"], "reuse-pool")
        self.assertEqual(manifest["n_instances"], 1)
        self.assertEqual(manifest["n_tasks"], 1)
        generate_instance_mock.assert_not_called()

    def test_run_benchmark_generates_missing_pooled_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_pool_root = tmp_root / "instances"
            spec_path = _write_spec(
                tmp_root / "generate-pool.json",
                {
                    "instance_pool_root": str(instance_pool_root),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {}}],
                },
            )

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ) as generate_instance_mock, patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                run_benchmark(output_root=tmp_root / "runs", spec_path=spec_path)
                generated_exists = (instance_pool_root / "rc" / "s" / "rc-n0002-seed1.json").exists()

        self.assertTrue(generated_exists)
        generate_instance_mock.assert_called_once_with(family="rc", n=2, seed=1)

    def test_run_benchmark_range_expands_and_is_copied(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_payload = {
                "instance_pool_root": str(tmp_root / "instances"),
                "instances": [{"family": "rc", "n": {"start": 2, "stop": 4, "step": 1}, "seeds": [1, 3]}],
                "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {}}],
            }
            spec_path = _write_spec(tmp_root / "range-expand.json", spec_payload)

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                side_effect=lambda family, n, seed: _build_record(
                    instance_id=f"{family}-n{n:04d}-seed{seed}",
                    family=family,
                    seed=seed,
                    n=n,
                ),
            ), patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                )

            manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            copied_spec = json.loads((run_dir / "spec.json").read_text(encoding="utf-8"))

        self.assertEqual(run_dir.name, "range-expand")
        self.assertEqual(copied_spec, spec_payload)
        self.assertEqual(
            manifest["instance_requests"],
            [
                {"instance_id": "rc-n0002-seed1", "family": "rc", "n": 2, "seed": 1},
                {"instance_id": "rc-n0002-seed3", "family": "rc", "n": 2, "seed": 3},
                {"instance_id": "rc-n0003-seed1", "family": "rc", "n": 3, "seed": 1},
                {"instance_id": "rc-n0003-seed3", "family": "rc", "n": 3, "seed": 3},
                {"instance_id": "rc-n0004-seed1", "family": "rc", "n": 4, "seed": 1},
                {"instance_id": "rc-n0004-seed3", "family": "rc", "n": 4, "seed": 3},
            ],
        )

    def test_run_benchmark_resume_skips_completed_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "resume-run.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {}}],
                },
            )

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ), patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ) as run_solver:
                first_run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                )
                first_manifest = json.loads((first_run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
                second_run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                )
                second_manifest = json.loads((second_run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))

        self.assertEqual(first_run_dir, second_run_dir)
        self.assertEqual(first_manifest["created_at"], second_manifest["created_at"])
        self.assertEqual(run_solver.call_count, 1)

    def test_run_benchmark_different_solver_params_are_distinct_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "param-distinct.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [
                        {"target": "sat-baseline:pysat-cadical", "params": {"limit": 1}},
                        {"target": "sat-baseline:pysat-cadical", "params": {"limit": 2}},
                    ],
                },
            )

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ), patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                run_dir = run_benchmark(output_root=tmp_root / "runs", spec_path=spec_path)

            results = [
                json.loads(line)
                for line in (run_dir / RESULTS_FILENAME).read_text(encoding="utf-8").strip().splitlines()
            ]

        self.assertEqual(len(results), 2)
        self.assertEqual(
            {json.dumps(row["solver_params"], sort_keys=True) for row in results},
            {'{"limit": 1}', '{"limit": 2}'},
        )

    def test_run_benchmark_rejects_invalid_specs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            missing_fields = _write_spec(tmp_root / "missing.json", {})
            removed_name = _write_spec(
                tmp_root / "removed-name.json",
                {
                    "name": "old-style",
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical"}],
                },
            )
            both_n_shapes = _write_spec(
                tmp_root / "both.json",
                {
                    "instances": [
                        {
                            "family": "rc",
                            "n_values": [2],
                            "n": {"start": 2, "stop": 4, "step": 1},
                            "seeds": [1],
                        }
                    ],
                    "solvers": [{"target": "sat-baseline:pysat-cadical"}],
                },
            )
            empty_seeds = _write_spec(
                tmp_root / "empty.json",
                {
                    "instances": [{"family": "rc", "n_values": [2], "seeds": []}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical"}],
                },
            )

            with self.assertRaises(ValueError):
                run_benchmark(output_root=tmp_root / "runs", spec_path=missing_fields)
            with self.assertRaises(ValueError):
                run_benchmark(output_root=tmp_root / "runs", spec_path=removed_name)
            with self.assertRaises(ValueError):
                run_benchmark(output_root=tmp_root / "runs", spec_path=both_n_shapes)
            with self.assertRaises(ValueError):
                run_benchmark(output_root=tmp_root / "runs", spec_path=empty_seeds)

    def test_run_benchmark_rejects_kissat404_on_windows_before_creating_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "kissat-on-windows.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-kissat404", "params": {}}],
                },
            )

            with patch("three_col_circle_code.bench.runner.platform.system", return_value="Windows"):
                with self.assertRaisesRegex(ValueError, "not supported on Windows"):
                    run_benchmark(output_root=tmp_root / "runs", spec_path=spec_path)

            self.assertFalse((tmp_root / "runs" / "kissat-on-windows").exists())

    def test_cli_supports_spec_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "cli-run.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {}}],
                },
            )

            with patch(
                "three_col_circle_code.bench.runner.collect_environment_metadata",
                return_value={},
            ), patch(
                "three_col_circle_code.bench.runner.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ), patch(
                "three_col_circle_code.bench.runner.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                exit_code = main(
                    [
                        "--spec",
                        str(spec_path),
                        "--output-root",
                        str(tmp_root / "runs"),
                    ]
                )
                has_manifest = (tmp_root / "runs" / "cli-run" / MANIFEST_FILENAME).exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(has_manifest)


def _write_instance(path: Path, *, instance_id: str, family: str, seed: int) -> Path:
    save_instance(_build_record(instance_id=instance_id, family=family, seed=seed), path)
    return path


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
            created_at="2026-04-13T00:00:00Z",
        ),
        graph=graph,
    )


def _write_spec(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fake_solver_result(
    *,
    backend: str,
    wall_time_s: float,
    details: Optional[dict] = None,
) -> SolverResult:
    return SolverResult(
        solver=SAT_BASELINE_SOLVER,
        backend=backend,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        is_three_colorable=True,
        n_vertices=2,
        m_edges=1,
        details=details or {"requested_params": {}},
        error=None,
    )


if __name__ == "__main__":
    unittest.main()
