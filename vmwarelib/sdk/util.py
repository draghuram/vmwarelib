
import sys
import textwrap

from pyVmomi import vim
from pyVmomi import vmodl

unit_k = 1024
unit_m = unit_k * 1024
unit_g = unit_m * 1024
unit_t = unit_g * 1024
unit_p = unit_t * 1024
unit_e = unit_p * 1024

num_bytes = {"B": 1, "KB": unit_k, "MB": unit_m, "GB": unit_g, "TB": unit_t, "PB": unit_p, "EB": unit_e}

def convert_to_bytes(size, unit):
    if not unit:
        return size

    return size * num_bytes[unit]

def bytes_to_readable_units(num_bytes):
    if num_bytes < 1024:
        return "{:03.2f} Bytes".format(num_bytes)

    num_kb = num_bytes/1024
    if num_kb < 1024:
        return "{:03.2f} KB".format(num_kb)

    num_mb = num_kb/1024
    if num_mb < 1024:
        return "{:03.2f} MB".format(num_mb)

    num_gb = num_mb/1024
    if num_gb < 1024:
        return "{:03.2f} GB".format(num_gb)

    num_tb = num_gb/1024
    if num_tb < 1024:
        return "{:03.2f} TB".format(num_tb)

    num_pb = num_tb/1024
    if num_pb < 1024:
        return "{:03.2f} PB".format(num_pb)

    num_eb = num_pb/1024
    if num_eb < 1024:
        return "{:03.2f} EB".format(num_eb)

    return "{:03.2f} Bytes".format(num_bytes)

# Copied from pyvmomi-community-samples project (and slightly modified).
def wait_for_tasks(service_instance, tasks):
    """Given the service instance si and tasks, it returns after all the
    tasks are complete
    """
    result = {}

    property_collector = service_instance.content.propertyCollector
    task_list = [str(task) for task in tasks]
    # Create filter
    obj_specs = [vmodl.query.PropertyCollector.ObjectSpec(obj=task)
                 for task in tasks]
    property_spec = vmodl.query.PropertyCollector.PropertySpec(type=vim.Task,
                                                               pathSet=[],
                                                               all=True)
    filter_spec = vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = obj_specs
    filter_spec.propSet = [property_spec]
    pcfilter = property_collector.CreateFilter(filter_spec, True)

    try:
        version, state = None, None

        # Loop looking for updates till the state moves to a completed state.
        while len(task_list):
            update = property_collector.WaitForUpdates(version)
            for filter_set in update.filterSet:
                for obj_set in filter_set.objectSet:
                    task = obj_set.obj
                    for change in obj_set.changeSet:
                        if change.name == 'info':
                            state = change.val.state
                        elif change.name == 'info.state':
                            state = change.val
                        else:
                            continue

                        if not str(task) in task_list:
                            continue

                        if state == vim.TaskInfo.State.success:
                            # Remove task from taskList
                            task_list.remove(str(task))
                            result[task.info.key] = task
                        elif state == vim.TaskInfo.State.error:
                            raise task.info.error

            # Move to next version
            version = update.version

        return result
    finally:
        if pcfilter:
            pcfilter.Destroy()

def _create_char_spinner():
    """Creates a generator yielding a char based spinner.
    """
    while True:
        for c in '|/-\\':
            yield c

_spinner = _create_char_spinner()

def spinner(label=''):
    """Prints label with a spinner.

    When called repeatedly from inside a loop this prints
    a one line CLI spinner.
    """
    sys.stdout.write("\r\t%s %s" % (label, next(_spinner)))
    sys.stdout.flush()


def answer_vm_question(virtual_machine):
    print()
    choices = virtual_machine.runtime.question.choice.choiceInfo
    default_option = None

    if virtual_machine.runtime.question.choice.defaultIndex is not None:
        ii = virtual_machine.runtime.question.choice.defaultIndex
        default_option = choices[ii]

    choice = None
    while choice not in [o.key for o in choices]:
        print("VM power on is paused by this question:\n\n")
        print("\n".join(textwrap.wrap(virtual_machine.runtime.question.text, 60)))
        for option in choices:
            print("\t %s: %s " % (option.key, option.label))
        if default_option is not None:
            print("default (%s): %s\n" % (default_option.label, default_option.key))
        choice = input("\nchoice number: ").strip()
        print("...")

    return choice

