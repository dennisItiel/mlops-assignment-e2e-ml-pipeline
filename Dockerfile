FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    docker.io \
    git \
 && update-ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /mlops-assignment

COPY pyproject.toml uv.lock ./
RUN uv sync --locked

ENV PATH="/mlops-assignment/.venv/bin:$PATH"

COPY pipeline pipeline/
COPY scripts scripts/
RUN chmod +x scripts/*.sh

# Default command shows help; Airflow DockerOperator overrides this.
CMD ["python", "scripts/run_pipeline_step.py", "--help"]
