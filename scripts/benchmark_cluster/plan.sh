#!/usr/bin/env bash
set -euo pipefail

SPEC="${SPEC:-eval/sample_specs/pipeline-parallel-smoke.json}"
RUN_ID="${RUN_ID:-cluster-smoke}"
PLAN_ROOT="${PLAN_ROOT:-eval/benchmark_plans}"
WORK_ROOT="${WORK_ROOT:-eval/benchmark_work}"

benchmark_plan \
  --spec "$SPEC" \
  --run-id "$RUN_ID" \
  --plan-root "$PLAN_ROOT" \
  --work-root "$WORK_ROOT" \
  --force

benchmark_status --plan-dir "$PLAN_ROOT/$RUN_ID"
