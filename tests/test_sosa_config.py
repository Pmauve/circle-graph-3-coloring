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
                "num_colors": 3,
                "produce_witness": True,
            },
        )

    def test_accepts_explicit_config(self) -> None:
        config = SosaConfig.from_mapping(
            {
                "base_case_n": 5,
                "base_case_algorithm": "sat",
                "num_colors": 4,
                "produce_witness": False,
            }
        )

        self.assertEqual(
            config,
            SosaConfig(
                base_case_n=5,
                base_case_algorithm="sat",
                num_colors=4,
                produce_witness=False,
            ),
        )

    def test_rejects_invalid_algorithm(self) -> None:
        with self.assertRaisesRegex(ValueError, "base_case_algorithm"):
            SosaConfig.from_mapping({"base_case_algorithm": "oracle"})

    def test_rejects_negative_base_case_n(self) -> None:
        with self.assertRaisesRegex(ValueError, "base_case_n"):
            SosaConfig.from_mapping({"base_case_n": -1})

    def test_rejects_invalid_num_colors(self) -> None:
        with self.assertRaisesRegex(ValueError, "num_colors"):
            SosaConfig.from_mapping({"num_colors": 0})

    def test_rejects_non_boolean_produce_witness(self) -> None:
        with self.assertRaisesRegex(ValueError, "produce_witness"):
            SosaConfig.from_mapping({"produce_witness": "false"})

    def test_rejects_unsupported_aliases(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported SOSA parameter"):
            SosaConfig.from_mapping({"k": 4})
        with self.assertRaisesRegex(ValueError, "unsupported SOSA parameter"):
            SosaConfig.from_mapping({"witness": False})
        with self.assertRaisesRegex(ValueError, "unsupported SOSA parameter"):
            SosaConfig.from_mapping({"brute_force_cutoff": 6})


if __name__ == "__main__":
    unittest.main()
