import click
from core.config import ConfigManager


@click.group()
def config_cmd():
    """Gerencia configurações do Nano-IaaS."""
    pass


@config_cmd.command()
def show():
    """Mostra configuração atual."""
    config = ConfigManager()
    click.echo(f"Profile ativo: {config.active_profile}")
    click.echo("Profiles disponíveis:")
    for name in config.list_profiles():
        marker = " ⭐" if name == config.active_profile else ""
        click.echo(f"  - {name}{marker}")


@config_cmd.command()
@click.argument('name')
def activate(name):
    """Ativa um profile."""
    config = ConfigManager()
    if name not in config.list_profiles():
        click.echo(f"❌ Profile '{name}' não existe", err=True)
        return
    config.active_profile = name
    click.echo(f"✅ Profile '{name}' ativado!")
