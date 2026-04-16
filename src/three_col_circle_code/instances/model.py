from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, Mapping, Optional

import networkx as nx


INSTANCE_FORMAT_VERSION = 1
CANONICAL_NODE_LINK_EDGES_KEY = "edges"
LEGACY_NODE_LINK_EDGES_KEY = "links"


class InstanceFormatError(ValueError):
    """Raised when an instance file or metadata block has the wrong shape."""

    pass


@dataclass(frozen=True)
class InstanceMetadata:
    """Structured metadata stored alongside a canonical instance graph."""

    instance_id: str
    family: str
    seed: Optional[int]
    generator: str
    n: int
    m: int
    bucket: str
    source: str
    created_at: str
    generation_time_seconds: Optional[float] = None
    max_attempts_per_node: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return metadata as a plain dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "InstanceMetadata":
        """Build metadata from a mapping and enforce required fields."""
        required_fields = (
            "instance_id",
            "family",
            "generator",
            "n",
            "m",
            "bucket",
            "source",
            "created_at",
        )
        missing = [field for field in required_fields if field not in data]
        if missing:
            raise InstanceFormatError(
                "instance metadata is missing required field(s): " + ", ".join(missing)
            )
        return cls(
            instance_id=str(data["instance_id"]),
            family=str(data["family"]),
            seed=data.get("seed"),
            generator=str(data["generator"]),
            n=int(data["n"]),
            m=int(data["m"]),
            bucket=str(data["bucket"]),
            source=str(data["source"]),
            created_at=str(data["created_at"]),
            generation_time_seconds=(
                None
                if data.get("generation_time_seconds") is None
                else float(data["generation_time_seconds"])
            ),
            max_attempts_per_node=(
                None
                if data.get("max_attempts_per_node") is None
                else int(data["max_attempts_per_node"])
            ),
        )


@dataclass(frozen=True)
class InstanceRecord:
    """Bundle canonical metadata and the corresponding NetworkX graph."""

    metadata: InstanceMetadata
    graph: nx.Graph


@dataclass(frozen=True)
class ValidationIssue:
    """Single validation problem found in an instance graph or metadata block."""

    code: str
    message: str


@dataclass
class ValidationReport:
    """Collected validation errors and warnings for one instance."""

    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return True when validation found no errors."""
        return not self.errors

    def add_error(self, code: str, message: str) -> None:
        """Append an error entry to the report."""
        self.errors.append(ValidationIssue(code=code, message=message))

    def add_warning(self, code: str, message: str) -> None:
        """Append a warning entry to the report."""
        self.warnings.append(ValidationIssue(code=code, message=message))


def build_legacy_metadata(
    *, instance_id: str, n: int, m: int, family: str = "legacy", created_at: Optional[str] = None
) -> InstanceMetadata:
    """Create synthetic metadata for a legacy raw node-link graph file."""
    return InstanceMetadata(
        instance_id=instance_id,
        family=family,
        seed=None,
        generator="legacy_node_link",
        n=n,
        m=m,
        bucket=bucket_for_n(n),
        source="legacy",
        created_at=created_at or datetime.now(UTC).isoformat(),
    )


def bucket_for_n(n: int) -> str:
    """Map an exact vertex count to the project's size bucket label."""
    if n <= 250:
        return "s"
    if n <= 750:
        return "m"
    if n <= 1500:
        return "l"
    return "xl"
