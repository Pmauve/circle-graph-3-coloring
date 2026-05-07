from __future__ import annotations

import os
import json
import subprocess
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

from three_col_circle_code.solvers.common import (
    SOLVER_STATUS_ERROR,
    SOLVER_STATUS_OK,
    SolverResult,
)
from three_col_circle_code.instances.native import THREE_COL_NATIVE_BIN_ENV


SAT_3_COL_NATIVE_SOLVER = "sat-3-col-native"
IMPLEMENTATION_STATUS = "native-rust-sat-v4"
DEFAULT_BACKEND = "dimacs-pipe"
SUPPORTED_BACKENDS = ("dimacs-pipe", "cadical-rustsat", "kissat-rustsat")
DEFAULT_TIMEOUT_S = 3600.0
PYTHON_TIMEOUT_GRACE_S = 30.0


def solve_sat_3_col_native_from_path(
    instance_path: str | Path,
    *,
    params: Optional[Mapping[str, Any]] = None,
) -> SolverResult:
    """Run the standalone Rust SAT encoder on a DIMACS-circle `.col` file."""
    config = dict(params or {})
    binary = _resolve_native_binary()
    n_vertices, m_edges = _read_problem_size(instance_path)
    try:
        backend = _parse_backend(config)
        solver_bin = _parse_solver_bin(config, backend=backend)
        timeout_s = _parse_timeout_s(config)
    except ValueError as exc:
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details={
                "implementation_status": IMPLEMENTATION_STATUS,
                "config": config,
                "binary": binary,
                "core_time_source": "missing",
            },
            error=str(exc),
        )

    details: dict[str, Any] = {
        "implementation_status": IMPLEMENTATION_STATUS,
        "config": config,
        "binary": binary,
        "backend": backend,
        "timeout_s": timeout_s,
        "core_time_source": "missing",
    }
    if solver_bin is not None:
        details["solver_bin"] = solver_bin
    if not binary or not Path(binary).is_file():
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details,
            error=f"{THREE_COL_NATIVE_BIN_ENV} is not set or does not point to an executable",
        )

    command = [
        binary,
        "sat",
        "solve",
        str(instance_path),
        "--backend",
        backend,
        "--timeout-s",
        _format_timeout(timeout_s),
    ]
    if solver_bin is not None:
        command.extend(["--solver-bin", solver_bin])
    started_at = perf_counter()
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_s + PYTHON_TIMEOUT_GRACE_S,
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
            error=f"native SAT timed out after {timeout_s:g}s",
            wall_time_s=wall_time_s,
        )
    except OSError as exc:
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details | {"command": command},
            error=f"failed to run native SAT binary: {exc}",
        )
    wall_time_s = perf_counter() - started_at

    status_line, timings, parse_error = _parse_native_stdout(completed.stdout)
    details.update(
        {
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }
    )
    details.update(timings)
    core_time_s = timings.get("core_time_s")
    if core_time_s is not None:
        details["core_time_source"] = "sat_native_reported"

    allowed_unknown_exit = completed.returncode == 3 and status_line == "UNKNOWN"
    if (
        (completed.returncode != 0 and not allowed_unknown_exit)
        or status_line == "ERROR"
        or parse_error is not None
    ):
        error_parts = []
        if parse_error is not None:
            error_parts.append(parse_error)
        if completed.returncode != 0:
            error_parts.append(f"native SAT exited with code {completed.returncode}")
        if completed.stderr:
            error_parts.append(completed.stderr.strip())
        if completed.stdout:
            error_parts.append(completed.stdout.strip())
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details,
            error="; ".join(error_parts) or "native SAT failed",
            wall_time_s=wall_time_s,
            core_time_s=core_time_s,
        )

    if status_line == "COLORABLE":
        is_colorable = True
    elif status_line == "NOT_COLORABLE":
        is_colorable = False
    elif status_line == "UNKNOWN":
        is_colorable = None
    else:
        return _error_result(
            n_vertices=n_vertices,
            m_edges=m_edges,
            details=details,
            error=f"unsupported native SAT status {status_line!r}",
            wall_time_s=wall_time_s,
            core_time_s=core_time_s,
        )

    return SolverResult(
        solver=SAT_3_COL_NATIVE_SOLVER,
        backend=None,
        status=SOLVER_STATUS_OK,
        wall_time_s=wall_time_s,
        core_time_s=core_time_s,
        is_colorable=is_colorable,
        n_vertices=n_vertices,
        m_edges=m_edges,
        details=details,
        error=None,
    )


