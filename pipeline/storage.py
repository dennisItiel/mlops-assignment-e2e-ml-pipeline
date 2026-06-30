"""Upload run artifacts to S3-compatible object storage."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def s3_upload_enabled() -> bool:
    _load_env()
    return bool(os.getenv("S3_BUCKET"))


def upload_run_directory(run_dir: Path, run_id: str | None = None) -> str | None:
    """Upload runs/<run-id>/ to s3://<bucket>/<prefix>/<run-id>/.

    Returns the remote URI, or None when S3 is not configured.
    """
    _load_env()
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        return None

    import boto3
    from botocore.client import Config

    run_id = run_id or run_dir.name
    prefix = os.getenv("S3_PREFIX", "swe-bench-runs").strip("/")
    remote_prefix = f"{prefix}/{run_id}"

    client_kwargs: dict = {
        "service_name": "s3",
        "config": Config(signature_version="s3v4"),
    }
    if endpoint := os.getenv("S3_ENDPOINT_URL"):
        client_kwargs["endpoint_url"] = endpoint
    if region := os.getenv("AWS_DEFAULT_REGION"):
        client_kwargs["region_name"] = region

    s3 = boto3.client(**client_kwargs)

    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        key = f"{remote_prefix}/{path.relative_to(run_dir).as_posix()}"
        s3.upload_file(str(path), bucket, key)

    if endpoint:
        base = endpoint.rstrip("/")
        return f"{base}/{bucket}/{remote_prefix}/"
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    return f"s3://{bucket}/{remote_prefix}/"


def update_manifest_remote_uri(run_dir: Path, remote_uri: str) -> None:
    import json

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["remote_artifact_uri"] = remote_uri
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
