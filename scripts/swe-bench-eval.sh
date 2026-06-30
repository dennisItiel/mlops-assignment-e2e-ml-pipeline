#!/usr/bin/env bash
set -euo pipefail

DATASET_NAME="${DATASET_NAME:-princeton-nlp/SWE-bench_Verified}"
SPLIT="${SPLIT:-test}"
PREDICTIONS_PATH="${PREDICTIONS_PATH:-trajectories/preds.json}"
MAX_WORKERS="${MAX_WORKERS:-5}"
RUN_ID="${RUN_ID:-test}"
REPORT_DIR="${REPORT_DIR:-.}"
WORKDIR="${WORKDIR:-.}"

cd "${WORKDIR}"

python -m swebench.harness.run_evaluation \
    --dataset_name "${DATASET_NAME}" \
    --split "${SPLIT}" \
    --predictions_path "${PREDICTIONS_PATH}" \
    --max_workers "${MAX_WORKERS}" \
    --run_id "${RUN_ID}" \
    --report_dir "${REPORT_DIR}"
