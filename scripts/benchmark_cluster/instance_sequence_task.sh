#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-cluster-smoke}"
PLAN_ROOT="${PLAN_ROOT:-eval/benchmark_plans}"
PLAN_DIR="${PLAN_DIR:-$PLAN_ROOT/$RUN_ID}"
TASK_INDEX="${TASK_INDEX:-${SLURM_ARRAY_TASK_ID:-${SGE_TASK_ID:-}}}"

if [ -z "$TASK_INDEX" ]; then
  echo "TASK_INDEX is not set" >&2
  exit 2
fi

benchmark_generate_instance_sequence --plan-dir "$PLAN_DIR" --index "$TASK_INDEX"
