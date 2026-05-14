import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from three_col_circle_code.generation.color_utils import validate_num_colors
from three_col_circle_code.generation.families import seeded_families
from three_col_circle_code.instances.catalog import DEFAULT_INSTANCE_ROOT
from three_col_circle_code.solvers.common import SolverConfig
from three_col_circle_code.solvers.registry import resolve_solver_configs


@dataclass(frozen=True)
class InstanceRequest:
    instance_id: str
    family: str
    n: int
    seed: int
    num_colors: int
    generator_params: dict[str, Any]
    family_label: str | None = None
    output_format: str = "circle"
    sequence_id: str | None = None


@dataclass(frozen=True)
class RunSpec:
    instance_pool_root: Path
    instance_requests: tuple[InstanceRequest, ...]
    solver_configs: tuple[SolverConfig, ...]
    repetitions: int = 1
    warmup_repetitions: int = 0


def load_run_spec(spec_path: Path) -> tuple[str, RunSpec]:
    spec_source = Path(spec_path).read_text(encoding="utf-8")
    try:
        payload = json.loads(spec_source)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid benchmark run spec JSON: {exc}") from exc
    return spec_source, normalize_run_spec(payload)


def normalize_run_spec(payload: Any) -> RunSpec:
    if not isinstance(payload, Mapping):
        raise ValueError("benchmark run spec must be a JSON object")
    if "name" in payload:
        raise ValueError("benchmark run spec field 'name' has been removed; use the spec filename stem instead")

    missing = [field for field in ("instances", "solvers") if field not in payload]
    if missing:
        raise ValueError("benchmark run spec is missing required field(s): " + ", ".join(missing))

    instances = payload["instances"]
    if not isinstance(instances, list) or not instances:
        raise ValueError("benchmark run spec field 'instances' must be a non-empty list")

    solvers = payload["solvers"]
    if not isinstance(solvers, list) or not solvers:
        raise ValueError("benchmark run spec field 'solvers' must be a non-empty list")

    normalized_instance_blocks = [_normalize_instance_block(block) for block in instances]
    return RunSpec(
        instance_pool_root=Path(payload.get("instance_pool_root", DEFAULT_INSTANCE_ROOT)),
        instance_requests=_expand_instance_requests(normalized_instance_blocks),
        solver_configs=_resolve_solver_configs([_normalize_solver_block(block) for block in solvers]),
        repetitions=_positive_int(payload.get("repetitions", 1), field_name="repetitions"),
        warmup_repetitions=_nonnegative_int(
            payload.get("warmup_repetitions", 0),
            field_name="warmup_repetitions",
        ),
    )


