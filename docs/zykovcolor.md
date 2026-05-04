# ZykovColor Integration

ZykovColor is used as an external native solver. The Python benchmark target
`zykovcolor` writes the instance to a temporary DIMACS-circle file, runs the
ZykovColor executable, parses the final result line, and stores the answer in
the normal benchmark result format.

The upstream source is not vendored into this repository. It is fetched at a
pinned commit by:

```bash
scripts/zykovcolor/install.sh --fetch-only
```

To build it, install/provide the upstream native dependencies and run:

```bash
export GUROBI_HOME=/path/to/gurobi
export BOOST_ROOT=/path/to/boost
scripts/zykovcolor/install.sh
```

The script currently pins upstream ZykovColor to commit:

```text
412e051417886ef0423565777c7814cda7f967e5
```

After a successful build, point benchmarks at the binary either with an
environment variable:

```bash
export ZYKOVCOLOR_BIN="$PWD/external/ZykovColor/cmake-build/ZykovColor"
```

or with solver params:

```json
{
  "target": "zykovcolor",
  "label": "ZykovColor",
  "params": {
    "executable": "external/ZykovColor/cmake-build/ZykovColor",
    "configuration": "zykov-color",
    "mode": "single-k",
    "decision_num_colors": 3,
    "timeout_s": 3600
  }
}
```

The wrapper recognizes both upstream result styles:

```text
IncSatGC computed chromatic number of 3
IncSatGC computed SAT for k = 3
```

For chromatic-number output, the benchmark decision answer is:

```text
is_colorable = chromatic_number <= decision_num_colors
```

For a fair fixed 3-colorability comparison against SOSA, use:

```json
{
  "target": "zykovcolor",
  "label": "ZykovColor k=3",
  "params": {
    "configuration": "zykov-color",
    "mode": "single-k",
    "decision_num_colors": 3,
    "timeout_s": 3600
  }
}
```

Internally this passes ZykovColor's numeric CLI strategy for single-k solving:

```text
--strategy 2 --num-colors 3
```
