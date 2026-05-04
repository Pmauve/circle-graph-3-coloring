import os
import re
import subprocess
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Optional, Sequence

import networkx as nx

from three_col_circle_code.instances.dimacs_circle import write_dimacs_circle
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.instances.model import InstanceMetadata, InstanceRecord, bucket_for_n
from three_col_circle_code.solvers.common import (
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_OK,
    SolverResult,
)


ZYKOVCOLOR_SOLVER = "zykovcolor"
DEFAULT_DECISION_NUM_COLORS = 3
DEFAULT_CONFIGURATION = "zykov-color"
DEFAULT_TIMEOUT_S = 3600.0
ZYKOVCOLOR_BIN_ENV = "ZYKOVCOLOR_BIN"

_CHROMATIC_RE = re.compile(r"IncSatGC computed chromatic number of\s+(\d+)")
_SINGLE_K_RE = re.compile(r"IncSatGC computed\s+(SAT|UNSAT)\s+for k\s*=\s*(\d+)")
_STATS_TOTAL_TIME_RE = re.compile(r"Stats:\s+Time\s+.*?Total:\s*(\d+)s\s+(\d+)ms")
_DECIMAL_TOTAL_TIME_RE = re.compile(r"total time\D+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)


def solve_zykovcolor(
    instance_or_graph: InstanceRecord | nx.Graph,
    *,
    params: Optional[Mapping[str, Any]] = None,
) -> SolverResult:
    """Run the external ZykovColor executable on a DIMACS-circle file."""
    requested_params = dict(params or {})
    record = _coerce_instance_record(instance_or_graph)
    try:
        with tempfile.TemporaryDirectory(prefix="zykovcolor-") as tmpdir:
            dimacs_path = Path(tmpdir) / f"{record.metadata.instance_id}.col"
            write_dimacs_circle(record, dimacs_path)
            return _run_zykovcolor_on_path(
                record=record,
                dimacs_path=dimacs_path,
                requested_params=requested_params,
            )
    except Exception as exc:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error=str(exc),
            details={"error_type": type(exc).__name__},
        )


def solve_zykovcolor_path(
    instance_path: Path,
    *,
    params: Optional[Mapping[str, Any]] = None,
) -> SolverResult:
    """Run ZykovColor directly on an existing DIMACS-circle file."""
    requested_params = dict(params or {})
    try:
        record = load_instance(instance_path, validate=False)
    except Exception as exc:
        return _error_result(
            record=_fallback_record_for_path(instance_path),
            requested_params=requested_params,
            error=str(exc),
            details={"error_type": type(exc).__name__},
        )
    return _run_zykovcolor_on_path(
        record=record,
        dimacs_path=Path(instance_path),
        requested_params=requested_params,
    )


def parse_zykovcolor_output(
    stdout: str,
    *,
    decision_num_colors: int = DEFAULT_DECISION_NUM_COLORS,
) -> Optional[tuple[bool, dict[str, Any]]]:
    """Parse the final ZykovColor result line into a decision answer."""
    single_k_match = _SINGLE_K_RE.search(stdout)
    if single_k_match:
        status = single_k_match.group(1)
        k = int(single_k_match.group(2))
        return status == "SAT", {"zykovcolor_mode": "single_k", "k": k, "raw_answer": status}

    chromatic_match = _CHROMATIC_RE.search(stdout)
    if chromatic_match:
        chromatic_number = int(chromatic_match.group(1))
        return chromatic_number <= decision_num_colors, {
            "zykovcolor_mode": "chromatic_number",
            "chromatic_number": chromatic_number,
        }
    return None


