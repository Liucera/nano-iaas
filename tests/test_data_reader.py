import pytest
from core.data_reader import DataReader


class TestDataReader:
    """Testes para o motor de leitura de dados."""
    
    def test_infer_format_json(self):
        assert DataReader.infer_format("dados.json") == "json"
        assert DataReader.infer_format("dados.jsonl") == "json"
    
    def test_infer_format_csv(self):
        assert DataReader.infer_format("dados.csv") == "csv"
    
    def test_infer_format_parquet(self):
        assert DataReader.infer_format("dados.parquet") == "parquet"
    
    def test_infer_format_unknown(self):
        assert DataReader.infer_format("dados.xyz") == "raw"
    
    def test_parse_jsonl(self):
        content = b'{"id": 1, "name": "Alice"}\n{"id": 2, "name": "Bob"}'
        records = list(DataReader.parse_raw(content, "json"))
        assert len(records) == 2
        assert records[0]["name"] == "Alice"
        assert records[1]["name"] == "Bob"
    
    def test_parse_csv(self):
        content = b"id,name\n1,Alice\n2,Bob"
        records = list(DataReader.parse_raw(content, "csv"))
        assert len(records) == 2
        assert records[0]["name"] == "Alice"
    
    def test_to_json(self):
        data = [{"id": 1, "name": "Alice"}]
        lines = list(DataReader.to_json(iter(data)))
        assert len(lines) == 1
        assert '"name": "Alice"' in lines[0]
    
    def test_to_csv(self):
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        lines = list(DataReader.to_csv(iter(data)))
        assert len(lines) == 3  # header + 2 rows
        assert "id,name" in lines[0]
        assert "1,Alice" in lines[1]
