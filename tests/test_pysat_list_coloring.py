import sys
import unittest
from importlib.util import find_spec
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.sat.pysat_baseline import (
    build_reduced_list_coloring_cnf,
    solve_reduced_list_coloring_cnf,
)

HAS_PYSAT = find_spec("pysat") is not None


class PySatListColoringEncodingTests(unittest.TestCase):
    def test_build_reduced_list_coloring_cnf_uses_only_allowed_colors(self):
        cnf = build_reduced_list_coloring_cnf(
            active_vertices_mask=0b11,
            neighbor_indices=((1,), (0,)),
            allowed_color_masks=(0b011, 0b110),
            num_colors=3,
        )

        self.assertEqual(cnf.n_vars, 4)
        self.assertEqual(cnf.n_clauses, 3)
        self.assertEqual(cnf.clauses[0], [1, 2])
        self.assertEqual(cnf.clauses[1], [3, 4])
        self.assertEqual(cnf.clauses[2], [-2, -3])
        self.assertNotIn((0, 2), cnf.var_map)
        self.assertNotIn((1, 0), cnf.var_map)

    def test_build_reduced_list_coloring_cnf_emits_empty_clause_for_empty_domain(self):
        cnf = build_reduced_list_coloring_cnf(
            active_vertices_mask=0b1,
            neighbor_indices=((),),
            allowed_color_masks=(0,),
            num_colors=3,
        )

        self.assertEqual(cnf.n_vars, 0)
        self.assertEqual(cnf.clauses, [[]])

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the PySAT list-coloring tests")
    def test_solve_reduced_list_coloring_cnf_detects_unsat_state(self):
        is_sat = solve_reduced_list_coloring_cnf(
            active_vertices_mask=0b11,
            neighbor_indices=((1,), (0,)),
            allowed_color_masks=(0b001, 0b001),
            num_colors=3,
        )

        self.assertFalse(is_sat)

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the PySAT list-coloring tests")
    def test_solve_reduced_list_coloring_cnf_detects_sat_state(self):
        is_sat = solve_reduced_list_coloring_cnf(
            active_vertices_mask=0b11,
            neighbor_indices=((1,), (0,)),
            allowed_color_masks=(0b001, 0b110),
            num_colors=3,
        )

        self.assertTrue(is_sat)


if __name__ == "__main__":
    unittest.main()
