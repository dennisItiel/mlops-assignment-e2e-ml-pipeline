#!/usr/bin/env bash
# Build pipeline + Airflow images and start the production compose stack.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — edit secrets before running in production."
fi

# Ensure HOST_PROJECT_DIR matches this machine.
if ! grep -q "^HOST_PROJECT_DIR=" .env; then
  echo "HOST_PROJECT_DIR=${PROJECT_ROOT}" >> .env
else
  sed -i "s|^HOST_PROJECT_DIR=.*|HOST_PROJECT_DIR=${PROJECT_ROOT}|" .env
fi

if ! grep -q "^AIRFLOW_FERNET_KEY=.\+" .env 2>/dev/null; then
  FERNET_KEY="$(python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null || true)"
  if [[ -n "${FERNET_KEY}" ]]; then
    echo "AIRFLOW_FERNET_KEY=${FERNET_KEY}" >> .env
  fi
fi

export AIRFLOW_UID="${AIRFLOW_UID:-$(id -u)}"

echo "==> Building pipeline execution image"
docker compose build pipeline-image

echo "==> Building Airflow image"
docker compose build airflow-apiserver

echo "==> Initializing Airflow metadata DB"
docker compose up airflow-init

echo "==> Starting services"
docker compose up -d

cat <<EOF

Production stack is up.

  Airflow: http://localhost:${AIRFLOW_PORT:-8080}  (${AIRFLOW_USERNAME:-admin}/${AIRFLOW_PASSWORD:-admin})
  MLflow:  http://localhost:${MLFLOW_PORT:-5000}

Trigger DAG: evaluate_agent_production

EOF
