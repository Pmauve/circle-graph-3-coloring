import random
from dataclasses import dataclass
from typing import Literal

from three_col_circle_code.generation.circle_state import (
    IncrementalCircleState,
    build_graph_from_state,
)
from three_col_circle_code.generation.color_utils import available_colors, validate_num_colors


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


def generate_random_circle_graph_yes_constructive(
    size,
    *,
    rng=None,
    config,
    max_attempts_per_node=None,
    num_colors=3,
):
    """Generate a connected k-colorable circle graph using constructive chord placement."""
    _validate_generation_request(size, max_attempts_per_node)
    validate_num_colors(num_colors)

    rng = rng or random
    state = IncrementalCircleState(colors={})
    palette = tuple(range(1, num_colors + 1))

    for node_id in range(size):
        if node_id == 0:
            state.endpoint_order = [node_id, node_id]
            state.adjacency[node_id] = set()
            state.colors[node_id] = rng.choice(palette)
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
                num_colors=num_colors,
            )
            candidates = _collect_constructive_second_gap_candidates(
                state.endpoint_order,
                state.colors,
                start_gap,
                direction,
                config.full_sweep,
                num_colors=num_colors,
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


def _choose_constructive_start(endpoint_order, colors, config, rng, *, node_id=None, num_colors=3):
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
            num_colors=num_colors,
        )
        if best_score is None or score > best_score:
            best_score = score
            best_pairs = [pair]
        elif score == best_score:
            best_pairs.append(pair)
    return rng.choice(best_pairs)


def _constructive_frontier_stats(endpoint_order, colors, start_gap, direction, *, node_id=None, num_colors=3):
    frontier_length = 0
    max_active = 0
    for candidate in _iter_gap_candidates(
        endpoint_order,
        colors,
        start_gap=start_gap,
        direction=direction,
        full_sweep=False,
        num_colors=num_colors,
    ):
        frontier_length += 1
        max_active = max(max_active, candidate.active_count)
    return frontier_length, max_active


def _collect_constructive_second_gap_candidates(
    endpoint_order,
    colors,
    start_gap,
    direction,
    full_sweep,
    *,
    node_id=None,
    num_colors=3,
):
    return list(
        _iter_gap_candidates(
            endpoint_order,
            colors,
            start_gap=start_gap,
            direction=direction,
            full_sweep=full_sweep,
            num_colors=num_colors,
        )
    )


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


def _iter_gap_candidates(
    endpoint_order,
    colors,
    *,
    start_gap,
    direction,
    full_sweep,
    num_colors,
):
    # This single incremental scanner keeps k-color candidate logic in one place.
    # It mainly pays off for full-sweep weighted generation; non-full-sweep configs
    # accept a small absolute slowdown to avoid maintaining a second scan path.
    active_neighbors: set[int] = set()
    current_low = start_gap
    current_high = start_gap
    started = False
    for step, gap in enumerate(_ordered_second_gaps(len(endpoint_order), start_gap, direction), start=1):
        low_gap, high_gap = sorted((start_gap, gap))
        _move_active_interval(
            endpoint_order,
            active_neighbors,
            current_low,
            current_high,
            low_gap,
            high_gap,
        )
        current_low = low_gap
        current_high = high_gap

        candidate_colors = ()
        if active_neighbors:
            candidate_colors = available_colors(colors, active_neighbors, num_colors)
        if not candidate_colors:
            if started and not full_sweep:
                break
            continue

        started = True
        yield ConstructiveCandidate(
            second_gap=gap,
            available_colors=candidate_colors,
            active_count=len(active_neighbors),
            step=step,
            neighbors=frozenset(active_neighbors),
        )


def _move_active_interval(endpoint_order, active_neighbors, old_low, old_high, new_low, new_high):
    if new_low > old_low:
        _toggle_endpoint_range(endpoint_order, active_neighbors, old_low, new_low)
    elif new_low < old_low:
        _toggle_endpoint_range(endpoint_order, active_neighbors, new_low, old_low)

    if new_high > old_high:
        _toggle_endpoint_range(endpoint_order, active_neighbors, old_high, new_high)
    elif new_high < old_high:
        _toggle_endpoint_range(endpoint_order, active_neighbors, new_high, old_high)


def _toggle_endpoint_range(endpoint_order, active_neighbors, start, stop):
    for index in range(start, stop):
        node_id = endpoint_order[index]
        if node_id in active_neighbors:
            active_neighbors.remove(node_id)
        else:
            active_neighbors.add(node_id)


def _insert_node_at_gaps(endpoint_order, node_id, first_gap, second_gap):
    low_gap, high_gap = sorted((first_gap, second_gap))
    endpoint_order.insert(low_gap, node_id)
    endpoint_order.insert(high_gap + 1, node_id)


def _commit_candidate(state, node_id, start_gap, candidate, color):
    _insert_node_at_gaps(
        state.endpoint_order,
        node_id,
        start_gap,
        candidate.second_gap,
    )
    state.adjacency[node_id] = set(candidate.neighbors)
    for neighbor in candidate.neighbors:
        state.adjacency[neighbor].add(node_id)
    state.colors[node_id] = color