def _parse_backend(config: Mapping[str, Any]) -> str:
    backend = str(config.get("backend", DEFAULT_BACKEND))
    if backend not in SUPPORTED_BACKENDS:
        raise ValueError(f"native SAT backend must be one of {SUPPORTED_BACKENDS!r}")
    return backend


def _parse_solver_bin(config: Mapping[str, Any], *, backend: str) -> Optional[str]:
    raw_value = config.get("solver_bin")
    if backend in {"cadical-rustsat", "kissat-rustsat"} and raw_value is None:
        return None
    if raw_value is None:
        raise ValueError("native SAT params.solver_bin is required")
    value = str(raw_value)
    if not value:
        raise ValueError("native SAT params.solver_bin must not be empty")
    return value


def _parse_timeout_s(config: Mapping[str, Any]) -> float:
    raw_value = config.get("timeout_s", DEFAULT_TIMEOUT_S)
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("native SAT parameter 'timeout_s' must be numeric") from exc
    if value <= 0.0:
        raise ValueError("native SAT parameter 'timeout_s' must be positive")
    return value


def _resolve_native_binary() -> Optional[str]:
    configured = os.environ.get(THREE_COL_NATIVE_BIN_ENV)
    if configured:
        return configured
    return None


def _parse_native_stdout(
    stdout: str,
) -> tuple[Optional[str], dict[str, float], Optional[str]]:
    stripped = stdout.strip()
    if stripped.startswith("{"):
        try:
            payload = json.loads(stripped.splitlines()[0])
        except json.JSONDecodeError as exc:
            return None, {}, f"invalid native SAT JSON output: {exc}"
        if not isinstance(payload, dict):
            return None, {}, "native SAT JSON output is not an object"
        solver_status = payload.get("solver_status")
        if solver_status is None:
            return None, {}, "native SAT JSON output is missing solver_status"
        timings = {}
        for key in ("core_time_s",):
            if key in payload:
                try:
                    timings[key] = float(payload[key])
                except (TypeError, ValueError):
                    return str(solver_status), timings, f"invalid native SAT {key} value {payload[key]!r}"
        return str(solver_status), timings, None

    status: Optional[str] = None
    timings: dict[str, float] = {}
    for raw_line in stdout.splitlines():
        parts = raw_line.strip().split()
        if not parts:
            continue
        if parts[:1] == ["s"] and len(parts) == 2:
            status = parts[1]
        elif parts[:1] == ["t"] and len(parts) == 3 and parts[1] == "core_time_s":
            try:
                timings[parts[1]] = float(parts[2])
            except ValueError:
                return status, timings, f"invalid native SAT {parts[1]} value {parts[2]!r}"
    if status is None:
        return None, timings, "native SAT output is missing status line"
    return status, timings, None


def _read_problem_size(instance_path: str | Path) -> tuple[int, int]:
    path = Path(instance_path)
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


def _format_timeout(timeout_s: float) -> str:
    return f"{timeout_s:g}"


def _error_result(
    *,
    n_vertices: int,
    m_edges: int,
    details: dict[str, Any],
    error: str,
    wall_time_s: Optional[float] = None,
    core_time_s: Optional[float] = None,
) -> SolverResult:
    return SolverResult(
        solver=SAT_3_COL_NATIVE_SOLVER,
        backend=None,
        status=SOLVER_STATUS_ERROR,
        wall_time_s=wall_time_s,
        core_time_s=core_time_s,
        is_colorable=None,
        n_vertices=n_vertices,
        m_edges=m_edges,
        details=details,
        error=error,
    )
