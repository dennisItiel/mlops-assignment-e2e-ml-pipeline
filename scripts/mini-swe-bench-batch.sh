#!/usr/bin/env bash
set -euo pipefail

SUBSET="${SUBSET:-verified}"
SPLIT="${SPLIT:-test}"
MODEL="${MODEL:-nebius/moonshotai/Kimi-K2.6}"
TASK_SLICE="${TASK_SLICE:-0:3}"
WORKERS="${WORKERS:-5}"
OUTPUT_DIR="${OUTPUT_DIR:-trajectories}"
COST_LIMIT="${COST_LIMIT:-0}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG="${SWEBENCH_CONFIG:-${PROJECT_ROOT}/../mini-swe-agent/src/minisweagent/config/benchmarks/swebench.yaml}"

if [[ ! -f "${CONFIG}" ]]; then
  CONFIG="$(python - <<'PY'
import minisweagent
from pathlib import Path
print(Path(minisweagent.__file__).resolve().parent / "config/benchmarks/swebench.yaml")
PY
)"
fi

MSWEA_COST_TRACKING='ignore_errors' mini-extra swebench \
    --subset "${SUBSET}" \
    --split "${SPLIT}" \
    --model "${MODEL}" \
    --slice "${TASK_SLICE}" \
    --workers "${WORKERS}" \
    --config "${CONFIG}" \
    -c "agent.cost_limit=${COST_LIMIT}" \
    -o "${OUTPUT_DIR}"
