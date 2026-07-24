import json
import os
from typing import Iterator, Dict, Any

from google.cloud import storage
from google.oauth2 import service_account
from google.api_core.exceptions import GoogleAPIError

from core.provider import CloudProvider
from core.data_reader import DataReader


class GCSReader(CloudProvider):
    """Leitor real de dados do Google Cloud Storage para Nano-IaaS."""

    name = "gcp"

    def __init__(self):
        self.client = None
        self.project_id = None
        self.data_reader = DataReader()

    def authenticate(self, profile: Dict[str, Any]) -> bool:
        try:
            raw_credentials = profile.get("service_account_json") or os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
            self.project_id = profile.get("project_id")

            if raw_credentials:
                info = json.loads(raw_credentials) if isinstance(raw_credentials, str) else raw_credentials
                credentials = service_account.Credentials.from_service_account_info(info)
                self.project_id = self.project_id or info.get("project_id")
                self.client = storage.Client(project=self.project_id, credentials=credentials)
                return True

            credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if credentials_path:
                self.client = storage.Client.from_service_account_json(credentials_path, project=self.project_id)
                return True

            self.client = storage.Client(project=self.project_id)
            return True
        except Exception:
            print("Erro ao autenticar no GCP")
            return False

    def validate_credentials(self) -> bool:
        """Valida a service account com uma chamada autenticada ao GCS."""
        try:
            buckets = self.client.list_buckets(max_results=1)
            next(iter(buckets), None)
            return True
        except Exception:
            print("Erro ao validar credenciais GCP")
            return False

    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        try:
            for bucket in self.client.list_buckets():
                yield {"name": bucket.name, "location": bucket.location, "created": bucket.time_created.isoformat() if bucket.time_created else None, "type": "bucket"}
        except GoogleAPIError:
            print("Erro ao listar buckets GCS")
            raise

    def read(self, resource_path: str, format: str = "json", **options) -> Iterator[Dict[str, Any]]:
        path = resource_path.replace("gs://", "")
        parts = path.split("/", 1)
        bucket_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ""
        limit = options.get("limit", 100)
        count = 0

        try:
            bucket = self.client.bucket(bucket_name)
            for blob in self.client.list_blobs(bucket, prefix=prefix):
                if count >= limit:
                    return
                if blob.name.endswith("/"):
                    continue
                content = blob.download_as_bytes()
                file_format = self.data_reader.infer_format(blob.name)
                for record in self.data_reader.parse_raw(content, file_format):
                    if count >= limit:
                        return
                    record["_source"] = f"gs://{bucket_name}/{blob.name}"
                    record["_bucket"] = bucket_name
                    record["_updated"] = blob.updated.isoformat() if blob.updated else None
                    record["_size"] = blob.size
                    yield record
                    count += 1
        except GoogleAPIError:
            print("Erro ao ler GCS")
            raise

    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        path = resource_path.replace("gs://", "")
        parts = path.split("/", 1)
        bucket_name = parts[0]
        blob_name = parts[1] if len(parts) > 1 else ""
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.get_blob(blob_name)
            if not blob:
                return {"error": "Objeto não encontrado"}
            return {"bucket": bucket_name, "name": blob.name, "size": blob.size, "content_type": blob.content_type or "unknown", "time_created": blob.time_created.isoformat() if blob.time_created else None, "updated": blob.updated.isoformat() if blob.updated else None, "etag": blob.etag}
        except GoogleAPIError:
            return {"error": "Falha ao obter metadados GCS"}
