import random
from dataclasses import dataclass
from typing import Literal

from three_col_circle_code.generation.circle_state import (
    IncrementalCircleState,
    build_graph_from_state,
)


EndSelection = Literal["uniform", "max_active", "weighted_active", "farthest"]


@dataclass(frozen=True)
class ConstructiveConfig:
    start_lookahead: int
    end_selection: EndSelection
    full_sweep: bool


@dataclass(frozen=True)
class ConstructiveCandidate:
    second_gap: int
    available_colors: tuple[int, ...]
    active_count: int
    step: int
    neighbors: frozenset[int]

    @property
    def gap(self) -> int:
        return self.second_gap


_AVAILABLE_COLORS_BY_MASK: dict[int, tuple[int, ...]] = {
    0: (),
    1: (1,),
    2: (2,),
    3: (1, 2),
    4: (3,),
    5: (1, 3),
    6: (2, 3),
    7: (1, 2, 3),
}

_COLOR_BIT = {
    1: 1,
    2: 2,
    3: 4,
}


CONSTRUCTIVE_CONFIGS: dict[str, ConstructiveConfig] = {
    "rccy": ConstructiveConfig(start_lookahead=16, end_selection="max_active", full_sweep=False),
    "rccy_tuned": ConstructiveConfig(start_lookahead=16, end_selection="max_active", full_sweep=False),
    "rccy_baseline": ConstructiveConfig(start_lookahead=1, end_selection="uniform", full_sweep=False),
    "rccy_full_sweep_weighted_active": ConstructiveConfig(
        start_lookahead=16,
        end_selection="weighted_active",
        full_sweep=True,
    ),
    "rccy_full_sweep_max_active": ConstructiveConfig(
        start_lookahead=16,
        end_selection="max_active",
        full_sweep=True,
    ),
}


def generate_random_circle_graph_yes_constructive(size, *, rng=None, config, max_attempts_per_node=None):
    """Generate a connected 3-colorable circle graph using constructive chord placement."""
    _validate_generation_request(size, max_attempts_per_node)

    rng = rng or random
    state = IncrementalCircleState(colors={})

    for node_id in range(size):
        if node_id == 0:
            state.endpoint_order = [node_id, node_id]
            state.adjacency[node_id] = set()
            state.colors[node_id] = rng.choice((1, 2, 3))
            continue

        attempts = 0
        while True:
            if max_attempts_per_node is not None and attempts >= max_attempts_per_node:
                raise RuntimeError(
                    "failed to generate constructive random circle graph for node " + str(node_id)
                )

            start_gap, direction = _choose_constructive_start(
                state.endpoint_order,
                state.colors,
                config,
                rng,
            )
            candidates = _collect_constructive_second_gap_candidates(
                state.endpoint_order,
                state.colors,
                start_gap,
                direction,
                config.full_sweep,
            )
            if candidates:
                chosen = _find_constructive_second_gap(candidates, config.end_selection, rng)
                chosen_color = rng.choice(chosen.available_colors)
                _commit_candidate(state, node_id, start_gap, chosen, chosen_color)
                break
            attempts += 1

    return build_graph_from_state(state)


def _validate_generation_request(size, max_attempts_per_node):
    if size < 0:
        raise ValueError("size must be non-negative")
    if max_attempts_per_node is not None and max_attempts_per_node < 1:
        raise ValueError("max_attempts_per_node must be at least 1")


def _choose_constructive_start(endpoint_order, colors, config, rng, *, node_id=None):
    if not endpoint_order:
        return 0, 1
    if config.start_lookahead <= 1:
        return rng.randint(0, len(endpoint_order)), rng.choice((-1, 1))

    best_pairs: list[tuple[int, int]] = []
    best_score: tuple[int, int] | None = None
    for _ in range(config.start_lookahead):
        pair = (rng.randint(0, len(endpoint_order)), rng.choice((-1, 1)))
        score = _constructive_frontier_stats(
            endpoint_order,
            colors,
            pair[0],
            pair[1],
        )
        if best_score is None or score > best_score:
            best_score = score
            best_pairs = [pair]
        elif score == best_score:
            best_pairs.append(pair)
    return rng.choice(best_pairs)


