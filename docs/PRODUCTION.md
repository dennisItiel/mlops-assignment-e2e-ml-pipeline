# Production deployment (VM + Docker Compose)

This guide covers the **production-style** stack: Airflow and MLflow in Docker Compose, agent/eval steps in isolated containers via `DockerOperator`, and optional S3 upload.

## Architecture

```text
evaluate_agent_production DAG
  prepare_run           @task (Airflow) -> runs/<run-id>/config.json
  run_agent             DockerOperator  -> mlops-assignment image
  run_eval              DockerOperator  -> mlops-assignment image
  upload_artifacts      @task           -> optional S3 upload
  summarize_and_log     @task           -> metrics, manifest, MLflow
```

| Component | File |
|-----------|------|
| Production DAG | `dags/evaluate_agent_production.py` |
| Easy-mode DAG | `dags/evaluate_agent.py` |
| Pipeline image | `Dockerfile` |
| Airflow image | `Dockerfile.airflow` |
| Compose stack | `docker-compose.yaml` |

## 1. Provision the VM

Recommended: **8 CPU, 32 GB RAM**, Ubuntu 24.04, public IP, SSH key.

```bash
ssh ubuntu@<vm-ip>
```

## 2. Bootstrap the VM

```bash
curl -fsSL https://raw.githubusercontent.com/minotru/mlops-assignment-e2e-ml-pipeline/main/scripts/setup-vm.sh | bash
# or, if you already cloned the repo:
bash scripts/setup-vm.sh
```

Log out and back in (or `newgrp docker`) so Docker group membership applies.

## 3. Configure environment

```bash
cd ~/mlops-assignment-e2e-ml-pipeline   # or your clone path
cp .env.example .env
nano .env
```

Required:

| Variable | Example |
|----------|---------|
| `NEBIUS_API_KEY` | your key |
| `HOST_PROJECT_DIR` | `/home/ubuntu/mlops-assignment-e2e-ml-pipeline` |

Optional S3 (skip upload if `S3_BUCKET` is empty):

| Variable | Example |
|----------|---------|
| `S3_BUCKET` | `my-bucket` |
| `S3_PREFIX` | `swe-bench-runs` |
| `S3_ENDPOINT_URL` | Nebius/MinIO endpoint if not AWS |
| `AWS_ACCESS_KEY_ID` | ... |
| `AWS_SECRET_ACCESS_KEY` | ... |

## 4. Start the stack

```bash
bash scripts/start-production.sh
```

This builds images, runs DB migrations, and starts:

- **PostgreSQL** — Airflow + MLflow metadata
- **MLflow** — http://\<vm-ip\>:5000
- **Airflow** — http://\<vm-ip\>:8080 (`admin` / `admin` by default)

## 5. Trigger a production run

In the Airflow UI, trigger **`evaluate_agent_production`**.

Suggested VM params:

| Param | Value |
|-------|-------|
| `task_slice` | `0:3` |
| `workers` | `2` |
| `upload_to_s3` | `true` if S3 configured, else `false` |

## 6. Verify outputs

Local run folder (on VM):

```text
runs/<run-id>/
  config.json
  manifest.json      # includes remote_artifact_uri when S3 is configured
  metrics.json
  run-agent/
  run-eval/
```

MLflow: experiment `swe-bench-eval` at http://\<vm-ip\>:5000

S3: `s3://<bucket>/<prefix>/<run-id>/` (or your object storage UI)

## 7. Screenshots for submission

Save under `screenshots/`:

- `airflow_dag.png` — completed `evaluate_agent_production` graph
- `mlflow_runs.png` — MLflow experiment runs
- `object_storage_artifacts.png` — S3/object storage browser (if configured)

## Troubleshooting

### DAG import error: `docker` provider missing

Rebuild the Airflow image:

```bash
docker compose build airflow-apiserver
docker compose up -d
```

### DockerOperator cannot access Docker socket

Ensure `/var/run/docker.sock` is mounted and your user is in the `docker` group.

### `prepare_run` and DockerOperator path mismatch

`HOST_PROJECT_DIR` in `.env` must be the **absolute host path** to the repo. Both Airflow and pipeline containers bind-mount this directory.

### MLflow connection from Airflow tasks

Inside compose, use `MLFLOW_TRACKING_URI=http://mlflow:5000` (set in `.env.example`).

### Easy mode vs production

| Mode | Start command | DAG |
|------|---------------|-----|
| Local dev | `bash run-airflow-standalone.sh` | `evaluate_agent` |
| Production | `bash scripts/start-production.sh` | `evaluate_agent_production` |

You can keep developing locally with `evaluate_agent`, then deploy the same repo to the VM for production runs.
