import platform
import socket
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


DEFAULT_PACKAGES = ("networkx", "pysmt", "python-sat", "pydot", "three_col_circle_code")


def collect_environment_metadata(
    package_names: Iterable[str] = DEFAULT_PACKAGES,
    repo_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Collect basic environment and version metadata for a benchmark run."""
    resolved_repo_root = repo_root or _detect_repo_root()
    return {
        "collected_at": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "hostname": socket.gethostname(),
        "executable": sys.executable,
        "git_root": str(resolved_repo_root) if resolved_repo_root is not None else None,
        "git_commit": _git_output(["rev-parse", "HEAD"], repo_root=resolved_repo_root),
        "git_dirty": _git_dirty(repo_root=resolved_repo_root),
        "package_versions": _package_versions(package_names),
    }


def _package_versions(package_names: Iterable[str]) -> Dict[str, str]:
    versions: Dict[str, str] = {}
    for package_name in package_names:
        try:
            versions[package_name] = importlib_metadata.version(package_name)
        except importlib_metadata.PackageNotFoundError:
            versions[package_name] = "not-installed"
    return versions


def _git_output(args: list[str], *, repo_root: Optional[Path]) -> str | None:
    if repo_root is None:
        return None
    try:
        completed = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _git_dirty(*, repo_root: Optional[Path]) -> bool | None:
    if repo_root is None:
        return None
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return bool(completed.stdout.strip())


def _detect_repo_root() -> Optional[Path]:
    """Find the checkout root containing this source file."""
    for candidate in Path(__file__).resolve().parents:
        if (candidate / ".git").exists():
            return candidate
    return None
