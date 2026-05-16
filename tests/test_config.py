import pytest
import tempfile
import os
from pathlib import Path

from core.config import ConfigManager


class TestConfigManager:
    """Testes para o gerenciador de configurações."""
    
    @pytest.fixture
    def temp_config(self, monkeypatch):
        """Cria um diretório temporário para configurações."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / ".nano-iaas"
            config_dir.mkdir()
            
            # Mockar o diretório de config
            monkeypatch.setattr(ConfigManager, "CONFIG_DIR", config_dir)
            monkeypatch.setattr(ConfigManager, "CONFIG_FILE", config_dir / "config.yaml")
            
            yield ConfigManager()
    
    def test_default_profile(self, temp_config):
        assert temp_config.active_profile == "default"
    
    def test_list_profiles(self, temp_config):
        profiles = temp_config.list_profiles()
        assert "default" in profiles
    
    def test_set_and_get_profile(self, temp_config):
        temp_config.set_profile("test", {
            "aws": {"mode": "sso", "profile_name": "test"},
            "local": {"base_path": "/tmp"}
        })
        
        profile = temp_config.get_profile("test")
        assert profile["aws"]["profile_name"] == "test"
        assert profile["local"]["base_path"] == "/tmp"
    
    def test_activate_profile(self, temp_config):
        temp_config.set_profile("prod", {"aws": {"mode": "sso"}})
        temp_config.active_profile = "prod"
        assert temp_config.active_profile == "prod"
