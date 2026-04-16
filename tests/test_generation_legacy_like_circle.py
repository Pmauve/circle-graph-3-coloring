import random
import sys
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.generation.legacy_like_circle import (
    generate_random_circle_graph_fast,
    generate_random_circle_graph_yes_fast,
)
from three_col_circle_code.graph_generator import (
    get_random_circle_graph,
    get_random_circle_graph_yes_inst,
    no_clique_greater_3,
)
from three_col_circle_code.instances.validate import validate_instance
from three_col_circle_code.util import verify_3coloring


class FastLegacyLikeCircleGenerationTests(unittest.TestCase):
    def test_generate_random_circle_graph_fast_is_reproducible(self) -> None:
        first = generate_random_circle_graph_fast(8, rng=random.Random(17), max_attempts_per_node=10_000)
        second = generate_random_circle_graph_fast(8, rng=random.Random(17), max_attempts_per_node=10_000)

        self.assertEqual(_graph_signature(first), _graph_signature(second))

    def test_generate_random_circle_graph_fast_validates(self) -> None:
        graph = generate_random_circle_graph_fast(8, rng=random.Random(29), max_attempts_per_node=10_000)

        report = validate_instance(graph)

        self.assertTrue(report.ok)
        self.assertTrue(no_clique_greater_3(graph))
        self.assertTrue(graph.number_of_nodes() > 0)
        self.assertTrue(all("level" not in attrs for _, attrs in graph.nodes(data=True)))

    def test_generate_random_circle_graph_fast_returns_connected_graph(self) -> None:
        graph = generate_random_circle_graph_fast(10, rng=random.Random(31), max_attempts_per_node=10_000)

        self.assertTrue(graph.number_of_nodes() > 0)
        self.assertTrue(nx.is_connected(graph))

    def test_generate_random_circle_graph_fast_matches_legacy_backend_on_small_seed_matrix(self) -> None:
        for n in range(4, 9):
            for seed in range(1, 21):
                legacy_graph = get_random_circle_graph(
                    n,
                    save=False,
                    rng=random.Random(seed),
                    max_attempts_per_node=10_000,
                )
                fast_graph = generate_random_circle_graph_fast(
                    n,
                    rng=random.Random(seed),
                    max_attempts_per_node=10_000,
                )
                self.assertEqual(
                    _graph_signature(legacy_graph),
                    _graph_signature(fast_graph),
                    msg=f"legacy and fast rc generation diverged for n={n}, seed={seed}",
                )

    def test_generate_random_circle_graph_yes_fast_is_reproducible(self) -> None:
        first = generate_random_circle_graph_yes_fast(8, rng=random.Random(17), max_attempts_per_node=10_000)
        second = generate_random_circle_graph_yes_fast(8, rng=random.Random(17), max_attempts_per_node=10_000)

        self.assertEqual(_colored_graph_signature(first), _colored_graph_signature(second))

    def test_generate_random_circle_graph_yes_fast_validates_and_has_valid_coloring(self) -> None:
        graph = generate_random_circle_graph_yes_fast(8, rng=random.Random(29), max_attempts_per_node=10_000)

        report = validate_instance(graph)

        self.assertTrue(report.ok)
        self.assertTrue(no_clique_greater_3(graph))
        self.assertTrue(nx.is_connected(graph))
        self.assertTrue(verify_3coloring(graph, log_errors=False) is True)
        self.assertTrue(all("level" not in attrs for _, attrs in graph.nodes(data=True)))
        self.assertTrue(all("color" in attrs for _, attrs in graph.nodes(data=True)))

    def test_generate_random_circle_graph_yes_fast_matches_legacy_backend_on_small_seed_matrix(self) -> None:
        for n in range(4, 9):
            for seed in range(1, 21):
                legacy_graph = get_random_circle_graph_yes_inst(
                    n,
                    save=False,
                    rng=random.Random(seed),
                    max_attempts_per_node=10_000,
                )
                fast_graph = generate_random_circle_graph_yes_fast(
                    n,
                    rng=random.Random(seed),
                    max_attempts_per_node=10_000,
                )
                self.assertEqual(
                    _colored_graph_signature(legacy_graph),
                    _colored_graph_signature(fast_graph),
                    msg=f"legacy and fast rcy generation diverged for n={n}, seed={seed}",
                )


def _graph_signature(graph) -> tuple:
    node_signature = tuple(
        sorted((node_id, attrs["label"], attrs["l"], attrs["r"]) for node_id, attrs in graph.nodes(data=True))
    )
    edge_signature = tuple(sorted(tuple(sorted(edge)) for edge in graph.edges()))
    return node_signature, edge_signature


def _colored_graph_signature(graph) -> tuple:
    node_signature = tuple(
        sorted((node_id, attrs["label"], attrs["l"], attrs["r"], attrs["color"]) for node_id, attrs in graph.nodes(data=True))
    )
    edge_signature = tuple(sorted(tuple(sorted(edge)) for edge in graph.edges()))
    return node_signature, edge_signature


if __name__ == "__main__":
    unittest.main()
