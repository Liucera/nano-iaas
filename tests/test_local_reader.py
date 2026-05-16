import pytest
import tempfile
import os
from pathlib import Path

from providers.local.local_reader import LocalReader


class TestLocalReader:
    """Testes para o provider local."""
    
    @pytest.fixture
    def temp_dir(self):
        """Cria um diretório temporário com arquivos de teste."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Criar JSONL
            with open(os.path.join(tmpdir, "users.jsonl"), "w") as f:
                f.write('{"id": 1, "name": "Alice"}\n')
                f.write('{"id": 2, "name": "Bob"}\n')
            
            # Criar CSV
            with open(os.path.join(tmpdir, "data.csv"), "w") as f:
                f.write("id,name\n1,Alice\n2,Bob\n")
            
            yield tmpdir
    
    def test_authenticate(self, temp_dir):
        reader = LocalReader(base_path=temp_dir)
        assert reader.authenticate({}) == True
    
    def test_list_resources(self, temp_dir):
        reader = LocalReader(base_path=temp_dir)
        resources = list(reader.list_resources())
        assert len(resources) == 2
        assert any(r["name"] == "users.jsonl" for r in resources)
        assert any(r["name"] == "data.csv" for r in resources)
    
    def test_read_jsonl(self, temp_dir):
        reader = LocalReader(base_path=temp_dir)
        records = list(reader.read("users.jsonl"))
        assert len(records) == 2
        assert records[0]["name"] == "Alice"
        assert records[1]["name"] == "Bob"
        assert "_source" in records[0]
    
    def test_read_csv(self, temp_dir):
        reader = LocalReader(base_path=temp_dir)
        records = list(reader.read("data.csv"))
        assert len(records) == 2
        assert records[0]["name"] == "Alice"
    
    def test_read_limit(self, temp_dir):
        reader = LocalReader(base_path=temp_dir)
        records = list(reader.read("users.jsonl", limit=1))
        assert len(records) == 1
        assert records[0]["name"] == "Alice"
    
    def test_get_metadata(self, temp_dir):
        reader = LocalReader(base_path=temp_dir)
        meta = reader.get_metadata("users.jsonl")
        assert meta["format"] == "json"
        assert "size" in meta