def _normalize_instance_block(block: Any) -> dict[str, Any]:
    if not isinstance(block, Mapping):
        raise ValueError("each run spec instance block must be an object")
    if "family" not in block:
        raise ValueError("run spec instance block is missing required field 'family'")
    if "seeds" not in block:
        raise ValueError("run spec instance block is missing required field 'seeds'")

    family = str(block["family"])
    if family not in seeded_families():
        raise ValueError(
            f"unsupported benchmark run family {family!r}; expected one of {sorted(seeded_families())}"
        )

    has_n_values = "n_values" in block
    has_n_range = "n" in block
    if has_n_values == has_n_range:
        raise ValueError("run spec instance block must contain exactly one of 'n_values' or 'n'")

    seeds = block["seeds"]
    if not isinstance(seeds, list) or not seeds:
        raise ValueError("run spec instance block field 'seeds' must be a non-empty list")
    normalized_seeds = [int(seed) for seed in seeds]
    if len(set(normalized_seeds)) != len(normalized_seeds):
        raise ValueError("run spec instance block field 'seeds' must not contain duplicates")

    normalized_block: dict[str, Any] = {
        "family": family,
        "seeds": sorted(normalized_seeds),
        "num_colors": _normalize_num_colors(block.get("num_colors", 3)),
        "params": _normalize_generator_params(family, block.get("params", {})),
        "label": _normalize_optional_label(block.get("label")),
        "output_format": _normalize_output_format(block.get("output_format", "circle")),
    }
    if has_n_values:
        n_values = block["n_values"]
        if not isinstance(n_values, list) or not n_values:
            raise ValueError("run spec instance block field 'n_values' must be a non-empty list")
        normalized_n_values = [int(value) for value in n_values]
        if any(value < 1 for value in normalized_n_values):
            raise ValueError("run spec instance block field 'n_values' must contain positive integers")
        if len(set(normalized_n_values)) != len(normalized_n_values):
            raise ValueError("run spec instance block field 'n_values' must not contain duplicates")
        normalized_block["n_values"] = sorted(normalized_n_values)
        return normalized_block

    n_range = block["n"]
    if not isinstance(n_range, Mapping):
        raise ValueError("run spec instance block field 'n' must be an object")
    missing = [field for field in ("start", "stop", "step") if field not in n_range]
    if missing:
        raise ValueError("run spec instance block field 'n' is missing required field(s): " + ", ".join(missing))
    start = int(n_range["start"])
    stop = int(n_range["stop"])
    step = int(n_range["step"])
    if start < 1 or stop < 1 or step < 1:
        raise ValueError("run spec instance block field 'n' requires positive start, stop, and step")
    if stop < start:
        raise ValueError("run spec instance block field 'n' requires stop >= start")
    normalized_block["n"] = {"start": start, "stop": stop, "step": step}
    return normalized_block


def _normalize_solver_block(block: Any) -> dict[str, Any]:
    if not isinstance(block, Mapping):
        raise ValueError("each run spec solver block must be an object")
    if "target" not in block:
        raise ValueError("run spec solver block is missing required field 'target'")
    params = block.get("params", {})
    if not isinstance(params, Mapping):
        raise ValueError("run spec solver block field 'params' must be an object")
    normalized: dict[str, Any] = {"target": str(block["target"]), "params": dict(params)}
    if "label" in block:
        label = str(block["label"]).strip()
        if not label:
            raise ValueError("run spec solver block field 'label' must not be empty")
        normalized["label"] = label
    return normalized


def _expand_instance_requests(instance_blocks: Sequence[Mapping[str, Any]]) -> tuple[InstanceRequest, ...]:
    requests: list[InstanceRequest] = []
    seen_instance_ids: set[str] = set()
    for block_index, block in enumerate(instance_blocks, start=1):
        from_range = "n" in block
        n_values = list(block["n_values"]) if not from_range else _expand_n_range(block["n"])
        for n_value in n_values:
            for seed_value in block["seeds"]:
                instance_id = instance_id_for_request(
                    family=block["family"],
                    n=n_value,
                    seed=seed_value,
                    num_colors=block["num_colors"],
                    generator_params=block["params"],
                )
                sequence_id = None
                if from_range:
                    sequence_id = (
                        f"block{block_index}:"
                        f"{block['family']}:{params_id_part(block['params'])}:"
                        f"k{block['num_colors']:02d}:seed{seed_value}:"
                        f"{block['output_format']}"
                    )
                if instance_id in seen_instance_ids:
                    raise ValueError(f"benchmark run spec contains duplicate instance request {instance_id!r}")
                seen_instance_ids.add(instance_id)
                requests.append(
                    InstanceRequest(
                        instance_id=instance_id,
                        family=block["family"],
                        n=n_value,
                        seed=seed_value,
                        num_colors=block["num_colors"],
                        generator_params=dict(block["params"]),
                        family_label=block["label"],
                        output_format=block["output_format"],
                        sequence_id=sequence_id,
                    )
                )
    return tuple(sorted(requests, key=lambda item: (item.family, item.num_colors, item.n, item.seed)))


def _expand_n_range(n_range: Mapping[str, Any]) -> list[int]:
    return list(range(int(n_range["start"]), int(n_range["stop"]) + 1, int(n_range["step"])))


