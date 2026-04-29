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

After all trials finished, merge once:

```bash
benchmark_merge \
  --plan-dir eval/benchmark_plans/pipeline-smoke \
  --output-root eval/runs \
  --force
```

Set `TASK_INDEX` from the scheduler array variable, for example `$SLURM_ARRAY_TASK_ID` or `$SGE_TASK_ID`.
Generic shell templates live in `scripts/benchmark_cluster/`.

## Outputs

```text
eval/benchmark_plans/<run-id>/instances.jsonl
eval/benchmark_plans/<run-id>/trials.jsonl
eval/benchmark_work/<run-id>/instances/<index>/result.json
eval/benchmark_work/<run-id>/trials/<index>/result.json
eval/runs/<run-id>/results.jsonl
eval/runs/<run-id>/report.html
```

Instances themselves live in the spec's `instance_pool_root`, not in the work directory.

## Notes

Instance generation is deterministic, so it can run on any available node. Timing-sensitive solver trials should run on one comparable hardware class.

Generation and trial commands resume existing successful task outputs. Use `--force` to replace outputs.
