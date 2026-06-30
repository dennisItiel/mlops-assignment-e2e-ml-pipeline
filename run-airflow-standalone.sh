set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${PROJECT_ROOT}"

export AIRFLOW_HOME="${HOME}/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="${PROJECT_ROOT}/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=false

# Airflow (uv tool env) must see project code and project venv deps (mlflow, etc.)
VENV_SITE_PACKAGES="$(uv run python -c 'import site; print(site.getsitepackages()[0])')"
export PYTHONPATH="${PROJECT_ROOT}:${VENV_SITE_PACKAGES}${PYTHONPATH:+:${PYTHONPATH}}"

mkdir -p "${AIRFLOW_HOME}"

echo '{"admin": "admin"}' > "${AIRFLOW_HOME}/simple_auth_manager_passwords.json.generated"

uv tool run apache-airflow standalone
