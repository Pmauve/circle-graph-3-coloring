import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

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
from three_col_circle_code.bench.run_sequence import main, run_instance_sequence
from three_col_circle_code.instances.native import validation_sidecar_path


class BenchRunSequenceTests(unittest.TestCase):
    def test_run_instance_sequence_runs_trials_and_keeps_circle_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instances = _write_sequence_plan(tmp_root)

            trial_calls: list[int] = []

            with patch(
                "three_col_circle_code.bench.run_sequence.run_instance_sequence_generation",
                side_effect=lambda **kwargs: _fake_sequence_generation(work_root, instances),
            ), patch(
                "three_col_circle_code.bench.run_sequence.run_trial",
                side_effect=lambda **kwargs: _fake_run_trial(work_root, trial_calls, kwargs["index"]),
            ), patch(
                "three_col_circle_code.bench.run_sequence.staged_runtime_instance",
                side_effect=_fake_staged_runtime_instance,
            ):
                result_paths = run_instance_sequence(plan_dir=plan_dir, index=1)

            self.assertEqual(trial_calls, [1, 2, 3, 4])
            self.assertEqual(
                result_paths,
                [
                    instance_result_path(work_root, 1),
                    instance_result_path(work_root, 2),
                    trial_result_path(work_root, 1),
                    trial_result_path(work_root, 2),
                    trial_result_path(work_root, 3),
                    trial_result_path(work_root, 4),
                ],
            )
            for row in instances:
                self.assertTrue(row.instance_path.exists())
                self.assertTrue(validation_sidecar_path(row.instance_path).exists())

    def test_run_instance_sequence_accepts_keep_instances_compatibility_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instances = _write_sequence_plan(tmp_root)

            with patch(
                "three_col_circle_code.bench.run_sequence.run_instance_sequence_generation",
                side_effect=lambda **kwargs: _fake_sequence_generation(work_root, instances),
            ), patch(
                "three_col_circle_code.bench.run_sequence.run_trial",
                side_effect=lambda **kwargs: _fake_run_trial(work_root, [], kwargs["index"]),
            ), patch(
                "three_col_circle_code.bench.run_sequence.staged_runtime_instance",
                side_effect=_fake_staged_runtime_instance,
            ):
                run_instance_sequence(plan_dir=plan_dir, index=1, keep_instances=True)

            for row in instances:
                self.assertTrue(row.instance_path.exists())
                self.assertTrue(validation_sidecar_path(row.instance_path).exists())

    def test_cli_accepts_sequence_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instances = _write_sequence_plan(tmp_root)

            with patch(
                "three_col_circle_code.bench.run_sequence.run_instance_sequence_generation",
                side_effect=lambda **kwargs: _fake_sequence_generation(work_root, instances),
            ), patch(
                "three_col_circle_code.bench.run_sequence.run_trial",
                side_effect=lambda **kwargs: _fake_run_trial(work_root, [], kwargs["index"]),
            ), patch(
                "three_col_circle_code.bench.run_sequence.staged_runtime_instance",
                side_effect=_fake_staged_runtime_instance,
            ):
                exit_code = main(["--plan-dir", str(plan_dir), "--index", "1"])

        self.assertEqual(exit_code, 0)

    def test_run_instance_sequence_marks_trials_invalid_after_generation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, work_root, instances = _write_sequence_plan(tmp_root)

            trial_calls: list[int] = []
            staged_calls: list[Path] = []

            with patch(
                "three_col_circle_code.bench.run_sequence.run_instance_sequence_generation",
                side_effect=lambda **kwargs: _fake_sequence_generation_with_error(work_root, instances),
            ), patch(
                "three_col_circle_code.bench.run_sequence.run_trial",
                side_effect=lambda **kwargs: _fake_run_trial(work_root, trial_calls, kwargs["index"]),
            ), patch(
                "three_col_circle_code.bench.run_sequence.staged_runtime_instance",
                side_effect=lambda path: _recording_staged_runtime_instance(staged_calls, path),
            ):
                result_paths = run_instance_sequence(plan_dir=plan_dir, index=1)

            self.assertEqual(trial_calls, [1, 2, 3, 4])
            self.assertEqual(staged_calls, [instances[0].instance_path])
            self.assertEqual(
                result_paths,
                [
                    instance_result_path(work_root, 1),
                    instance_result_path(work_root, 2),
                    trial_result_path(work_root, 1),
                    trial_result_path(work_root, 2),
                    trial_result_path(work_root, 3),
                    trial_result_path(work_root, 4),
                ],
            )


