"""Production DAG: DockerOperator execution, optional S3 upload, MLflow logging."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task
from airflow.models.param import Param
from airflow.operators.python import get_current_context
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.run import (  # noqa: E402
    build_run_config,
    collect_metrics,
    log_mlflow_run,
    prepare_run_dir,
    write_manifest,
    write_metrics,
)
from pipeline.storage import (  # noqa: E402
    s3_upload_enabled,
    update_manifest_remote_uri,
    upload_run_directory,
)

PIPELINE_IMAGE = os.getenv("PIPELINE_IMAGE", "mlops-assignment:latest")
HOST_PROJECT_DIR = os.getenv("HOST_PROJECT_DIR", str(PROJECT_ROOT))
CONTAINER_PROJECT_DIR = os.getenv("CONTAINER_PROJECT_DIR", "/mlops-assignment")
DOCKER_URL = os.getenv("DOCKER_URL", "unix://var/run/docker.sock")

DEFAULT_RETRIES = int(os.getenv("PIPELINE_TASK_RETRIES", "1"))


def pipeline_mounts() -> list[Mount]:
    return [
        Mount(source=HOST_PROJECT_DIR, target=CONTAINER_PROJECT_DIR, type="bind"),
        Mount(source="/var/run/docker.sock", target="/var/run/docker.sock", type="bind"),
    ]


def container_env() -> dict[str, str]:
    keys = (
        "NEBIUS_API_KEY",
        "MSWEA_COST_TRACKING",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "S3_ENDPOINT_URL",
    )
    env = {key: os.environ[key] for key in keys if os.environ.get(key)}
    env.setdefault("MSWEA_COST_TRACKING", "ignore_errors")
    return env


def docker_step_command(step: str, run_dir_xcom: str) -> list[str]:
    return [
        "python",
        "scripts/run_pipeline_step.py",
        step,
        "--run-dir",
        f"{{{{ ti.xcom_pull(task_ids='{run_dir_xcom}')['container_run_dir'] }}}}",
    ]


@dag(
    dag_id="evaluate_agent_production",
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    doc_md=__doc__,
    params={
        "split": Param("test", type="string"),
        "subset": Param("verified", type="string"),
        "workers": Param(2, type="integer"),
        "model": Param("nebius/moonshotai/Kimi-K2.6", type="string"),
        "task_slice": Param("0:3", type="string"),
        "run_id": Param("", type="string"),
        "cost_limit": Param(0, type="number"),
        "upload_to_s3": Param(True, type="boolean"),
    },
    tags=["swe-bench", "mlops", "production"],
    default_args={
        "retries": DEFAULT_RETRIES,
        "retry_delay": timedelta(minutes=2),
    },
)
def evaluate_agent_production_dag():
    @task(retries=0)
    def prepare_run() -> dict:
        params = get_current_context()["params"]
        run_config = build_run_config(params)
        run_dir = prepare_run_dir(run_config)
        return {
            "run_config": run_config,
            "run_dir": str(run_dir.resolve()),
            "container_run_dir": f"{CONTAINER_PROJECT_DIR}/runs/{run_config['run_id']}",
        }

    run_context = prepare_run()

    run_agent = DockerOperator(
        task_id="run_agent",
        image=PIPELINE_IMAGE,
        api_version="auto",
        auto_remove="success",
        docker_url=DOCKER_URL,
        command=docker_step_command("agent", "prepare_run"),
        mounts=pipeline_mounts(),
        environment=container_env(),
        mount_tmp_dir=False,
        tty=False,
        execution_timeout=timedelta(hours=6),
    )

    run_eval = DockerOperator(
        task_id="run_eval",
        image=PIPELINE_IMAGE,
        api_version="auto",
        auto_remove="success",
        docker_url=DOCKER_URL,
        command=docker_step_command("eval", "prepare_run"),
        mounts=pipeline_mounts(),
        environment=container_env(),
        mount_tmp_dir=False,
        tty=False,
        execution_timeout=timedelta(hours=6),
    )

    @task
    def upload_artifacts(run_context: dict) -> dict:
        params = get_current_context()["params"]
        run_dir = Path(run_context["run_dir"])
        remote_uri = None
        if params.get("upload_to_s3") and s3_upload_enabled():
            remote_uri = upload_run_directory(run_dir, run_context["run_config"]["run_id"])
        return {**run_context, "remote_artifact_uri": remote_uri}

    @task
    def summarize_and_log(run_context: dict) -> dict:
        run_config = run_context["run_config"]
        run_dir = Path(run_context["run_dir"])
        eval_dir = run_dir / "run-eval"
        remote_uri = run_context.get("remote_artifact_uri")

        metrics = collect_metrics(eval_dir, run_config)
        write_metrics(run_dir, metrics)
        write_manifest(run_dir, run_config, metrics, remote_artifact_uri=remote_uri)
        if remote_uri:
            update_manifest_remote_uri(run_dir, remote_uri)

        artifact_uri = str(run_dir.resolve())
        mlflow_run_id = log_mlflow_run(
            run_config,
            metrics,
            artifact_uri,
            remote_artifact_uri=remote_uri,
        )
        return {
            "run_id": run_config["run_id"],
            "run_dir": artifact_uri,
            "remote_artifact_uri": remote_uri,
            "metrics": metrics,
            "mlflow_run_id": mlflow_run_id,
        }

    uploaded = upload_artifacts(run_context)
    summary = summarize_and_log(uploaded)

    run_context >> run_agent >> run_eval >> uploaded >> summary


evaluate_agent_production_dag()
