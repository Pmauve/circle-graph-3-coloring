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
circle comments, builds the fixed 3-color CNF in memory, and pipes that CNF to
the configured SAT solver over stdin. Normal execution does not write a `.cnf`
file and does not materialize a Python/NetworkX graph.

The native solver reports:

```text
t parse_encode_time_s 0.000123
t solve_time_s 0.004567
t core_time_s 0.004690
```

`solve_time_s` includes external process startup, DIMACS transfer over stdin,
the SAT solver's DIMACS parsing, and SAT solving time. A future embedded
CaDiCaL/Kissat backend can remove the process and DIMACS parsing overhead.
