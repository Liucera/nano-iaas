from typing import Iterator, Dict, Any
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError

from core.provider import CloudProvider
from core.data_reader import DataReader


class BlobReader(CloudProvider):
    """Leitor de dados Azure Blob Storage para Nano-IaaS."""

    name = "azure"

    def __init__(self):
        self.client = None
        self.data_reader = DataReader()

    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """
        Autentica usando connection string.

        profile esperado: {"connection_string": "..."}
        Se profile estiver vazio, tenta a variavel de ambiente
        AZURE_STORAGE_CONNECTION_STRING (usada como fallback do sistema,
        equivalente ao comportamento do S3Reader com IAM Role).
        """
        try:
            import os
            connection_string = profile.get('connection_string')
            if profile and not connection_string:
                # O cadastro por service principal e suportado pelo backend, mas
                # sua validacao real pertence a Macroetapa 6. Nao use a
                # credencial do sistema quando o usuario possui perfil proprio.
                print("❌ Credencial Azure pendente de validação")
                return False
            connection_string = connection_string or os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
            if not connection_string:
                print("❌ Nenhuma connection string do Azure disponivel")
                return False

            self.client = BlobServiceClient.from_connection_string(connection_string)
            return True
        except Exception:
            print("❌ Erro ao autenticar no Azure")
            return False

    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        """Lista containers da storage account."""
        try:
            for container in self.client.list_containers():
                yield {
                    'name': container['name'],
                    'created': container['last_modified'].isoformat() if container.get('last_modified') else None,
                    'type': 'container'
                }
        except AzureError:
            print("❌ Erro ao listar containers")

    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        """
        Le blobs de um container.

        Args:
            resource_path: azure://container/prefix/ ou azure://container/blob_name
        """
        path = resource_path.replace('azure://', '')
        parts = path.split('/', 1)
        container_name = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''

        limit = options.get('limit', 100)
        count = 0

        try:
            container_client = self.client.get_container_client(container_name)
            blobs = container_client.list_blobs(name_starts_with=prefix)

            for blob in blobs:
                if count >= limit:
                    return
                if blob.name.endswith('/'):
                    continue

                blob_client = container_client.get_blob_client(blob.name)
                content = blob_client.download_blob().readall()

                file_format = self.data_reader.infer_format(blob.name)

                for record in self.data_reader.parse_raw(content, file_format):
                    if count >= limit:
                        return
                    record['_source'] = f"azure://{container_name}/{blob.name}"
                    record['_last_modified'] = blob.last_modified.isoformat() if blob.last_modified else None
                    record['_size'] = blob.size
                    yield record
                    count += 1

        except AzureError:
            print("❌ Erro ao ler Blob Storage")

    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        path = resource_path.replace('azure://', '')
        parts = path.split('/', 1)
        container_name = parts[0]
        blob_name = parts[1] if len(parts) > 1 else ''

        try:
            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            props = blob_client.get_blob_properties()
            return {
                'container': container_name,
                'blob': blob_name,
                'size': props.size,
                'last_modified': props.last_modified.isoformat() if props.last_modified else None,
                'content_type': props.content_settings.content_type if props.content_settings else 'unknown',
                'etag': props.etag
            }
        except AzureError:
            return {'error': 'Não foi possível consultar os metadados no Azure Blob Storage'}
