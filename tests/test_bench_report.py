import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.report import build_benchmark_report
from three_col_circle_code.bench.report_data import (
    SUMMARY_BY_BUCKET_FILENAME,
    SUMMARY_BY_N_FILENAME,
    SUMMARY_OVERALL_FILENAME,
    load_benchmark_report_data,
    solver_variant_label,
    write_summary_csvs,
)
from three_col_circle_code.bench.report_html import render_report_html
from three_col_circle_code.bench.report_plots import runtime_vs_size_figure, solver_target_color
from three_col_circle_code.bench.results import MANIFEST_FILENAME, RESULTS_FILENAME


class BenchReportDataTests(unittest.TestCase):
    def test_load_benchmark_report_data_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _write_sample_run(Path(tmpdir) / "sample-run", with_manifest=False)

            data = load_benchmark_report_data(run_dir)

        self.assertFalse(data.metadata.manifest_present)
        self.assertEqual(data.metadata.run_id, "sample-run")
        self.assertEqual(data.metadata.n_instances, 2)
        self.assertEqual(
            data.metadata.solver_targets,
            (
                "sat-baseline:pysat-cadical",
                "sosa-3-col-exact [base_case_n=64]",
                "sosa-3-col-exact [base_case_n=8]",
            ),
        )
        self.assertEqual(data.headline_metrics.n_unanimous_agreements, 1)
        self.assertEqual(data.headline_metrics.n_disagreements, 1)

    def test_load_benchmark_report_data_with_manifest_enriches_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _write_sample_run(Path(tmpdir) / "sample-run", with_manifest=True)

            data = load_benchmark_report_data(run_dir)

        self.assertTrue(data.metadata.manifest_present)
        self.assertEqual(data.metadata.run_id, "sample-run")
        self.assertEqual(data.metadata.created_at, "2026-04-17T12:00:00+00:00")
        self.assertEqual(data.metadata.n_instances, 2)
        self.assertEqual(data.metadata.n_tasks, 6)
        self.assertEqual(data.headline_metrics.n_ok, 5)
        self.assertEqual(data.headline_metrics.n_error, 1)
        self.assertEqual(data.headline_metrics.n_invalid, 0)
        self.assertEqual(data.headline_metrics.best_median_runtime_solver_target, "sosa-3-col-exact [base_case_n=64]")
        self.assertEqual(len(data.disagreement_rows), 1)
        disagreement = data.disagreement_rows[0]
        self.assertEqual(disagreement.instance_id, "rcy_fast-k03-n0003-seed2")
        self.assertEqual({label for label, _ in disagreement.statuses}, set(data.metadata.solver_targets))

    def test_write_summary_csvs_matches_expected_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _write_summary_run(Path(tmpdir) / "summary-run")

            write_summary_csvs(run_dir)

            by_n_rows = _read_csv_rows(run_dir / SUMMARY_BY_N_FILENAME)
            by_bucket_rows = _read_csv_rows(run_dir / SUMMARY_BY_BUCKET_FILENAME)
            overall_rows = _read_csv_rows(run_dir / SUMMARY_OVERALL_FILENAME)

        self.assertEqual(len(by_n_rows), 4)
        rc_sat = next(
            row
            for row in by_n_rows
            if row["family"] == "rc" and row["solver_target"] == "sat-baseline:pysat-cadical"
        )
        self.assertEqual(rc_sat["n_instances"], "2")
        self.assertEqual(rc_sat["n_ok"], "2")
        self.assertEqual(rc_sat["n_error"], "0")
        self.assertEqual(rc_sat["n_invalid"], "0")
        self.assertEqual(rc_sat["repetitions"], "2")
        self.assertEqual(rc_sat["ok_repetitions"], "2")
        self.assertEqual(rc_sat["mean_wall_time_s"], "2.0")
        self.assertEqual(rc_sat["median_wall_time_s"], "2.0")

        rc_sosa_small = next(
            row
            for row in by_bucket_rows
            if row["family"] == "rc" and row["solver_target"] == "sosa-3-col-exact [base_case_n=8]"
        )
        self.assertEqual(rc_sosa_small["n_error"], "1")
        self.assertEqual(rc_sosa_small["mean_wall_time_s"], "")

        rc_sosa_large = next(
            row
            for row in by_bucket_rows
            if row["family"] == "rc" and row["solver_target"] == "sosa-3-col-exact [base_case_n=64]"
        )
        self.assertEqual(rc_sosa_large["n_ok"], "1")
        self.assertEqual(rc_sosa_large["median_wall_time_s"], "2.0")

        invalid_overall = next(
            row
            for row in overall_rows
            if row["family"] == "" and row["solver_target"] == "sosa-3-col-exact [base_case_n=8]"
        )
        self.assertEqual(invalid_overall["n_invalid"], "1")

    def test_solver_variant_label_sorts_params_stably(self) -> None:
        self.assertEqual(
            solver_variant_label("sosa-3-col-exact", {"beta": 2, "alpha": 1}),
            "sosa-3-col-exact [alpha=1, beta=2]",
        )

    def test_solver_variant_label_uses_explicit_label(self) -> None:
        self.assertEqual(
            solver_variant_label("sosa-3-col-exact", {"base_case_n": 8}, "SOSA backtracking"),
            "SOSA backtracking",
        )

    def test_load_benchmark_report_data_uses_manifest_and_row_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "labeled-run"
            run_dir.mkdir()
            row = {
                "run_id": "labeled-run",
                "instance_id": "rc-k03-n0002-seed1",
                "instance_path": "instance.json",
                "family": "rc",
                "bucket": "s",
                "n": 2,
                "m": 1,
                "seed": 1,
                "source": "generated",
                "solver_target": "sosa-3-col-exact",
                "solver": "sosa-3-col-exact",
                "backend": None,
                "solver_params": {"base_case_n": 8},
                "solver_label": "SOSA backtracking",
                "status": "ok",
                "wall_time_s": 1.0,
                "is_colorable": True,
                "validation_ok": True,
                "validation_errors": [],
                "details": {},
                "error": None,
            }
            manifest = {
                "run_id": "labeled-run",
                "created_at": "2026-04-17T12:00:00+00:00",
                "solvers": [
                    {
                        "target": "sosa-3-col-exact",
                        "label": "SOSA backtracking",
                        "params": {"base_case_n": 8},
                    }
                ],
                "n_instances": 1,
                "n_tasks": 1,
                "environment": {},
            }
            (run_dir / RESULTS_FILENAME).write_text(json.dumps(row) + "\n", encoding="utf-8")
            (run_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")

            data = load_benchmark_report_data(run_dir)

        self.assertEqual(data.metadata.solver_targets, ("SOSA backtracking",))
        self.assertEqual(data.solver_summary_rows[0].solver_target, "SOSA backtracking")

    def test_load_benchmark_report_data_dedupes_duplicate_task_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _write_duplicate_row_run(Path(tmpdir) / "duplicate-run")

            data = load_benchmark_report_data(run_dir)

        self.assertEqual(len(data.rows), 3)
        self.assertEqual(data.headline_metrics.total_rows, 3)
        self.assertEqual(data.headline_metrics.n_unanimous_agreements, 1)
        self.assertEqual(data.headline_metrics.n_disagreements, 0)
        self.assertEqual(len(data.solver_summary_rows), 3)
        sosa_small = next(
            row for row in data.solver_summary_rows if row.solver_target == "sosa-3-col-exact [base_case_n=8]"
        )
        self.assertEqual(sosa_small.n_rows, 1)
        self.assertEqual(sosa_small.median_wall_time_s, 9.0)


class BenchReportHtmlTests(unittest.TestCase):
    def test_runtime_vs_size_figure_exposes_family_and_y_axis_controls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _write_sample_run(Path(tmpdir) / "sample-run", with_manifest=True)
            data = load_benchmark_report_data(run_dir)

        figure = runtime_vs_size_figure(data)

        self.assertEqual(figure.layout.yaxis.type, "log")
        self.assertEqual(len(figure.layout.updatemenus), 2)
        self.assertEqual(figure.layout.updatemenus[0].buttons[0].label, "All families")
        self.assertEqual(figure.layout.updatemenus[1].buttons[0].label, "Linear")
        self.assertEqual(figure.layout.updatemenus[1].buttons[1].label, "Log")
        self.assertIsNone(figure.layout.title.text)
        self.assertEqual(figure.layout.updatemenus[0].y, 1.16)
        self.assertEqual(figure.layout.updatemenus[1].y, 1.16)
        self.assertEqual(figure.layout.legend.orientation, "h")
        self.assertEqual(figure.layout.legend.y, -0.22)
        self.assertEqual(figure.layout.margin.t, 96)
        self.assertEqual(figure.layout.margin.b, 112)
        self.assertEqual(
            tuple(annotation.text for annotation in figure.layout.annotations),
            ("Family", "Y scale"),
        )

    def test_render_report_html_contains_key_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _write_sample_run(Path(tmpdir) / "sample-run", with_manifest=True)
            data = load_benchmark_report_data(run_dir)

        html = render_report_html(
            data=data,
            runtime_vs_size_figure=runtime_vs_size_figure(data),
        )

        self.assertIn("Headline Stats", html)
        self.assertIn("Runtime vs Size", html)
        self.assertIn("Solver Summary", html)
        self.assertIn("Disagreements", html)
        self.assertIn("Plotly.newPlot", html)
        self.assertIn(solver_target_color("sosa-3-col-exact [base_case_n=8]"), html)
        self.assertIn(solver_target_color("sosa-3-col-exact [base_case_n=64]"), html)
        self.assertIn("rcy_fast", html)
        self.assertIn("All families", html)
        self.assertIn("Y scale", html)
        self.assertNotIn("X scale", html)
        self.assertIn("sosa-3-col-exact [base_case_n=8]", html)
        self.assertIn("sosa-3-col-exact [base_case_n=64]", html)
        self.assertIn("solver_params", html)
        self.assertIn("scrollZoom", html)
        self.assertIn("displayModeBar", html)

    def test_solver_target_color_is_deterministic(self) -> None:
        self.assertEqual(
            solver_target_color("sosa-3-col-exact [base_case_n=8]"),
            solver_target_color("sosa-3-col-exact [base_case_n=8]"),
        )
        self.assertNotEqual(
            solver_target_color("sosa-3-col-exact [base_case_n=8]"),
            solver_target_color("sosa-3-col-exact [base_case_n=64]"),
        )


class BenchReportBuildTests(unittest.TestCase):
    def test_build_benchmark_report_writes_default_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = _write_sample_run(Path(tmpdir) / "sample-run", with_manifest=True)

            output_path = build_benchmark_report(run_dir)
            exists = output_path.exists()
            output_name = output_path.name

        self.assertEqual(output_name, "report.html")
        self.assertTrue(exists)

    def test_build_benchmark_report_supports_explicit_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            run_dir = _write_sample_run(tmp_root / "sample-run", with_manifest=True)
            explicit_output = tmp_root / "reports" / "custom-report.html"

            output_path = build_benchmark_report(run_dir, explicit_output)
            has_explicit_report = explicit_output.exists()

        self.assertEqual(output_path, explicit_output)
        self.assertTrue(has_explicit_report)


def _write_sample_run(run_dir: Path, *, with_manifest: bool) -> Path:
    run_dir.mkdir(parents=True, exist_ok=False)
    rows = [
        {
            "run_id": "sample-run",
            "instance_id": "rc-k03-n0002-seed1",
            "instance_path": str(run_dir / ".." / "instances" / "rc-k03-n0002-seed1.json"),
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sat-baseline:pysat-cadical",
            "solver": "sat-baseline",
            "backend": "pysat-cadical",
            "solver_params": {},
            "status": "ok",
            "wall_time_s": 1.0,
            "is_colorable": True,
            "validation_ok": True,
            "validation_errors": [],
            "details": {},
            "error": None,
        },
        {
            "run_id": "sample-run",
            "instance_id": "rc-k03-n0002-seed1",
            "instance_path": str(run_dir / ".." / "instances" / "rc-k03-n0002-seed1.json"),
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 8},
            "status": "ok",
            "wall_time_s": 2.0,
            "is_colorable": True,
            "validation_ok": True,
            "validation_errors": [],
            "details": {},
            "error": None,
        },
        {
            "run_id": "sample-run",
            "instance_id": "rc-k03-n0002-seed1",
            "instance_path": str(run_dir / ".." / "instances" / "rc-k03-n0002-seed1.json"),
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 64},
            "status": "ok",
            "wall_time_s": 0.8,
            "is_colorable": True,
            "validation_ok": True,
            "validation_errors": [],
            "details": {},
            "error": None,
        },
        {
            "run_id": "sample-run",
            "instance_id": "rcy_fast-k03-n0003-seed2",
            "instance_path": str(run_dir / ".." / "instances" / "rcy_fast-k03-n0003-seed2.json"),
            "family": "rcy_fast",
            "bucket": "s",
            "n": 3,
            "m": 2,
            "seed": 2,
            "source": "generated",
            "solver_target": "sat-baseline:pysat-cadical",
            "solver": "sat-baseline",
            "backend": "pysat-cadical",
            "solver_params": {},
            "status": "ok",
            "wall_time_s": 1.5,
            "is_colorable": False,
            "validation_ok": True,
            "validation_errors": [],
            "details": {},
            "error": None,
        },
        {
            "run_id": "sample-run",
            "instance_id": "rcy_fast-k03-n0003-seed2",
            "instance_path": str(run_dir / ".." / "instances" / "rcy_fast-k03-n0003-seed2.json"),
            "family": "rcy_fast",
            "bucket": "s",
            "n": 3,
            "m": 2,
            "seed": 2,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 8},
            "status": "error",
            "wall_time_s": None,
            "is_colorable": None,
            "validation_ok": True,
            "validation_errors": [],
            "details": {},
            "error": "solver failed",
        },
        {
            "run_id": "sample-run",
            "instance_id": "rcy_fast-k03-n0003-seed2",
            "instance_path": str(run_dir / ".." / "instances" / "rcy_fast-k03-n0003-seed2.json"),
            "family": "rcy_fast",
            "bucket": "s",
            "n": 3,
            "m": 2,
            "seed": 2,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 64},
            "status": "ok",
            "wall_time_s": 1.2,
            "is_colorable": False,
            "validation_ok": True,
            "validation_errors": [],
            "details": {},
            "error": None,
        },
    ]
    (run_dir / RESULTS_FILENAME).write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    if with_manifest:
        manifest = {
            "run_id": "sample-run",
            "created_at": "2026-04-17T12:00:00+00:00",
            "solvers": [
                {"target": "sat-baseline:pysat-cadical", "params": {}},
                {"target": "sosa-3-col-exact", "params": {"base_case_n": 8}},
                {"target": "sosa-3-col-exact", "params": {"base_case_n": 64}},
            ],
            "n_instances": 2,
            "n_tasks": 6,
            "environment": {"python_version": "test"},
        }
        (run_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def _write_summary_run(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=False)
    rows = [
        {
            "instance_id": "a",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "solver_target": "sat-baseline:pysat-cadical",
            "solver_params": {},
            "status": "ok",
            "wall_time_s": 1.0,
        },
        {
            "instance_id": "b",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "solver_target": "sat-baseline:pysat-cadical",
            "solver_params": {},
            "status": "ok",
            "wall_time_s": 3.0,
        },
        {
            "instance_id": "c",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "solver_target": "sosa-3-col-exact",
            "solver_params": {"base_case_n": 8},
            "status": "error",
            "wall_time_s": None,
        },
        {
            "instance_id": "d",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "solver_target": "sosa-3-col-exact",
            "solver_params": {"base_case_n": 64},
            "status": "ok",
            "wall_time_s": 2.0,
        },
        {
            "instance_id": "broken",
            "family": None,
            "bucket": None,
            "n": None,
            "solver_target": "sosa-3-col-exact",
            "solver_params": {"base_case_n": 8},
            "status": "invalid",
            "wall_time_s": None,
        },
    ]
    (run_dir / RESULTS_FILENAME).write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return run_dir


def _write_duplicate_row_run(run_dir: Path) -> Path:
    run_dir.mkdir(parents=True, exist_ok=False)
    rows = [
        {
            "run_id": "duplicate-run",
            "instance_id": "rc-k03-n0002-seed1",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sat-baseline:pysat-cadical",
            "solver": "sat-baseline",
            "backend": "pysat-cadical",
            "solver_params": {},
            "status": "ok",
            "wall_time_s": 1.0,
            "is_colorable": True,
            "validation_ok": True,
            "error": None,
        },
        {
            "run_id": "duplicate-run",
            "instance_id": "rc-k03-n0002-seed1",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 8},
            "status": "ok",
            "wall_time_s": 2.0,
            "is_colorable": True,
            "validation_ok": True,
            "error": None,
        },
        {
            "run_id": "duplicate-run",
            "instance_id": "rc-k03-n0002-seed1",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 8},
            "status": "ok",
            "wall_time_s": 9.0,
            "is_colorable": True,
            "validation_ok": True,
            "error": None,
        },
        {
            "run_id": "duplicate-run",
            "instance_id": "rc-k03-n0002-seed1",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 64},
            "status": "ok",
            "wall_time_s": 0.8,
            "is_colorable": True,
            "validation_ok": True,
            "error": None,
        },
    ]
    (run_dir / RESULTS_FILENAME).write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "run_id": "duplicate-run",
        "created_at": "2026-04-20T12:00:00+00:00",
        "solvers": [
            {"target": "sat-baseline:pysat-cadical", "params": {}},
            {"target": "sosa-3-col-exact", "params": {"base_case_n": 8}},
            {"target": "sosa-3-col-exact", "params": {"base_case_n": 64}},
        ],
        "n_instances": 1,
        "n_tasks": 3,
        "environment": {"python_version": "test"},
    }
    (run_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def _write_untimed_solver_run(run_dir: Path) -> Path:
    run_dir = _write_sample_run(run_dir, with_manifest=True)
    rows = [
        {
            "run_id": "untimed-run",
            "instance_id": "rc-k03-n0002-seed1",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sat-baseline:pysat-cadical",
            "solver": "sat-baseline",
            "backend": "pysat-cadical",
            "solver_params": {},
            "status": "ok",
            "wall_time_s": 1.0,
            "is_colorable": True,
            "validation_ok": True,
            "error": None,
        },
        {
            "run_id": "untimed-run",
            "instance_id": "rc-k03-n0002-seed1",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 8},
            "status": "error",
            "wall_time_s": None,
            "is_colorable": None,
            "validation_ok": True,
            "error": "solver failed",
        },
        {
            "run_id": "untimed-run",
            "instance_id": "rc-k03-n0002-seed1",
            "family": "rc",
            "bucket": "s",
            "n": 2,
            "m": 1,
            "seed": 1,
            "source": "generated",
            "solver_target": "sosa-3-col-exact",
            "solver": "sosa-3-col-exact",
            "backend": None,
            "solver_params": {"base_case_n": 64},
            "status": "ok",
            "wall_time_s": 0.8,
            "is_colorable": True,
            "validation_ok": True,
            "error": None,
        },
    ]
    (run_dir / RESULTS_FILENAME).write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "run_id": "untimed-run",
        "created_at": "2026-04-17T12:00:00+00:00",
        "solvers": [
            {"target": "sat-baseline:pysat-cadical", "params": {}},
            {"target": "sosa-3-col-exact", "params": {"base_case_n": 8}},
            {"target": "sosa-3-col-exact", "params": {"base_case_n": 64}},
        ],
        "n_instances": 1,
        "n_tasks": 3,
        "environment": {"python_version": "test"},
    }
    (run_dir / MANIFEST_FILENAME).write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as infile:
        return list(csv.DictReader(infile))


if __name__ == "__main__":
    unittest.main()
