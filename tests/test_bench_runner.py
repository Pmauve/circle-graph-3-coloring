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

from three_col_circle_code.bench.plan_io import instance_result_path
from three_col_circle_code.bench.report_data import (
    SUMMARY_BY_BUCKET_FILENAME,
    SUMMARY_BY_N_FILENAME,
    SUMMARY_OVERALL_FILENAME,
)
from three_col_circle_code.bench.results import MANIFEST_FILENAME, RESULTS_FILENAME
from three_col_circle_code.bench.runner import main, run_benchmark
from three_col_circle_code.instances.io import save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.solvers.common import SOLVER_STATUS_OK, SolverResult
from three_col_circle_code.solvers.sat import SAT_BASELINE_SOLVER


class BenchRunnerTests(unittest.TestCase):
    def test_run_benchmark_orchestrates_plan_tasks_merge_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "sat-smoke.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [
                        {
                            "target": "sat-baseline:legacy-pysmt-msat",
                            "label": "MathSAT legacy",
                            "params": {"cutoff": 5},
                        }
                    ],
                },
            )
            progress = io.StringIO()

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_col_with_native",
                side_effect=_write_native_generated_instance,
            ), patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                return_value=None,
            ), patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(backend="legacy-pysmt-msat", wall_time_s=0.25),
            ) as run_solver:
                run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                    progress_stream=progress,
                )

            manifest = json.loads((run_dir / MANIFEST_FILENAME).read_text(encoding="utf-8"))
            result_lines = (run_dir / RESULTS_FILENAME).read_text(encoding="utf-8").strip().splitlines()
            result = json.loads(result_lines[0])
            plan_dir = tmp_root / "plans" / "sat-smoke"
            work_root = tmp_root / "work" / "sat-smoke"
            has_instance_plan = (plan_dir / "instances.jsonl").exists()
            has_trial_plan = (plan_dir / "trials.jsonl").exists()
            has_instance_result = (work_root / "instances" / "000001" / "result.json").exists()
            has_trial_result = (work_root / "trials" / "000001" / "result.json").exists()
            has_summary_by_n = (run_dir / SUMMARY_BY_N_FILENAME).exists()
            has_summary_by_bucket = (run_dir / SUMMARY_BY_BUCKET_FILENAME).exists()
            has_summary_overall = (run_dir / SUMMARY_OVERALL_FILENAME).exists()
            has_report = (run_dir / "report.html").exists()
            progress_output = progress.getvalue()

        self.assertEqual(run_dir.name, "sat-smoke")
        self.assertEqual(manifest["run_id"], "sat-smoke")
        self.assertEqual(manifest["execution_mode"], "merged_trial_outputs")
        self.assertEqual(manifest["n_instances"], 1)
        self.assertEqual(manifest["n_tasks"], 1)
        self.assertEqual(len(result_lines), 1)
        self.assertEqual(result["instance_id"], "rc-k03-n0002-seed1")
        self.assertEqual(result["solver_target"], "sat-baseline:legacy-pysmt-msat")
        self.assertEqual(result["solver_params"], {"cutoff": 5})
        self.assertEqual(result["solver_label"], "MathSAT legacy")
        self.assertEqual(result["solver"], SAT_BASELINE_SOLVER)
        self.assertEqual(result["backend"], "legacy-pysmt-msat")
        self.assertTrue(result["validation_ok"])
        self.assertFalse(has_instance_plan)
        self.assertFalse(has_trial_plan)
        self.assertFalse(has_instance_result)
        self.assertFalse(has_trial_result)
        self.assertTrue(has_summary_by_n)
        self.assertTrue(has_summary_by_bucket)
        self.assertTrue(has_summary_overall)
        self.assertTrue(has_report)
        self.assertIn("Planning benchmark from", progress_output)
        self.assertIn("Preparing 1 instance(s) with jobs=1", progress_output)
        self.assertIn("instance preparation: generated rc-k03-n0002-seed1", progress_output)
        self.assertIn("Instance preparation summary: reused existing=0, generated new=1", progress_output)
        self.assertIn("Cleaned benchmark temporary directory", progress_output)
        self.assertIn("Running 1 trial(s) with jobs=1", progress_output)
        self.assertIn("Merging trial outputs", progress_output)
        run_solver.assert_called_once()

    def test_run_benchmark_reuses_existing_pooled_instances(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_pool_root = tmp_root / "instances"
            _write_instance(
                instance_pool_root / "rc" / "s" / "rc-k03-n0002-seed1.col",
                instance_id="rc-k03-n0002-seed1",
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
                "three_col_circle_code.bench.generate_instance.generate_col_with_native",
            ) as generate_instance_mock, patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                return_value=None,
            ), patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                progress = io.StringIO()
                run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                    progress_stream=progress,
                )
                progress_output = progress.getvalue()

        self.assertEqual(run_dir.name, "reuse-pool")
        self.assertIn("instance preparation: reused rc-k03-n0002-seed1", progress_output)
        self.assertIn("reused existing=1, generated new=0", progress_output)
        generate_instance_mock.assert_not_called()

    def test_run_benchmark_cleans_isolated_outputs_after_success(self) -> None:
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
                "three_col_circle_code.bench.generate_instance.generate_col_with_native",
                side_effect=_write_native_generated_instance,
            ) as generate_instance_mock, patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                return_value=None,
            ), patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ) as run_solver_mock:
                first_run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                )
                second_run_dir = run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                )

        self.assertEqual(first_run_dir, second_run_dir)
        self.assertEqual(generate_instance_mock.call_count, 1)
        self.assertEqual(run_solver_mock.call_count, 2)
        self.assertFalse((tmp_root / "plans" / "resume-run").exists())
        self.assertFalse((tmp_root / "work" / "resume-run").exists())

    def test_run_benchmark_stops_before_trials_when_instance_generation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(
                tmp_root / "bad-generation.json",
                {
                    "instance_pool_root": str(tmp_root / "instances"),
                    "instances": [{"family": "rc", "n_values": [2], "seeds": [1]}],
                    "solvers": [{"target": "sat-baseline:pysat-cadical", "params": {}}],
                },
            )

            def write_failed_instance_result(plan_dir: Path, index: int, force: bool) -> Path:
                work_root = tmp_root / "work" / "bad-generation"
                result_path = instance_result_path(work_root, index)
                result_path.parent.mkdir(parents=True, exist_ok=True)
                result_path.write_text(
                    json.dumps({"index": index, "status": "error", "error": "boom"}),
                    encoding="utf-8",
                )
                return result_path

            with patch(
                "three_col_circle_code.bench.runner.run_instance_generation",
                side_effect=write_failed_instance_result,
            ), patch("three_col_circle_code.bench.runner.run_trial") as run_trial_mock:
                with self.assertRaisesRegex(ValueError, "instance generation did not complete"):
                    run_benchmark(
                        output_root=tmp_root / "runs",
                        spec_path=spec_path,
                        plan_root=tmp_root / "plans",
                        work_root=tmp_root / "work",
                    )

        run_trial_mock.assert_not_called()

    def test_run_benchmark_rejects_invalid_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            spec_path = _write_spec(tmp_root / "unused.json", {})

            with self.assertRaisesRegex(ValueError, "jobs"):
                run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=spec_path,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                    jobs=0,
                )

        self.assertFalse((tmp_root / "plans").exists())

    def test_run_benchmark_rejects_invalid_specs_before_creating_plan(self) -> None:
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

            with self.assertRaises(ValueError):
                run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=missing_fields,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                )
            with self.assertRaises(ValueError):
                run_benchmark(
                    output_root=tmp_root / "runs",
                    spec_path=removed_name,
                    plan_root=tmp_root / "plans",
                    work_root=tmp_root / "work",
                )

        self.assertFalse((tmp_root / "plans" / "missing").exists())
        self.assertFalse((tmp_root / "plans" / "removed-name").exists())

    def test_run_benchmark_rejects_kissat404_on_windows_before_creating_plan(self) -> None:
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

            with patch("three_col_circle_code.bench.planning.platform.system", return_value="Windows"):
                with self.assertRaisesRegex(ValueError, "not supported on Windows"):
                    run_benchmark(
                        output_root=tmp_root / "runs",
                        spec_path=spec_path,
                        plan_root=tmp_root / "plans",
                        work_root=tmp_root / "work",
                    )

        self.assertFalse((tmp_root / "plans" / "kissat-on-windows").exists())

    def test_cli_supports_local_pipeline_flags(self) -> None:
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
                "three_col_circle_code.bench.generate_instance.generate_col_with_native",
                side_effect=_write_native_generated_instance,
            ), patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                return_value=None,
            ), patch(
                "three_col_circle_code.bench.run_trial.run_solver",
                return_value=_fake_solver_result(backend="pysat-cadical", wall_time_s=0.1),
            ):
                exit_code = main(
                    [
                        "--spec",
                        str(spec_path),
                        "--output-root",
                        str(tmp_root / "runs"),
                        "--plan-root",
                        str(tmp_root / "plans"),
                        "--work-root",
                        str(tmp_root / "work"),
                        "--jobs",
                        "1",
                    ]
                )
                has_manifest = (tmp_root / "runs" / "cli-run" / MANIFEST_FILENAME).exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(has_manifest)


def _write_instance(path: Path, *, instance_id: str, family: str, seed: int) -> Path:
    save_instance(_build_record(instance_id=instance_id, family=family, seed=seed), path)
    return path


def _write_native_generated_instance(*, instance_path: Path, family: str, n: int, seed: int, **_kwargs) -> None:
    instance_id = f"{family}-k03-n{n:04d}-seed{seed}"
    save_instance(_build_record(instance_id=instance_id, family=family, seed=seed, n=n), instance_path)


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
        is_colorable=True,
        n_vertices=2,
        m_edges=1,
        details=details or {"requested_params": {}},
        error=None,
    )


if __name__ == "__main__":
    unittest.main()
