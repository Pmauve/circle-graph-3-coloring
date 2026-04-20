import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.sosa.config import SosaConfig


class SosaConfigTests(unittest.TestCase):
    def test_defaults_to_flat_backtracking_config(self) -> None:
        config = SosaConfig.from_mapping()

        self.assertEqual(
            config.to_dict(),
            {
                "base_case_n": 8,
                "base_case_algorithm": "backtracking",
            },
        )

    def test_accepts_explicit_algorithm(self) -> None:
        config = SosaConfig.from_mapping(
            {
                "base_case_n": 5,
                "base_case_algorithm": "sat",
            }
        )

        self.assertEqual(
            config,
            SosaConfig(
                base_case_n=5,
                base_case_algorithm="sat",
            ),
        )

    def test_legacy_cutoff_name_still_works(self) -> None:
        config = SosaConfig.from_mapping({"brute_force_cutoff": 6})

        self.assertEqual(config.base_case_n, 6)
        self.assertEqual(config.base_case_algorithm, "backtracking")

    def test_rejects_invalid_algorithm(self) -> None:
        with self.assertRaisesRegex(ValueError, "base_case_algorithm"):
            SosaConfig.from_mapping({"base_case_algorithm": "oracle"})

    def test_rejects_negative_base_case_n(self) -> None:
        with self.assertRaisesRegex(ValueError, "base_case_n"):
            SosaConfig.from_mapping({"base_case_n": -1})


if __name__ == "__main__":
    unittest.main()
