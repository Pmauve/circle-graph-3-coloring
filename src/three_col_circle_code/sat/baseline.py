from dataclasses import dataclass

LEGACY_PYSMT_MSAT = "legacy-pysmt-msat"
PYSAT_CADICAL = "pysat-cadical"
PYSAT_KISSAT404 = "pysat-kissat404"


@dataclass(frozen=True)
class BaselineSolveResult:
    is_sat: bool
    elapsed_time: float
    backend: str
    n_vertices: int
    m_edges: int
    elapsed_time_source: str


def solve_3color_baseline(graph, backend=PYSAT_CADICAL):
    if backend == LEGACY_PYSMT_MSAT:
        return _solve_legacy_pysmt_msat(graph)
    if backend == PYSAT_CADICAL:
        from three_col_circle_code.sat.pysat_baseline import solve_pysat_cadical

        return solve_pysat_cadical(graph)
    if backend == PYSAT_KISSAT404:
        from three_col_circle_code.sat.pysat_baseline import solve_pysat_kissat404

        return solve_pysat_kissat404(graph)
    raise ValueError(
        f"unsupported SAT baseline backend '{backend}', expected one of "
        f"'{LEGACY_PYSMT_MSAT}', '{PYSAT_CADICAL}', '{PYSAT_KISSAT404}'"
    )


def _solve_legacy_pysmt_msat(graph):
    from three_col_circle_code.sat_builder import is_three_colorable

    can_solve, elapsed_time = is_three_colorable(graph)
    return BaselineSolveResult(
        is_sat=can_solve,
        elapsed_time=elapsed_time,
        backend=LEGACY_PYSMT_MSAT,
        n_vertices=len(graph.nodes),
        m_edges=len(graph.edges),
        elapsed_time_source="mathsat_solve_timer",
    )
