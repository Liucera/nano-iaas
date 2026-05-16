import os
from pathlib import Path
from typing import Iterator, Dict, Any

from core.provider import CloudProvider
from core.data_reader import DataReader


class LocalReader(CloudProvider):
    """Provider local para testes — lê arquivos do filesystem."""
    
    name = "local"
    
    def __init__(self, base_path: str = "."):
        self.base_path = Path(base_path).resolve()
        self.data_reader = DataReader()
    
    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """Sempre autentica (local não precisa de credenciais)."""
        if 'base_path' in profile:
            self.base_path = Path(profile['base_path']).resolve()
        return self.base_path.exists()
    
    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        """Lista arquivos no diretório base."""
        pattern = filters.get('pattern', '*')
        for item in self.base_path.glob(pattern):
            if item.is_file():
                stat = item.stat()
                yield {
                    'name': item.name,
                    'path': str(item),
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'type': 'file'
                }
    
    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        """
        Lê arquivo local.
        
        Args:
            resource_path: Caminho relativo ao base_path (ex: dados/users.jsonl)
        """
        file_path = self.base_path / resource_path
        limit = options.get('limit', 1000)
        count = 0
        
        if not file_path.exists():
            print(f"❌ Arquivo não encontrado: {file_path}")
            return
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        parse_format = self.data_reader.infer_format(str(file_path))
        
        for record in self.data_reader.parse_raw(content, parse_format):
            if count >= limit:
                return
            record['_source'] = f"local://{resource_path}"
            record['_file'] = str(file_path)
            yield record
            count += 1
    
    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        """Metadados de arquivo local."""
        file_path = self.base_path / resource_path
        if not file_path.exists():
            return {'error': 'Arquivo não encontrado'}
        
        stat = file_path.stat()
        return {
            'path': str(file_path),
            'size': stat.st_size,
            'modified': stat.st_mtime,
            'format': self.data_reader.infer_format(str(file_path))
        }
