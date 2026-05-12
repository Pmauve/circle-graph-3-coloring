import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Any, Optional


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

    summary = validate_circle_with_python(path) if path.suffix == ".circle" else validate_col_with_native(path)
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


def validate_circle_with_python(instance_path: Path) -> NativeInstanceSummary:
    """Validate a compact DIMACS-circle geometry artifact without materializing edges."""
    path = Path(instance_path)
    comments: dict[str, str] = {}
    n_problem: int | None = None
    m_problem: int | None = None
    endpoint_order: list[int] = []
    in_endpoint_order = False
    saw_endpoint_order = False
    with path.open(encoding="utf-8") as infile:
        for line_number, raw_line in enumerate(infile, start=1):
            line = raw_line.strip().lstrip("\ufeff")
            if not line:
                continue
            parts = line.split()
            if parts[0] == "c":
                action = _circle_endpoint_order_action(parts[1:])
                if action == "START":
                    if in_endpoint_order or saw_endpoint_order:
                        raise NativeInstanceInvalid(f"duplicate or nested chord endpoint order at line {line_number}")
                    in_endpoint_order = True
                    saw_endpoint_order = True
                elif action == "END":
                    if not in_endpoint_order:
                        raise NativeInstanceInvalid(f"chord endpoint order END without START at line {line_number}")
                    in_endpoint_order = False
                elif in_endpoint_order:
                    try:
                        endpoint_order.extend(int(token) for token in parts[1:])
                    except ValueError as exc:
                        raise NativeInstanceInvalid(f"invalid endpoint id at line {line_number}") from exc
                else:
                    _capture_circle_metadata_comment(comments, parts[1:])
                continue
            if parts[0] == "p":
                if parts[1:2] != ["circle"] or len(parts) != 4:
                    raise NativeInstanceInvalid(f"unsupported circle problem line at line {line_number}: {line!r}")
                if n_problem is not None:
                    raise NativeInstanceInvalid(f"duplicate circle problem line at line {line_number}")
                try:
                    n_problem = int(parts[2])
                    m_problem = int(parts[3])
                except ValueError as exc:
                    raise NativeInstanceInvalid(f"invalid circle problem line at line {line_number}: {line!r}") from exc
                continue
            raise NativeInstanceInvalid(f"unsupported circle line at line {line_number}: {line!r}")

    if in_endpoint_order:
        raise NativeInstanceInvalid("chord endpoint order block is missing END")
    if n_problem is None or m_problem is None:
        raise NativeInstanceInvalid("circle file is missing a problem line")
    if not saw_endpoint_order:
        raise NativeInstanceInvalid("circle file is missing a chord endpoint order block")
    if len(endpoint_order) != 2 * n_problem:
        raise NativeInstanceInvalid(
            f"chord endpoint order has {len(endpoint_order)} entries, expected {2 * n_problem}"
        )
    counts = [0] * (n_problem + 1)
    for vertex in endpoint_order:
        if vertex < 1 or vertex > n_problem:
            raise NativeInstanceInvalid(f"endpoint vertex id {vertex} out of range 1..{n_problem}")
        counts[vertex] += 1
    bad_counts = [vertex for vertex in range(1, n_problem + 1) if counts[vertex] != 2]
    if bad_counts:
        raise NativeInstanceInvalid(f"vertices without exactly two endpoints: {bad_counts[:8]}")
    metadata_n = comments.get("n")
    metadata_m = comments.get("m")
    try:
        if metadata_n is not None and int(metadata_n) != n_problem:
            raise NativeInstanceInvalid(f"metadata n={metadata_n} does not match problem n={n_problem}")
        if metadata_m is not None and int(metadata_m) != m_problem:
            raise NativeInstanceInvalid(f"metadata m={metadata_m} does not match problem m={m_problem}")
        num_colors = None if comments.get("num_colors") is None else int(comments["num_colors"])
    except ValueError as exc:
        raise NativeInstanceInvalid("circle metadata contains a non-integer numeric field") from exc
    return NativeInstanceSummary(
        instance_id=comments.get("instance_id", path.stem),
        family=comments.get("family"),
        n=n_problem,
        m=m_problem,
        num_colors=num_colors,
    )


