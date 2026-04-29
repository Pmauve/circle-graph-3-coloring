#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:-cluster-smoke}"
PLAN_ROOT="${PLAN_ROOT:-eval/benchmark_plans}"
PLAN_DIR="${PLAN_DIR:-$PLAN_ROOT/$RUN_ID}"
OUTPUT_ROOT="${OUTPUT_ROOT:-eval/runs}"

benchmark_status --plan-dir "$PLAN_DIR" --fail-on-incomplete
benchmark_merge --plan-dir "$PLAN_DIR" --output-root "$OUTPUT_ROOT" --force
