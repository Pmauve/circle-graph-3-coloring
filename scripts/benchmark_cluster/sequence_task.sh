#!/usr/bin/env bash
set -euo pipefail

if [ -f "${ENV_CLUSTER:-env_cluster.sh}" ]; then
  # shellcheck source=/dev/null
  source "${ENV_CLUSTER:-env_cluster.sh}"
fi

RUN_ID="${RUN_ID:-cluster-smoke}"
PLAN_ROOT="${PLAN_ROOT:-eval/benchmark_plans}"
PLAN_DIR="${PLAN_DIR:-$PLAN_ROOT/$RUN_ID}"
TASK_INDEX="${TASK_INDEX:-}"
if [ -z "$TASK_INDEX" ] && [ -n "${SLURM_ARRAY_TASK_ID:-}" ]; then
  TASK_INDEX="$SLURM_ARRAY_TASK_ID"
fi
if [ -z "$TASK_INDEX" ] && [ -n "${SGE_TASK_ID:-}" ]; then
  TASK_INDEX="$SGE_TASK_ID"
fi

if [ -z "$TASK_INDEX" ]; then
  echo "TASK_INDEX is not set" >&2
  exit 2
fi

args=(--plan-dir "$PLAN_DIR" --index "$TASK_INDEX")
if [ "${FORCE:-0}" = "1" ] || [ "${FORCE:-}" = "true" ]; then
  args+=(--force)
fi
if [ "${KEEP_INSTANCES:-0}" = "1" ] || [ "${KEEP_INSTANCES:-}" = "true" ]; then
  args+=(--keep-instances)
fi

benchmark_run_instance_sequence "${args[@]}"
