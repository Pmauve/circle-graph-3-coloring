import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.generate_instance import (
    main,
    run_instance_generation,
    run_instance_sequence_generation,
    sequence_main,
)
from three_col_circle_code.bench.plan_io import (
    InstancePlanRow,
    instance_result_path,
    write_instance_plan,
    write_plan_manifest,
)
from three_col_circle_code.instances.io import load_instance, save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.instances.native import NativeInstanceInvalid
from three_col_circle_code.instances.validate import validate_instance


class BenchGenerateInstanceTests(unittest.TestCase):
    def test_run_instance_generation_generates_missing_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json"
            plan_dir, work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1),
            ) as generate, patch(
                "three_col_circle_code.bench.generate_instance.collect_environment_metadata",
                return_value={"hostname": "worker-1"},
            ):
                result_path = run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))
            loaded = load_instance(instance_path)

        self.assertEqual(result_path, instance_result_path(work_root, 1))
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["generated"])
        self.assertTrue(result["validation_ok"])
        self.assertEqual(result["environment"], {"hostname": "worker-1"})
        self.assertEqual(loaded.metadata.instance_id, "rc-k03-n0002-seed1")
        generate.assert_called_once_with(family="rc", n=2, seed=1, num_colors=3)

    def test_run_instance_generation_passes_planned_num_colors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rcy_fast" / "s" / "rcy_fast-k04-n0002-seed1.json"
            plan_dir, _work_root = _write_plan(
                tmp_root,
                instance_path=instance_path,
                instance_id="rcy_fast-k04-n0002-seed1",
                family="rcy_fast",
                num_colors=4,
            )

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(
                    instance_id="rcy_fast-k04-n0002-seed1",
                    family="rcy_fast",
                    seed=1,
                    num_colors=4,
                ),
            ) as generate:
                run_instance_generation(plan_dir=plan_dir, index=1)

        generate.assert_called_once_with(family="rcy_fast", n=2, seed=1, num_colors=4)

    def test_run_instance_generation_skips_existing_valid_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json"
            save_instance(_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1), instance_path)
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch("three_col_circle_code.bench.generate_instance.generate_instance") as generate, patch(
                "three_col_circle_code.bench.generate_instance.validate_instance",
                wraps=validate_instance,
            ) as validate:
                result_path = run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["generated"])
        validate.assert_called_once()
        generate.assert_not_called()

    def test_run_instance_generation_skips_existing_col_with_native_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.col"
            instance_path.parent.mkdir(parents=True)
            instance_path.write_text("p edge 2 0\n", encoding="utf-8")
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                return_value=None,
            ) as validate, patch(
                "three_col_circle_code.bench.generate_instance.load_instance"
            ) as load_instance, patch(
                "three_col_circle_code.bench.generate_instance.generate_instance"
            ) as generate:
                result_path = run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["generated"])
        self.assertTrue(result["validation_ok"])
        validate.assert_called_once_with(instance_path)
        load_instance.assert_not_called()
        generate.assert_not_called()

    def test_run_instance_generation_generates_missing_col_with_native(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc_fast" / "s" / "rc_fast-k03-n0002-seed1.col"
            plan_dir, _work_root = _write_plan(
                tmp_root,
                instance_path=instance_path,
                instance_id="rc_fast-k03-n0002-seed1",
                family="rc_fast",
            )

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_col_with_native",
                return_value=None,
            ) as native_generate, patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                return_value=None,
            ) as validate, patch(
                "three_col_circle_code.bench.generate_instance.generate_instance"
            ) as generate:
                result_path = run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["generated"])
        self.assertTrue(result["validation_ok"])
        native_generate.assert_called_once_with(
            instance_path=instance_path,
            family="rc_fast",
            n=2,
            seed=1,
            num_colors=3,
            alpha=None,
            output_format="col",
        )
        validate.assert_called_once_with(instance_path, force=True)
        generate.assert_not_called()

    def test_run_instance_generation_marks_invalid_existing_col(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.col"
            instance_path.parent.mkdir(parents=True)
            instance_path.write_text("bad", encoding="utf-8")
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                side_effect=NativeInstanceInvalid("bad instance"),
            ), patch("three_col_circle_code.bench.generate_instance.generate_instance") as generate:
                result_path = run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "invalid")
        generate.assert_not_called()

    def test_run_instance_generation_force_rechecks_existing_instance_without_regenerating(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json"
            save_instance(_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1), instance_path)
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1),
            ) as generate:
                result_path = run_instance_generation(plan_dir=plan_dir, index=1, force=True)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "skipped")
        self.assertFalse(result["generated"])
        generate.assert_not_called()

    def test_run_instance_generation_regenerates_invalid_existing_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json"
            instance_path.parent.mkdir(parents=True)
            instance_path.write_text("{not json", encoding="utf-8")
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1),
            ):
                result_path = run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))
            loaded = load_instance(instance_path)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["generated"])
        self.assertEqual(loaded.metadata.instance_id, "rc-k03-n0002-seed1")

    def test_run_instance_generation_skips_completed_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json"
            plan_dir, work_root = _write_plan(tmp_root, instance_path=instance_path)
            result_path = instance_result_path(work_root, 1)
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "index": 1,
                        "status": "ok",
                        "instance_id": "rc-k03-n0002-seed1",
                        "instance_path": str(instance_path),
                    }
                ),
                encoding="utf-8",
            )

            with patch("three_col_circle_code.bench.generate_instance.generate_instance") as generate:
                returned = run_instance_generation(plan_dir=plan_dir, index=1)

        self.assertEqual(returned, result_path)
        generate.assert_not_called()

    def test_run_instance_generation_reruns_stale_completed_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json"
            plan_dir, work_root = _write_plan(tmp_root, instance_path=instance_path)
            result_path = instance_result_path(work_root, 1)
            result_path.parent.mkdir(parents=True)
            result_path.write_text(
                json.dumps(
                    {
                        "index": 1,
                        "status": "ok",
                        "instance_id": "old-instance",
                        "instance_path": str(instance_path),
                    }
                ),
                encoding="utf-8",
            )

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1),
            ) as generate:
                run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["instance_id"], "rc-k03-n0002-seed1")
        generate.assert_called_once()

    def test_run_instance_generation_rejects_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root = _write_plan(
                tmp_root,
                instance_path=tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json",
            )

            with self.assertRaisesRegex(ValueError, "does not contain index"):
                run_instance_generation(plan_dir=plan_dir, index=2)

    def test_cli_prints_result_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-k03-n0002-seed1.json"
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-k03-n0002-seed1", family="rc", seed=1),
            ):
                exit_code = main(["--plan-dir", str(plan_dir), "--index", "1"])
                instance_exists = instance_path.exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(instance_exists)

    def test_run_instance_sequence_generation_generates_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            rows = []
            for index, n in enumerate((100, 200, 300), start=1):
                instance_id = f"rcy_fast-k03-n{n:04d}-seed1"
                rows.append(
                    InstancePlanRow(
                        index=index,
                        instance_id=instance_id,
                        family="rcy_fast",
                        n=n,
                        seed=1,
                        num_colors=3,
                        sequence_id="seq-1",
                        instance_path=tmp_root / "instances" / "rcy_fast" / "s" / f"{instance_id}.circle",
                    )
                )
            plan_dir, work_root = _write_custom_plan(tmp_root, tuple(rows))

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_col_sequence_with_native",
                return_value=[],
            ) as native_sequence, patch(
                "three_col_circle_code.bench.generate_instance.inspect_col_with_native",
                return_value=None,
            ) as inspect, patch(
                "three_col_circle_code.bench.generate_instance.collect_environment_metadata",
                return_value={"hostname": "worker-1"},
            ):
                result_paths = run_instance_sequence_generation(plan_dir=plan_dir, index=1)

            results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]

        self.assertEqual(result_paths, [instance_result_path(work_root, index) for index in (1, 2, 3)])
        self.assertTrue(all(result["status"] == "ok" for result in results))
        self.assertTrue(all(result["generated"] for result in results))
        native_sequence.assert_called_once_with(
            output_dir=tmp_root / "instances",
            family="rcy_fast",
            start_n=100,
            stop_n=300,
            step_n=100,
            seed=1,
            num_colors=3,
            alpha=None,
            output_format="circle",
        )
        self.assertEqual(inspect.call_count, 3)

    def test_run_instance_sequence_generation_preserves_completed_prefix_on_native_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            rows = []
            for index, n in enumerate((100, 200, 300), start=1):
                instance_id = f"rc_fast-k03-n{n:04d}-seed1"
                rows.append(
                    InstancePlanRow(
                        index=index,
                        instance_id=instance_id,
                        family="rc_fast",
                        n=n,
                        seed=1,
                        num_colors=3,
                        sequence_id="seq-1",
                        instance_path=tmp_root / "instances" / "rc_fast" / "s" / f"{instance_id}.circle",
                    )
                )
            plan_dir, _work_root = _write_custom_plan(tmp_root, tuple(rows))

            def fail_after_first_artifact(**_kwargs: object) -> None:
                rows[0].instance_path.parent.mkdir(parents=True, exist_ok=True)
                rows[0].instance_path.write_text("p circle 100 3\n", encoding="utf-8")
                raise RuntimeError("failed to generate rc_fast vertex 200 after 10000 attempts")

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_col_sequence_with_native",
                side_effect=fail_after_first_artifact,
            ), patch(
                "three_col_circle_code.bench.generate_instance.inspect_col_with_native",
                return_value=None,
            ) as inspect, patch(
                "three_col_circle_code.bench.generate_instance.collect_environment_metadata",
                return_value={"hostname": "worker-1"},
            ):
                result_paths = run_instance_sequence_generation(plan_dir=plan_dir, index=1)

            results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]

        self.assertEqual([result["status"] for result in results], ["ok", "error", "error"])
        self.assertEqual([result["generated"] for result in results], [True, False, False])
        self.assertTrue(results[0]["validation_ok"])
        self.assertIsNone(results[0]["error"])
        self.assertIn("failed to generate rc_fast vertex 200", results[1]["error"])
        inspect.assert_called_once_with(rows[0].instance_path)

    def test_sequence_cli_prints_result_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            rows = []
            for index, n in enumerate((100, 200), start=1):
                instance_id = f"rc-k03-n{n:04d}-seed1"
                rows.append(
                    InstancePlanRow(
                        index=index,
                        instance_id=instance_id,
                        family="rc",
                        n=n,
                        seed=1,
                        num_colors=3,
                        sequence_id="seq-1",
                        instance_path=tmp_root / "instances" / "rc" / "s" / f"{instance_id}.circle",
                    )
                )
            plan_dir, _work_root = _write_custom_plan(tmp_root, tuple(rows))

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_col_sequence_with_native",
                return_value=[],
            ), patch(
                "three_col_circle_code.bench.generate_instance.ensure_validated_sidecar",
                return_value=None,
            ):
                exit_code = sequence_main(["--plan-dir", str(plan_dir), "--index", "1"])

        self.assertEqual(exit_code, 0)


