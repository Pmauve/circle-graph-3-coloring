import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.generation.color_utils import (
    available_color_mask,
    available_colors,
    color_bit,
    colors_from_mask,
    full_color_mask,
    validate_num_colors,
)


class GenerationColorUtilsTests(unittest.TestCase):
    def test_validate_num_colors_accepts_positive_palette_sizes(self) -> None:
        for num_colors in (1, 3, 4):
            validate_num_colors(num_colors)

    def test_validate_num_colors_rejects_non_positive_palette_sizes(self) -> None:
        for num_colors in (0, -1):
            with self.assertRaisesRegex(ValueError, "num_colors"):
                validate_num_colors(num_colors)

    def test_color_bit_uses_one_based_color_identifiers(self) -> None:
        self.assertEqual(color_bit(1), 1)
        self.assertEqual(color_bit(2), 2)
        self.assertEqual(color_bit(3), 4)

    def test_full_color_mask_contains_palette_colors(self) -> None:
        self.assertEqual(full_color_mask(1), 0b1)
        self.assertEqual(full_color_mask(3), 0b111)
        self.assertEqual(full_color_mask(5), 0b11111)

    def test_available_colors_returns_all_colors_without_neighbors(self) -> None:
        self.assertEqual(available_colors({}, (), 3), (1, 2, 3))

    def test_available_colors_excludes_neighbor_colors(self) -> None:
        colors = {10: 1, 11: 3}

        self.assertEqual(available_colors(colors, (10, 11), 4), (2, 4))
        self.assertEqual(available_color_mask(colors, (10, 11), 4), 0b1010)

    def test_available_colors_supports_larger_palettes(self) -> None:
        colors = {0: 2, 1: 5}

        self.assertEqual(available_colors(colors, (0, 1), 5), (1, 3, 4))

    def test_available_colors_rejects_colors_outside_palette(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside palette"):
            available_colors({0: 4}, (0,), 3)

    def test_colors_from_mask_returns_ascending_one_based_colors(self) -> None:
        self.assertEqual(colors_from_mask(0b10101, 5), (1, 3, 5))


if __name__ == "__main__":
    unittest.main()