def _constructive_frontier_stats(endpoint_order, colors, start_gap, direction, *, node_id=None):
    frontier_length = 0
    max_active = 0
    started = False
    for step, gap in enumerate(_ordered_second_gaps(len(endpoint_order), start_gap, direction), start=1):
        active_count = _active_count_for_gap(
            endpoint_order,
            colors,
            start_gap=start_gap,
            second_gap=gap,
        )
        if active_count is None:
            if started:
                break
            continue
        started = True
        frontier_length += 1
        max_active = max(max_active, active_count)
    return frontier_length, max_active


def _collect_constructive_second_gap_candidates(
    endpoint_order,
    colors,
    start_gap,
    direction,
    full_sweep,
    *,
    node_id=None,
):
    candidates: list[ConstructiveCandidate] = []
    started = False
    for step, gap in enumerate(_ordered_second_gaps(len(endpoint_order), start_gap, direction), start=1):
        candidate = _candidate_for_gap(
            endpoint_order,
            colors,
            start_gap=start_gap,
            second_gap=gap,
            step=step,
        )
        if candidate is None:
            if started and not full_sweep:
                break
            continue
        started = True
        candidates.append(candidate)
    return candidates


def _find_constructive_second_gap(candidates, end_selection, rng):
    if end_selection == "uniform":
        return rng.choice(candidates)
    if end_selection == "max_active":
        best_score = None
        best_candidates = []
        for candidate in candidates:
            score = candidate.active_count
            if best_score is None or score > best_score:
                best_score = score
                best_candidates = [candidate]
            elif score == best_score:
                best_candidates.append(candidate)
        return rng.choice(best_candidates)
    if end_selection == "farthest":
        best_step = None
        farthest_candidates = []
        for candidate in candidates:
            step = candidate.step
            if best_step is None or step > best_step:
                best_step = step
                farthest_candidates = [candidate]
            elif step == best_step:
                farthest_candidates.append(candidate)
        return rng.choice(farthest_candidates)
    if end_selection == "weighted_active":
        weights = [candidate.active_count for candidate in candidates]
        return rng.choices(candidates, weights=weights, k=1)[0]
    raise ValueError(f"unsupported end_selection {end_selection!r}")


def _ordered_second_gaps(endpoint_order_len, start_gap, direction):
    n_gaps = endpoint_order_len + 1
    current = start_gap
    for _ in range(n_gaps - 1):
        current = (current + direction) % n_gaps
        yield current


def _candidate_for_gap(endpoint_order, colors, *, start_gap, second_gap, step):
    low_gap, high_gap = sorted((start_gap, second_gap))
    neighbors = _candidate_neighbors_between(endpoint_order, low_gap, high_gap)
    if not neighbors:
        return None
    available_colors = _available_colors(colors, neighbors)
    if not available_colors:
        return None
    return ConstructiveCandidate(
        second_gap=second_gap,
        available_colors=available_colors,
        active_count=len(neighbors),
        step=step,
        neighbors=frozenset(neighbors),
    )


def _active_count_for_gap(endpoint_order, colors, *, start_gap, second_gap):
    low_gap, high_gap = sorted((start_gap, second_gap))
    neighbors = _candidate_neighbors_between(endpoint_order, low_gap, high_gap)
    if not neighbors or not _available_colors(colors, neighbors):
        return None
    return len(neighbors)


def _insert_node_at_gaps(endpoint_order, node_id, first_gap, second_gap):
    low_gap, high_gap = sorted((first_gap, second_gap))
    candidate_order = list(endpoint_order)
    candidate_order.insert(low_gap, node_id)
    candidate_order.insert(high_gap + 1, node_id)
    return candidate_order


def _candidate_neighbors_between(endpoint_order, left_gap, right_gap):
    neighbors: set[int] = set()
    for index in range(left_gap, right_gap):
        value = endpoint_order[index]
        if value in neighbors:
            neighbors.remove(value)
        else:
            neighbors.add(value)
    return neighbors


def _available_colors(colors, neighbors):
    mask = 7
    for neighbor in neighbors:
        mask &= ~_COLOR_BIT[colors[neighbor]]
    return _AVAILABLE_COLORS_BY_MASK[mask]


def _commit_candidate(state, node_id, start_gap, candidate, color):
    state.endpoint_order = _insert_node_at_gaps(
        state.endpoint_order,
        node_id,
        start_gap,
        candidate.second_gap,
    )
    state.adjacency[node_id] = set(candidate.neighbors)
    for neighbor in candidate.neighbors:
        state.adjacency[neighbor].add(node_id)
    state.colors[node_id] = color
