# Benchmark Pipeline

Use `benchmark_run` locally. Use the task commands on the cluster.

Smoke spec:

```bash
eval/sample_specs/pipeline-smoke.json
eval/sample_specs/pipeline-parallel-smoke.json
eval/sample_specs/sosa-k-smoke.json
```

## Local

Run the full pipeline:

```bash
benchmark_run --spec eval/sample_specs/pipeline-smoke.json --jobs 4
```

This plans the run, generates missing instances, runs all trials, merges results, writes summaries, and builds `report.html`.

Benchmark instances are canonical compact `.circle` DIMACS-circle files. A
`.circle` file stores metadata plus the chord endpoint order only; solver-ready
edge lists are materialized as temporary `.circle.col` files in scratch storage
immediately before solver execution. The planner reuses matching `.circle`
files from the spec's `instance_pool_root` and generation writes missing
instances directly as `.circle`.

Set instance-side `num_colors` in an `instances` block when generating `k > 3` instances. Solver `params.num_colors` stays independent, so the same generated instance can still be tested with different solver palettes.

## Cluster

Create the plan once:

```bash
benchmark_plan \
  --spec eval/sample_specs/pipeline-smoke.json \
  --run-id pipeline-smoke \
  --force
```

The plan manifest contains `n_instances` and `n_trials`:

```bash
benchmark_status --plan-dir eval/benchmark_plans/pipeline-smoke
```

Submit an array over `1..n_instances`:

```bash
benchmark_generate_instance \
  --plan-dir eval/benchmark_plans/pipeline-smoke \
  --index "$TASK_INDEX"
```

After instance generation finished, submit an array over `1..n_trials`:

```bash
benchmark_run_trial \
  --plan-dir eval/benchmark_plans/pipeline-smoke \
  --index "$TASK_INDEX"
```

Trials trust the validation result produced by the instance task. For an
isolated debug run, add `--validate-instance` to re-run full instance validation
before invoking the solver.

After all trials finished, merge once:

```bash
benchmark_merge \
  --plan-dir eval/benchmark_plans/pipeline-smoke \
  --output-root eval/runs \
  --force
```

Set `TASK_INDEX` from the scheduler array variable, for example `$SLURM_ARRAY_TASK_ID` or `$SGE_TASK_ID`.
Generic shell templates live in `scripts/benchmark_cluster/`.

For SGE, prefer the guarded staged submit helper when launching a full run:

```bash
RUN_ID=pipeline-smoke \
SGE_RESOURCE=bc5 \
scripts/benchmark_cluster/sge_staged_submit.sh
```

This uses the tracked generic task scripts and passes SGE resource, memory, log,
restart, environment, and working-directory options through `qsub`. The defaults
are `SGE_RESOURCE=bc1`, `INSTANCE_H_VMEM=2G`, `TRIAL_H_VMEM=8G`, and
`SGE_LOG_DIR=logs`. It also uses `qsub -sync y` and gates each stage with
`benchmark_status`. This is stricter than `-hold_jid`: scheduler holds wait for
predecessor jobs to finish, but they do not assert that every array task
produced successful benchmark outputs.

### Sequence Runs

For plans whose instance rows have `sequence_id`, use the sequence task instead
of separate instance and trial arrays when you want each growable trajectory to
be generated incrementally and each instance materialized once for all of its
trials:

```bash
RUN_ID=my-sequence-run
SEQUENCE_COUNT="$(python - <<'PY'
from pathlib import Path
from three_col_circle_code.bench.generate_instance import planned_instance_sequence_count
print(planned_instance_sequence_count(Path("eval/benchmark_plans") / "my-sequence-run"))
PY
)"

qsub -N "${RUN_ID}-seq" \
  -cwd -V -o logs -e logs -r y \
  -l bc1 -l h_vmem=16G \
  -t "1-${SEQUENCE_COUNT}:1" \
  -v RUN_ID="$RUN_ID" \
  scripts/benchmark_cluster/sequence_task.sh
```

Each sequence task generates one native `.circle` sequence, materializes one
temporary `.circle.col` per instance in `$TMPDIR`, runs all planned trials for
that instance against the staged file, and then lets the scratch file disappear.
It keeps canonical `.circle` files, `.circle.validation.json` sidecars,
`eval/benchmark_plans/<run-id>`, and `eval/benchmark_work/<run-id>` intact so
`benchmark_status`, `benchmark_merge`, and failure diagnostics still work
normally.

## Outputs

```text
eval/benchmark_plans/<run-id>/instances.jsonl
eval/benchmark_plans/<run-id>/trials.jsonl
eval/benchmark_work/<run-id>/instances/<index>/result.json
eval/benchmark_work/<run-id>/trials/<index>/result.json
eval/runs/<run-id>/results.jsonl
eval/runs/<run-id>/report.html
```

Canonical compact instances live in the spec's `instance_pool_root`, not in the
work directory. Runtime `.circle.col` files are scratch artifacts and should not
be treated as benchmark outputs.

Trial result rows record both `wall_time_s` and `core_time_s`. Wall time is the
default report metric and includes parsing, subprocess overhead, and solver
execution. Core time is the solver-specific hard-problem time after benchmark
instance parsing. Reports include a wall/core toggle and Plotly hover text
includes `average_degree = 2m / n`.

## Notes

Instance generation is deterministic, so it can run on any available node. Timing-sensitive solver trials should run on one comparable hardware class.

Generation and trial commands resume existing successful task outputs. Use `--force` to replace outputs.
If an instance generation task failed or is missing, `benchmark_run_trial` writes
a structured invalid trial result instead of exiting before creating
`result.json`; status reports should therefore show explicit trial failures
rather than silent missing trial outputs for known-bad instance prerequisites.
