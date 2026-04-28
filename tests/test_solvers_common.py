import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.solvers.common import (
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_OK,
    SolverConfig,
    SolverResult,
    solver_target,
)


class SolverCommonTests(unittest.TestCase):
    def test_solver_target_omits_missing_backend(self) -> None:
        self.assertEqual(solver_target("sosa-3-col-exact"), "sosa-3-col-exact")

    def test_solver_target_includes_backend(self) -> None:
        self.assertEqual(solver_target("sat-baseline", "pysat-cadical"), "sat-baseline:pysat-cadical")

    def test_solver_config_normalizes_optional_params(self) -> None:
        config = SolverConfig.from_mapping(
            "sosa-3-col-exact",
            params={"cutoff": 5},
            label="Exact SOSA",
        )

        self.assertEqual(config.solver, "sosa-3-col-exact")
        self.assertIsNone(config.backend)
        self.assertEqual(config.params, {"cutoff": 5})
        self.assertEqual(config.label, "Exact SOSA")
        self.assertEqual(config.target, "sosa-3-col-exact")

    def test_solver_result_stores_shared_result_fields(self) -> None:
        result = SolverResult(
            solver="sat-baseline",
            backend="legacy-pysmt-msat",
            status=SOLVER_STATUS_OK,
            wall_time_s=0.1,
            is_colorable=True,
            n_vertices=3,
            m_edges=2,
            details={"cutoff": 5},
            error=None,
        )

        self.assertEqual(result.status, SOLVER_STATUS_OK)
        self.assertEqual(result.backend, "legacy-pysmt-msat")
        self.assertTrue(result.is_colorable)
        self.assertEqual(result.details, {"cutoff": 5})
        self.assertNotEqual(SOLVER_STATUS_OK, SOLVER_STATUS_ERROR)


if __name__ == "__main__":
    unittest.main()
