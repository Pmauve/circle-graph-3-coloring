import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.planning import (
    expected_instance_path,
    prepare_run_directory,
    resolve_existing_instance_path,
)
from three_col_circle_code.bench.specs import normalize_run_spec


class BenchPlanningTests(unittest.TestCase):
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

        self.assertEqual(path, Path("eval/instances/rc/s/rc-k03-n0002-seed1.col"))

    def test_resolve_existing_instance_path_finds_legacy_nested_name(self) -> None:
        with _temporary_run_dir() as instance_root:
            run_spec = normalize_run_spec(
                {
                    "instance_pool_root": str(instance_root),
                    "instances": [{"family": "rc_fast", "n_values": [200], "seeds": [42]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                }
            )
            legacy_path = instance_root / "rc_fast" / "s" / "rc_fast-n0200-seed42.col"
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_text("", encoding="utf-8")

            path, resolution = resolve_existing_instance_path(
                instance_pool_root=instance_root,
                request=run_spec.instance_requests[0],
            )

        self.assertEqual(path, legacy_path)
        self.assertEqual(resolution, "nested-legacy")

    def test_resolve_existing_instance_path_prefers_canonical_name(self) -> None:
        with _temporary_run_dir() as instance_root:
            run_spec = normalize_run_spec(
                {
                    "instance_pool_root": str(instance_root),
                    "instances": [{"family": "rc_fast", "n_values": [200], "seeds": [42]}],
                    "solvers": [{"target": "sosa-3-col-exact"}],
                }
            )
            canonical_path = instance_root / "rc_fast" / "s" / "rc_fast-k03-n0200-seed42.col"
            legacy_path = instance_root / "rc_fast" / "s" / "rc_fast-n0200-seed42.col"
            canonical_path.parent.mkdir(parents=True)
            canonical_path.write_text("", encoding="utf-8")
            legacy_path.write_text("", encoding="utf-8")

            path, resolution = resolve_existing_instance_path(
                instance_pool_root=instance_root,
                request=run_spec.instance_requests[0],
            )

        self.assertEqual(path, canonical_path)
        self.assertEqual(resolution, "nested-canonical")

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
