import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, mock_open, patch

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from three_col_circle_code.sat.baseline import LEGACY_PYSMT_MSAT, PYSAT_CADICAL
from three_col_circle_code.sat.main import main


class SatMainTests(unittest.TestCase):
    def _run_main(self, argv, expected_backend):
        writer = MagicMock()
        result = SimpleNamespace(is_sat=True, elapsed_time=0.25)

        with patch.object(sys, "argv", argv):
            with patch("three_col_circle_code.sat.main.os.listdir", return_value=["g.json"]):
                with patch("three_col_circle_code.sat.main.read_graph_from_json", return_value=nx.path_graph(2)):
                    with patch("three_col_circle_code.sat.main.solve_3color_baseline", return_value=result) as solve:
                        with patch("three_col_circle_code.sat.main.os.path.exists", return_value=True):
                            with patch("builtins.open", mock_open()):
                                with patch("three_col_circle_code.sat.main.csv.DictWriter", return_value=writer):
                                    main()

        solve.assert_called_once()
        self.assertEqual(solve.call_args.kwargs["backend"], expected_backend)
        writer.writeheader.assert_called_once()
        writer.writerows.assert_called_once()

    def test_main_uses_legacy_backend_by_default(self):
        self._run_main(
            ["evaluate_graphs", "r", "s"],
            LEGACY_PYSMT_MSAT,
        )

    def test_main_accepts_explicit_backend(self):
        self._run_main(
            ["evaluate_graphs", "r", "s", PYSAT_CADICAL],
            PYSAT_CADICAL,
        )


if __name__ == "__main__":
    unittest.main()
