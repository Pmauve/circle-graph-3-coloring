import sys
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.sat.pysat_baseline import COLOR_ORDER, build_reduced_cnf


class PySatBaselineEncodingTests(unittest.TestCase):
    def test_build_reduced_cnf_counts_path_graph(self):
        graph = nx.path_graph(2)

        cnf = build_reduced_cnf(graph)

        self.assertEqual(cnf.n_vars, 6)
        self.assertEqual(cnf.n_clauses, 5)
        self.assertEqual(
            cnf.clauses,
            [
                [1, 2, 3],
                [4, 5, 6],
                [-1, -4],
                [-2, -5],
                [-3, -6],
            ],
        )

    def test_build_reduced_cnf_uses_graph_node_order(self):
        graph = nx.Graph()
        graph.add_node(10)
        graph.add_node(3)
        graph.add_edge(10, 3)

        cnf = build_reduced_cnf(graph)

        self.assertEqual(COLOR_ORDER, ("r", "b", "g"))
        self.assertEqual(cnf.var_map[(10, "r")], 1)
        self.assertEqual(cnf.var_map[(10, "b")], 2)
        self.assertEqual(cnf.var_map[(10, "g")], 3)
        self.assertEqual(cnf.var_map[(3, "r")], 4)
        self.assertEqual(cnf.var_map[(3, "b")], 5)
        self.assertEqual(cnf.var_map[(3, "g")], 6)

    def test_build_reduced_cnf_counts_triangle(self):
        graph = nx.cycle_graph(3)

        cnf = build_reduced_cnf(graph)

        self.assertEqual(cnf.n_vars, 9)
        self.assertEqual(cnf.n_clauses, 12)


if __name__ == "__main__":
    unittest.main()
