#!/usr/bin/env python3
"""Smoke-test pipeline helpers without calling the agent or SWE-bench harness."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.run import (
    build_run_config,
    collect_metrics,
    prepare_run_dir,
    write_manifest,
    write_metrics,
)

SAMPLE_EVAL = PROJECT_ROOT / "sample"


def main() -> None:
    run_config = build_run_config(
        {
            "split": "test",
            "subset": "verified",
            "workers": 1,
            "model": "nebius/moonshotai/Kimi-K2.6",
            "task_slice": "0:3",
            "run_id": "offline-smoke-test",
        }
    )
    run_dir = prepare_run_dir(run_config)

    agent_dir = run_dir / "run-agent"
    eval_dir = run_dir / "run-eval"
    shutil.copy(SAMPLE_EVAL / "trajectories/preds.json", agent_dir / "preds.json")
    shutil.copytree(SAMPLE_EVAL / "trajectories", agent_dir / "trajectories", dirs_exist_ok=True)
    shutil.copy(
        SAMPLE_EVAL / "nebius__moonshotai__Kimi-K2.6.test.json",
        eval_dir / "nebius__moonshotai__Kimi-K2.6.offline-smoke-test.json",
    )

    metrics = collect_metrics(eval_dir, run_config)
    write_metrics(run_dir, metrics)
    write_manifest(run_dir, run_config, metrics)

    print(json.dumps({"run_dir": str(run_dir), "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
