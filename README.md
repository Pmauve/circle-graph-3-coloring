# 3-coloring-code

This code was used in [[1]](#1) for the evaluation of the 3-coloring algorithm proposed in [[2]](#2).
This repository also contains the graphs used for the evaluation in [[1]](#1).

## Installing

After cloning the repository, open a terminal at ```path_to_repo/3-col-code/``` and execute the following commands to install this project:
```
python3 -m venv venv
source venv/bin/activate
pip install -e .
pip install -U pip
pip install -e .
cd ..
pysmt-install --msat
```

To verify if the installation was successful, execute:

```
which benchmark_run
```

If the response is ```path_to_repo/3-col-code/venv/bin/benchmark_run``` then the project has been successfully installed.
To verify that the SAT solver has been successfully installed, execute ```pysmt-install --check```.
You should see that the msat solver is installed.

You can now use the following scripts.

## Generating test instances: ```generate_graphs.sh <generator> <size>```

To generate a random graph, execute the script using the two parameters ```generator``` and ```size```.

| Generator  | Description                       |
|------------|-----------------------------------|
| r          | a random graph                    |
| ry         | a random, 3-colorable graph       |
| rc         | a random circle graph             |
| rcy        | a random 3-colorable circle graph |

| Size | Number of vertices $n$  |
|------|-------------------------|
| s    | $3 \leq n \leq 250$     |
| m    | $250 \leq n \leq 750$   |
| l    | $750 \leq n \leq 1500$  |
| xl   | $1500 \leq n \leq 5000$ |

The generated graph are stored at ```eval/graph_data/<generator>/<size>```.


## Evaluate coloring strategy: ```eval_coloring.sh <generator> <size>```

Colors all graphs found under ```eval/graph_data/<generator>/<size>``` using the strategy from [[2]](#2) 
and checks if the coloring is valid.

## Assign variables using naive backtracking: ```var_bt_eval.sh <generator> <size>```

Generates SAT formula $\Phi$ for all graphs found under ```eval/graph_data/<generator>/<size>``` and
checks if $\Phi$ has a valid truth assignment using naive backtracking.
Note that the procedure terminates after one hour if no solution is found.

## Assign variables using modified backtracking: ```bt_eval.sh <generator> <size>```

Generates SAT formula $\Phi$ for all graphs found under ```eval/graph_data/<generator>/<size>``` and
checks if $\Phi$ has a valid truth assignment using the modified backtracking from [[2]](#2).
Note that the procedure terminates after one hour if no solution is found.

## How to use results

The aforementioned scripts create single csv files per graph. 
In order to merge these files to e.g. generate plots, you may use the ```plots.py``` script.
Just add the functions you want to use to generate the respective plot to the ```main()``` function.

## Benchmark runs

The newer benchmark tooling uses spec-driven run directories under `eval/runs/`.
For the full task-oriented local and cluster workflow, see `docs/benchmark-pipeline.md`.

Run one benchmark spec with:

```bash
benchmark_run --spec path/to/spec.json
```

A minimal tracked example spec lives at `eval/sample_specs/sosa-smoke.json`.
The benchmark runner reuses matching files from `eval/instances/` and generates missing instances.
Because the run directory is derived from the spec filename stem, running that file writes to `eval/runs/sosa-smoke/`.

```bash
benchmark_run --spec eval/sample_specs/sosa-smoke.json
```

Generated benchmark instances use canonical metadata with a `num_colors` field.
The default is `3`, and generated instance IDs always include the palette size, for example `rc-k03-n0008-seed1`.
Only guaranteed-yes families `rcy_fast` and `rccy*` support `num_colors` values other than `3`.
Those generators use colors from `1..k`, but they do not force every color to appear.

Instance `num_colors` and solver params are independent.
For example, a benchmark can generate a `k04` instance and run a solver with `num_colors=5`.
See `eval/sample_specs/sosa-k-smoke.json` for a small example.

SOSA benchmark targets:

- `sosa-3-col-exact`: theorem-backed exact 3-color SOSA
- `sosa-k-col-heuristic`: experimental SOSA branching with k-color base-case checks

SOSA params:

- `base_case_n`: switch to the base-case solver at this active subinstance size
- `base_case_algorithm`: `backtracking` or `sat`
- `num_colors`: `3` for exact SOSA, at least `4` for the heuristic target
- `produce_witness`: whether to output `coloring_by_node` where supported

Solver blocks may also include an optional display-only `label` used in reports.

Exact example:

```json
{
  "target": "sosa-3-col-exact",
  "label": "SOSA backtracking",
  "params": {
    "base_case_n": 8,
    "base_case_algorithm": "backtracking",
    "num_colors": 3,
    "produce_witness": true
  }
}
```

Heuristic example:

```json
{
  "target": "sosa-k-col-heuristic",
  "label": "SOSA k=4",
  "params": {
    "base_case_n": 8,
    "base_case_algorithm": "backtracking",
    "num_colors": 4,
    "produce_witness": false
  }
}
```

Unsupported combinations are rejected. The exact target requires `num_colors=3`; SAT-backed SOSA and the k-color heuristic are decision-only for now, so they require `produce_witness=false`.

Each run directory stores:

- `spec.json`
- `manifest.json`
- `results.jsonl`
- `summary_by_n.csv`
- `summary_by_bucket.csv`
- `summary_overall.csv`
- `report.html`

The run directory name is derived from the spec filename stem, so rerunning the same spec file automatically resumes the same run directory.

## Support

For questions or comments feel free to reach out to [bachmanp@fim.uni-passau.de](mailto:bachmanp@fim.uni-passau.de) 

## References

<a id="1">[1]</a>
P. Bachmann, I. Rutter, P. Stumpf. On 3-Coloring Circle Graphs. 
In Proceedings of the 31st International Symposium on Graph Drawing and Network Visualization (GD'23),
pages 152-160. Springer Cham, 2023. [doi.org/10.1007/978-3-031-49272-3_11](https://doi.org/10.1007/978-3-031-49272-3_11).

<a id="2">[2]</a> 
W. Unger. The complexity of colouring circle graphs. In Proceedings of the 9th Annual
Symposium on Theoretical Aspects of Computer Science (STACS’92), pages 389–400. Springer
Berlin Heidelberg, 1992. [doi:10.1007/3-540-55210-3_199](https://doi.org/10.1007/3-540-55210-3_199).
