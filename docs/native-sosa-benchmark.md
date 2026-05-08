# Native Rust SOSA Benchmark Backend

The native Rust solver is exposed to benchmark specs as:

```text
sosa-3-col-native
```

For serious benchmark runs, build and run the binary in the same environment as
the Python benchmark harness. In WSL/Linux:

```bash
cd native/sosa_native
cargo build --release
export SOSA_NATIVE_BIN="$PWD/target/release/sosa_native"
```

If `SOSA_NATIVE_BIN` is not set, the Python wrapper will also look for
`native/sosa_native/target/release/sosa_native` relative to the repository root.

On Windows PowerShell:

```powershell
cd native/sosa_native
cargo build --release
$env:SOSA_NATIVE_BIN="$PWD\target\release\sosa_native.exe"
```

Example solver block:

```yaml
solvers:
  - target: sosa-3-col-native
    label: SOSA base=128
    params:
      base_case_n: 128
      timeout_s: 3600
```

The native solver supports three base-case algorithms:

```text
backtracking
cadical-rustsat
kissat-rustsat
```

`backtracking` is the default and preserves the original in-process leaf search.
The RustSAT options solve the reduced SOSA list-coloring leaf directly through
CaDiCaL or Kissat:

```yaml
solvers:
  - target: sosa-3-col-native
    label: SOSA base=512 Kissat
    params:
      base_case_n: 512
      base_case_algorithm: kissat-rustsat
      timeout_s: 3600
```

The Python wrapper passes `.col` files directly to the Rust binary. Normal
benchmark trials pass `--skip-graph-validation`, because generated/reused
benchmark artifacts should already have been validated. The Rust solver still
performs syntax, range, and circle-shape checks; the skipped part is the
expensive crossing/edge consistency validation.

Legacy JSON instance paths are exported to a temporary DIMACS-circle file before
the Rust binary is invoked.

The native solver reports core solving time as:

```text
t core_time_s 0.000123
```

`core_time_s` is measured inside Rust after file parsing and compact instance
construction.

Extra native counters are opt-in for profiling:

```bash
sosa_native solve instance.col --base-case-n 512 --base-case-algorithm kissat-rustsat --stats
```

With `--stats`, the solver also prints `t` lines for solver calls, base-case
calls, SAT clause/literal counts, and SAT build/solve time. Leave `--stats` off
for performance benchmark runs.
