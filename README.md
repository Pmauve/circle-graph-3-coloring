# Circle Graph 3-Coloring: Can Simplicity Beat SAT?

This repository contains the code used for the experiments in
*Circle Graph 3-Coloring: Can Simplicity Beat SAT?*

The repository started from the experimental code accompanying Bachmann, Rutter,
and Stumpf, *On 3-Coloring Circle Graphs* (GD 2023). It has since been
extended for the experiments in the current paper. The main additions are Rust
implementations of the SOSA solver, native SAT baselines, new generators, and a
Python benchmark runner.

## Repository Status

Main workflow:

- native SOSA implementation for circle graph 3-coloring;
- native circle graph instance generation and validation;
- native SAT baselines using CaDiCaL/Kissat through RustSAT;
- Python scripts for benchmark planning, execution, merging, and reports.

Reference and compatibility code:

- older Python coloring and SAT implementations;
- PySMT/MathSAT-based legacy paths.

For the paper experiments, use the native Rust tools through the Python
benchmark runner.

## Quick Start

Install the Python package in editable mode:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Build and test the native tools:

```bash
cd native
cargo test
cargo build --release
cd ..
export THREE_COL_NATIVE_BIN="$PWD/native/target/release/three_col_native"
```

Run a small local benchmark smoke test:

```bash
benchmark_run --spec eval/sample_specs/pipeline-parallel-smoke.json --jobs 4
```

This creates a small run, generates the needed instances, runs the trials, and
writes an HTML report under `eval/runs/`.

On Windows PowerShell, set the native binary path with:

```powershell
$env:THREE_COL_NATIVE_BIN = "$PWD\native\target\release\three_col_native.exe"
```

If `benchmark_run` is not found, make sure the virtual environment is active and
rerun `python -m pip install -e ".[dev]"`.

## Benchmarks

Local benchmark runs use `benchmark_run`:

```bash
benchmark_run --spec eval/sample_specs/pipeline-smoke.json --jobs 4
```

The repository keeps only three example specs:

- `pipeline-smoke.json`: minimal end-to-end benchmark smoke test.
- `pipeline-parallel-smoke.json`: smoke test with local parallel execution.
- `native-sat-sosa-zykov-smoke.json`: example with SOSA, SAT, and ZykovColor entries.

The same run can also be staged step by step:

```bash
benchmark_plan --spec path/to/spec.json --run-id my-run --force
benchmark_generate_instance --plan-dir eval/benchmark_plans/my-run --index 1
benchmark_run_trial --plan-dir eval/benchmark_plans/my-run --index 1
benchmark_merge --plan-dir eval/benchmark_plans/my-run --output-root eval/runs --force
```

Generated benchmark directories are ignored by git:

- `eval/benchmark_plans/`
- `eval/benchmark_work/`
- `eval/runs/`
- generated files under `eval/instances/`

## Paper Artifacts

Summary data for the main benchmark run is included under:

```text
eval/paper_runs/native-density-yes-main-seed10-v2/
```

This directory contains the benchmark spec, sanitized run metadata, CSV
summaries used for the paper plots, and a static HTML report. The raw
trial-level `results.jsonl` file is omitted because it is large and contains
environment-specific metadata.

## Instance Families

The paper uses descriptive family names. Benchmark specs use shorter internal
identifiers:

| Paper name | Internal family |
| --- | --- |
| `random-any` | `rc_fast` |
| `simple-yes` | `rcy_fast` |
| `alpha-dense-yes` | `rccy_alpha` with `params.alpha` |

The native generator documentation is in `docs/native-generators.md`. The
DIMACS-circle format is documented in `docs/dimacs-circle.md`.

## External Solvers

The native SOSA solver and native SAT baseline are part of this repository.
Some comparison runs need additional solver support:

- CaDiCaL and Kissat are used through RustSAT in the native SAT baseline.
- ZykovColor is an optional external solver; see `docs/zykovcolor.md`.
- MathSAT/PySMT paths are retained for legacy comparison only and are not needed
  for the primary workflow.

Solver availability depends on the platform and local build environment. The
smoke specs avoid optional solvers where possible.

## Provenance

This repository builds on the experimental code released with:

P. Bachmann, I. Rutter, P. Stumpf. *On 3-Coloring Circle Graphs*. Proceedings of
the 31st International Symposium on Graph Drawing and Network Visualization
(GD 2023), pages 152-160. Springer Cham, 2023.
<https://doi.org/10.1007/978-3-031-49272-3_11>

The original project metadata declared the MIT license. This repository includes
a top-level MIT license file for clarity.

## Citation

If you use this repository, please cite the accompanying paper. Citation
metadata will be updated after publication.

## License

This repository is released under the MIT license. See `LICENSE`.