def _run_zykovcolor_on_path(
    *,
    record: InstanceRecord,
    dimacs_path: Path,
    requested_params: dict[str, Any],
) -> SolverResult:
    executable = str(requested_params.get("executable") or os.environ.get(ZYKOVCOLOR_BIN_ENV) or "ZykovColor")
    decision_num_colors = int(requested_params.get("decision_num_colors", DEFAULT_DECISION_NUM_COLORS))
    timeout_s = float(requested_params.get("timeout_s", DEFAULT_TIMEOUT_S))
    configuration = str(requested_params.get("configuration", DEFAULT_CONFIGURATION))
    mode_args = _mode_args(requested_params.get("mode"), decision_num_colors=decision_num_colors)
    extra_args = _normalize_extra_args(requested_params.get("extra_args", ()))
    command = [executable, str(dimacs_path), f"--{configuration}", *mode_args, *extra_args]

    try:
        started_at = perf_counter()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        wall_time_s = perf_counter() - started_at
    except subprocess.TimeoutExpired as exc:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error=f"ZykovColor timed out after {timeout_s:g}s",
            details={
                "timeout_s": timeout_s,
                "stdout_tail": _tail(exc.stdout),
                "stderr_tail": _tail(exc.stderr),
            },
        )
    except Exception as exc:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error=str(exc),
            details={"error_type": type(exc).__name__},
        )

    core_time_s = _parse_core_time(completed.stdout)
    details: dict[str, Any] = {
        "requested_params": requested_params,
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "decision_num_colors": decision_num_colors,
        "core_time_source": "zykovcolor_reported" if core_time_s is not None else "missing",
    }
    if completed.returncode != 0:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error=f"ZykovColor exited with code {completed.returncode}",
            wall_time_s=wall_time_s,
            details=details,
        )

    parsed = parse_zykovcolor_output(
        completed.stdout,
        decision_num_colors=decision_num_colors,
    )
    if parsed is None:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error="could not parse ZykovColor result",
            wall_time_s=wall_time_s,
            details=details,
        )
    is_colorable, parsed_details = parsed
    details.update(parsed_details)
    return SolverResult(
        solver=ZYKOVCOLOR_SOLVER,
        backend=None,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        core_time_s=core_time_s,
        is_colorable=is_colorable,
        n_vertices=record.graph.number_of_nodes(),
        m_edges=record.graph.number_of_edges(),
        details=details,
        error=None,
    )


def _coerce_instance_record(instance_or_graph: InstanceRecord | nx.Graph) -> InstanceRecord:
    if isinstance(instance_or_graph, InstanceRecord):
        return instance_or_graph
    graph = instance_or_graph
    metadata = InstanceMetadata(
        instance_id="graph",
        family="ad-hoc",
        seed=None,
        generator="ad_hoc_graph",
        n=graph.number_of_nodes(),
        m=graph.number_of_edges(),
        bucket=bucket_for_n(graph.number_of_nodes()),
        source="ad-hoc",
        created_at="unknown",
    )
    return InstanceRecord(metadata=metadata, graph=graph)


def _fallback_record_for_path(path: Path) -> InstanceRecord:
    graph = nx.Graph()
    metadata = InstanceMetadata(
        instance_id=Path(path).stem,
        family="dimacs-circle",
        seed=None,
        generator="dimacs_circle_import",
        n=0,
        m=0,
        bucket=bucket_for_n(0),
        source="imported",
        created_at="unknown",
    )
    return InstanceRecord(metadata=metadata, graph=graph)


def _normalize_extra_args(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, Sequence):
        raise ValueError("ZykovColor params.extra_args must be a string list")
    return [str(item) for item in value]


def _mode_args(value: Any, *, decision_num_colors: int) -> list[str]:
    if value is None or value == "chromatic-number":
        return []
    if value in {"single-k", "single_k"}:
        return ["--strategy", "2", "--num-colors", str(decision_num_colors)]
    raise ValueError("ZykovColor params.mode must be 'chromatic-number' or 'single-k'")


def _error_result(
    *,
    record: InstanceRecord,
    requested_params: dict[str, Any],
    error: str,
    wall_time_s: Optional[float] = None,
    details: Optional[dict[str, Any]] = None,
) -> SolverResult:
    merged_details = {"requested_params": requested_params}
    if details:
        merged_details.update(details)
    return SolverResult(
        solver=ZYKOVCOLOR_SOLVER,
        backend=None,
        status=SOLVER_STATUS_ERROR,
        wall_time_s=wall_time_s,
        core_time_s=None,
        is_colorable=None,
        n_vertices=record.graph.number_of_nodes(),
        m_edges=record.graph.number_of_edges(),
        details=merged_details,
        error=error,
    )


def _tail(value: Optional[str], *, max_chars: int = 4000) -> str:
    if value is None:
        return ""
    return value[-max_chars:]


def _parse_core_time(stdout: str) -> Optional[float]:
    stats_match = _STATS_TOTAL_TIME_RE.search(stdout)
    if stats_match is not None:
        seconds = int(stats_match.group(1))
        milliseconds = int(stats_match.group(2))
        return seconds + milliseconds / 1000.0
    decimal_match = _DECIMAL_TOTAL_TIME_RE.search(stdout)
    if decimal_match is None:
        return None
    return float(decimal_match.group(1))
