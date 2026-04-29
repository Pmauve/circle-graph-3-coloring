import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.generate_instance import main, run_instance_generation
from three_col_circle_code.bench.plan_io import (
    InstancePlanRow,
    instance_result_path,
    write_instance_plan,
    write_plan_manifest,
)
from three_col_circle_code.instances.io import load_instance, save_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.instances.validate import validate_instance


class BenchGenerateInstanceTests(unittest.TestCase):
    def test_run_instance_generation_generates_missing_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
            plan_dir, work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
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
        self.assertEqual(loaded.metadata.instance_id, "rc-n0002-seed1")
        generate.assert_called_once_with(family="rc", n=2, seed=1)

    def test_run_instance_generation_skips_existing_valid_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)
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

    def test_run_instance_generation_force_regenerates_existing_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
            save_instance(_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1), instance_path)
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ) as generate:
                result_path = run_instance_generation(plan_dir=plan_dir, index=1, force=True)

            result = json.loads(result_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["generated"])
        generate.assert_called_once()

    def test_run_instance_generation_regenerates_invalid_existing_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
            instance_path.parent.mkdir(parents=True)
            instance_path.write_text("{not json", encoding="utf-8")
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ):
                result_path = run_instance_generation(plan_dir=plan_dir, index=1)

            result = json.loads(result_path.read_text(encoding="utf-8"))
            loaded = load_instance(instance_path)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["generated"])
        self.assertEqual(loaded.metadata.instance_id, "rc-n0002-seed1")

    def test_run_instance_generation_skips_completed_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
            plan_dir, work_root = _write_plan(tmp_root, instance_path=instance_path)
            result_path = instance_result_path(work_root, 1)
            result_path.parent.mkdir(parents=True)
            result_path.write_text('{"status": "ok"}', encoding="utf-8")

            with patch("three_col_circle_code.bench.generate_instance.generate_instance") as generate:
                returned = run_instance_generation(plan_dir=plan_dir, index=1)

        self.assertEqual(returned, result_path)
        generate.assert_not_called()

    def test_run_instance_generation_rejects_missing_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            plan_dir, _work_root = _write_plan(
                tmp_root,
                instance_path=tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json",
            )

            with self.assertRaisesRegex(ValueError, "does not contain index"):
                run_instance_generation(plan_dir=plan_dir, index=2)

    def test_cli_prints_result_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            instance_path = tmp_root / "instances" / "rc" / "s" / "rc-n0002-seed1.json"
            plan_dir, _work_root = _write_plan(tmp_root, instance_path=instance_path)

            with patch(
                "three_col_circle_code.bench.generate_instance.generate_instance",
                return_value=_build_record(instance_id="rc-n0002-seed1", family="rc", seed=1),
            ):
                exit_code = main(["--plan-dir", str(plan_dir), "--index", "1"])
                instance_exists = instance_path.exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(instance_exists)


def _write_plan(tmp_root: Path, *, instance_path: Path) -> tuple[Path, Path]:
    plan_dir = tmp_root / "plans" / "smoke"
    work_root = tmp_root / "work" / "smoke"
    write_instance_plan(
        plan_dir,
        (
            InstancePlanRow(
                index=1,
                instance_id="rc-n0002-seed1",
                family="rc",
                n=2,
                seed=1,
                instance_path=instance_path,
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


if __name__ == "__main__":
    unittest.main()
