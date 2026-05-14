from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional


SUPPORTED_BASE_CASE_ALGORITHMS = ("backtracking", "sat")
SUPPORTED_CONFIG_KEYS = (
    "base_case_n",
    "base_case_algorithm",
    "num_colors",
    "produce_witness",
)


@dataclass(frozen=True, slots=True)
class SosaConfig:
    """Configuration for the paper-faithful SOSA solver."""

    base_case_n: int = 8
    base_case_algorithm: str = "backtracking"
    num_colors: int = 3
    produce_witness: bool = True

    @classmethod
    def from_mapping(cls, params: Optional[Mapping[str, Any]] = None) -> "SosaConfig":
        """Build a config from benchmark/user parameters."""
        defaults = cls()
        if not params:
            return defaults
        unsupported_keys = sorted(set(params) - set(SUPPORTED_CONFIG_KEYS))
        if unsupported_keys:
            raise ValueError(
                "unsupported SOSA parameter(s): " + ", ".join(unsupported_keys)
            )

        base_case_n = int(params.get("base_case_n", defaults.base_case_n))
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

        num_colors = int(params.get("num_colors", defaults.num_colors))
        if num_colors < 1:
            raise ValueError("SOSA parameter 'num_colors' must be positive")

        produce_witness = params.get("produce_witness", defaults.produce_witness)
        if not isinstance(produce_witness, bool):
            raise ValueError("SOSA parameter 'produce_witness' must be a boolean")

        return cls(
            base_case_n=base_case_n,
            base_case_algorithm=base_case_algorithm,
            num_colors=num_colors,
            produce_witness=produce_witness,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable config view."""
        return {
            "base_case_n": self.base_case_n,
            "base_case_algorithm": self.base_case_algorithm,
            "num_colors": self.num_colors,
            "produce_witness": self.produce_witness,
        }