def _resolve_solver_configs(solver_blocks: Sequence[Mapping[str, Any]]) -> tuple[SolverConfig, ...]:
    configs: list[SolverConfig] = []
    seen_configs: set[tuple[str, str]] = set()
    seen_labels: set[str] = set()
    for block in solver_blocks:
        resolved = resolve_solver_configs((block["target"],))
        for config in resolved:
            label = block.get("label")
            if label is not None:
                label = str(label)
                if label in seen_labels:
                    raise ValueError(
                        f"benchmark run spec contains duplicate solver label {label!r}"
                    )
                seen_labels.add(label)
            configured = SolverConfig(
                solver=config.solver,
                backend=config.backend,
                params=dict(block["params"]),
                label=label,
            )
            config_key = (configured.target, canonical_params_json(configured.params))
            if config_key in seen_configs:
                raise ValueError(
                    f"benchmark run spec contains duplicate solver configuration {configured.target!r}"
                )
            seen_configs.add(config_key)
            configs.append(configured)
    return tuple(sorted(configs, key=lambda config: config.target))


def instance_id_for_request(
    *,
    family: str,
    n: int,
    seed: int,
    num_colors: int,
    generator_params: Mapping[str, Any] | None = None,
) -> str:
    params_part = params_id_part(generator_params or {})
    if params_part:
        return f"{family}-{params_part}-k{num_colors:02d}-n{n:04d}-seed{seed}"
    return f"{family}-k{num_colors:02d}-n{n:04d}-seed{seed}"


def params_id_part(params: Mapping[str, Any]) -> str:
    if not params:
        return ""
    parts = []
    for key in sorted(params):
        value = params[key]
        if key == "alpha":
            parts.append(f"alpha{_float_id_label(float(value))}")
        else:
            parts.append(f"{key}{_value_id_label(value)}")
    return "-".join(parts)


def _normalize_num_colors(value: Any) -> int:
    num_colors = int(value)
    validate_num_colors(num_colors)
    return num_colors


def _normalize_generator_params(family: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("run spec instance block field 'params' must be an object")
    params = dict(value)
    if family == "rccy_alpha":
        allowed = {"alpha"}
        unknown = sorted(set(params).difference(allowed))
        if unknown:
            raise ValueError(f"unsupported rccy_alpha params: {unknown}")
        alpha = float(params.get("alpha", 0.0))
        if alpha < 0.0 or not math.isfinite(alpha):
            raise ValueError("rccy_alpha parameter 'alpha' must be finite and non-negative")
        return {"alpha": alpha}
    if params:
        raise ValueError(f"family {family!r} does not support generator params")
    return {}


def _normalize_optional_label(value: Any) -> str | None:
    if value is None:
        return None
    label = str(value).strip()
    if not label:
        raise ValueError("run spec instance block field 'label' must not be empty")
    return label


def _normalize_output_format(value: Any) -> str:
    output_format = str(value)
    if output_format not in {"col", "circle"}:
        raise ValueError("run spec instance block field 'output_format' must be 'col' or 'circle'")
    return output_format


def _float_id_label(value: float) -> str:
    label = f"{value:.12f}".rstrip("0").rstrip(".")
    return label.replace(".", "p")


def _value_id_label(value: Any) -> str:
    if isinstance(value, float):
        return _float_id_label(value)
    return str(value).replace(".", "p")


def canonical_params_json(params: Mapping[str, Any]) -> str:
    return json.dumps(dict(params), sort_keys=True, separators=(",", ":"))


def _positive_int(value: Any, *, field_name: str) -> int:
    normalized = int(value)
    if normalized < 1:
        raise ValueError(f"benchmark run spec field '{field_name}' must be a positive integer")
    return normalized


def _nonnegative_int(value: Any, *, field_name: str) -> int:
    normalized = int(value)
    if normalized < 0:
        raise ValueError(f"benchmark run spec field '{field_name}' must be non-negative")
    return normalized
