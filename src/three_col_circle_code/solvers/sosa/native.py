from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

from three_col_circle_code.instances.dimacs_circle import write_dimacs_circle
from three_col_circle_code.instances.io import load_instance
from three_col_circle_code.solvers.common import (
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_OK,
    SolverResult,
)
from three_col_circle_code.solvers.resource_usage import run_with_resource_usage


SOSA_3_COL_NATIVE_SOLVER = "sosa-3-col-native"
SOSA_NATIVE_BIN_ENV = "SOSA_NATIVE_BIN"
IMPLEMENTATION_STATUS = "native-rust-file-backend"
DEFAULT_BASE_CASE_N = 128
DEFAULT_BASE_CASE_ALGORITHM = "backtracking"
SUPPORTED_BASE_CASE_ALGORITHMS = ("backtracking", "cadical-rustsat", "kissat-rustsat")
DEFAULT_INPUT_MODE = "strict-listed-edges"
SUPPORTED_INPUT_MODES = (
    "strict-listed-edges",
    "trusted-listed-edges",
    "lazy-circle-neighbors",
)
DEFAULT_TIMEOUT_S = 3600.0
DEFAULT_STATS = False


def solve_sosa_3_col_native_from_path(
    instance_path: str | Path,
    *,
    params: Optional[Mapping[str, Any]] = None,
    validate_instance_artifact: bool = False,
) -> SolverResult:
    """Run the standalone Rust SOSA solver on a DIMACS-circle `.col` file."""
    config = dict(params or {})
    binary = _resolve_native_binary()
    n_vertices, m_edges = _read_problem_size(instance_path)
    try:
        base_case_n = _parse_base_case_n(config)
        base_case_algorithm = _parse_base_case_algorithm(config)
        input_mode = _parse_input_mode(config)
        timeout_s = _parse_timeout_s(config)
        stats = _parse_stats(config)
    except ValueError as exc:
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details={
                "implementation_status": IMPLEMENTATION_STATUS,
                "config": config,
                "core_time_source": "missing",
                "binary": binary,
            },
            error=str(exc),
        )
    details: dict[str, Any] = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "config": config,
        "core_time_source": "missing",
        "binary": binary,
        "base_case_n": base_case_n,
        "base_case_algorithm": base_case_algorithm,
        "input_mode": input_mode,
        "timeout_s": timeout_s,
        "stats": stats,
        "skip_graph_validation": not validate_instance_artifact,
    }

    if not binary or not Path(binary).is_file():
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details,
            error=f"{SOSA_NATIVE_BIN_ENV} is not set or does not point to an executable",
        )

    try:
        with _native_input_path(instance_path) as native_input_path:
            return _run_native_binary(
                binary=binary,
                instance_path=native_input_path,
                n_vertices=n_vertices,
                m_edges=m_edges,
                base_case_n=base_case_n,
                base_case_algorithm=base_case_algorithm,
                input_mode=input_mode,
                timeout_s=timeout_s,
                stats=stats,
                validate_instance_artifact=validate_instance_artifact,
                details=details,
            )
    except Exception as exc:
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details | {"error_type": type(exc).__name__},
            error=str(exc),
        )


