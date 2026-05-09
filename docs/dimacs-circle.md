# DIMACS Circle Instances

DIMACS circle instances are plain DIMACS edge files with an optional circle
representation in comment lines. General graph solvers can ignore the comments.
Circle-graph solvers can read the comments to recover the chord representation.

```text
c format version 1
c instance id rc-n0004-seed1
c family rc
c seed 1
c n 4
c m 3
c average degree 1.5
c num colors 3
c source generated
c generator seeded_random_circle_graph_legacy
c created at 2026-04-17T00:14:13.075606+00:00
c generation time seconds 0.005482300010044128
c max attempts per node 10000
c hord endpoint order START
c 4 2 1 1 3 4 2 3
c hord endpoint order END
p edge 4 3
e 4 3
e 3 1
e 2 1
```

The integers in the chord endpoint order block are the cyclic endpoint order. Each DIMACS vertex id from
`1..n` must appear exactly twice. Writers wrap the order across multiple
plain comment lines inside the chord endpoint order block:

```text
c hord endpoint order START
c 4 2 1 1
c 3 4 2 3
c hord endpoint order END
```

Readers concatenate all integer tokens from the plain `c ...` rows between
`START` and `END`.

Validation rules:

- The problem line is `p edge n m`.
- Edges are written as `e u v` using contiguous DIMACS vertex ids `1..n`.
- The chord endpoint order block starts with exactly `c hord endpoint order START`.
- The chord endpoint order block ends with exactly `c hord endpoint order END`.
- Inside the chord endpoint order block, every line except `END` must be `c` followed only
  by integer vertex ids.
- The chord endpoint order length is exactly `2n`.
- Every vertex id from `1..n` appears exactly twice.
- The edge set implied by chord crossings must exactly match the DIMACS edge
  lines.
- Writers preserve the endpoint order from the source instance and wrap at a
  fixed token count for deterministic output.
- Metadata comments outside the chord endpoint order block are optional and ignored by
  generic DIMACS solvers. Writers should include all canonical metadata fields
  when they are available:
  - `c format version 1`
  - `c instance id <value>`
  - `c family <value>`
  - `c seed <integer-or-none>`
  - `c n <integer>`
  - `c m <integer>`
  - `c average degree <float>`
  - `c num colors <integer>`
  - `c source <value>`
  - `c generator <value>`
  - `c created at <timestamp>`
  - `c generation time seconds <float-or-none>`
  - `c max attempts per node <integer-or-none>`
- `average degree` is the ordinary graph average degree `2m / n`, formatted
  deterministically by the writer. For `n = 0`, writers use `0`.
