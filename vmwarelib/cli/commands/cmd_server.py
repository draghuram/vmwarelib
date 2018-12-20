
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

@cli.command()
@util.pass_context
@click.option('--vmname', help="Name of vm to be created.")
@click.option('--datastore', help="Name of datastore under which you want to create the vm.")
@click.option('--datacenter', help="Name of datacenter.")
@click.option('--host', help="Name of host.")
@click.option('--memory', default='128', help="Memory in MB's to allocate for vm.")
@click.option('--cpus', default='2', help="Number of cpu's for the vm.")
def create_dummy_vm(ctx, vmname, datastore, datacenter, host, memory, cpus):
    ctx.server.create_dummy_vm(vmname, datastore, datacenter, host, memory, cpus)
    print("VM created successfully!")

@cli.command()
@util.pass_context
@click.option('--uuid', help="VM's instance UUID.")
@click.option('--ip', help="VM's IP.(Optional)")
@click.option('--ipath', help="VM's Inventory path.(Optional)")
def delete_vm(ctx, ip, ipath, uuid):
    identity = {"ip": ip, "ipath": ipath, "uuid": uuid}
    ctx.server.delete_vm(identity)
    print("VM deleted successfully!")

@cli.command()
@util.pass_context
@click.option('--vmname', help="Name of vm to be created.")
@click.option('--template', help="Name of the template you want to clone.")
@click.option('--datastore', help="Name of datastore under which you want to create the vm.")
@click.option('--datacenter', help="Name of datacenter.")
@click.option('--hostname', help="Name of host/cluster.")
def create_vm_from_template(ctx, vmname, template, datastore, datacenter, hostname):
    ctx.server.create_vm_from_template(vmname, template, datastore, datacenter, hostname)
    print("VM create successfully form template!")










