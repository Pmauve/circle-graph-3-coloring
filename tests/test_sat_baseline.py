import sys
import unittest
from importlib.util import find_spec
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.sat.baseline import (
    LEGACY_PYSMT_MSAT,
    PYSAT_CADICAL,
    PYSAT_KISSAT404,
    solve_3color_baseline,
)

HAS_PYSMT = find_spec("pysmt") is not None
HAS_PYSAT = find_spec("pysat") is not None
try:
    from pysat.solvers import Kissat404  # noqa: F401
except ImportError:
    HAS_PYSAT_KISSAT = False
else:
    HAS_PYSAT_KISSAT = True

if HAS_PYSMT:
    from three_col_circle_code.sat_builder import is_three_colorable


class SatBaselineTests(unittest.TestCase):
    def test_unknown_backend_fails_clearly(self):
        graph = nx.path_graph(2)

        with self.assertRaises(ValueError):
            solve_3color_baseline(graph, backend="unknown-backend")

    @unittest.skipUnless(HAS_PYSAT_KISSAT, "python-sat with Kissat404 support is required")
    def test_kissat_backend_solves_small_sat_instance(self):
        graph = nx.path_graph(2)

        result = solve_3color_baseline(graph, backend=PYSAT_KISSAT404)

        self.assertTrue(result.is_sat)
        self.assertEqual(result.backend, PYSAT_KISSAT404)
        self.assertEqual(result.n_vertices, 2)
        self.assertEqual(result.m_edges, 1)
        self.assertGreaterEqual(result.elapsed_time, 0.0)

    @unittest.skipUnless(HAS_PYSAT_KISSAT, "python-sat with Kissat404 support is required")
    def test_kissat_backend_solves_small_unsat_instance(self):
        graph = nx.complete_graph(4)

        result = solve_3color_baseline(graph, backend=PYSAT_KISSAT404)

        self.assertFalse(result.is_sat)
        self.assertEqual(result.backend, PYSAT_KISSAT404)
        self.assertEqual(result.n_vertices, 4)
        self.assertEqual(result.m_edges, 6)
    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the PySAT baseline tests")
    def test_modern_backend_solves_small_sat_instance(self):
        graph = nx.path_graph(2)

        result = solve_3color_baseline(graph, backend=PYSAT_CADICAL)

        self.assertTrue(result.is_sat)
        self.assertEqual(result.backend, PYSAT_CADICAL)
        self.assertEqual(result.n_vertices, 2)
        self.assertEqual(result.m_edges, 1)
        self.assertGreaterEqual(result.elapsed_time, 0.0)

    @unittest.skipUnless(HAS_PYSAT, "python-sat is required for the PySAT baseline tests")
    def test_modern_backend_solves_small_unsat_instance(self):
        graph = nx.complete_graph(4)

        result = solve_3color_baseline(graph, backend=PYSAT_CADICAL)

        self.assertFalse(result.is_sat)
        self.assertEqual(result.backend, PYSAT_CADICAL)
        self.assertEqual(result.n_vertices, 4)
        self.assertEqual(result.m_edges, 6)

    @unittest.skipUnless(HAS_PYSMT, "pysmt is required for the legacy SAT baseline tests")
    def test_legacy_shared_interface_returns_metadata(self):
        graph = nx.path_graph(3)

        result = solve_3color_baseline(graph, backend=LEGACY_PYSMT_MSAT)

        self.assertTrue(result.is_sat)
        self.assertEqual(result.backend, LEGACY_PYSMT_MSAT)
        self.assertEqual(result.n_vertices, 3)
        self.assertEqual(result.m_edges, 2)
        self.assertGreaterEqual(result.elapsed_time, 0.0)

    @unittest.skipUnless(HAS_PYSMT, "pysmt is required for the legacy SAT baseline tests")
    def test_legacy_wrapper_preserves_tuple_shape(self):
        graph = nx.complete_graph(4)

        result = is_three_colorable(graph)

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertFalse(result[0])
        self.assertGreaterEqual(result[1], 0.0)


if __name__ == "__main__":
    unittest.main()
