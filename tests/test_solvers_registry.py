import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord
from three_col_circle_code.solvers.common import SOLVER_STATUS_OK, SolverConfig, SolverResult
from three_col_circle_code.solvers.registry import (
    available_solver_names,
    resolve_solver_configs,
    run_solver,
)
from three_col_circle_code.solvers.sat import SAT_BASELINE_SOLVER
from three_col_circle_code.solvers.sosa import SOSA_SOLVER
from three_col_circle_code.sat.baseline import LEGACY_PYSMT_MSAT, PYSAT_CADICAL, PYSAT_KISSAT404


class SolverRegistryTests(unittest.TestCase):
    def test_available_solver_names_lists_registered_solver_families(self) -> None:
        self.assertEqual(available_solver_names(), (SAT_BASELINE_SOLVER, SOSA_SOLVER))

    def test_resolve_solver_configs_expands_sat_family_to_all_backends(self) -> None:
        configs = resolve_solver_configs((SAT_BASELINE_SOLVER,))

        self.assertEqual(
            [(config.solver, config.backend) for config in configs],
            [
                (SAT_BASELINE_SOLVER, LEGACY_PYSMT_MSAT),
                (SAT_BASELINE_SOLVER, PYSAT_CADICAL),
                (SAT_BASELINE_SOLVER, PYSAT_KISSAT404),
            ],
        )

    def test_run_solver_dispatches_to_sat_solver(self) -> None:
        graph = nx.path_graph(2)
        config = SolverConfig(solver=SAT_BASELINE_SOLVER, backend="pysat-cadical", params={"k": 1})
        fake_result = SolverResult(
            solver=SAT_BASELINE_SOLVER,
            backend="pysat-cadical",
            status=SOLVER_STATUS_OK,
            wall_time_s=0.1,
            is_colorable=True,
            n_vertices=2,
            m_edges=1,
            details={},
            error=None,
        )

        with patch(
            "three_col_circle_code.solvers.registry.solve_sat_solver",
            return_value=fake_result,
        ) as solve:
            result = run_solver(graph, config)

        solve.assert_called_once_with(graph, backend="pysat-cadical", params={"k": 1})
        self.assertIs(result, fake_result)

    def test_run_solver_accepts_instance_record_and_unwraps_graph(self) -> None:
        graph = nx.path_graph(2)
        record = InstanceRecord(
            metadata=InstanceMetadata(
                instance_id="path-2",
                family="paper",
                seed=None,
                generator="manual",
                n=2,
                m=1,
                bucket="s",
                source="handcrafted",
                created_at="2026-04-13T00:00:00Z",
            ),
            graph=graph,
        )
        config = SolverConfig(solver=SAT_BASELINE_SOLVER, backend="legacy-pysmt-msat")
        fake_result = SolverResult(
            solver=SAT_BASELINE_SOLVER,
            backend="legacy-pysmt-msat",
            status=SOLVER_STATUS_OK,
            wall_time_s=0.1,
            is_colorable=True,
            n_vertices=2,
            m_edges=1,
            details={},
            error=None,
        )

        with patch(
            "three_col_circle_code.solvers.registry.solve_sat_solver",
            return_value=fake_result,
        ) as solve:
            result = run_solver(record, config)

        solve.assert_called_once_with(graph, backend="legacy-pysmt-msat", params={})
        self.assertIs(result, fake_result)

    def test_resolve_solver_configs_rejects_unknown_solver(self) -> None:
        with self.assertRaises(ValueError):
            resolve_solver_configs(("unknown",))

    def test_run_solver_dispatches_to_sosa_solver(self) -> None:
        graph = nx.path_graph(2)
        config = SolverConfig(solver=SOSA_SOLVER, params={"brute_force_cutoff": 8})
        fake_result = SolverResult(
            solver=SOSA_SOLVER,
            backend=None,
            status=SOLVER_STATUS_OK,
            wall_time_s=0.1,
            is_colorable=True,
            n_vertices=2,
            m_edges=1,
            details={},
            error=None,
        )

        with patch(
            "three_col_circle_code.solvers.registry.solve_sosa",
            return_value=fake_result,
        ) as solve:
            result = run_solver(graph, config)

        solve.assert_called_once_with(graph, params={"brute_force_cutoff": 8})
        self.assertIs(result, fake_result)


if __name__ == "__main__":
    unittest.main()
