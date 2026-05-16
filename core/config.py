import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class Profile(BaseModel):
    aws: Optional[Dict[str, Any]] = None
    gcp: Optional[Dict[str, Any]] = None
    azure: Optional[Dict[str, Any]] = None


class ConfigManager:
    """Gerenciador de configurações multi-profile."""
    
    CONFIG_DIR = Path.home() / '.nano-iaas'
    CONFIG_FILE = CONFIG_DIR / 'config.yaml'
    
    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._ensure_config_exists()
        self.load()
    
    def _ensure_config_exists(self):
        """Cria estrutura de config se não existir."""
        self.CONFIG_DIR.mkdir(exist_ok=True)
        if not self.CONFIG_FILE.exists():
            default_config = {
                'version': '1.0',
                'active_profile': 'default',
                'profiles': {
                    'default': {
                        'aws': {'mode': 'sso', 'profile_name': 'default'},
                        'gcp': {'mode': 'adc', 'project': None},
                        'azure': {'mode': 'cli', 'subscription': None},
                        'local': {'base_path': '.'}
                    }
                }
            }
            self.save(default_config)
    
    def load(self):
        """Carrega configuração do disco."""
        with open(self.CONFIG_FILE, 'r') as f:
            self._config = yaml.safe_load(f)
    
    def save(self, config: Optional[Dict[str, Any]] = None):
        """Salva configuração no disco."""
        config = config or self._config
        with open(self.CONFIG_FILE, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    
    @property
    def active_profile(self) -> str:
        return self._config.get('active_profile', 'default')
    
    @active_profile.setter
    def active_profile(self, profile_name: str):
        self._config['active_profile'] = profile_name
        self.save()
    
    def get_profile(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Retorna configuração de um profile."""
        name = name or self.active_profile
        return self._config.get('profiles', {}).get(name, {})
    
    def set_profile(self, name: str, config: Dict[str, Any]):
        """Cria ou atualiza um profile."""
        if 'profiles' not in self._config:
            self._config['profiles'] = {}
        self._config['profiles'][name] = config
        self.save()
    
    def list_profiles(self) -> list:
        """Lista todos os profiles disponíveis."""
        return list(self._config.get('profiles', {}).keys())
