import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any


THREE_COL_NATIVE_BIN_ENV = "THREE_COL_NATIVE_BIN"


class NativeInstanceError(RuntimeError):
    """Raised when native instance validation cannot be executed."""


class NativeInstanceInvalid(ValueError):
    """Raised when native validation rejects an instance."""


@dataclass(frozen=True)
class NativeInstanceSummary:
    instance_id: str | None
    family: str | None
    n: int
    m: int
    num_colors: int | None


def validation_sidecar_path(instance_path: Path) -> Path:
    return Path(str(instance_path) + ".validation.json")


def ensure_validated_sidecar(instance_path: Path, *, force: bool = False) -> NativeInstanceSummary:
    """Return native instance metadata, validating and writing a sidecar if needed."""
    path = Path(instance_path)
    digest = sha256_file(path)
    sidecar = validation_sidecar_path(path)
    if not force:
        cached = _read_current_sidecar(sidecar, instance_path=path, digest=digest)
        if cached is not None:
            return NativeInstanceSummary(
                instance_id=str(cached["instance_id"]),
                family=None,
                n=0,
                m=0,
                num_colors=None,
            )

    summary = validate_col_with_native(path)
    _write_sidecar(sidecar, summary=summary, digest=digest)
    return summary


def sidecar_is_current(instance_path: Path) -> bool:
    path = Path(instance_path)
    sidecar = validation_sidecar_path(path)
    if not sidecar.exists() or not path.exists():
        return False
    return _read_current_sidecar(sidecar, instance_path=path, digest=sha256_file(path)) is not None


def validate_col_with_native(instance_path: Path) -> NativeInstanceSummary:
    return _run_native_instance_command("validate", Path(instance_path))


def inspect_col_with_native(instance_path: Path) -> NativeInstanceSummary:
    return _run_native_instance_command("inspect", Path(instance_path))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as infile:
        for chunk in iter(lambda: infile.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_native_instance_command(command: str, instance_path: Path) -> NativeInstanceSummary:
    binary = os.environ.get(THREE_COL_NATIVE_BIN_ENV)
    if not binary:
        raise NativeInstanceError(f"{THREE_COL_NATIVE_BIN_ENV} is required for native instance validation")
    try:
        completed = subprocess.run(
            [binary, "instance", command, str(instance_path)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise NativeInstanceError(f"failed to start {binary!r}: {exc}") from exc

    payload = _parse_native_json(completed.stdout)
    if completed.returncode != 0:
        message = str(payload.get("error") or completed.stderr or completed.stdout or "native validation failed")
        if completed.returncode == 2:
            raise NativeInstanceInvalid(message)
        raise NativeInstanceError(message)
    if payload.get("status") != "ok":
        raise NativeInstanceError(f"unexpected native instance status {payload.get('status')!r}")
    return NativeInstanceSummary(
        instance_id=_optional_str(payload.get("instance_id")),
        family=_optional_str(payload.get("family")),
        n=int(payload["n"]),
        m=int(payload["m"]),
        num_colors=None if payload.get("num_colors") is None else int(payload["num_colors"]),
    )


def _parse_native_json(stdout: str) -> dict[str, Any]:
    first_line = stdout.strip().splitlines()[0] if stdout.strip() else "{}"
    try:
        payload = json.loads(first_line)
    except json.JSONDecodeError as exc:
        raise NativeInstanceError(f"native instance command returned invalid JSON: {stdout!r}") from exc
    if not isinstance(payload, dict):
        raise NativeInstanceError("native instance command returned non-object JSON")
    return payload


def _read_current_sidecar(sidecar: Path, *, instance_path: Path, digest: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("validated") is not True:
        return None
    if payload.get("sha256") != digest:
        return None
    expected_instance_id = instance_path.stem
    if payload.get("instance_id") != expected_instance_id:
        return None
    return payload


def _write_sidecar(sidecar: Path, *, summary: NativeInstanceSummary, digest: str) -> None:
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "instance_id": summary.instance_id,
        "sha256": digest,
        "validated": True,
    }
    tmp_path = sidecar.with_name(f".{sidecar.name}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    tmp_path.replace(sidecar)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
