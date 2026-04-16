import random
import sys
import unittest
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.generation.constructive_circle import (
    CONSTRUCTIVE_CONFIGS,
    ConstructiveConfig,
    _choose_constructive_start,
    _collect_constructive_second_gap_candidates,
    _find_constructive_second_gap,
    generate_random_circle_graph_yes_constructive,
)
from three_col_circle_code.instances.validate import validate_instance
from three_col_circle_code.util import verify_3coloring


class ConstructiveCircleGenerationTests(unittest.TestCase):
    def test_constructive_generation_is_reproducible_for_all_public_configs(self) -> None:
        for family, config in CONSTRUCTIVE_CONFIGS.items():
            first = generate_random_circle_graph_yes_constructive(
                8,
                rng=random.Random(17),
                config=config,
                max_attempts_per_node=10_000,
            )
            second = generate_random_circle_graph_yes_constructive(
                8,
                rng=random.Random(17),
                config=config,
                max_attempts_per_node=10_000,
            )

            self.assertEqual(
                _colored_graph_signature(first),
                _colored_graph_signature(second),
                msg=f"constructive family {family} is not reproducible",
            )

    def test_constructive_generation_produces_valid_connected_colored_graphs(self) -> None:
        for family, config in CONSTRUCTIVE_CONFIGS.items():
            graph = generate_random_circle_graph_yes_constructive(
                8,
                rng=random.Random(29),
                config=config,
                max_attempts_per_node=10_000,
            )
            report = validate_instance(graph)

            self.assertTrue(report.ok, msg=f"{family} failed validation")
            self.assertTrue(nx.is_connected(graph), msg=f"{family} is disconnected")
            self.assertTrue(verify_3coloring(graph, log_errors=False) is True, msg=f"{family} coloring invalid")
            self.assertTrue(all("level" not in attrs for _, attrs in graph.nodes(data=True)))
            self.assertTrue(all("color" in attrs for _, attrs in graph.nodes(data=True)))

    def test_first_frontier_only_stops_before_later_feasible_regions(self) -> None:
        endpoint_order = [0, 1, 2, 0, 1, 2]
        colors = {0: 1, 1: 2, 2: 3}

        early = _collect_constructive_second_gap_candidates(
            endpoint_order,
            colors,
            0,
            1,
            False,
            node_id=99,
        )
        full = _collect_constructive_second_gap_candidates(
            endpoint_order,
            colors,
            0,
            1,
            True,
            node_id=99,
        )

        self.assertEqual([(candidate.gap, candidate.step) for candidate in early], [(1, 1), (2, 2)])
        self.assertEqual([(candidate.gap, candidate.step) for candidate in full], [(1, 1), (2, 2), (4, 4), (5, 5)])

    def test_max_active_selection_prefers_densest_candidates(self) -> None:
        candidates = _collect_constructive_second_gap_candidates(
            [0, 1, 2, 0, 1, 2],
            {0: 1, 1: 2, 2: 3},
            0,
            1,
            True,
            node_id=99,
        )

        chosen = _find_constructive_second_gap(candidates, "max_active", random.Random(7))

        self.assertEqual(chosen.active_count, max(candidate.active_count for candidate in candidates))

    def test_weighted_active_selection_uses_active_counts_as_weights(self) -> None:
        candidates = _collect_constructive_second_gap_candidates(
            [0, 1, 2, 0, 1, 2],
            {0: 1, 1: 2, 2: 3},
            0,
            1,
            True,
            node_id=99,
        )
        rng = _TrackingWeightedRandom()

        chosen = _find_constructive_second_gap(candidates, "weighted_active", rng)

        self.assertIs(chosen, candidates[0])
        self.assertEqual(rng.seen_weights, [candidate.active_count for candidate in candidates])

    def test_start_lookahead_chooses_lexicographically_best_sampled_start(self) -> None:
        rng = _DeterministicPairRandom(
            randint_values=[0, 1, 4],
            choice_values=[1, -1, 1, (1, -1)],
        )

        chosen = _choose_constructive_start(
            [0, 1, 2, 3, 0, 1, 2, 3],
            {0: 1, 1: 2, 2: 3, 3: 1},
            ConstructiveConfig(start_lookahead=3, end_selection="max_active", full_sweep=False),
            rng,
            node_id=99,
        )

        self.assertEqual(chosen, (1, -1))


def _colored_graph_signature(graph) -> tuple:
    node_signature = tuple(
        sorted((node_id, attrs["label"], attrs["l"], attrs["r"], attrs["color"]) for node_id, attrs in graph.nodes(data=True))
    )
    edge_signature = tuple(sorted(tuple(sorted(edge)) for edge in graph.edges()))
    return node_signature, edge_signature


class _TrackingWeightedRandom:
    def __init__(self) -> None:
        self.seen_weights = None

    def choices(self, population, weights=None, k=1):
        self.seen_weights = list(weights)
        return [population[0]]


class _DeterministicPairRandom:
    def __init__(self, *, randint_values, choice_values) -> None:
        self._randint_values = iter(randint_values)
        self._choice_values = iter(choice_values)

    def randint(self, _a, _b):
        return next(self._randint_values)

    def choice(self, population):
        value = next(self._choice_values)
        if isinstance(population[0], tuple):
            return population[0]
        if value not in population:
            raise AssertionError(f"value {value!r} not in population {population!r}")
        return value


if __name__ == "__main__":
    unittest.main()
