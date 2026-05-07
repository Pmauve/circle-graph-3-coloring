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

Example solver block:

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

The Rust binary reads the benchmark `.col` file as DIMACS edge input, ignores
circle comments, streams the fixed 3-color CNF to the configured SAT solver over
stdin, and parses the solver's SAT/UNSAT/UNKNOWN status. Normal execution does
not write a `.cnf` file and does not materialize a Python/NetworkX graph.

The native solver reports:

```text
t parse_encode_time_s 0.000123
t solve_time_s 0.004567
t core_time_s 0.004690
```

`solve_time_s` includes external process startup, DIMACS transfer over stdin,
the SAT solver's DIMACS parsing, and SAT solving time. A future embedded
CaDiCaL/Kissat backend can remove the process and DIMACS parsing overhead.

External SAT binaries commonly exit with `10` for SAT and `20` for UNSAT. The
native wrapper accepts those conventional codes and treats other unexpected
nonzero exits as solver errors.
