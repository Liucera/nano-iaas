import pytest
from click.testing import CliRunner

from cli.main import cli


class TestCLI:
    """Testes para a interface de linha de comando."""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_version(self, runner):
        result = runner.invoke(cli, ['--version'])
        assert result.exit_code == 0
        assert 'nano-iaas' in result.output
    
    def test_config_show(self, runner):
        result = runner.invoke(cli, ['config', 'show'])
        assert result.exit_code == 0
        assert 'Profile ativo' in result.output
    
    def test_list_local(self, runner):
        result = runner.invoke(cli, ['list', 'local'])
        assert result.exit_code == 0
        assert 'setup.py' in result.output or 'file' in result.output
    
    def test_read_local_jsonl(self, runner):
        result = runner.invoke(cli, ['read', 'tests/data/users.jsonl', '--limit', '1'])
        assert result.exit_code == 0
        assert 'Alice' in result.output
    
    def test_read_local_csv(self, runner):
        result = runner.invoke(cli, ['read', 'tests/data/metrics.csv', '--format', 'json'])
        assert result.exit_code == 0
        assert 'cpu_usage' in result.output
    
    def test_read_local_limit(self, runner):
        result = runner.invoke(cli, ['read', 'tests/data/users.jsonl', '--limit', '1'])
        assert result.exit_code == 0
        # Filtrar apenas linhas JSON (ignorar logs)
        lines = [l for l in result.output.split('\n') if l.strip() and l.strip().startswith('{')]
        assert len(lines) == 1  # Apenas Alice (1 registro JSON)
