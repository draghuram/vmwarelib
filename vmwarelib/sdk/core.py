
import collections
import logging
import re
#from typing import Dict, Tuple, List
import urllib3

from pyVim import connect as vim_connect
from pyVmomi import vim

import requests

from vmwarelib.sdk import util

urllib3.disable_warnings()

class Server:
    def __init__(self, host, username, password, ignore_cert_warnings=False):
        self.host = host
        self.username = username
        self.password = password

        conn_func = vim_connect.SmartConnect
        if ignore_cert_warnings:
            conn_func = vim_connect.SmartConnectNoSSL

        logging.info("Connecting to vSphere server {}, user: {}".format(host, username))
        self.service_instance = conn_func(host=host, user=username, pwd=password)

    def cleanup(self):
        logging.debug("Cleaning up connection to vSphere server {}...".format(self.host))
        vim_connect.Disconnect(self.service_instance)

    def list_vms(self, pat):
        content = self.service_instance.RetrieveContent()

        container = content.rootFolder
        viewType = [vim.VirtualMachine]
        recursive = True
        containerView = content.viewManager.CreateContainerView(container, viewType, recursive)

        children = containerView.view
        for vm in children:
            vm_name = vm.summary.config.name
            if not pat or vm_name.lower().find(pat.lower()) != -1:
                yield VirtualMachine(self, vmobj=vm)

def get_root_backing(backing):
    assert backing is not None

    while backing:
        if not backing.parent:
            return backing

        backing = backing.parent

class VirtualDisk:
    def __init__(self, server, deviceobj, vmobj, snapobj=None):
        self.server = server
        self.deviceobj = deviceobj
        self.vmobj = vmobj
        self.snapobj = snapobj

        self.label = deviceobj.deviceInfo.label
        self.key = deviceobj.key
        self.summary = deviceobj.deviceInfo.summary
        self.backing_type = type(deviceobj.backing).__name__
        self.uuid = self.deviceobj.backing.uuid
        self.backing = deviceobj.backing
        self.root_backing = get_root_backing(self.backing)
        self.changeId = self.backing.changeId
        self.capacityInBytes = self.deviceobj.capacityInBytes

    def info(self):
        data = collections.OrderedDict()

        data["key"] = self.key
        data["label"] = self.label
        data["backingType"] = self.backing_type
        data["capacityInBytes"] = self.deviceobj.capacityInBytes
        data["capacity"] = util.bytes_to_readable_units(self.deviceobj.capacityInBytes)
        data["uuid"] = self.uuid
        data["path"] = self.deviceobj.backing.fileName
        data["rootPath"] = self.root_backing.fileName
        if self.changeId:
            data["changeId"] = self.changeId

        return data

    def get_changed_areas(self, changeid="*"):
        if not self.snapobj:
            raise Exception("Disk needs to be from Snapshot. ")

        start = 0
        while start < self.capacityInBytes:
            disk_change_info = self.vmobj.QueryChangedDiskAreas(self.snapobj, self.key, start, changeid)
            start += disk_change_info.length

            yield [(x.start, x.length) for x in disk_change_info.changedArea]

    def delete(self):
        util.delete_disk(self.server.service_instance, self.vmobj, self.deviceobj)

    def resize(self, size_gb):
        util.resize_disk(self.server.service_instance, self.vmobj, self.deviceobj, size_gb)

def _get_snapshot_with_name(snap, name):
    if snap.name == name:
        return snap.snapshot

    if snap.childSnapshotList:
        for child in snap.childSnapshotList:
            result = _get_snapshot_with_name(child, name)
            if result: return result

    return None

# Note that snapshot names need not be unique so it is possible to have
# more than one snapshot with same name. Until a better way is found to
# identify a snapshot, we will look up with name. So to use this method,
# there should not be multiple snapshots with same name.
def get_snapshot_with_name(name, vmobj):
    if not vmobj.snapshot:
        raise Exception("No snapshot was found with name ({})".format(name))

    for snap in vmobj.snapshot.rootSnapshotList:
        result = _get_snapshot_with_name(snap, name)
        if result:
            return result

    raise Exception("No snapshot was found with name ({})".format(name))

class Datastore:
    def __init__(self, server, hostobj, dsobj):
        self.server = server
        self.hostobj = hostobj
        self.dsobj = dsobj

        self.name = self.dsobj.name
        self.dstype = self.dsobj.summary.type
        
class VirtualMachineSnapshot:
    def __init__(self, server, vmobj, name, snapobj=None):
        self.server = server
        self.vmobj = vmobj
        self.name = name
        self.snapobj = snapobj
        if not snapobj:
            self.snapobj = get_snapshot_with_name(name, self.vmobj)
            
        self.moref = self.snapobj._moId

    def delete(self, remove_children=False):
        task = self.snapobj.RemoveSnapshot_Task(removeChildren=remove_children)
        result = util.wait_for_tasks(self.server.service_instance, [task])

    def get_disks(self):
        disks = []
        for device in self.snapobj.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk):
                disks.append(VirtualDisk(self.server, device, self.vmobj, self.snapobj))

        return disks

    def info(self):
        data = collections.OrderedDict()

        data["name"] = self.name
        data["moref"] = self.moref
        data["cbtEnabled"] = str(bool(self.snapobj.config.changeTrackingEnabled))

        return data

