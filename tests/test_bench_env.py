import sys
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.bench.env import DEFAULT_PACKAGES, collect_environment_metadata


class BenchEnvTests(unittest.TestCase):
    def test_collect_environment_metadata_has_core_fields(self) -> None:
        metadata = collect_environment_metadata(package_names=("networkx",))

        self.assertIn("collected_at", metadata)
        self.assertIn("python_version", metadata)
        self.assertIn("platform", metadata)
        self.assertIn("hostname", metadata)
        self.assertIn("package_versions", metadata)
        self.assertIn("networkx", metadata["package_versions"])

    def test_default_packages_include_python_sat(self) -> None:
        self.assertIn("python-sat", DEFAULT_PACKAGES)

    def test_collect_environment_metadata_runs_git_commands_in_repo_root(self) -> None:
        repo_root = Path("C:/repo")

        with patch(
            "three_col_circle_code.bench.env.subprocess.run",
            side_effect=[
                CompletedProcess(args=["git"], returncode=0, stdout="abc123\n"),
                CompletedProcess(args=["git"], returncode=0, stdout=""),
            ],
        ) as run:
            metadata = collect_environment_metadata(package_names=(), repo_root=repo_root)

        self.assertEqual(metadata["git_root"], str(repo_root))
        self.assertEqual(metadata["git_commit"], "abc123")
        self.assertFalse(metadata["git_dirty"])
        self.assertEqual(run.call_args_list[0].kwargs["cwd"], str(repo_root))
        self.assertEqual(run.call_args_list[1].kwargs["cwd"], str(repo_root))


if __name__ == "__main__":
    unittest.main()
