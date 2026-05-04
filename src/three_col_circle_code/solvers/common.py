from dataclasses import dataclass, field
from typing import Any, Mapping, Optional


SOLVER_STATUS_OK = "ok"
SOLVER_STATUS_ERROR = "error"


@dataclass(frozen=True)
class SolverConfig:
    """Generic solver invocation settings."""

    solver: str
    backend: Optional[str] = None
    params: dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None

    @classmethod
    def from_mapping(
        cls,
        solver: str,
        *,
        backend: Optional[str] = None,
        params: Optional[Mapping[str, Any]] = None,
        label: Optional[str] = None,
    ) -> "SolverConfig":
        """Build a config from optional mapping inputs."""
        return cls(
            solver=solver,
            backend=backend,
            params=dict(params or {}),
            label=label,
        )

    @property
    def target(self) -> str:
        """Return the stable solver target string."""
        return solver_target(self.solver, self.backend)


@dataclass(frozen=True)
class SolverResult:
    """Normalized result shape shared by all non-legacy solvers."""

    solver: str
    backend: Optional[str]
    status: str
    wall_time_s: Optional[float]
    is_colorable: Optional[bool]
    n_vertices: int
    m_edges: int
    details: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    core_time_s: Optional[float] = None


def solver_target(solver: str, backend: Optional[str] = None) -> str:
    """Build a stable solver target identifier."""
    if backend is None:
        return solver
    return f"{solver}:{backend}"
