from pathlib import Path
from typing import Iterable, Optional, Union

from three_col_circle_code.instances.io import load_instance


DEFAULT_INSTANCE_ROOT = Path("eval") / "instances"


def discover_instances(root: Union[str, Path] = DEFAULT_INSTANCE_ROOT) -> list[Path]:
    """Return all supported instance files below a root in deterministic order."""
    root_path = Path(root)
    if root_path.is_file():
        return [root_path] if root_path.suffix in {".col", ".json"} else []
    if not root_path.exists():
        return []
    return sorted(
        path
        for suffix in ("*.col", "*.json")
        for path in root_path.rglob(suffix)
        if path.is_file()
    )


def filter_instances(
    paths: Iterable[Union[str, Path]],
    *,
    family: Optional[str] = None,
    buckets: Optional[Iterable[str]] = None,
    n_min: Optional[int] = None,
    n_max: Optional[int] = None,
    source: Optional[str] = None,
    seed: Optional[int] = None,
    instance_ids: Optional[Iterable[str]] = None,
) -> list[Path]:
    """Filter instance paths by metadata fields and return them in deterministic order."""
    bucket_set = set(buckets) if buckets is not None else None
    instance_id_set = set(instance_ids) if instance_ids is not None else None
    matches: list[Path] = []

    for path in sorted(Path(path) for path in paths):
        record = load_instance(path)
        metadata = record.metadata
        if family is not None and metadata.family != family:
            continue
        if bucket_set is not None and metadata.bucket not in bucket_set:
            continue
        if n_min is not None and metadata.n < n_min:
            continue
        if n_max is not None and metadata.n > n_max:
            continue
        if source is not None and metadata.source != source:
            continue
        if seed is not None and metadata.seed != seed:
            continue
        if instance_id_set is not None and metadata.instance_id not in instance_id_set:
            continue
        matches.append(path)

    return matches
