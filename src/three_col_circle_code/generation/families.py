from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
import random
from typing import Iterable


@dataclass(frozen=True)
class FamilySpec:
    family: str
    graph_generator_attr: str
    legacy_cli_supported: bool
    seeded_supported: bool
    seeded_generator_name: str | None
    legacy_path_tokens: tuple[str, ...]


FAMILY_SPECS: tuple[FamilySpec, ...] = (
    FamilySpec(
        family="r",
        graph_generator_attr="get_random_graph",
        legacy_cli_supported=True,
        seeded_supported=False,
        seeded_generator_name=None,
        legacy_path_tokens=("r",),
    ),
    FamilySpec(
        family="ry",
        graph_generator_attr="get_random_yes_inst",
        legacy_cli_supported=True,
        seeded_supported=False,
        seeded_generator_name=None,
        legacy_path_tokens=("ry",),
    ),
    FamilySpec(
        family="rc",
        graph_generator_attr="get_random_circle_graph",
        legacy_cli_supported=True,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_legacy",
        legacy_path_tokens=("rc",),
    ),
    FamilySpec(
        family="rc_fast",
        graph_generator_attr="get_random_circle_graph_fast",
        legacy_cli_supported=True,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_fast_legacy_like",
        legacy_path_tokens=("rc_fast",),
    ),
    FamilySpec(
        family="rcy",
        graph_generator_attr="get_random_circle_graph_yes_inst",
        legacy_cli_supported=True,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_yes_legacy",
        legacy_path_tokens=("rcy",),
    ),
    FamilySpec(
        family="rcy_fast",
        graph_generator_attr="get_random_circle_graph_yes_fast",
        legacy_cli_supported=True,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_yes_fast_legacy_like",
        legacy_path_tokens=("rcy_fast",),
    ),
    FamilySpec(
        family="rccy",
        graph_generator_attr="get_random_circle_graph_yes_inst_constructive",
        legacy_cli_supported=True,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_yes_constructive_tuned",
        legacy_path_tokens=("rccy",),
    ),
    FamilySpec(
        family="rccy_tuned",
        graph_generator_attr="get_random_circle_graph_yes_inst_constructive_tuned",
        legacy_cli_supported=False,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_yes_constructive_tuned",
        legacy_path_tokens=("rccy_tuned",),
    ),
    FamilySpec(
        family="rccy_baseline",
        graph_generator_attr="get_random_circle_graph_yes_inst_constructive_baseline",
        legacy_cli_supported=False,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_yes_constructive_baseline",
        legacy_path_tokens=("rccy_baseline",),
    ),
    FamilySpec(
        family="rccy_full_sweep_weighted_active",
        graph_generator_attr="get_random_circle_graph_yes_inst_constructive_full_sweep_weighted_active",
        legacy_cli_supported=False,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_yes_constructive_full_sweep_weighted_active",
        legacy_path_tokens=("rccy_full_sweep_weighted_active",),
    ),
    FamilySpec(
        family="rccy_full_sweep_max_active",
        graph_generator_attr="get_random_circle_graph_yes_inst_constructive_full_sweep_max_active",
        legacy_cli_supported=False,
        seeded_supported=True,
        seeded_generator_name="seeded_random_circle_graph_yes_constructive_full_sweep_max_active",
        legacy_path_tokens=("rccy_full_sweep_max_active",),
    ),
)

_FAMILY_BY_NAME = {spec.family: spec for spec in FAMILY_SPECS}


def get_family_spec(family: str) -> FamilySpec:
    try:
        return _FAMILY_BY_NAME[family]
    except KeyError as exc:
        raise ValueError(f"unsupported family {family!r}; expected one of {sorted(_FAMILY_BY_NAME)}") from exc


def legacy_cli_families() -> tuple[str, ...]:
    return tuple(spec.family for spec in FAMILY_SPECS if spec.legacy_cli_supported)


def seeded_families() -> tuple[str, ...]:
    return tuple(spec.family for spec in FAMILY_SPECS if spec.seeded_supported)


def generate_seeded_family(*, family: str, n: int, seed: int, max_attempts_per_node: int):
    spec = get_family_spec(family)
    if not spec.seeded_supported or spec.seeded_generator_name is None:
        raise ValueError(f"family {family!r} does not support seeded instance generation")
    graph_generator_fn = _load_graph_generator_fn(spec.graph_generator_attr)
    graph = graph_generator_fn(
        n,
        save=False,
        rng=random.Random(seed),
        max_attempts_per_node=max_attempts_per_node,
    )
    return graph, spec.seeded_generator_name


def run_legacy_cli_family(*, family: str, n_nodes: int, timestamp: float):
    spec = get_family_spec(family)
    if not spec.legacy_cli_supported:
        raise ValueError(f"family {family!r} does not support the legacy generator CLI")
    graph_generator_fn = _load_graph_generator_fn(spec.graph_generator_attr)
    return graph_generator_fn(n_nodes, timestamp=timestamp)


def infer_legacy_family_from_parts(parts: Iterable[str]) -> str | None:
    normalized_parts = {part.lower() for part in parts}
    for spec in FAMILY_SPECS:
        if any(token in normalized_parts for token in spec.legacy_path_tokens):
            return spec.family
    return None


@lru_cache(maxsize=None)
def _load_graph_generator_fn(name: str):
    module = import_module("three_col_circle_code.graph_generator")
    return getattr(module, name)
