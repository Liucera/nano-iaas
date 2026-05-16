import json
from typing import Iterator, Dict, Any
from pathlib import Path

from core.provider import CloudProvider
from core.data_reader import DataReader


class GCSReaderMock(CloudProvider):
    """Mock do Google Cloud Storage para desenvolvimento/testes."""
    
    name = "gcp"
    
    def __init__(self):
        self.data_reader = DataReader()
        self.mock_buckets = [
            {"name": "nano-iaas-dev", "location": "us-central1", "created": "2026-01-01T00:00:00+00:00"},
            {"name": "nano-iaas-prod", "location": "us-east1", "created": "2026-02-01T00:00:00+00:00"},
            {"name": "nano-iaas-backup", "location": "europe-west1", "created": "2026-03-01T00:00:00+00:00"},
        ]
    
    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """Simula autenticação GCP."""
        print("✅ GCP (MOCK) autenticado com sucesso!")
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
        """
        Lê dados mock do GCS.
        
        RESOURCE_PATH: gs://bucket/prefix/ ou caminho local para teste
        """
        # Se for caminho local, ler do disco
        if not resource_path.startswith('gs://'):
            # Tentar ler como arquivo local para testes
            local_path = Path(resource_path)
            if local_path.exists():
                return self._read_file(local_path, resource_path, options)
            print(f"❌ Recurso não encontrado: {resource_path}")
            return
        
        # Parse gs://bucket/prefix
        path = resource_path.replace('gs://', '')
        parts = path.split('/', 1)
        bucket = parts[0]
        prefix = parts[1] if len(parts) > 1 else ''
        
        limit = options.get('limit', 100)
        count = 0
        
        # Simular arquivos no bucket mock
        mock_files = self._get_mock_files(bucket, prefix)
        
        for file_info in mock_files:
            if count >= limit:
                return
            
            # Ler conteúdo do arquivo mock (do disco local)
            local_file = Path("tests/data") / file_info['local_name']
            if not local_file.exists():
                continue
            
            for record in self._read_file(local_file, resource_path, options):
                if count >= limit:
                    return
                record['_source'] = f"gs://{bucket}/{file_info['name']}"
                record['_bucket'] = bucket
                yield record
                count += 1
    
    def _read_file(self, file_path: Path, original_path: str, options: Dict) -> Iterator[Dict[str, Any]]:
        """Lê arquivo do disco local."""
        with open(file_path, 'rb') as f:
            content = f.read()
        
        file_format = self.data_reader.infer_format(str(file_path))
        
        for record in self.data_reader.parse_raw(content, file_format):
            yield record
    
    def _get_mock_files(self, bucket: str, prefix: str) -> list:
        """Retorna arquivos mock para um bucket/prefix."""
        # Mapeamento de arquivos mock disponíveis
        all_files = [
            {'name': 'dados/users.jsonl', 'local_name': 'users.jsonl', 'bucket': 'nano-iaas-dev'},
            {'name': 'dados/metrics.csv', 'local_name': 'metrics.csv', 'bucket': 'nano-iaas-dev'},
            {'name': 'logs/app.log', 'local_name': 'users.jsonl', 'bucket': 'nano-iaas-prod'},
        ]
        
        # Filtrar por bucket e prefix
        return [f for f in all_files 
                if f['bucket'] == bucket and f['name'].startswith(prefix)]
    
    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        """Retorna metadados mock."""
        return {
            'bucket': 'nano-iaas-dev',
            'name': resource_path.replace('gs://', ''),
            'size': 1024,
            'content_type': 'application/json',
            'time_created': '2026-05-16T10:00:00+00:00',
            'updated': '2026-05-16T10:00:00+00:00',
            'mock': True
        }
