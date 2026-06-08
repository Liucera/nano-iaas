from typing import Iterator, Dict, Any
from pathlib import Path
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
        print("✅ AWS (MOCK) autenticado com sucesso!")
        return True

    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        for bucket in self.mock_buckets:
            yield {
                'name': bucket['name'],
                'location': bucket['location'],
                'created': bucket['created'],
                'type': 'bucket'
            }

    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        path = resource_path.replace('s3://', '')
        parts = path.split('/', 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''

        mock_files = [
            {'name': 'dados/users.jsonl', 'local_name': 'users.jsonl', 'bucket': 'nano-iaas-raw'},
            {'name': 'dados/metrics.csv', 'local_name': 'metrics.csv', 'bucket': 'nano-iaas-raw'},
        ]

        files = [f for f in mock_files if f['bucket'] == bucket and f['name'].startswith(prefix)]

        for file_info in files:
            local_file = Path("tests/data") / file_info['local_name']
            if not local_file.exists():
                continue
            with open(local_file, 'rb') as f:
                content = f.read()
            file_format = self.data_reader.infer_format(str(local_file))
            for record in self.data_reader.parse_raw(content, file_format):
                record['_source'] = f"s3://{bucket}/{file_info['name']}"
                record['_bucket'] = bucket
                yield record

    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        return {
            'bucket': 'nano-iaas-raw',
            'key': resource_path.replace('s3://', ''),
            'size': 1024,
            'content_type': 'application/json',
            'mock': True
        }