def _write_plan(
    tmp_root: Path,
    *,
    instance_path: Path,
    instance_id: str = "rc-k03-n0002-seed1",
    family: str = "rc",
    num_colors: int = 3,
) -> tuple[Path, Path]:
    plan_dir = tmp_root / "plans" / "smoke"
    work_root = tmp_root / "work" / "smoke"
    output_format = instance_path.suffix.lstrip(".")
    if output_format not in {"col", "circle"}:
        output_format = "circle"
    write_instance_plan(
        plan_dir,
        (
            InstancePlanRow(
                index=1,
                instance_id=instance_id,
                family=family,
                n=2,
                seed=1,
                num_colors=num_colors,
                instance_path=instance_path,
                output_format=output_format,
            ),
        ),
    )
    write_plan_manifest(
        plan_dir,
        {
            "run_id": "smoke",
            "created_at": "2026-04-29T00:00:00+00:00",
            "work_root": work_root,
            "n_instances": 1,
            "n_trials": 0,
        },
    )
    return plan_dir, work_root


def _write_custom_plan(tmp_root: Path, rows: tuple[InstancePlanRow, ...]) -> tuple[Path, Path]:
    plan_dir = tmp_root / "plans" / "smoke"
    work_root = tmp_root / "work" / "smoke"
    write_instance_plan(plan_dir, rows)
    write_plan_manifest(
        plan_dir,
        {
            "run_id": "smoke",
            "created_at": "2026-04-29T00:00:00+00:00",
            "work_root": work_root,
            "n_instances": len(rows),
            "n_trials": 0,
        },
    )
    return plan_dir, work_root


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


if __name__ == "__main__":
    unittest.main()
