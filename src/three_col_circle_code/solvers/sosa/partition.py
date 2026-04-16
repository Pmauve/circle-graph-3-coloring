from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CirclePartition:
    """Boundary-based circle partition over the canonical endpoint order.

    The four arcs are represented as clockwise half-open intervals over
    `0..n_endpoints-1`:

    - `L = [left_boundary, top_boundary)`
    - `T = [top_boundary, right_boundary)`
    - `R = [right_boundary, bottom_boundary)`
    - `B = [bottom_boundary, left_boundary)`

    modulo `n_endpoints`. Empty arcs are allowed and correspond to repeated
    consecutive boundaries.
    """

    n_endpoints: int
    left_boundary: int
    top_boundary: int
    right_boundary: int
    bottom_boundary: int

    def __post_init__(self) -> None:
        if self.n_endpoints < 0:
            raise ValueError("circle partitions require a non-negative endpoint count")
        if self.n_endpoints == 0:
            if any(
                boundary != 0
                for boundary in (
                    self.left_boundary,
                    self.top_boundary,
                    self.right_boundary,
                    self.bottom_boundary,
                )
            ):
                raise ValueError("zero-endpoint partitions must use boundary 0")
            return
        for boundary in (
            self.left_boundary,
            self.top_boundary,
            self.right_boundary,
            self.bottom_boundary,
        ):
            if not 0 <= boundary < self.n_endpoints:
                raise ValueError(
                    f"partition boundary {boundary} is out of range for {self.n_endpoints} endpoints"
                )

    def boundaries(self) -> tuple[int, int, int, int]:
        """Return the boundaries in `L, T, R, B` order."""
        return (
            self.left_boundary,
            self.top_boundary,
            self.right_boundary,
            self.bottom_boundary,
        )

    def arc_positions(self, arc_name: str) -> tuple[int, ...]:
        """Return the endpoint positions contained in one named arc."""
        if self.n_endpoints == 0:
            return ()
        start, end = self._arc_bounds(arc_name)
        positions = []
        current = start
        while current != end:
            positions.append(current)
            current = (current + 1) % self.n_endpoints
        return tuple(positions)

    def contains_position(self, arc_name: str, position: int) -> bool:
        """Return whether one endpoint position lies in the named arc."""
        if not 0 <= position < self.n_endpoints:
            raise ValueError(
                f"endpoint position {position} is out of range for {self.n_endpoints} endpoints"
            )
        start, end = self._arc_bounds(arc_name)
        if start == end:
            return False
        if start < end:
            return start <= position < end
        return position >= start or position < end

    def endpoint_arc(self, position: int) -> str:
        """Return the unique arc name containing one endpoint position."""
        for arc_name in ("L", "T", "R", "B"):
            if self.contains_position(arc_name, position):
                return arc_name
        raise AssertionError("every endpoint position must lie in exactly one arc")

    def rotate_counterclockwise(self) -> "CirclePartition":
        """Return the rotated partition P̃ from Lemma 3.7.

        The rotation is defined by:
        - L(P̃) := T(P)
        - T(P̃) := R(P)
        - R(P̃) := B(P)
        - B(P̃) := L(P)
        """
        return CirclePartition(
            n_endpoints=self.n_endpoints,
            left_boundary=self.top_boundary,
            top_boundary=self.right_boundary,
            right_boundary=self.bottom_boundary,
            bottom_boundary=self.left_boundary,
        )

    def _arc_bounds(self, arc_name: str) -> tuple[int, int]:
        arc_name = arc_name.upper()
        if arc_name == "L":
            return self.left_boundary, self.top_boundary
        if arc_name == "T":
            return self.top_boundary, self.right_boundary
        if arc_name == "R":
            return self.right_boundary, self.bottom_boundary
        if arc_name == "B":
            return self.bottom_boundary, self.left_boundary
        raise ValueError(f"unknown circle partition arc {arc_name!r}")
