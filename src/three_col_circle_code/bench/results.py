import json
import re
from pathlib import Path
from typing import Any, Dict, Union


DEFAULT_RUNS_ROOT = Path("eval") / "runs"
MANIFEST_FILENAME = "manifest.json"
RESULTS_FILENAME = "results.jsonl"


def normalize_run_label(label: str) -> str:
    """Return a filesystem-safe run label."""
    sanitized = _sanitize_label(label)
    if not sanitized:
        raise ValueError("run label must contain at least one alphanumeric character")
    return sanitized


def write_manifest(run_dir: Union[str, Path], manifest: Dict[str, Any]) -> Path:
    """Write the benchmark manifest JSON file for a run."""
    manifest_path = Path(run_dir) / MANIFEST_FILENAME
    with manifest_path.open("w", encoding="utf-8") as outfile:
        json.dump(manifest, outfile, indent=2, sort_keys=True)
        outfile.write("\n")
    return manifest_path


def append_result(run_dir: Union[str, Path], result: Dict[str, Any]) -> Path:
    """Append one structured result record to the run JSONL file."""
    results_path = Path(run_dir) / RESULTS_FILENAME
    with results_path.open("a", encoding="utf-8") as outfile:
        outfile.write(json.dumps(result, sort_keys=True))
        outfile.write("\n")
    return results_path


def _sanitize_label(label: str) -> str:
    collapsed = re.sub(r"[^A-Za-z0-9._-]+", "-", label.strip())
    collapsed = re.sub(r"-{2,}", "-", collapsed)
    return collapsed.strip("-")
