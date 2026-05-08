#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${RUN_ID:?RUN_ID is required}"
PLAN_ROOT="${PLAN_ROOT:-eval/benchmark_plans}"
PLAN_DIR="${PLAN_DIR:-$PLAN_ROOT/$RUN_ID}"
OUTPUT_ROOT="${OUTPUT_ROOT:-eval/runs}"
INSTANCE_TASK="${INSTANCE_TASK:-scripts/benchmark_cluster/instance_task.sh}"
TRIAL_TASK="${TRIAL_TASK:-scripts/benchmark_cluster/trial_task.sh}"
INSTANCE_JOB_NAME="${INSTANCE_JOB_NAME:-${RUN_ID}-inst}"
TRIAL_JOB_NAME="${TRIAL_JOB_NAME:-${RUN_ID}-trial}"
SGE_RESOURCE="${SGE_RESOURCE:-${RESOURCE:-bc1}}"
INSTANCE_H_VMEM="${INSTANCE_H_VMEM:-2G}"
TRIAL_H_VMEM="${TRIAL_H_VMEM:-8G}"
SGE_LOG_DIR="${SGE_LOG_DIR:-logs}"
SGE_RESTART="${SGE_RESTART:-y}"

read_manifest_field() {
  local field="$1"
  python - "$PLAN_DIR" "$field" <<'PY'
import json
import sys
from pathlib import Path

manifest = json.loads((Path(sys.argv[1]) / "manifest.json").read_text(encoding="utf-8"))
print(manifest[sys.argv[2]])
PY
}

run_qsub_sync() {
  set +e
  qsub -sync y "$@"
  local exit_code="$?"
  set -e
  if [ "$exit_code" -ne 0 ]; then
    echo "qsub -sync y exited with code ${exit_code}; checking benchmark outputs anyway" >&2
  fi
}

n_instances="$(read_manifest_field n_instances)"
n_trials="$(read_manifest_field n_trials)"
mkdir -p "$SGE_LOG_DIR"

echo "submitting instance generation array 1-${n_instances}"
run_qsub_sync \
  -N "$INSTANCE_JOB_NAME" \
  -cwd -V -o "$SGE_LOG_DIR" -e "$SGE_LOG_DIR" -r "$SGE_RESTART" \
  -l "$SGE_RESOURCE" -l "h_vmem=$INSTANCE_H_VMEM" \
  -t "1-${n_instances}:1" \
  -v "RUN_ID=$RUN_ID" \
  "$INSTANCE_TASK"

echo "checking instance generation status"
benchmark_status --plan-dir "$PLAN_DIR" --require-ready-for-trials

echo "submitting trial array 1-${n_trials}"
run_qsub_sync \
  -N "$TRIAL_JOB_NAME" \
  -cwd -V -o "$SGE_LOG_DIR" -e "$SGE_LOG_DIR" -r "$SGE_RESTART" \
  -l "$SGE_RESOURCE" -l "h_vmem=$TRIAL_H_VMEM" \
  -t "1-${n_trials}:1" \
  -v "RUN_ID=$RUN_ID" \
  "$TRIAL_TASK"

echo "checking trial status"
benchmark_status --plan-dir "$PLAN_DIR" --require-ready-for-merge

echo "merging run"
benchmark_merge --plan-dir "$PLAN_DIR" --output-root "$OUTPUT_ROOT" --force
