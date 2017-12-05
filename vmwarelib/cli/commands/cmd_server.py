
import click
from tabulate import tabulate

from vmwarelib.cli import util

@click.command()
@util.pass_context
@click.argument('info')
def cli(ctx, **kwargs):
    """Server commands.
    """

    print("Server Time: {}".format(ctx.server.service_instance.CurrentTime()))


