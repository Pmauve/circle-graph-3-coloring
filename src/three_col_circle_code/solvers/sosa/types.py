from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from three_col_circle_code.solvers.sosa.colors import ALL_COLOR_MASK
from three_col_circle_code.solvers.sosa.partition import CirclePartition


FixedColorAssignments = tuple[tuple[int, int], ...]
VertexColoring = dict[int, int]


def merge_fixed_colors(*assignment_groups: Iterable[tuple[int, int]]) -> FixedColorAssignments:
    """Merge fixed-color assignments into one canonical tuple."""
    merged: dict[int, int] = {}
    for assignment_group in assignment_groups:
        for vertex_index, color_mask in assignment_group:
            previous = merged.get(vertex_index)
            if previous is not None and previous != color_mask:
                raise AssertionError("conflicting fixed-color assignments")
            merged[vertex_index] = color_mask
    return tuple(sorted(merged.items()))


def fixed_colors_to_dict(assignments: Iterable[tuple[int, int]]) -> VertexColoring:
    """Convert canonical fixed-color tuples into a mutable coloring map."""
    return {vertex_index: color_mask for vertex_index, color_mask in assignments}


@dataclass(frozen=True, slots=True)
class SosaSearchState:
    """Immutable snapshot of the active SOSA list-coloring subinstance I."""

    active_vertices_mask: int
    allowed_color_masks: tuple[int, ...]

    @classmethod
    def initial(cls, *, n_vertices: int) -> "SosaSearchState":
        """Create the initial state where every active vertex allows all colors."""
        return cls(
            active_vertices_mask=(1 << n_vertices) - 1,
            allowed_color_masks=tuple(ALL_COLOR_MASK for _ in range(n_vertices)),
        )

    @property
    def n_active_vertices(self) -> int:
        """Return |V(I)| for the current active subinstance."""
        return self.active_vertices_mask.bit_count()

    def is_active(self, vertex_index: int) -> bool:
        """Return whether one vertex is still present in the subinstance."""
        return bool(self.active_vertices_mask & (1 << vertex_index))


@dataclass(frozen=True, slots=True)
class RrExhaustionResult:
    """RR-exhausted subinstance together with the colors fixed during RR."""

    state: SosaSearchState
    fixed_colors: FixedColorAssignments = ()


@dataclass(slots=True)
class SosaStats:
    """Mutable counters collected while solving one SOSA instance."""

    solver_calls: int = 0
    base_case_calls: int = 0
    base_case_search_nodes: int = 0
    lemma_33_calls: int = 0
    lemma_36_calls: int = 0
    lemma_37_calls: int = 0
    lemma_38_calls: int = 0
    rr_steps: int = 0
    max_recursion_depth: int = 0

    def record_depth(self, depth: int) -> None:
        """Track the deepest theorem-level or base-case depth reached so far."""
        if depth > self.max_recursion_depth:
            self.max_recursion_depth = depth

    def to_details_dict(self) -> dict[str, int]:
        """Return the standardized SOSA statistics payload."""
        return {
            "solver_calls": self.solver_calls,
            "base_case_calls": self.base_case_calls,
            "base_case_search_nodes": self.base_case_search_nodes,
            "lemma_33_calls": self.lemma_33_calls,
            "lemma_36_calls": self.lemma_36_calls,
            "lemma_37_calls": self.lemma_37_calls,
            "lemma_38_calls": self.lemma_38_calls,
            "rr_steps": self.rr_steps,
            "max_recursion_depth": self.max_recursion_depth,
        }


@dataclass(frozen=True, slots=True)
class SemiSeparatedInstance:
    """One semi-separated tuple (I, P) from Lemma 3.7."""

    state: SosaSearchState
    partition: CirclePartition
    fixed_colors: FixedColorAssignments = ()


@dataclass(frozen=True, slots=True)
class FullySeparatedInstance:
    """One fully-separated tuple (I, P) from Lemma 3.8 or Lemma 3.3."""

    state: SosaSearchState
    partition: CirclePartition
    fixed_colors: FixedColorAssignments = ()
