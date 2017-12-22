
import os
import tempfile

import click
from tabulate import tabulate

from vmwarelib.cli import util
from vmwarelib.sdk import core

@click.group()
@util.pass_context
@click.option('--ip', help="Host's IP.")
def cli(ctx, ip, **kwargs):
    """Host commands.
    """

    if not ip:
        raise Exception('IP of the Host is required. ')

    ctx.ip = ip
    ctx.host = core.VmwareHost(ctx.server, {"ip": ctx.ip})

@cli.command()
@util.pass_context
def info(ctx):
    print()

    for k, v in ctx.host.info().items():
        print("{:>20}: {:<}".format(k, v))

@cli.command()
@util.pass_context
def list_datastores(ctx):
    print()

    datastores = ctx.host.get_datastores()

    if not datastores:
        print("No datastores found...")
        return

    for ds in datastores:
        print("{:>50}: {:<}".format(ds.name, ds.dstype))

@cli.command()
@util.pass_context
@click.option('--name', help="Name. ")
@click.option('--nashost', help="Host. ")
@click.option('--share', help="Share. ")
@click.option('--amode', type=click.Choice(['ro', 'rw']), default='rw', help="access mode. ")
@click.option('--dstype', type=click.Choice(['nfs', 'cifs']), default='nfs', help="Type. ")
def create_nas_datastore(ctx, name, nashost, share, amode, dstype):
    if not name or not nashost or not share:
        raise Exception('name, nashost, and share are required. ')

    datastore = ctx.host.create_nas_datastore(name, nashost, share, amode, dstype)

@cli.command()
@util.pass_context
@click.argument('name')
def delete_datastore(ctx, name):
    ctx.host.remove_datastore(name)

@cli.command()
@util.pass_context
def list_logs(ctx):
    for log in ctx.host.list_logs():
        print(log.fileName)