def _run_native_binary(
    *,
    binary: str,
    instance_path: Path,
    n_vertices: int,
    m_edges: int,
    base_case_n: int,
    base_case_algorithm: str,
    input_mode: str,
    timeout_s: float,
    stats: bool,
    validate_instance_artifact: bool,
    details: dict[str, Any],
) -> SolverResult:
    command = [
        binary,
        "solve",
        str(instance_path),
        "--base-case-n",
        str(base_case_n),
        "--base-case-algorithm",
        base_case_algorithm,
        "--input-mode",
        input_mode,
    ]
    if not validate_instance_artifact:
        command.append("--skip-graph-validation")
    if stats:
        command.append("--stats")

    started_at = perf_counter()
    try:
        completed, resource_usage = run_with_resource_usage(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        wall_time_s = perf_counter() - started_at
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details
            | {
                "command": command,
                "stdout_tail": _tail(exc.stdout),
                "stderr_tail": _tail(exc.stderr),
            },
            error=f"native SOSA timed out after {timeout_s:g}s",
            wall_time_s=wall_time_s,
        )
    except OSError as exc:
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details | {"command": command},
            error=f"failed to run native SOSA binary: {exc}",
        )
    wall_time_s = perf_counter() - started_at

    status_line, timings, parse_error = _parse_native_stdout(completed.stdout)
    native_solve_time_s = timings.get("solve_time_s", timings.get("core_time_s"))
    load_prepare_time_s = _sum_optional_timings(
        timings.get("parse_time_s"),
        timings.get("build_time_s"),
    )
    total_native_time_s = _sum_optional_timings(load_prepare_time_s, native_solve_time_s)
    legacy_core_time_s = timings.get("core_time_s")
    details.update(
        {
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
            "peak_rss_kb": resource_usage.peak_rss_kb,
            "resource_usage_source": resource_usage.method,
        }
    )
    details.update(timings)
    if native_solve_time_s is not None:
        details["solve_time_s"] = native_solve_time_s
    if load_prepare_time_s is not None:
        details["load_prepare_time_s"] = load_prepare_time_s
    if total_native_time_s is not None:
        details["total_native_time_s"] = total_native_time_s
    if total_native_time_s is not None:
        details["native_time_source"] = "sosa_native_total"
    elif legacy_core_time_s is not None:
        details["core_time_source"] = "sosa_native_reported"

    if completed.returncode != 0 or status_line == "ERROR" or parse_error is not None:
        error_parts = []
        if parse_error is not None:
            error_parts.append(parse_error)
        if completed.returncode != 0:
            error_parts.append(f"native SOSA exited with code {completed.returncode}")
        if completed.stderr:
            error_parts.append(completed.stderr.strip())
        if completed.stdout:
            error_parts.append(completed.stdout.strip())
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details,
            error="; ".join(error_parts) or "native SOSA failed",
            wall_time_s=wall_time_s,
            core_time_s=legacy_core_time_s,
            total_native_time_s=total_native_time_s,
            peak_rss_kb=resource_usage.peak_rss_kb,
        )

    if status_line == "COLORABLE":
        is_colorable = True
    elif status_line == "NOT_COLORABLE":
        is_colorable = False
    else:
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details,
            error=f"unsupported native SOSA status {status_line!r}",
            wall_time_s=wall_time_s,
            core_time_s=legacy_core_time_s,
            total_native_time_s=total_native_time_s,
            peak_rss_kb=resource_usage.peak_rss_kb,
        )

    return SolverResult(
        solver=SOSA_3_COL_NATIVE_SOLVER,
        backend=None,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        core_time_s=legacy_core_time_s,
        total_native_time_s=total_native_time_s,
        is_colorable=is_colorable,
        n_vertices=n_vertices,
        m_edges=m_edges,
        details=details,
        error=None,
        peak_rss_kb=resource_usage.peak_rss_kb,
    )


def _parse_base_case_n(config: Mapping[str, Any]) -> int:
    raw_value = config.get("base_case_n", DEFAULT_BASE_CASE_N)
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("native SOSA parameter 'base_case_n' must be an integer") from exc
    if value < 0:
        raise ValueError("native SOSA parameter 'base_case_n' must be non-negative")
    return value


def _parse_base_case_algorithm(config: Mapping[str, Any]) -> str:
    value = str(config.get("base_case_algorithm", DEFAULT_BASE_CASE_ALGORITHM))
    if value not in SUPPORTED_BASE_CASE_ALGORITHMS:
        raise ValueError(
            "native SOSA parameter 'base_case_algorithm' must be one of "
            f"{SUPPORTED_BASE_CASE_ALGORITHMS!r}"
        )
    return value


def _parse_input_mode(config: Mapping[str, Any]) -> str:
    value = str(config.get("input_mode", DEFAULT_INPUT_MODE))
    if value not in SUPPORTED_INPUT_MODES:
        raise ValueError(
            "native SOSA parameter 'input_mode' must be one of "
            f"{SUPPORTED_INPUT_MODES!r}"
        )
    return value


def _parse_timeout_s(config: Mapping[str, Any]) -> float:
    raw_value = config.get("timeout_s", DEFAULT_TIMEOUT_S)
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("native SOSA parameter 'timeout_s' must be numeric") from exc
    if value <= 0.0:
        raise ValueError("native SOSA parameter 'timeout_s' must be positive")
    return value


