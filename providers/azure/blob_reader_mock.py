import json
from typing import Iterator, Dict, Any
from pathlib import Path

from core.provider import CloudProvider
from core.data_reader import DataReader


class BlobReaderMock(CloudProvider):
    """Mock do Azure Blob Storage para desenvolvimento/testes."""
    
    name = "azure"
    
    def __init__(self):
        self.data_reader = DataReader()
        self.mock_containers = [
            {"name": "nano-iaas-data", "last_modified": "2026-01-01T00:00:00+00:00"},
            {"name": "nano-iaas-logs", "last_modified": "2026-02-01T00:00:00+00:00"},
            {"name": "nano-iaas-backups", "last_modified": "2026-03-01T00:00:00+00:00"},
        ]
    
    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """Simula autenticação Azure."""
        print("✅ Azure (MOCK) autenticado com sucesso!")
        return True
    
    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        """Lista containers mock."""
        for container in self.mock_containers:
            yield {
                'name': container['name'],
                'last_modified': container['last_modified'],
                'type': 'container'
            }
    
    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        """
        Lê dados mock do Azure Blob.
        
        RESOURCE_PATH: azure://container/prefix/ ou caminho local
        """
        # Se for caminho local, ler do disco
        if not resource_path.startswith('azure://'):
            local_path = Path(resource_path)
            if local_path.exists():
                return self._read_file(local_path, resource_path, options)
            print(f"❌ Recurso não encontrado: {resource_path}")
            return
        
        # Parse azure://container/prefix
        path = resource_path.replace('azure://', '')
        parts = path.split('/', 1)
        container = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''
        
        limit = options.get('limit', 100)
        count = 0
        
        # Simular blobs no container mock
        mock_blobs = self._get_mock_blobs(container, prefix)
        
        for blob_info in mock_blobs:
            if count >= limit:
                return
            
            local_file = Path("tests/data") / blob_info['local_name']
            if not local_file.exists():
                continue
            
            for record in self._read_file(local_file, resource_path, options):
                if count >= limit:
                    return
                record['_source'] = f"azure://{container}/{blob_info['name']}"
                record['_container'] = container
                yield record
                count += 1
    
    def _read_file(self, file_path: Path, original_path: str, options: Dict) -> Iterator[Dict[str, Any]]:
        """Lê arquivo do disco local."""
        with open(file_path, 'rb') as f:
            content = f.read()
        
        file_format = self.data_reader.infer_format(str(file_path))
        
        for record in self.data_reader.parse_raw(content, file_format):
            yield record
    
    def _get_mock_blobs(self, container: str, prefix: str) -> list:
        """Retorna blobs mock para um container/prefix."""
        all_blobs = [
            {'name': 'dados/users.jsonl', 'local_name': 'users.jsonl', 'container': 'nano-iaas-data'},
            {'name': 'dados/metrics.csv', 'local_name': 'metrics.csv', 'container': 'nano-iaas-data'},
            {'name': 'logs/2026/05/app.log', 'local_name': 'users.jsonl', 'container': 'nano-iaas-logs'},
        ]
        
        return [b for b in all_blobs 
                if b['container'] == container and b['name'].startswith(prefix)]
    
    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        """Retorna metadados mock."""
        return {
            'container': 'nano-iaas-data',
            'name': resource_path.replace('azure://', ''),
            'size': 2048,
            'content_type': 'application/json',
            'last_modified': '2026-05-16T10:00:00+00:00',
            'etag': '"mock-etag-12345"',
            'mock': True
        }
