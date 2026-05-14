from dataclasses import dataclass

from three_col_circle_code.sat.baseline import PYSAT_CADICAL, PYSAT_KISSAT404

COLOR_ORDER = ("r", "b", "g")
PYSAT_CADICAL_SOLVER_NAME = "cadical195"


@dataclass(frozen=True)
class ReducedColoringCnf:
    clauses: list[list[int]]
    var_map: dict[tuple[int, str], int]
    n_vars: int
    n_clauses: int


@dataclass(frozen=True)
class ReducedListColoringCnf:
    clauses: list[list[int]]
    var_map: dict[tuple[int, int], int]
    n_vars: int
    n_clauses: int


def build_reduced_cnf(graph):
    clauses = []
    var_map = {}
    next_var = 1

    for node in graph.nodes:
        vertex_clause = []
        for color in COLOR_ORDER:
            var_map[(node, color)] = next_var
            vertex_clause.append(next_var)
            next_var += 1
        clauses.append(vertex_clause)

    for u, v in graph.edges:
        for color in COLOR_ORDER:
            clauses.append([-var_map[(u, color)], -var_map[(v, color)]])

    return ReducedColoringCnf(
        clauses=clauses,
        var_map=var_map,
        n_vars=len(var_map),
        n_clauses=len(clauses),
    )


def build_reduced_list_coloring_cnf(
    *,
    active_vertices_mask: int,
    neighbor_indices: tuple[tuple[int, ...], ...],
    allowed_color_masks: tuple[int, ...],
    num_colors: int,
) -> ReducedListColoringCnf:
    from three_col_circle_code.solvers.sosa.mask_ops import iter_mask_indices

    clauses = []
    var_map = {}
    next_var = 1
    active_vertices = tuple(iter_mask_indices(active_vertices_mask))
    color_mask_limit = (1 << num_colors) - 1

    for vertex_index in active_vertices:
        vertex_clause = []
        allowed_mask = allowed_color_masks[vertex_index] & color_mask_limit
        for color_index in range(num_colors):
            color_mask = 1 << color_index
            if not (allowed_mask & color_mask):
                continue
            var_map[(vertex_index, color_index)] = next_var
            vertex_clause.append(next_var)
            next_var += 1
        clauses.append(vertex_clause)

    for vertex_index in active_vertices:
        allowed_mask = allowed_color_masks[vertex_index] & color_mask_limit
        for neighbor_index in neighbor_indices[vertex_index]:
            if neighbor_index <= vertex_index or not (active_vertices_mask & (1 << neighbor_index)):
                continue
            shared_mask = allowed_mask & allowed_color_masks[neighbor_index] & color_mask_limit
            for color_index in range(num_colors):
                color_mask = 1 << color_index
                if not (shared_mask & color_mask):
                    continue
                clauses.append(
                    [
                        -var_map[(vertex_index, color_index)],
                        -var_map[(neighbor_index, color_index)],
                    ]
                )

    return ReducedListColoringCnf(
        clauses=clauses,
        var_map=var_map,
        n_vars=len(var_map),
        n_clauses=len(clauses),
    )


def solve_reduced_list_coloring_cnf(
    *,
    active_vertices_mask: int,
    neighbor_indices: tuple[tuple[int, ...], ...],
    allowed_color_masks: tuple[int, ...],
    num_colors: int,
    backend: str = PYSAT_CADICAL,
) -> bool:
    cnf = build_reduced_list_coloring_cnf(
        active_vertices_mask=active_vertices_mask,
        neighbor_indices=neighbor_indices,
        allowed_color_masks=allowed_color_masks,
        num_colors=num_colors,
    )
    is_sat, _elapsed_time = _solve_pysat_cnf(clauses=cnf.clauses, backend=backend)
    return is_sat


def solve_pysat_cadical(graph):
    from three_col_circle_code.sat.baseline import BaselineSolveResult

    cnf = build_reduced_cnf(graph)
    is_sat, elapsed_time = _solve_pysat_cnf(clauses=cnf.clauses, backend=PYSAT_CADICAL)

    return BaselineSolveResult(
        is_sat=is_sat,
        elapsed_time=elapsed_time,
        backend=PYSAT_CADICAL,
        n_vertices=len(graph.nodes),
        m_edges=len(graph.edges),
        elapsed_time_source="pysat_solver_time",
    )


def solve_pysat_kissat404(graph):
    from three_col_circle_code.sat.baseline import BaselineSolveResult

    cnf = build_reduced_cnf(graph)
    is_sat, elapsed_time = _solve_pysat_cnf(clauses=cnf.clauses, backend=PYSAT_KISSAT404)

    return BaselineSolveResult(
        is_sat=is_sat,
        elapsed_time=elapsed_time,
        backend=PYSAT_KISSAT404,
        n_vertices=len(graph.nodes),
        m_edges=len(graph.edges),
        elapsed_time_source="pysat_solver_time",
    )


def _solve_pysat_cnf(*, clauses: list[list[int]], backend: str) -> tuple[bool, float]:
    if any(not clause for clause in clauses):
        return False, 0.0

    if backend == PYSAT_CADICAL:
        try:
            from pysat.solvers import NoSuchSolverError, Solver
        except ImportError as exc:
            raise ImportError(
                "python-sat is required for the PySAT + CaDiCaL baseline"
            ) from exc

        try:
            with Solver(name=PYSAT_CADICAL_SOLVER_NAME, bootstrap_with=clauses, use_timer=True) as solver:
                is_sat = solver.solve()
                return is_sat, _solver_time_s(solver)
        except NoSuchSolverError as exc:
            raise RuntimeError(
                f"PySAT solver '{PYSAT_CADICAL_SOLVER_NAME}' is unavailable"
            ) from exc

    if backend == PYSAT_KISSAT404:
        try:
            from pysat.solvers import Kissat404
        except ImportError as exc:
            raise ImportError(
                "python-sat with Kissat404 support is required for the PySAT + Kissat 4.0.4 baseline"
            ) from exc

        with Kissat404(bootstrap_with=clauses, use_timer=True) as solver:
            is_sat = solver.solve()
            return is_sat, _solver_time_s(solver)

    raise ValueError(
        f"unsupported PySAT backend '{backend}', expected one of "
        f"'{PYSAT_CADICAL}', '{PYSAT_KISSAT404}'"
    )


def _solver_time_s(solver: object) -> float:
    """Return the PySAT solver-reported elapsed time for the last solve call."""
    try:
        return float(solver.time())
    except (AttributeError, TypeError, ValueError):
        return 0.0