def generate_col_with_native(
    *,
    instance_path: Path,
    family: str,
    n: int,
    seed: int,
    num_colors: int = 3,
    max_attempts_per_node: int = 10_000,
    alpha: Optional[float] = None,
    output_format: str = "col",
) -> NativeInstanceSummary:
    """Generate a DIMACS-circle instance through the native CLI."""
    binary = os.environ.get(THREE_COL_NATIVE_BIN_ENV)
    if not binary:
        raise NativeInstanceError(f"{THREE_COL_NATIVE_BIN_ENV} is required for native instance generation")
    path = Path(instance_path)
    try:
        command = [
            binary,
            "instance",
            "generate",
            "--family",
            family,
            "--n",
            str(n),
            "--seed",
            str(seed),
            "--num-colors",
            str(num_colors),
            "--max-attempts-per-node",
            str(max_attempts_per_node),
            "--output",
            str(path),
        ]
        if alpha is not None:
            command.extend(["--alpha", str(alpha)])
        if output_format != "col":
            command.extend(["--output-format", output_format])
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise NativeInstanceError(f"failed to start {binary!r}: {exc}") from exc

    payload = _parse_native_json(completed.stdout)
    if completed.returncode != 0:
        message = str(payload.get("error") or completed.stderr or completed.stdout or "native generation failed")
        raise NativeInstanceError(message)
    if payload.get("status") != "ok":
        raise NativeInstanceError(f"unexpected native generation status {payload.get('status')!r}")
    return NativeInstanceSummary(
        instance_id=_optional_str(payload.get("instance_id")),
        family=_optional_str(payload.get("family")),
        n=int(payload["n"]),
        m=int(payload["m"]),
        num_colors=None if payload.get("num_colors") is None else int(payload["num_colors"]),
    )


def generate_col_sequence_with_native(
    *,
    output_dir: Path,
    family: str,
    start_n: int,
    stop_n: int,
    step_n: int,
    seed: int,
    num_colors: int = 3,
    max_attempts_per_node: int = 10_000,
    alpha: Optional[float] = None,
    output_format: str = "col",
) -> list[Path]:
    """Generate a sequence of DIMACS-circle instances through the native CLI."""
    binary = os.environ.get(THREE_COL_NATIVE_BIN_ENV)
    if not binary:
        raise NativeInstanceError(f"{THREE_COL_NATIVE_BIN_ENV} is required for native instance generation")
    try:
        command = [
            binary,
            "instance",
            "generate-sequence",
            "--family",
            family,
            "--start-n",
            str(start_n),
            "--stop-n",
            str(stop_n),
            "--step-n",
            str(step_n),
            "--seed",
            str(seed),
            "--num-colors",
            str(num_colors),
            "--max-attempts-per-node",
            str(max_attempts_per_node),
            "--output-dir",
            str(output_dir),
        ]
        if alpha is not None:
            command.extend(["--alpha", str(alpha)])
        if output_format != "col":
            command.extend(["--output-format", output_format])
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise NativeInstanceError(f"failed to start {binary!r}: {exc}") from exc

    payload = _parse_native_json(completed.stdout)
    if completed.returncode != 0:
        message = str(payload.get("error") or completed.stderr or completed.stdout or "native sequence generation failed")
        raise NativeInstanceError(message)
    if payload.get("status") != "ok":
        raise NativeInstanceError(f"unexpected native sequence status {payload.get('status')!r}")
    paths = payload.get("paths")
    if not isinstance(paths, list):
        raise NativeInstanceError("native sequence command did not return a paths list")
    return [Path(str(path)) for path in paths]


def materialize_circle_with_native(*, circle_path: Path, output_path: Path) -> NativeInstanceSummary:
    """Materialize a compact .circle file into a full .circle.col file through the native CLI."""
    binary = os.environ.get(THREE_COL_NATIVE_BIN_ENV)
    if not binary:
        raise NativeInstanceError(f"{THREE_COL_NATIVE_BIN_ENV} is required for native instance materialization")
    try:
        completed = subprocess.run(
            [
                binary,
                "instance",
                "materialize-circle",
                str(circle_path),
                "--output",
                str(output_path),
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise NativeInstanceError(f"failed to start {binary!r}: {exc}") from exc

    payload = _parse_native_json(completed.stdout)
    if completed.returncode != 0:
        message = str(payload.get("error") or completed.stderr or completed.stdout or "native materialization failed")
        raise NativeInstanceError(message)
    if payload.get("status") != "ok":
        raise NativeInstanceError(f"unexpected native materialization status {payload.get('status')!r}")
    return NativeInstanceSummary(
        instance_id=Path(circle_path).stem,
        family=None,
        n=int(payload["n"]),
        m=int(payload["m"]),
        num_colors=None,
    )


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


def _circle_endpoint_order_action(parts: list[str]) -> str | None:
    if len(parts) == 4 and parts[:3] == ["hord", "endpoint", "order"]:
        if parts[3] in {"START", "END"}:
            return parts[3]
        return "UNKNOWN"
    return None


def _capture_circle_metadata_comment(comments: dict[str, str], parts: list[str]) -> None:
    metadata_keys = {
        ("instance", "id"): "instance_id",
        ("family",): "family",
        ("n",): "n",
        ("m",): "m",
        ("num", "colors"): "num_colors",
    }
    for key_parts, key in metadata_keys.items():
        if tuple(parts[: len(key_parts)]) == key_parts and len(parts) > len(key_parts):
            comments[key] = " ".join(parts[len(key_parts) :])
            return


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
