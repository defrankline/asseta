# MLflow tracking server (ADR-007): official image pinned by digest + the two drivers it lacks (Postgres backend
# store, S3/MinIO artifact store). Versions pinned; boto3 matches backend/uv.lock.
FROM ghcr.io/mlflow/mlflow:v3.17.0@sha256:78803b7afd156eced665b023554bc199a4723d4466e7cba3732f7284f3cddd11
RUN pip install --no-cache-dir psycopg2-binary==2.9.10 boto3==1.43.116
COPY start.py /opt/asseta/start.py
EXPOSE 5000
HEALTHCHECK --interval=10s --timeout=3s --retries=30 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)" || exit 1
ENTRYPOINT ["python", "/opt/asseta/start.py"]