amodemap = {
    'rw': vim.host.MountInfo.AccessMode.readWrite,
    'ro': vim.host.MountInfo.AccessMode.readOnly
}

fsmap = {
    "nfs": vim.host.FileSystemVolume.FileSystemType.NFS,
    "cifs": vim.host.FileSystemVolume.FileSystemType.CIFS
}

class VmwareHost:
    def __init__(self, server, identity):
        self.server = server

        self.hostobj = server.service_instance.content.searchIndex.FindByIp(None, identity["ip"], False)
        if not self.hostobj:
            raise Exception("Could not find host with IP: ({})".format(identity["ip"]))

        self.diagmgr = server.service_instance.content.diagnosticManager

        self.name = self.hostobj.name
        self.moref = self.hostobj._moId

    def info(self):
        data = collections.OrderedDict()

        data["name"] = self.name
        data["moref"] = self.moref

        return data

    def get_datastores(self):
        dslist = self.hostobj.datastore
        if not dslist:
            return []

        return sorted([Datastore(self.server, self.hostobj, ds) for ds in dslist], key=lambda x: x.name)

    def remove_datastore(self, dsname):
        dslist = self.hostobj.datastore
        for ds in dslist:
            if ds.name == dsname:
                self.hostobj.configManager.datastoreSystem.RemoveDatastore(ds)
                return

        raise Exception("Could not find datastore ({})".format(dsname))

    def create_nas_datastore(self, name, nashost, share, amode="rw", dstype="nfs"):
        spec = vim.host.NasVolume.Specification(remoteHost=nashost, remotePath=share, localPath=name,
                                                accessMode=amodemap[amode], type=fsmap[dstype])
        return self.hostobj.configManager.datastoreSystem.CreateNasDatastore(spec)

    def list_logs(self):
        return self.diagmgr.QueryDescriptions()

