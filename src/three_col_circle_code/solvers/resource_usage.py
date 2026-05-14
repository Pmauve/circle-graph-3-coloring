from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence


_MAX_RSS_RE = re.compile(r"Maximum resident set size \(kbytes\):\s*(\d+)")


@dataclass(frozen=True)
class ResourceUsage:
    """Resource usage captured for one external process invocation."""

    peak_rss_kb: Optional[int]
    method: str


def run_with_resource_usage(
    command: Sequence[str],
    *,
    check: bool = False,
    capture_output: bool = False,
    text: bool = False,
    timeout: Optional[float] = None,
) -> tuple[subprocess.CompletedProcess[str], ResourceUsage]:
    """Run a command and capture peak RSS when GNU time is available."""
    time_binary = _gnu_time_binary()
    if time_binary is None:
        completed = subprocess.run(
            list(command),
            check=check,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
        )
        return completed, ResourceUsage(peak_rss_kb=None, method="unavailable")

    usage_path = _temporary_usage_path()
    wrapped_command = [time_binary, "-v", "-o", str(usage_path), *command]
    try:
        completed = subprocess.run(
            wrapped_command,
            check=check,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
        )
        return completed, ResourceUsage(
            peak_rss_kb=_parse_peak_rss_kb(usage_path),
            method="gnu_time_v",
        )
    finally:
        try:
            usage_path.unlink()
        except FileNotFoundError:
            pass


def _gnu_time_binary() -> Optional[str]:
    if os.name == "nt":
        return None
    candidate = shutil.which("time")
    if candidate is not None and Path(candidate).is_file():
        return candidate
    usr_bin_time = Path("/usr/bin/time")
    if usr_bin_time.is_file():
        return str(usr_bin_time)
    return None


def _temporary_usage_path() -> Path:
    fd, raw_path = tempfile.mkstemp(prefix="three-col-resource-", suffix=".txt")
    os.close(fd)
    return Path(raw_path)


def _parse_peak_rss_kb(path: Path) -> Optional[int]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = _MAX_RSS_RE.search(text)
    if match is None:
        return None
    return int(match.group(1))
