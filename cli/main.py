#!/usr/bin/env python3
import click
import sys
from pathlib import Path

# Adicionar root ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.commands.read import read_cmd
from cli.commands.list import list_cmd
from cli.commands.config import config_cmd


@click.group()
@click.version_option(version='0.1.0', prog_name='nano-iaas')
@click.pass_context
def cli(ctx):
    """Nano-IaaS: Leitura de dados multi-cloud via terminal."""
    ctx.ensure_object(dict)


cli.add_command(read_cmd, name='read')
cli.add_command(list_cmd, name='list')
cli.add_command(config_cmd, name='config')


if __name__ == '__main__':
    cli()
