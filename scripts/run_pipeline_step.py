#!/usr/bin/env python3
"""Run a single pipeline step inside the execution container."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.run import run_agent_batch, run_swebench_eval  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["agent", "eval"])
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Path to runs/<run-id>/ (absolute or relative to project root)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = PROJECT_ROOT / run_dir
    run_dir = run_dir.resolve()

    config_path = run_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing run config: {config_path}")

    run_config = json.loads(config_path.read_text(encoding="utf-8"))

    if args.step == "agent":
        preds_path = run_agent_batch(run_config, run_dir)
        print(json.dumps({"preds_path": str(preds_path)}))
    else:
        preds_path = run_dir / "run-agent" / "preds.json"
        eval_dir = run_swebench_eval(run_config, preds_path, run_dir)
        print(json.dumps({"eval_dir": str(eval_dir)}))


if __name__ == "__main__":
    main()
