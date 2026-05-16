import click
import json
import sys
from typing import Optional

from core.config import ConfigManager
from core.data_reader import DataReader
from providers.local.local_reader import LocalReader
from providers.aws.s3_reader import S3Reader


PROVIDERS = {
    'local': LocalReader,
    'aws': S3Reader,
    's3': S3Reader,
}


@click.command()
@click.argument('resource_path')
@click.option('--provider', '-p', help='Provedor (local, aws, gcp, azure)')
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
        nano-iaas read s3://meu-bucket/dados/ --provider aws
    """
    config = ConfigManager()
    profile_data = config.get_profile(profile)
    
    # Detectar provider pelo prefixo se não especificado
    if not provider:
        if resource_path.startswith('s3://'):
            provider = 'aws'
        else:
            provider = 'local'
    
    provider_class = PROVIDERS.get(provider.lower())
    if not provider_class:
        click.echo(f"❌ Provider '{provider}' não suportado", err=True)
        sys.exit(1)
    
    # Instanciar provider
    if provider == 'local':
        base_path = profile_data.get('local', {}).get('base_path', '.')
        reader = LocalReader(base_path=base_path)
    else:
        reader = provider_class()
    
    # Autenticar
    auth_config = profile_data.get(provider, {})
    if not reader.authenticate(auth_config):
        sys.exit(1)
    
    click.echo(f"🔍 Lendo {resource_path} [{provider}]...", err=True)
    
    # Ler dados
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
