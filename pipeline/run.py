"""Run helpers for the mini-swe-agent -> SWE-bench evaluation pipeline."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = PROJECT_ROOT / "runs"

SUBSET_TO_DATASET: dict[str, str] = {
    "verified": "princeton-nlp/SWE-bench_Verified",
    "lite": "SWE-bench/SWE-bench_Lite",
}

DEFAULT_PARAMS: dict[str, object] = {
    "split": "test",
    "subset": "verified",
    "workers": 1,
    "model": "nebius/moonshotai/Kimi-K2.6",
    "task_slice": "0:1",
    "run_id": "",
    "cost_limit": 0,
}


def _load_project_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def _swebench_config_path() -> Path:
    import minisweagent

    return Path(minisweagent.__file__).resolve().parent / "config/benchmarks/swebench.yaml"


def dataset_name_for_subset(subset: str) -> str:
    if subset in SUBSET_TO_DATASET:
        return SUBSET_TO_DATASET[subset]
    if "/" in subset:
        return subset
    raise ValueError(
        f"Unknown subset {subset!r}. Use one of {sorted(SUBSET_TO_DATASET)} "
        "or pass a Hugging Face dataset name."
    )


def build_run_config(params: dict) -> dict:
    """Merge Airflow/manual params with defaults and assign a run id."""
    run_config = {**DEFAULT_PARAMS, **{k: v for k, v in params.items() if v is not None}}
    if not run_config.get("run_id"):
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        run_config["run_id"] = f"{stamp}_{uuid4().hex[:8]}"
    run_config["created_at"] = datetime.now(UTC).isoformat()
    run_config["dataset_name"] = dataset_name_for_subset(str(run_config["subset"]))
    run_config["workers"] = int(run_config["workers"])
    run_config["cost_limit"] = float(run_config["cost_limit"])
    return run_config


def prepare_run_dir(run_config: dict) -> Path:
    """Create runs/<run-id>/ and write config.json."""
    run_dir = RUNS_ROOT / str(run_config["run_id"])
    agent_dir = run_dir / "run-agent"
    eval_dir = run_dir / "run-eval"
    agent_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    config_path = run_dir / "config.json"
    config_path.write_text(json.dumps(run_config, indent=2), encoding="utf-8")
    return run_dir


def _subprocess_env() -> dict[str, str]:
    _load_project_env()
    return {
        **os.environ,
        "MSWEA_COST_TRACKING": "ignore_errors",
    }


def run_agent_batch(run_config: dict, run_dir: Path) -> Path:
    """Run mini-swe-agent on a SWE-bench slice and write outputs under run-agent/."""
    agent_dir = run_dir / "run-agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "uv",
        "run",
        "mini-extra",
        "swebench",
        "--subset",
        str(run_config["subset"]),
        "--split",
        str(run_config["split"]),
        "--model",
        str(run_config["model"]),
        "--slice",
        str(run_config["task_slice"]),
        "--workers",
        str(run_config["workers"]),
        "-o",
        str(agent_dir),
        "-c",
        str(_swebench_config_path()),
        "-c",
        f"agent.cost_limit={run_config['cost_limit']}",
    ]
    subprocess.run(cmd, cwd=PROJECT_ROOT, env=_subprocess_env(), check=True)

    preds_path = agent_dir / "preds.json"
    if not preds_path.exists():
        raise FileNotFoundError(f"Expected agent predictions at {preds_path}")
    return preds_path


def run_swebench_eval(run_config: dict, preds_path: Path, run_dir: Path) -> Path:
    """Evaluate preds.json with SWE-bench and write logs under run-eval/."""
    eval_dir = run_dir / "run-eval"
    eval_dir.mkdir(parents=True, exist_ok=True)
    eval_run_id = str(run_config["run_id"])

    cmd = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        str(run_config["dataset_name"]),
        "--split",
        str(run_config["split"]),
        "--predictions_path",
        str(preds_path),
        "--max_workers",
        str(run_config["workers"]),
        "--run_id",
        eval_run_id,
        "--report_dir",
        str(eval_dir),
    ]
    subprocess.run(cmd, cwd=eval_dir, env=_subprocess_env(), check=True)
    return eval_dir


def aggregate_report_path(eval_dir: Path, run_config: dict) -> Path:
    model_key = str(run_config["model"]).replace("/", "__")
    return eval_dir / f"{model_key}.{run_config['run_id']}.json"


def collect_metrics(eval_dir: Path, run_config: dict) -> dict:
    """Parse the SWE-bench aggregate report into pipeline metrics."""
    report_path = aggregate_report_path(eval_dir, run_config)
    if not report_path.exists():
        candidates = [
            path
            for path in eval_dir.glob("*.json")
            if path.is_file() and path.name != "metrics.json"
        ]
        if len(candidates) == 1:
            report_path = candidates[0]
        else:
            raise FileNotFoundError(
                f"Could not find SWE-bench aggregate report in {eval_dir}. "
                f"Expected {aggregate_report_path(eval_dir, run_config)}."
            )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    submitted = int(report.get("submitted_instances", 0))
    resolved = int(report.get("resolved_instances", 0))
    return {
        "submitted_instances": submitted,
        "completed_instances": int(report.get("completed_instances", 0)),
        "resolved_instances": resolved,
        "unresolved_instances": int(report.get("unresolved_instances", 0)),
        "error_instances": int(report.get("error_instances", 0)),
        "empty_patch_instances": int(report.get("empty_patch_instances", 0)),
        "resolve_rate": (resolved / submitted) if submitted else 0.0,
        "aggregate_report": str(report_path.name),
    }


def write_metrics(run_dir: Path, metrics: dict) -> Path:
    metrics_path = run_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics_path


def write_manifest(run_dir: Path, run_config: dict, metrics: dict, remote_artifact_uri: str | None = None) -> Path:
    eval_dir = run_dir / "run-eval"
    manifest = {
        "run_id": run_config["run_id"],
        "created_at": run_config["created_at"],
        "artifact_root": str(run_dir),
        "parameters": {
            key: run_config[key]
            for key in (
                "split",
                "subset",
                "workers",
                "model",
                "task_slice",
                "cost_limit",
                "dataset_name",
            )
        },
        "paths": {
            "config": "config.json",
            "metrics": "metrics.json",
            "predictions": "run-agent/preds.json",
            "agent_output": "run-agent/",
            "eval_output": "run-eval/",
            "eval_logs": "run-eval/logs/",
            "eval_aggregate_report": metrics.get("aggregate_report"),
        },
        "metrics": metrics,
        "remote_artifact_uri": remote_artifact_uri,
    }
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def default_mlflow_tracking_uri() -> str:
    db_path = (PROJECT_ROOT / "mlflow.db").resolve()
    return f"sqlite:///{db_path.as_posix()}"


def log_mlflow_run(
    run_config: dict,
    metrics: dict,
    artifact_uri: str,
    remote_artifact_uri: str | None = None,
) -> str:
    """Log params, metrics, and artifact location to MLflow."""
    import mlflow

    _load_project_env()
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", default_mlflow_tracking_uri())
    experiment_name = os.getenv("MLFLOW_EXPERIMENT_NAME", "swe-bench-eval")

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)

    params = {
        "pipeline_run_id": str(run_config["run_id"]),
        "split": str(run_config["split"]),
        "subset": str(run_config["subset"]),
        "workers": str(run_config["workers"]),
        "model": str(run_config["model"]),
        "task_slice": str(run_config["task_slice"]),
        "cost_limit": str(run_config["cost_limit"]),
        "dataset_name": str(run_config["dataset_name"]),
    }

    with mlflow.start_run(run_name=str(run_config["run_id"])) as run:
        mlflow.log_params(params)
        mlflow.log_metrics(
            {
                key: float(value)
                for key, value in metrics.items()
                if isinstance(value, (int, float))
            }
        )
        mlflow.log_param("artifact_uri", artifact_uri)
        if remote_artifact_uri:
            mlflow.log_param("remote_artifact_uri", remote_artifact_uri)
        mlflow.set_tag("pipeline", "evaluate_agent")
        return run.info.run_id
