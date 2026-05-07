# Native Rust SAT Benchmark Backend

The native SAT baseline is exposed to benchmark specs as:

```text
sat-3-col-native
```

Build the Rust binary from the native workspace:

```bash
cd native
cargo build --release -p three_col_native
export THREE_COL_NATIVE_BIN="$PWD/target/release/three_col_native"
```

On the TU Wien cluster, keep the native binary and external SAT solver paths in
`env_cluster.sh` so SGE jobs and interactive smoke tests use the same tools:

```bash
export PATH="$HOME/.conda/envs/three-color/bin:$HOME/.cargo/bin:${PATH}"
export THREE_COL_NATIVE_BIN="$HOME/3-coloring-code/native/target/release/three_col_native"
export CADICAL_BIN="$HOME/opt/sat-solvers/cadical/build/cadical"
export KISSAT_BIN="$HOME/opt/sat-solvers/kissat/build/kissat"
```

Benchmark specs are JSON, so use absolute solver paths there rather than
`$CADICAL_BIN` or `$KISSAT_BIN`.

Example external solver block:

```json
{
  "target": "sat-3-col-native",
  "label": "Native SAT Kissat",
  "params": {
    "backend": "dimacs-pipe",
    "solver_bin": "/path/to/kissat",
    "timeout_s": 3600
  }
}
```

Example embedded CaDiCaL block:

```json
{
  "target": "sat-3-col-native",
  "label": "Native SAT CaDiCaL FFI",
  "params": {
    "backend": "cadical-ffi",
    "timeout_s": 3600
  }
}
```

Example embedded Kissat block:

```json
{
  "target": "sat-3-col-native",
  "label": "Native SAT Kissat 4.0.4 FFI",
  "params": {
    "backend": "kissat-ffi",
    "timeout_s": 3600
  }
}
```

The Rust binary reads the benchmark `.col` file as DIMACS edge input, ignores
circle comments, and builds the fixed 3-color CNF without materializing a
Python/NetworkX graph. With `backend = "dimacs-pipe"` it streams the CNF to the
configured SAT solver over stdin and parses the solver's SAT/UNSAT/UNKNOWN
status. With `backend = "cadical-ffi"` it adds clauses directly to the embedded
CaDiCaL binding in-process. With `backend = "kissat-ffi"` it adds clauses
directly to embedded Kissat 4.0.4 on Unix builds. Normal execution does not
write a `.cnf` file.

When the external SAT solver prints a recognized process-time line, the
`dimacs-pipe` wrapper reports that value as `core_time_s`:

```text
{"status":"ok","solver_status":"COLORABLE","core_time_s":0.004690}
```

For `cadical-ffi` and `kissat-ffi`, `core_time_s` is measured around the
embedded solver `solve()` call. `wall_time_s` is always measured by the Python
benchmark wrapper and includes Rust startup, `.col` parsing, clause
construction, and solving. For `dimacs-pipe`, `wall_time_s` also includes
external solver startup, DIMACS parsing, stdout/stderr handling, and process
shutdown.

External SAT binaries commonly exit with `10` for SAT and `20` for UNSAT. The
native wrapper accepts those conventional codes and treats other unexpected
nonzero exits as solver errors.
