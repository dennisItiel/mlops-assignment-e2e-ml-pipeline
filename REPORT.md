# Evaluation Pipeline Report

Local development report for the `evaluate_agent` Airflow DAG (easy mode).

## Architecture

```text
Airflow DAG: evaluate_agent
  prepare_run        -> runs/<run-id>/config.json
  run_agent          -> runs/<run-id>/run-agent/preds.json + trajectories
  run_eval           -> runs/<run-id>/run-eval/logs/ + aggregate report
  summarize_and_log  -> metrics.json, manifest.json, MLflow run
```

Implementation lives in:

- `dags/evaluate_agent.py` — Airflow DAG and task wiring
- `pipeline/run.py` — reusable helpers (`build_run_config`, `run_agent_batch`, etc.)
- `scripts/mini-swe-bench-batch.sh` / `scripts/swe-bench-eval.sh` — manual wrappers with env vars

## Local setup

```bash
cd mlops-assignment-e2e-ml-pipeline
cp .env.example .env   # add NEBIUS_API_KEY
uv sync
source .venv/bin/activate
```

Optional offline smoke test (no API calls, uses `sample/`):

```bash
python scripts/test-pipeline-offline.py
```

Requires Docker for real agent/eval steps.

## Trigger the DAG

```bash
bash run-airflow-standalone.sh
```

Open http://localhost:8080, log in with the credentials printed by Airflow standalone, and trigger `evaluate_agent`.

Suggested first-run params:

| Param | Value | Notes |
|-------|-------|-------|
| `split` | `test` | |
| `subset` | `verified` | |
| `workers` | `1` | keep low locally |
| `task_slice` | `0:1` | one instance for a quick run |
| `model` | `nebius/moonshotai/Kimi-K2.6` | |
| `cost_limit` | `0` | |
| `run_id` | *(empty)* | auto-generated timestamp id |

## Artifact layout

```text
runs/<run-id>/
  config.json
  run-agent/
    preds.json
    trajectories/...
  run-eval/
    logs/run_evaluation/<run-id>/...
    <model>.<run-id>.json
  metrics.json
  manifest.json
```

## MLflow

Default tracking URI: `sqlite:///.../mlflow.db` (see `.env.example`).

After a completed run:

```bash
mlflow ui --backend-store-uri sqlite:////home/itield7/mlops-assignment-e2e-ml-pipeline/mlflow.db
```

Open http://localhost:5000 and inspect experiment `swe-bench-eval`.

## Rerun by run id

1. Read `runs/<run-id>/config.json` for the original parameters.
2. Trigger `evaluate_agent` in Airflow with the same params (or set `run_id` explicitly to overwrite — use a new id to preserve history).
3. Compare runs in MLflow or diff `runs/<run-id>/metrics.json`.

## Completed runs

| run_id | task_slice | resolved / submitted | notes |
|--------|------------|----------------------|-------|
| `1` | `0:1` | 1 / 1 | first local Airflow run |
| `2` | `0:1` | 1 / 1 | second local run (MLflow sqlite fix) |

## Production deployment (VM)

See **[docs/PRODUCTION.md](docs/PRODUCTION.md)** for the full VM + Docker Compose guide.

Quick summary:

1. Bootstrap VM: `bash scripts/setup-vm.sh`
2. Configure `.env` (`NEBIUS_API_KEY`, `HOST_PROJECT_DIR`, optional S3)
3. Start stack: `bash scripts/start-production.sh`
4. Trigger DAG: **`evaluate_agent_production`** (DockerOperator + optional S3)

| Mode | Command | DAG |
|------|---------|-----|
| Local easy mode | `bash run-airflow-standalone.sh` | `evaluate_agent` |
| VM production | `bash scripts/start-production.sh` | `evaluate_agent_production` |