def _write_sequence_plan(tmp_root: Path) -> tuple[Path, Path, tuple[InstancePlanRow, ...]]:
    plan_dir = tmp_root / "plans" / "sequence"
    work_root = tmp_root / "work" / "sequence"
    instances = (
        InstancePlanRow(
            index=1,
            instance_id="rcy_fast-k03-n0100-seed1",
            family="rcy_fast",
            n=100,
            seed=1,
            instance_path=tmp_root / "instances" / "rcy_fast" / "s" / "rcy_fast-k03-n0100-seed1.circle",
            sequence_id="seq-1",
        ),
        InstancePlanRow(
            index=2,
            instance_id="rcy_fast-k03-n0200-seed1",
            family="rcy_fast",
            n=200,
            seed=1,
            instance_path=tmp_root / "instances" / "rcy_fast" / "s" / "rcy_fast-k03-n0200-seed1.circle",
            sequence_id="seq-1",
        ),
    )
    trials = []
    index = 1
    solver_specs = (
        ("SAT Kissat", "sat_native", {"solver": "kissat-rustsat"}),
        ("SOSA base=128", "sosa_native", {"base_case_n": 128}),
    )
    for row in instances:
        for solver_label, solver_target, solver_params in solver_specs:
            trials.append(
                TrialPlanRow(
                    index=index,
                    instance_id=row.instance_id,
                    instance_path=row.instance_path,
                    family=row.family,
                    n=row.n,
                    seed=row.seed,
                    solver="native",
                    backend=None,
                    solver_target=solver_target,
                    solver_params=solver_params,
                    solver_label=solver_label,
                )
            )
            index += 1
    write_instance_plan(plan_dir, instances)
    write_trial_plan(plan_dir, trials, instances=instances)
    write_plan_manifest(
        plan_dir,
        {
            "run_id": "sequence",
            "created_at": "2026-05-09T00:00:00+00:00",
            "work_root": work_root,
            "n_instances": len(instances),
            "n_trials": len(trials),
        },
    )
    return plan_dir, work_root, instances


def _fake_sequence_generation(work_root: Path, rows: tuple[InstancePlanRow, ...]) -> list[Path]:
    result_paths = []
    for row in rows:
        row.instance_path.parent.mkdir(parents=True, exist_ok=True)
        row.instance_path.write_text("c hord endpoint order START\nc 1 1\nc hord endpoint order END\np circle 1 0\n", encoding="utf-8")
        validation_sidecar_path(row.instance_path).write_text(
            json.dumps({"instance_id": row.instance_id, "validated": True}),
            encoding="utf-8",
        )
        result_path = instance_result_path(work_root, row.index)
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "index": row.index,
                    "kind": "instance",
                    "status": "ok",
                    "instance_id": row.instance_id,
                    "instance_path": str(row.instance_path),
                    "generated": True,
                    "validation_ok": True,
                    "validation_errors": [],
                }
            ),
            encoding="utf-8",
        )
        result_paths.append(result_path)
    return result_paths


def _fake_sequence_generation_with_error(work_root: Path, rows: tuple[InstancePlanRow, ...]) -> list[Path]:
    result_paths = _fake_sequence_generation(work_root, rows[:1])
    failed = rows[1]
    result_path = instance_result_path(work_root, failed.index)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "index": failed.index,
                "kind": "instance",
                "status": "error",
                "instance_id": failed.instance_id,
                "instance_path": str(failed.instance_path),
                "generated": False,
                "validation_ok": False,
                "validation_errors": [],
                "error": "generation failed",
            }
        ),
        encoding="utf-8",
    )
    result_paths.append(result_path)
    return result_paths


@contextmanager
def _fake_staged_runtime_instance(instance_path: Path):
    yield instance_path


@contextmanager
def _recording_staged_runtime_instance(calls: list[Path], instance_path: Path):
    calls.append(instance_path)
    yield instance_path


def _fake_run_trial(work_root: Path, calls: list[int], index: int) -> Path:
    calls.append(index)
    result_path = trial_result_path(work_root, index)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"index": index, "status": "ok"}), encoding="utf-8")
    return result_path


if __name__ == "__main__":
    unittest.main()
