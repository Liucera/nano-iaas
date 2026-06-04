from typing import Iterator, Dict, Any
from core.provider import CloudProvider
from core.data_reader import DataReader


class S3ReaderMock(CloudProvider):
    """Mock do AWS S3 para desenvolvimento/testes."""

    name = "aws"

    def __init__(self):
        self.data_reader = DataReader()
        self.mock_buckets = [
            {"name": "nano-iaas-raw", "location": "us-east-1", "created": "2026-01-01T00:00:00+00:00"},
            {"name": "nano-iaas-processed", "location": "us-west-2", "created": "2026-02-01T00:00:00+00:00"},
            {"name": "nano-iaas-archive", "location": "sa-east-1", "created": "2026-03-01T00:00:00+00:00"},
        ]

    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """Simula autenticação AWS."""
        print("✅ AWS (MOCK) autenticado com sucesso!")
        return True

    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        """Lista buckets mock."""
        for bucket in self.mock_buckets:
            yield {
                'name': bucket['name'],
                'location': bucket['location'],
                'created': bucket['created'],
                'type': 'bucket'
            }

    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        """Lê dados mock do S3."""
        print(f"📖 Lendo {resource_path} (MOCK)")
        return iter([])

    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        """Retorna metadados mock."""
        return {
            'bucket': 'nano-iaas-raw',
            'key': resource_path.replace('s3://', ''),
            'size': 1024,
            'content_type': 'application/json',
            'mock': True
        }
