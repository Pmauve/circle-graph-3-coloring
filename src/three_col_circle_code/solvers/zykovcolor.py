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
from three_col_circle_code.solvers.resource_usage import run_with_resource_usage


ZYKOVCOLOR_SOLVER = "zykovcolor"
DEFAULT_DECISION_NUM_COLORS = 3
DEFAULT_CONFIGURATION = "assignment"
DEFAULT_TIMEOUT_S = 3600.0
ZYKOVCOLOR_BIN_ENV = "ZYKOVCOLOR_BIN"

_CHROMATIC_RE = re.compile(r"IncSatGC computed chromatic number of\s+(\d+)")
_PREPROCESS_CHROMATIC_RE = re.compile(r"Result:\s+Chromatic number of\s+(\d+)\s+was determined", re.IGNORECASE)
_INSTANCE_K_RE = re.compile(r"Instance is\s+(SAT|UNSAT)\s+for K\s*=\s*(\d+)", re.IGNORECASE)
_SINGLE_K_RE = re.compile(r"IncSatGC computed\s+(SAT|UNSAT)\s+for k\s*=\s*(\d+)")
_RESULT_TIME_RE = re.compile(r"Result:.*?\bat\s+(\d+)s\s+(\d+)ms")
_REPORTED_TIME_LABELS = {
    "stats_total_time_s": "Total",
    "preprocessing_time_s": "Preprocessing",
    "algorithm_time_s": "Algorithm",
    "building_encoding_time_s": "Building encoding",
    "building_at_most_k_constraints_time_s": "Building at most k constraints",
    "cegar_time_s": "CEGAR",
    "sat_solving_time_s": "Sat solving",
}
_DECIMAL_TOTAL_TIME_RE = re.compile(r"total time\D+([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_EFFECTIVE_ENCODING_RE = re.compile(r"Options\s+:\s+Encoding\s+=\s+(.+)")
_EFFECTIVE_STRATEGY_RE = re.compile(r"Options\s+:\s+Strategy\s+=\s+(.+)")


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
    """Parse ZykovColor output into a decision answer."""
    chromatic_match = _PREPROCESS_CHROMATIC_RE.search(stdout) or _CHROMATIC_RE.search(stdout)
    if chromatic_match:
        chromatic_number = int(chromatic_match.group(1))
        return chromatic_number <= decision_num_colors, {
            "zykovcolor_mode": "chromatic_number",
            "chromatic_number": chromatic_number,
        }

    instance_k_match = _INSTANCE_K_RE.search(stdout)
    if instance_k_match:
        status = instance_k_match.group(1).upper()
        k = int(instance_k_match.group(2))
        return status == "SAT", {"zykovcolor_mode": "single_k", "k": k, "raw_answer": status}

    single_k_match = _SINGLE_K_RE.search(stdout)
    if single_k_match:
        status = single_k_match.group(1)
        k = int(single_k_match.group(2))
        return status == "SAT", {"zykovcolor_mode": "single_k", "k": k, "raw_answer": status}
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
    mode = _normalize_mode(requested_params.get("mode"))
    solver_args = _solver_args(requested_params.get("solver", "cadical"))
    mode_args = _mode_args(
        mode,
        configuration=configuration,
        decision_num_colors=decision_num_colors,
        solver_args=solver_args,
    )
    extra_args = _normalize_extra_args(requested_params.get("extra_args", ()))
    if "--solver" in extra_args:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error="ZykovColor params.extra_args must not include --solver; use params.solver instead",
            details={"native_time_source": "missing", "core_time_source": "missing"},
        )
    command = [executable, str(dimacs_path), *mode_args, *extra_args]

    try:
        started_at = perf_counter()
        completed, resource_usage = run_with_resource_usage(
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

    reported_times = _parse_reported_times(completed.stdout)
    result_time_s = reported_times.get("result_time_s")
    total_native_time_s = result_time_s if result_time_s is not None else reported_times.get("stats_total_time_s")
    load_prepare_time_s = reported_times.get("preprocessing_time_s")
    solve_time_s = reported_times.get("algorithm_time_s")
    effective_options = _parse_effective_options(completed.stdout)
    details: dict[str, Any] = {
        "requested_params": requested_params,
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
        "peak_rss_kb": resource_usage.peak_rss_kb,
        "resource_usage_source": resource_usage.method,
        "decision_num_colors": decision_num_colors,
        "configuration": configuration,
        "requested_mode": mode,
        "effective_encoding": effective_options.get("encoding"),
        "effective_strategy": effective_options.get("strategy"),
        "native_time_source": "zykovcolor_reported" if total_native_time_s is not None else "missing",
        "total_native_time_s": total_native_time_s,
        "load_prepare_time_s": load_prepare_time_s,
        "solve_time_s": solve_time_s,
        "zykovcolor_result_time_s": reported_times.get("result_time_s"),
        "zykovcolor_stats_total_time_s": reported_times.get("stats_total_time_s"),
        "zykovcolor_preprocessing_time_s": reported_times.get("preprocessing_time_s"),
        "zykovcolor_algorithm_time_s": reported_times.get("algorithm_time_s"),
        "zykovcolor_building_encoding_time_s": reported_times.get("building_encoding_time_s"),
        "zykovcolor_building_at_most_k_constraints_time_s": reported_times.get(
            "building_at_most_k_constraints_time_s"
        ),
        "zykovcolor_cegar_time_s": reported_times.get("cegar_time_s"),
        "zykovcolor_sat_solving_time_s": reported_times.get("sat_solving_time_s"),
        "core_time_source": "zykovcolor_reported" if total_native_time_s is not None else "missing",
    }
    validation_error = _effective_option_error(
        mode=mode,
        effective_options=effective_options,
    )
    if completed.returncode != 0:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error=f"ZykovColor exited with code {completed.returncode}",
            wall_time_s=wall_time_s,
            details=details,
            peak_rss_kb=resource_usage.peak_rss_kb,
        )
    if validation_error is not None:
        return _error_result(
            record=record,
            requested_params=requested_params,
            error=validation_error,
            wall_time_s=wall_time_s,
            details=details,
            peak_rss_kb=resource_usage.peak_rss_kb,
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
            peak_rss_kb=resource_usage.peak_rss_kb,
        )
    is_colorable, parsed_details = parsed
    details.update(parsed_details)
    return SolverResult(
        solver=ZYKOVCOLOR_SOLVER,
        backend=None,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        core_time_s=total_native_time_s,
        total_native_time_s=total_native_time_s,
        is_colorable=is_colorable,
        n_vertices=record.graph.number_of_nodes(),
        m_edges=record.graph.number_of_edges(),
        details=details,
        error=None,
        peak_rss_kb=resource_usage.peak_rss_kb,
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


def _normalize_mode(value: Any) -> str:
    if value is None:
        return "chromatic-number"
    normalized = str(value)
    if normalized in {"chromatic-number", "chromatic_number"}:
        return "chromatic-number"
    if normalized in {"single-k", "single_k"}:
        return "single-k"
    raise ValueError("ZykovColor params.mode must be 'chromatic-number' or 'single-k'")


def _solver_args(value: Any) -> list[str]:
    normalized = str(value).lower()
    if normalized in {"cadical", "cadical195", "1"}:
        return ["--solver", "1"]
    if normalized in {"glucose", "0"}:
        return ["--solver", "0"]
    raise ValueError("ZykovColor params.solver must be 'cadical' or 'glucose'")


def _mode_args(
    value: str,
    *,
    configuration: str,
    decision_num_colors: int,
    solver_args: list[str],
) -> list[str]:
    normalized_configuration = configuration.replace("_", "-")
    if value == "chromatic-number":
        if normalized_configuration == "custom":
            return solver_args
        if normalized_configuration in {"zykov-color", "assignment", "partial-order"}:
            return [f"--{normalized_configuration}"]
        raise ValueError(
            "ZykovColor params.configuration must be 'zykov-color', 'assignment', 'partial-order', or 'custom'"
        )
    if value in {"single-k", "single_k"}:
        common = ["--strategy", "2", "--num-colors", str(decision_num_colors), *solver_args]
        if normalized_configuration == "assignment":
            return ["--encoding", "0", *common, "--assignment-amo"]
        if normalized_configuration == "partial-order":
            return [
                "--encoding",
                "4",
                *common,
                "--reduce-graph",
                "--use-clique",
                "--mycielski-bound",
            ]
        if normalized_configuration == "zykov-color":
            return [
                "--encoding",
                "5",
                *common,
                "--reduce-graph",
                "--use-clique",
                "--mycielski-bound",
                "--dominated-decisions",
            ]
        if normalized_configuration == "custom":
            return common
        raise ValueError(
            "ZykovColor params.configuration must be 'assignment', 'partial-order', 'zykov-color', or 'custom'"
        )
    raise ValueError("ZykovColor params.mode must be 'chromatic-number' or 'single-k'")


def _error_result(
    *,
    record: InstanceRecord,
    requested_params: dict[str, Any],
    error: str,
    wall_time_s: Optional[float] = None,
    details: Optional[dict[str, Any]] = None,
    peak_rss_kb: Optional[int] = None,
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
        peak_rss_kb=peak_rss_kb,
    )


def _tail(value: Optional[str], *, max_chars: int = 4000) -> str:
    if value is None:
        return ""
    return value[-max_chars:]


def _parse_core_time(stdout: str) -> Optional[float]:
    times = _parse_reported_times(stdout)
    if times.get("result_time_s") is not None:
        return times["result_time_s"]
    if times.get("stats_total_time_s") is not None:
        return times["stats_total_time_s"]
    decimal_match = _DECIMAL_TOTAL_TIME_RE.search(stdout)
    if decimal_match is None:
        return None
    return float(decimal_match.group(1))


def _parse_reported_times(stdout: str) -> dict[str, float]:
    times: dict[str, float] = {}
    result_matches = _RESULT_TIME_RE.findall(stdout)
    if result_matches:
        seconds, milliseconds = result_matches[-1]
        times["result_time_s"] = _seconds_from_parts(seconds, milliseconds)

    for key, label in _REPORTED_TIME_LABELS.items():
        pattern = re.compile(
            rf"Stats:\s+Time[^\r\n]*?{re.escape(label)}:\s*(\d+)s\s+(\d+)ms",
            re.IGNORECASE,
        )
        matches = pattern.findall(stdout)
        if matches:
            seconds, milliseconds = matches[-1]
            times[key] = _seconds_from_parts(seconds, milliseconds)
    return times


def _seconds_from_parts(seconds: str, milliseconds: str) -> float:
    return int(seconds) + int(milliseconds) / 1000.0


def _parse_effective_options(stdout: str) -> dict[str, str]:
    options: dict[str, str] = {}
    encoding_match = _EFFECTIVE_ENCODING_RE.search(stdout)
    if encoding_match is not None:
        options["encoding"] = encoding_match.group(1).strip()
    strategy_match = _EFFECTIVE_STRATEGY_RE.search(stdout)
    if strategy_match is not None:
        options["strategy"] = strategy_match.group(1).strip()
    return options


def _effective_option_error(*, mode: str, effective_options: dict[str, str]) -> Optional[str]:
    if mode == "single-k" and effective_options.get("strategy") not in {None, "Single K"}:
        return (
            "ZykovColor effective strategy does not match requested single-k mode "
            f"(got {effective_options.get('strategy')!r})"
        )
    return None
