"""Configurable Airflow DAG: mini-swe-agent -> SWE-bench eval -> MLflow."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.python import get_current_context

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.run import (  # noqa: E402
    build_run_config,
    collect_metrics,
    log_mlflow_run,
    prepare_run_dir,
    run_agent_batch,
    run_swebench_eval,
    write_manifest,
    write_metrics,
)


@dag(
    dag_id="evaluate_agent",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    doc_md=__doc__,
    params={
        "split": Param("test", type="string", description="Dataset split"),
        "subset": Param("verified", type="string", description="SWE-bench subset"),
        "workers": Param(1, type="integer", description="Parallel workers"),
        "model": Param(
            "nebius/moonshotai/Kimi-K2.6",
            type="string",
            description="LLM model id",
        ),
        "task_slice": Param(
            "0:1",
            type="string",
            description="Instance slice, e.g. 0:3 for first three tasks",
        ),
        "run_id": Param(
            "",
            type="string",
            description="Optional run id; auto-generated if empty",
        ),
        "cost_limit": Param(
            0,
            type="number",
            description="Agent cost limit override",
        ),
    },
    tags=["swe-bench", "mlops"],
)
def evaluate_agent_dag():
    @task
    def prepare_run() -> dict:
        params = get_current_context()["params"]
        run_config = build_run_config(params)
        run_dir = prepare_run_dir(run_config)
        return {
            "run_config": run_config,
            "run_dir": str(run_dir),
        }

    @task
    def run_agent(run_context: dict) -> dict:
        run_config = run_context["run_config"]
        run_dir = Path(run_context["run_dir"])
        preds_path = run_agent_batch(run_config, run_dir)
        return {
            **run_context,
            "preds_path": str(preds_path),
        }

    @task
    def run_eval(run_context: dict) -> dict:
        run_config = run_context["run_config"]
        run_dir = Path(run_context["run_dir"])
        preds_path = Path(run_context["preds_path"])
        eval_dir = run_swebench_eval(run_config, preds_path, run_dir)
        return {
            **run_context,
            "eval_dir": str(eval_dir),
        }

    @task
    def summarize_and_log(run_context: dict) -> dict:
        run_config = run_context["run_config"]
        run_dir = Path(run_context["run_dir"])
        eval_dir = Path(run_context["eval_dir"])

        metrics = collect_metrics(eval_dir, run_config)
        write_metrics(run_dir, metrics)
        write_manifest(run_dir, run_config, metrics)
        artifact_uri = str(run_dir.resolve())
        mlflow_run_id = log_mlflow_run(run_config, metrics, artifact_uri)

        return {
            "run_id": run_config["run_id"],
            "run_dir": artifact_uri,
            "metrics": metrics,
            "mlflow_run_id": mlflow_run_id,
        }

    run_context = prepare_run()
    after_agent = run_agent(run_context)
    after_eval = run_eval(after_agent)
    summarize_and_log(after_eval)


evaluate_agent_dag()
