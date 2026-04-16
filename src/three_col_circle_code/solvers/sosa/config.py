from dataclasses import dataclass
from typing import Any, Mapping, Optional


@dataclass(frozen=True, slots=True)
class SosaConfig:
    """Configuration for the paper-faithful SOSA solver."""

    base_case_n: int = 8

    @classmethod
    def from_mapping(cls, params: Optional[Mapping[str, Any]] = None) -> "SosaConfig":
        """Build a config from benchmark/user parameters."""
        if not params:
            return cls()
        if "base_case_n" in params:
            base_case_n = params["base_case_n"]
        else:
            # Temporary compatibility for the previous scaffold parameter name.
            base_case_n = params.get("brute_force_cutoff", cls.base_case_n)
        base_case_n = int(base_case_n)
        if base_case_n < 0:
            raise ValueError("SOSA parameter 'base_case_n' must be non-negative")
        return cls(base_case_n=base_case_n)

    def to_dict(self) -> dict[str, Any]:
        """Return a serializable config view."""
        return {"base_case_n": self.base_case_n}
