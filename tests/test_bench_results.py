import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.results import (
    DEFAULT_RUNS_ROOT,
    RESULTS_FILENAME,
    MANIFEST_FILENAME,
    append_result,
    normalize_run_label,
    write_manifest,
)


class BenchResultsTests(unittest.TestCase):
    def test_normalize_run_label_sanitizes_human_text(self) -> None:
        self.assertEqual(normalize_run_label("rcy s+m / MathSAT"), "rcy-s-m-MathSAT")

    def test_write_manifest_writes_pretty_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run"
            run_dir.mkdir()
            manifest_path = write_manifest(run_dir, {"run_id": "abc", "solvers": ["pysmt-msat"]})
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest_path.name, MANIFEST_FILENAME)
        self.assertEqual(payload["run_id"], "abc")

    def test_append_result_appends_jsonl_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run"
            run_dir.mkdir()
            append_result(run_dir, {"instance_id": "a", "status": "ok"})
            append_result(run_dir, {"instance_id": "b", "status": "timeout"})
            lines = (run_dir / RESULTS_FILENAME).read_text(encoding="utf-8").strip().splitlines()

        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["instance_id"], "a")
        self.assertEqual(json.loads(lines[1])["status"], "timeout")

    def test_default_runs_root_points_to_eval_runs(self) -> None:
        self.assertEqual(DEFAULT_RUNS_ROOT.as_posix(), "eval/runs")


if __name__ == "__main__":
    unittest.main()
