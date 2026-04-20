from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional


SUPPORTED_BASE_CASE_ALGORITHMS = ("backtracking", "sat")


@dataclass(frozen=True, slots=True)
class SosaConfig:
    """Configuration for the paper-faithful SOSA solver."""

    base_case_n: int = 8
    base_case_algorithm: str = "backtracking"

    @classmethod
    def from_mapping(cls, params: Optional[Mapping[str, Any]] = None) -> "SosaConfig":
        """Build a config from benchmark/user parameters."""
        defaults = cls()
        if not params:
            return defaults

        base_case_n = int(
            params.get("base_case_n", params.get("brute_force_cutoff", defaults.base_case_n))
        )
        if base_case_n < 0:
            raise ValueError("SOSA parameter 'base_case_n' must be non-negative")

        base_case_algorithm = str(
            params.get("base_case_algorithm", defaults.base_case_algorithm)
        )
        if base_case_algorithm not in SUPPORTED_BASE_CASE_ALGORITHMS:
            raise ValueError(
                "SOSA parameter 'base_case_algorithm' must be one of "
                f"{SUPPORTED_BASE_CASE_ALGORITHMS}"
            )

        return cls(
            base_case_n=base_case_n,
            base_case_algorithm=base_case_algorithm,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable config view."""
        return {
            "base_case_n": self.base_case_n,
            "base_case_algorithm": self.base_case_algorithm,
        }
