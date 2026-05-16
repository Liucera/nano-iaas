import click
import json
import sys
from typing import Optional

from core.config import ConfigManager
from core.data_reader import DataReader
from providers.local.local_reader import LocalReader


@click.command()
@click.argument('resource_path')
@click.option('--provider', '-p', default='local', help='Provedor (local, aws, gcp, azure)')
@click.option('--format', '-f', default='auto', 
              type=click.Choice(['json', 'csv', 'parquet', 'raw', 'auto']))
@click.option('--limit', '-l', default=100, help='Limite de registros')
@click.option('--profile', help='Profile de configuração')
@click.option('--output', '-o', help='Arquivo de saída (default: stdout)')
def read_cmd(resource_path, provider, format, limit, profile, output):
    """
    Lê dados de um recurso.
    
    Exemplos:
        nano-iaas read tests/data/users.jsonl
        nano-iaas read tests/data/metrics.csv --format json
        nano-iaas read tests/data/users.jsonl --format csv
    """
    config = ConfigManager()
    profile_data = config.get_profile(profile)
    
    # Instanciar provider local (por enquanto só temos ele)
    if provider == 'local':
        base_path = profile_data.get('local', {}).get('base_path', '.')
        reader = LocalReader(base_path=base_path)
    else:
        click.echo(f"❌ Provider '{provider}' ainda não implementado", err=True)
        sys.exit(1)
    
    # Autenticar
    auth_config = profile_data.get(provider, {})
    if not reader.authenticate(auth_config):
        sys.exit(1)
    
    click.echo(f"🔍 Lendo {resource_path}...", err=True)
    
    # Ler dados - converter para lista para poder reutilizar
    records = list(reader.read(resource_path, format=format, limit=limit))
    
    if not records:
        click.echo("⚠️ Nenhum registro encontrado", err=True)
        return
    
    # Formatar saída
    if format == 'csv':
        lines = list(DataReader.to_csv(iter(records)))
        content = '\n'.join(lines)
    elif format == 'parquet':
        if not output:
            click.echo("❌ Parquet requer --output", err=True)
            sys.exit(1)
        path = DataReader.to_parquet(iter(records), output)
        click.echo(f"✅ Parquet salvo em: {path}", err=True)
        return
    else:
        # JSON/RAW/AUTO
        lines = []
        for record in records:
            lines.append(json.dumps(record, ensure_ascii=False, default=str))
        content = '\n'.join(lines)
    
    # Output
    if output:
        with open(output, 'w', encoding='utf-8') as f:
            f.write(content)
        click.echo(f"✅ Salvo em: {output}", err=True)
    else:
        click.echo(content)