def powerOnVM(vmobj):
    task = vmobj.PowerOn()

    # We track the question ID & answer so we don't end up answering the same
    # questions repeatedly.
    answers = {}
    while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
        if vmobj.runtime.question is not None:
            question_id = vmobj.runtime.question.id
            if question_id not in answers.keys():
                answers[question_id] = answer_vm_question(vmobj)
                vmobj.AnswerVM(question_id, answers[question_id])

        spinner(task.info.state)

    if task.info.state == vim.TaskInfo.State.error:
        raise task.info.error

def add_disk(service_instance, vmobj, size_gb, format="thin"):
    spec = vim.vm.ConfigSpec()

    # get all disks on a VM, set unit_number to the next available
    unit_number = 0
    for dev in vmobj.config.hardware.device:
        if hasattr(dev.backing, 'fileName'):
            unit_number = int(dev.unitNumber) + 1
            # unit_number 7 reserved for scsi controller
            if unit_number == 7:
                unit_number += 1
            if unit_number >= 16:
                raise Exception("Too many disks")

        if isinstance(dev, vim.vm.device.VirtualSCSIController):
            controller = dev

    dev_changes = []
    size_kb = size_gb * 1024 * 1024
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.fileOperation = "create"
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.add
    disk_spec.device = vim.vm.device.VirtualDisk()
    disk_spec.device.backing = vim.vm.device.VirtualDisk.FlatVer2BackingInfo()
    if format == 'thin':
        disk_spec.device.backing.thinProvisioned = True

    disk_spec.device.backing.diskMode = 'persistent'
    disk_spec.device.unitNumber = unit_number
    disk_spec.device.capacityInKB = size_kb
    disk_spec.device.controllerKey = controller.key
    dev_changes.append(disk_spec)
    spec.deviceChange = dev_changes

    task = vmobj.ReconfigVM_Task(spec=spec)
    wait_for_tasks(service_instance, [task])

def delete_disk(service_instance, vmobj, diskobj):
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.remove
    disk_spec.device = diskobj

    spec = vim.vm.ConfigSpec()
    spec.deviceChange = [disk_spec]
    task = vmobj.ReconfigVM_Task(spec=spec)
    wait_for_tasks(service_instance, [task])

def resize_disk(service_instance, vmobj, diskobj, size_gb):
    disk_spec = vim.vm.device.VirtualDeviceSpec()
    disk_spec.operation = vim.vm.device.VirtualDeviceSpec.Operation.edit
    disk_spec.device = diskobj
    disk_spec.device.capacityInKB = size_gb * 1024 * 1024

    spec = vim.vm.ConfigSpec()
    spec.deviceChange = [disk_spec]
    task = vmobj.ReconfigVM_Task(spec=spec)
    wait_for_tasks(service_instance, [task])


def add_scsi_controller(service_instance, vm):
    task = vm.ReconfigVM_Task(
        spec=vim.vm.ConfigSpec(
            deviceChange=[
                vim.vm.device.VirtualDeviceSpec(
                    operation=vim.vm.device.VirtualDeviceSpec.Operation.add,
                    device=vim.vm.device.VirtualLsiLogicSASController(
                        sharedBus=vim.vm.device.VirtualSCSIController.Sharing.noSharing
                    ),
                )
            ]
        )
    )
    wait_for_tasks(service_instance, [task])

# The identity is a dictonary with keys IP, UUID and Inventory Path any one of them is enough.s
def find_vmobj(service_instance, identity):
    if not identity:
        raise Exception('IP, UUID, or Inventory path of the VM is required. ')

    vmobj = None

    if identity.get("ip", None):
        vmobj = service_instance.content.searchIndex.FindByIp(None, identity["ip"], True)
        if not vmobj:
            raise Exception("Could not find virtual machine with IP: ({})".format(identity["ip"]))
    elif identity.get("ipath", None):
        vmobj = service_instance.content.searchIndex.FindByInventoryPath(identity["ipath"])
        if not vmobj:
            raise Exception("Could not find virtual machine with inventory path: ({})".format(identity["ipath"]))

        assert isinstance(vmobj, vim.VirtualMachine)
    elif identity.get("uuid", None):
        uuid = identity["uuid"]
        vmobj = service_instance.content.searchIndex.FindByUuid(None, uuid, True)
        if not vmobj:
            raise Exception("Could not find virtual machine with UUID: ({})".format(uuid))
    else:
        raise Exception("Could not find virtual machine, ip or inventory path is not provided.")

    return vmobj