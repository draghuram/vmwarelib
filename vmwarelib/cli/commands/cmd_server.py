
import click
from tabulate import tabulate

from vmwarelib.cli import util

@click.group()
@util.pass_context
def cli(ctx, **kwargs):
    """Server commands.
    """

    pass

@cli.command()
@util.pass_context
def info(ctx):
    print("Server Time: {}".format(ctx.server.service_instance.CurrentTime()))

@cli.command()
@util.pass_context
@click.option('--pat', help='Only VMs containing this pattern in their name will be listed.')
def list_vms(ctx, pat):
    print()
    for vm in ctx.server.list_vms(pat):
        print("{:>40}: {:<}".format(vm.name, vm.inventory_path))






