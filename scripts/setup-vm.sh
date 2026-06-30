#!/usr/bin/env bash
# Bootstrap a fresh Ubuntu VM for the production docker-compose stack.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/minotru/mlops-assignment-e2e-ml-pipeline.git}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/mlops-assignment-e2e-ml-pipeline}"

echo "==> Installing base packages"
sudo apt-get update
sudo apt-get install -y ca-certificates curl git

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker"
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  echo "Added $USER to docker group. Log out/in (or run: newgrp docker) before continuing."
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "==> Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi

if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  echo "==> Cloning repository"
  git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

cd "${INSTALL_DIR}"

if [[ ! -f .env ]]; then
  echo "==> Creating .env from template"
  cp .env.example .env
  sed -i "s|^HOST_PROJECT_DIR=.*|HOST_PROJECT_DIR=${INSTALL_DIR}|" .env
  echo "Edit ${INSTALL_DIR}/.env and set NEBIUS_API_KEY (and S3 creds if needed)."
fi

echo "==> Building images"
docker compose build pipeline-image airflow-init airflow-apiserver

echo
echo "VM setup complete."
echo "Next steps:"
echo "  1. Edit ${INSTALL_DIR}/.env"
echo "  2. cd ${INSTALL_DIR} && docker compose up airflow-init"
echo "  3. cd ${INSTALL_DIR} && docker compose up -d"
echo "  4. Open Airflow on port 8080 and trigger evaluate_agent_production"