def _parse_stats(config: Mapping[str, Any]) -> bool:
    return _parse_bool_param(config, "stats", DEFAULT_STATS)


def _parse_bool_param(config: Mapping[str, Any], name: str, default: bool) -> bool:
    raw_value = config.get(name, default)
    if isinstance(raw_value, bool):
        return raw_value
    raise ValueError(f"native SOSA parameter '{name}' must be a boolean")


def _resolve_native_binary() -> Optional[str]:
    configured = os.environ.get(SOSA_NATIVE_BIN_ENV)
    if configured:
        return configured
    binary_name = "sosa_native.exe" if os.name == "nt" else "sosa_native"
    repo_root = Path(__file__).resolve().parents[4]
    candidate = repo_root / "native" / "sosa_native" / "target" / "release" / binary_name
    if candidate.is_file():
        return str(candidate)
    return None


class _native_input_path:
    def __init__(self, instance_path: str | Path):
        self.original_path = Path(instance_path)
        self._tempdir: Optional[tempfile.TemporaryDirectory[str]] = None
        self.path: Optional[Path] = None

    def __enter__(self) -> Path:
        if self.original_path.suffix == ".col":
            self.path = self.original_path
            return self.path

        record = load_instance(self.original_path, validate=False)
        self._tempdir = tempfile.TemporaryDirectory(prefix="sosa-native-")
        self.path = Path(self._tempdir.name) / f"{record.metadata.instance_id}.col"
        write_dimacs_circle(record, self.path)
        return self.path

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._tempdir is not None:
            self._tempdir.cleanup()


def _parse_native_stdout(stdout: str) -> tuple[Optional[str], dict[str, float], Optional[str]]:
    status: Optional[str] = None
    timings: dict[str, float] = {}
    for raw_line in stdout.splitlines():
        parts = raw_line.strip().split()
        if not parts:
            continue
        if parts[:1] == ["s"] and len(parts) == 2:
            status = parts[1]
        elif parts[:1] == ["t"] and len(parts) == 3 and parts[1] in {
            "core_time_s",
            "parse_time_s",
            "build_time_s",
            "solve_time_s",
        }:
            try:
                timings[parts[1]] = float(parts[2])
            except ValueError:
                return status, timings, f"invalid native SOSA {parts[1]} value {parts[2]!r}"
    if status is None:
        return None, timings, "native SOSA output is missing status line"
    return status, timings, None


def _sum_optional_timings(*values: Optional[float]) -> Optional[float]:
    if any(value is None for value in values):
        return None
    return sum(float(value) for value in values if value is not None)


def _read_problem_size(instance_path: str | Path) -> tuple[int, int]:
    path = Path(instance_path)
    if path.suffix != ".col":
        try:
            record = load_instance(path, validate=False)
            return record.graph.number_of_nodes(), record.graph.number_of_edges()
        except Exception:
            return 0, 0
    try:
        with path.open("r", encoding="utf-8-sig") as infile:
            for raw_line in infile:
                parts = raw_line.strip().split()
                if len(parts) == 4 and parts[0] == "p" and parts[1] in {"edge", "col"}:
                    return int(parts[2]), int(parts[3])
    except (OSError, ValueError):
        pass
    return 0, 0


def _tail(text: Optional[str], *, limit: int = 4000) -> str:
    if text is None:
        return ""
    return text[-limit:]


def _error_result(
    *,
    n_vertices: int,
    m_edges: int,
    details: dict[str, Any],
    error: str,
    wall_time_s: Optional[float] = None,
    core_time_s: Optional[float] = None,
    total_native_time_s: Optional[float] = None,
    peak_rss_kb: Optional[int] = None,
) -> SolverResult:
    return SolverResult(
        solver=SOSA_3_COL_NATIVE_SOLVER,
        backend=None,
        status=SOLVER_STATUS_ERROR,
        wall_time_s=wall_time_s,
        core_time_s=core_time_s,
        total_native_time_s=total_native_time_s,
        is_colorable=None,
        n_vertices=n_vertices,
        m_edges=m_edges,
        details=details,
        error=error,
        peak_rss_kb=peak_rss_kb,
    )
