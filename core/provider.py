from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any
from pathlib import Path


class CloudProvider(ABC):
    """Interface base para todos os provedores cloud do Nano-IaaS."""
    
    name: str = ""
    supported_formats = ['json', 'csv', 'parquet', 'raw']
    
    @abstractmethod
    def authenticate(self, profile: Dict[str, Any]) -> bool:
        """Autentica no provedor cloud."""
        pass
    
    @abstractmethod
    def list_resources(self, **filters) -> Iterator[Dict[str, Any]]:
        """Lista recursos disponíveis (buckets, containers, etc)."""
        pass
    
    @abstractmethod
    def read(self, resource_path: str, format: str = 'json', **options) -> Iterator[Dict[str, Any]]:
        """
        Lê dados de um recurso cloud.
        
        Args:
            resource_path: Caminho do recurso (ex: s3://bucket/prefix/)
            format: Formato de saída desejado
            **options: Opções adicionais (limit, prefix, etc)
        """
        pass
    
    @abstractmethod
    def get_metadata(self, resource_path: str) -> Dict[str, Any]:
        """Retorna metadados do recurso (tamanho, última modificação, etc)."""
        pass
