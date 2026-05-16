import json
import csv
import io
from typing import Iterator, Dict, Any, Union
from pathlib import Path
import pandas as pd


class DataReader:
    """Motor de leitura e conversão de dados - provider agnóstico."""
    
    @staticmethod
    def to_json(data: Iterator[Dict[str, Any]]) -> Iterator[str]:
        """Converte registros para linhas JSON (JSONL)."""
        for record in data:
            yield json.dumps(record, ensure_ascii=False, default=str)
    
    @staticmethod
    def to_csv(data: Iterator[Dict[str, Any]], delimiter: str = ',') -> Iterator[str]:
        """Converte registros para CSV."""
        records = list(data)
        if not records:
            return iter([])
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=records[0].keys(), delimiter=delimiter)
        writer.writeheader()
        
        for record in records:
            writer.writerow(record)
        
        output.seek(0)
        for line in output:
            yield line.rstrip('\n')
    
    @staticmethod
    def to_parquet(data: Iterator[Dict[str, Any]], output_path: Union[str, Path]) -> Path:
        """Converte registros para Parquet."""
        df = pd.DataFrame(list(data))
        path = Path(output_path)
        df.to_parquet(path, index=False)
        return path
    
    @staticmethod
    def infer_format(file_path: str) -> str:
        """Inferir formato de arquivo pelo extensão."""
        ext = Path(file_path).suffix.lower()
        format_map = {
            '.json': 'json',
            '.jsonl': 'json',
            '.csv': 'csv',
            '.parquet': 'parquet',
            '.txt': 'raw',
            '.log': 'raw'
        }
        return format_map.get(ext, 'raw')
    
    @staticmethod
    def parse_raw(content: bytes, format_hint: str = 'json') -> Iterator[Dict[str, Any]]:
        """Parseia conteúdo bruto baseado no formato."""
        text = content.decode('utf-8')
        
        if format_hint == 'csv':
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                yield dict(row)
        elif format_hint == 'json':
            # Tentar JSONL primeiro
            for line in text.strip().split('\n'):
                line = line.strip()
                if line:
                    yield json.loads(line)
        else:
            yield {'raw_content': text}
