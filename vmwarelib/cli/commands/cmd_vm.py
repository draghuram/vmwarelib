
import os
import tempfile

import click
from tabulate import tabulate

from vmwarelib.cli import util
from vmwarelib.sdk import core

@click.group()
@util.pass_context
@click.option('--ip', help="VM's IP.")
@click.option('--ipath', help="VM's Inventory path.")
@click.option('--uuid', help="VM's instance UUID.")
def cli(ctx, ip, ipath, uuid, **kwargs):
    """VM commands.
    """

    if not ip and not ipath and not uuid:
        raise Exception('IP, UUID, or Inventory path of the VM is required. ')

    ctx.ip = ip
    ctx.ipath = ipath
    ctx.uuid = uuid
    ctx.vm = core.VirtualMachine(ctx.server, {"ip": ctx.ip, "ipath": ipath, "uuid": uuid})

@cli.command()
@util.pass_context
def info(ctx):
    print()

    for k, v in ctx.vm.info().items():
        print("{:>20}: {:<}".format(k, v))

    print()
    for disk in ctx.vm.get_disks():
        print("  {}".format(disk.label))
        for k, v in disk.info().items():
            if v is None: continue
            print("{:>20}: {:<}".format(k, v))

        print()

    print()
    for snap in ctx.vm.get_snapshots():
        print("  Snapshot ({})".format(snap.name))
        for k, v in snap.info().items():
            print("{:>20}: {:<}".format(k, v))
        
        print()

@cli.command()
@util.pass_context
@click.argument('name')
def create_snapshot(ctx, name):
    ctx.vm.create_snapshot(name)

@cli.command()
@util.pass_context
@click.argument('name')
def delete_snapshot(ctx, name):
    snap = ctx.vm.get_snapshot_with_name(name)
    snap.delete()

@cli.command()
@util.pass_context
@click.argument('name')
def snapinfo(ctx, name):
    snap = ctx.vm.get_snapshot_with_name(name)
    print()
    for k, v in snap.info().items():
        print("{:>20}: {:<}".format(k, v))

    print()
    for disk in snap.get_disks():
        print("  {}".format(disk.label))
        for k, v in disk.info().items():
            if v is None: continue
            print("{:>20}: {:<}".format(k, v))

        print()
            
@cli.command()
@util.pass_context
def delete_all_snapshots(ctx):
    ctx.vm.delete_all_snapshots()

@cli.command()
@util.pass_context
def list_snapshots(ctx):
    print()

    snapshot_names = [x.name for x in ctx.vm.get_snapshots()]

    if not snapshot_names:
        print("No snapshots found...")
        return

    for snapname in snapshot_names:
        print("  {}".format(snapname))

@cli.command()
@util.pass_context
def enable_cbt(ctx):
    ctx.vm.enable_cbt()

@cli.command()
@util.pass_context
def disable_cbt(ctx):
    ctx.vm.disable_cbt()

@cli.command()
@util.pass_context
@click.option('--output_file', '-o', help='Output file name for VMX. ')
def download_vmx(ctx, output_file):
    if not output_file:
        fd, output_file = tempfile.mkstemp(suffix='.vmx', prefix='vm_{}'.format(ctx.ip))
        os.close(fd)

    ctx.vm.download_vmx(output_file)

@cli.command()
@util.pass_context
@click.argument('key', type=click.INT)
@click.option('--snapname', help='Name of snapshot where disk needs to be looked up. Default is live VM. ')
@click.option('--from_changeid', help='Change ID from which incremental needs to be computed. ')
@click.option('--ca', is_flag=True, default=False, help='Shows changed areas when set. ')
def diskinfo(ctx, key, snapname, from_changeid, ca):
    if ca and not from_changeid:
        from_changeid = "*"

    if snapname:
        snap = ctx.vm.get_snapshot_with_name(snapname)
        disks = [x for x in snap.get_disks() if x.key == key]
    else:
        disks = [x for x in ctx.vm.get_disks() if x.key == key]

    assert len(disks) == 1, "Cannot find disk with key: " + key

    disk = disks[0]
    print()
    for k, v in disk.info().items():
        print("{:>20}: {:<}".format(k, v))

    if ca:
        print('\n  Changed Areas (from "{}"): \n'.format(from_changeid))

        for change_list in disk.get_changed_areas(from_changeid):
            for start, length in change_list:
                print("{:>20}: {:<}".format(start, length))

@cli.command()
@util.pass_context
@click.argument('vmxpath')
@click.option('--name', help='Display name of the VM. ')
def register(ctx, vmxpath, name):
    """Register a VM using the current VM's parameters for the most part.
    """

    ctx.vm.register(vmxpath, name)

@cli.command()
@util.pass_context
def unregister(ctx):
    """Unregister.
    """

    ctx.vm.unregister()

@cli.command()
@util.pass_context
def poweron(ctx):
    ctx.vm.poweron()

@cli.command()
@util.pass_context
def poweroff(ctx):
    ctx.vm.poweroff()

@cli.command()
@util.pass_context
@click.option('--size_gb', type=click.INT, help='Size of the disk in GB. ')
@click.option('--format', type=click.Choice(["thick", "thin"]), default="thin")
def add_disk(ctx, size_gb, format):
    ctx.vm.add_disk(size_gb, format)

@cli.command()
@util.pass_context
@click.argument('key', type=click.INT)
def delete_disk(ctx, key):
    disks = [x for x in ctx.vm.get_disks() if x.key == key]
    assert len(disks) == 1, "Cannot find disk with key: " + key
    disk = disks[0]

    disk.delete()

@cli.command()
@util.pass_context
@click.argument('newname')
def change_name(ctx, newname):
    ctx.vm.change_name(newname)





    