class VirtualMachine:
    def _find_vmobj(self, server, identity):
        if not identity:
            raise Exception('IP, UUID, or Inventory path of the VM is required. ')

        vmobj = None

        if identity.get("ip", None):
            vmobj = server.service_instance.content.searchIndex.FindByIp(None, identity["ip"], True)
            if not vmobj:
                raise Exception("Could not find virtual machine with IP: ({})".format(identity["ip"]))
        elif identity.get("ipath", None):
            vmobj = server.service_instance.content.searchIndex.FindByInventoryPath(identity["ipath"])
            if not vmobj:
                raise Exception("Could not find virtual machine with inventory path: ({})".format(identity["ipath"]))

            assert isinstance(vmobj, vim.VirtualMachine)
        elif identity.get("uuid", None):
            uuid = identity["uuid"]
            vmobj = server.service_instance.content.searchIndex.FindByUuid(None, uuid, True)
            if not vmobj:
                raise Exception("Could not find virtual machine with UUID: ({})".format(uuid))
        else:
            raise Exception("Could not find virtual machine, ip or inventory path is not provided.")

        return vmobj

    def __init__(self, server, identity=None, vmobj=None):
        self.server = server
        self.vmobj = vmobj

        if vmobj is None:
            self.vmobj = self._find_vmobj(server, identity)

        self.config = self.vmobj.config
        self.name = self.config.name
        self.runtime = self.vmobj.runtime
        self.summary = self.vmobj.summary
        self.summary_config = self.summary.config
        self.snap_info = self.vmobj.snapshot

        self.vmx_path = self.summary_config.vmPathName
        self.datacenter =self._get_datacenter(self.vmobj)
        self.parent_folder = self._get_parent_folder(self.vmobj)
        self.inventory_path = self._get_inventory_path(self.vmobj)
        self.uuid = self.config.uuid

        self.guest = self.vmobj.summary.guest
        if self.guest:
            self.ip = self.guest.ipAddress
            self.hostname = self.guest.hostName
            self.tools_status = self.guest.toolsVersionStatus2

    def _get_datacenter(self, obj):
        while obj:
            if isinstance(obj, vim.Datacenter):
                return obj

            obj = obj.parent

        raise Exception("Could not find datacenter for ({}), object ({})".format(obj.name, obj))

    def _get_inventory_path(self, obj):
        comps = []
        while obj:
            comps.append(obj.name)
            obj = obj.parent

        # For a VM, I am getting inventory path like:
        #   Datacenters/Engineering/vm/Raghu/testvm (raghu)
        # It seems, I don't need to keep the very first component which
        # is root folder.
        comps.pop()

        return '/'.join(reversed(comps))

    def _get_parent_folder(self, obj):
        while obj:
            if isinstance(obj, vim.Folder):
                return obj

            obj = obj.parent

        raise Exception("Could not find parent folder for ({}), object ({})".format(obj.name, obj))

    def _get_snapshots(self, sdk_snapshots, snapshots):
        for snap in sdk_snapshots:
            snapshots.append(VirtualMachineSnapshot(self.server, self.vmobj, snap.name, snapobj=snap.snapshot))
            if snap.childSnapshotList:
                self._get_snapshots(snap.childSnapshotList, snapshots)

    def get_snapshots(self):
        if not self.snap_info:
            return []

        snapshots = []
        self._get_snapshots(self.snap_info.rootSnapshotList, snapshots)

        return snapshots

    def create_snapshot(self, name, description="", memory=False, quiesce=True):
        task = self.vmobj.CreateSnapshot_Task(name=name, description=description, memory=memory, quiesce=quiesce)
        result = util.wait_for_tasks(self.server.service_instance, [task])

        return VirtualMachineSnapshot(self.server, self.vmobj, name)

    def get_snapshot_with_name(self, name):
        return VirtualMachineSnapshot(self.server, self.vmobj, name)

    def delete_all_snapshots(self):
        task = self.vmobj.RemoveAllSnapshots_Task()
        result = util.wait_for_tasks(self.server.service_instance, [task])

    def get_disks(self):
        disks = []
        for device in self.config.hardware.device:
            if isinstance(device, vim.vm.device.VirtualDisk):
                disks.append(VirtualDisk(self.server, device, self.vmobj))

        return disks

    def info(self):
        data = collections.OrderedDict()

        data["name"] = self.config.name
        data["moref"] = self.vmobj._moId
        data["guestFullName"] = self.config.guestFullName
        data["pathToVm"] = self.vmx_path
        data["datacenter"] = self.datacenter.name
        data["parentFolder"] = self.parent_folder.name
        data["inventoryPath"] = self.inventory_path
        data["instanceUuid"] = self.config.instanceUuid
        data["cbtEnabled"] = str(bool(self.config.changeTrackingEnabled))
        data["uuid"] = self.config.uuid
        data["powerState"] = self.runtime.powerState
        if self.runtime.powerState == 'poweredOn':
            data["host"] = self.runtime.host.name

        data["memoryMB"] = self.summary_config.memorySizeMB
        data["numDisks"] = self.summary_config.numVirtualDisks
        if self.ip:
            data["ip"] = self.ip
        if self.hostname:
            data["hostName"] = self.hostname
        if self.tools_status:
            data["toolsStatus"] = self.tools_status

        resource_pool = self.vmobj.resourcePool
        if resource_pool:
            data["resourcePool"] = resource_pool.name

        return data

    def enable_cbt(self):
        config_spec = vim.vm.ConfigSpec()
        config_spec.changeTrackingEnabled = True

        util.wait_for_tasks(self.server.service_instance, [self.vmobj.Reconfigure(config_spec)])

    def disable_cbt(self):
        config_spec = vim.vm.ConfigSpec()
        config_spec.changeTrackingEnabled = False

        util.wait_for_tasks(self.server.service_instance, [self.vmobj.Reconfigure(config_spec)])

    def download_vmx(self, output_file):
        m = re.match('\[(.*)\]\s*(.*)', self.vmx_path)
        if not m:
            raise Exception("Could not parse VMX path ({})".format(self.vmx_path))

        dsname = m.group(1).strip()
        filepath = m.group(2).strip()
        url = "https://{}/folder/{}".format(self.server.host, filepath)

        auth = requests.auth.HTTPBasicAuth(self.server.username, self.server.password)
        params = {'dcPath': self.datacenter.name, 'dsName': dsname}
        resp = requests.get(url, params=params, auth=auth, verify=False)

        with open(output_file, "wb") as f:
            f.write(resp.content)

    def register(self, vmxpath, name=None):
        task = self.parent_folder.RegisterVM_Task(path=vmxpath, name=name, asTemplate=False,
                                                  pool=self.vmobj.resourcePool)
        util.wait_for_tasks(self.server.service_instance, [task])

    def unregister(self):
        self.vmobj.UnregisterVM()

    def poweron(self):
        # PowerOnMultiVM_Task API is not working. I only see the message:
        #   "Initializing Power on..." 
        # in vSphere client but power on never happens.
        # task = self.datacenter.PowerOnMultiVM_Task([self.vmobj])

        # task = self.vmobj.PowerOnVM_Task()
        # util.wait_for_tasks(self.server.service_instance, [task])
        util.powerOnVM(self.vmobj)
        
    def poweroff(self):
        task = self.vmobj.PowerOffVM_Task()
        util.wait_for_tasks(self.server.service_instance, [task])

    def add_disk(self, size_gb, format="thin"):
        util.add_disk(self.server.service_instance, self.vmobj, size_gb, format)

    def change_name(self, newname):
        spec = vim.vm.ConfigSpec()
        spec.name = newname
        task = self.vmobj.ReconfigVM_Task(spec=spec)
        util.wait_for_tasks(self.server.service_instance, [task])

