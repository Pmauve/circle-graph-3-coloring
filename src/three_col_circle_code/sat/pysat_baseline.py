from dataclasses import dataclass
from time import perf_counter

COLOR_ORDER = ("r", "b", "g")
PYSAT_CADICAL_SOLVER_NAME = "cadical195"


@dataclass(frozen=True)
class ReducedColoringCnf:
    clauses: list[list[int]]
    var_map: dict[tuple[int, str], int]
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


def solve_pysat_cadical(graph):
    try:
        from pysat.solvers import NoSuchSolverError, Solver
    except ImportError as exc:
        raise ImportError(
            "python-sat is required for the PySAT + CaDiCaL baseline"
        ) from exc

    from three_col_circle_code.sat.baseline import BaselineSolveResult, PYSAT_CADICAL

    cnf = build_reduced_cnf(graph)

    try:
        with Solver(name=PYSAT_CADICAL_SOLVER_NAME, bootstrap_with=cnf.clauses) as solver:
            start = perf_counter()
            is_sat = solver.solve()
            elapsed_time = perf_counter() - start
    except NoSuchSolverError as exc:
        raise RuntimeError(
            f"PySAT solver '{PYSAT_CADICAL_SOLVER_NAME}' is unavailable"
        ) from exc

    return BaselineSolveResult(
        is_sat=is_sat,
        elapsed_time=elapsed_time,
        backend=PYSAT_CADICAL,
        n_vertices=len(graph.nodes),
        m_edges=len(graph.edges),
    )


def solve_pysat_kissat404(graph):
    try:
        from pysat.solvers import Kissat404
    except ImportError as exc:
        raise ImportError(
            "python-sat with Kissat404 support is required for the PySAT + Kissat 4.0.4 baseline"
        ) from exc

    from three_col_circle_code.sat.baseline import BaselineSolveResult, PYSAT_KISSAT404

    cnf = build_reduced_cnf(graph)

    with Kissat404(bootstrap_with=cnf.clauses) as solver:
        start = perf_counter()
        is_sat = solver.solve()
        elapsed_time = perf_counter() - start

    return BaselineSolveResult(
        is_sat=is_sat,
        elapsed_time=elapsed_time,
        backend=PYSAT_KISSAT404,
        n_vertices=len(graph.nodes),
        m_edges=len(graph.edges),
    )
