import click
import json
from typing import Optional

from core.config import ConfigManager
from providers.local.local_reader import LocalReader
from providers.aws.s3_reader import S3Reader
from providers.gcp.gcs_reader_mock import GCSReaderMock
from providers.azure.blob_reader_mock import BlobReaderMock

try:
    from rich.console import Console
    from rich.table import Table
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


PROVIDERS = {
    'local': LocalReader,
    'aws': S3Reader,
    'gcp': GCSReaderMock,
    'azure': BlobReaderMock,
}


@click.command()
@click.argument('provider', default='local')
@click.option('--profile', help='Profile de configuração')
@click.option('--format', '-f', default='table', 
              type=click.Choice(['table', 'json', 'csv']))
def list_cmd(provider, profile, format):
    """Lista recursos disponíveis."""
    config = ConfigManager()
    profile_data = config.get_profile(profile)
    
    provider_class = PROVIDERS.get(provider.lower())
    if not provider_class:
        click.echo(f"❌ Provider '{provider}' não suportado", err=True)
        return
    
    # Instanciar
    if provider == 'local':
        base_path = profile_data.get('local', {}).get('base_path', '.')
        reader = LocalReader(base_path=base_path)
    else:
        reader = provider_class()
    
    auth_config = profile_data.get(provider, {})
    if not reader.authenticate(auth_config):
        click.echo(f"❌ Falha na autenticação {provider}", err=True)
        return
    
    resources = list(reader.list_resources())
    
    if format == 'json':
        click.echo(json.dumps(resources, indent=2, ensure_ascii=False, default=str))
    elif format == 'csv':
        if resources:
            import csv
            import io
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=resources[0].keys())
            writer.writeheader()
            for r in resources:
                writer.writerow(r)
            click.echo(output.getvalue())
    else:
        # Table com Rich se disponível
        if RICH_AVAILABLE and resources:
            console = Console()
            table = Table(title=f"☁️  Recursos {provider.upper()}", show_header=True, header_style="bold magenta")
            
            for key in resources[0].keys():
                table.add_column(key.capitalize())
            
            for r in resources:
                table.add_row(*[str(v) for v in r.values()])
            
            console.print(table)
        else:
            # Fallback simples
            click.echo(f"{'NAME':<40} {'TYPE':<10}")
            click.echo("-" * 50)
            for r in resources:
                click.echo(f"{r['name']:<40} {r.get('type', 'unknown'):<10}")
