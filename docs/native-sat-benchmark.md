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

On the TU Wien cluster, keep the native binary path in `env_cluster.sh` so SGE
jobs and interactive smoke tests use the same build:

```bash
export PATH="$HOME/.conda/envs/three-color/bin:$HOME/.cargo/bin:${PATH}"
export THREE_COL_NATIVE_BIN="$HOME/3-coloring-code/native/target/release/three_col_native"
```

Example CaDiCaL block:

```json
{
  "target": "sat-3-col-native",
  "label": "SAT CaDiCaL",
  "params": {
    "backend": "cadical-rustsat",
    "timeout_s": 3600
  }
}
```

Example Kissat block:

```json
{
  "target": "sat-3-col-native",
  "label": "SAT Kissat",
  "params": {
    "backend": "kissat-rustsat",
    "timeout_s": 3600
  }
}
```

The Rust binary reads the benchmark `.col` file as DIMACS edge input, ignores
circle comments, and builds the fixed 3-color CNF without materializing a
Python/NetworkX graph. The supported backends are `cadical-rustsat` and
`kissat-rustsat`; both add clauses through RustSAT solver adapters. Normal
execution does not write a `.cnf` file.

`core_time_s` is measured around the solver `solve()` call:

```text
{"status":"ok","solver_status":"COLORABLE","core_time_s":0.004690}
```

`wall_time_s` is always measured by the Python benchmark wrapper and includes
Rust startup, `.col` parsing, clause construction, and solving.

Dense full-sweep instances can exceed an 8 GiB SGE `h_vmem` limit during clause
construction or solving. Use a larger memory resource for those runs, or split
the dense cases into a separate benchmark if the low-memory queues are otherwise
useful.
