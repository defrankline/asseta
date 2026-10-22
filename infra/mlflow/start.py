"""Ensure the MinIO artifact bucket exists (idempotent), then exec the MLflow server.

Backend store: Postgres database `mlflow` (role `mlflow`, created by the `mlflow-db-init` one-shot service).
Artifacts: s3://$MLFLOW_ARTIFACT_BUCKET on MinIO, proxied by the server (`--serve-artifacts`), so Asseta's API and
workers never hold MinIO credentials for MLflow. All secrets come from the environment (.env), never this file.
"""

import os
import sys
import time

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

bucket = os.environ.get("MLFLOW_ARTIFACT_BUCKET", "asseta-mlflow")
s3 = boto3.client(
    "s3",
    endpoint_url=os.environ["MLFLOW_S3_ENDPOINT_URL"],
    config=Config(s3={"addressing_style": "path"}, connect_timeout=5, read_timeout=10),
    region_name="us-east-1",
)
for attempt in range(30):
    try:
        try:
            s3.head_bucket(Bucket=bucket)
        except ClientError:
            s3.create_bucket(Bucket=bucket)
        break
    except (BotoCoreError, ClientError) as exc:  # MinIO still starting
        print(f"waiting for object storage ({type(exc).__name__})", file=sys.stderr, flush=True)
        time.sleep(2)
else:
    sys.exit("object storage unavailable")

user, password = os.environ["MLFLOW_DB_USER"], os.environ["MLFLOW_DB_PASSWORD"]
backend = f"postgresql+psycopg2://{user}:{password}@{os.environ.get('MLFLOW_DB_HOST', 'postgres')}:5432/mlflow"
os.execvp(
    "mlflow",
    [
        "mlflow",
        "server",
        "--host",
        "0.0.0.0",  # noqa: S104 - container port; published on 127.0.0.1 only by compose
        "--port",
        "5000",
        "--backend-store-uri",
        backend,
        "--serve-artifacts",
        "--artifacts-destination",
        f"s3://{bucket}",
        "--default-artifact-root",
        "mlflow-artifacts:/",
        "--allowed-hosts",
        os.environ.get("MLFLOW_ALLOWED_HOSTS", "mlflow,mlflow:5000,localhost,localhost:*,127.0.0.1,127.0.0.1:*"),
        "--workers",
        os.environ.get("MLFLOW_WORKERS", "2"),
    ],
)
