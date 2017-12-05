
==========
VMware Lib
==========

This project aims to a build a library that facilitates operations on
VMware entities such as Virtual machines and Datastores. The project 
includes two distinct components.

sdk
    Provides classes that can be directly used in your code.

cli
    Provides command line operations. 

Installation
============

For now, directly install into a local virtual env:
::

    # clone the project and change into the directory.
    $ git clone https://github.com/draghuram/vmwarelib
    $ cd vmwarelib

    # Create a virtual environment
    $ python3 -m venv $HOME/vmwarelib

    # Install the library
    $ $HOME/vmwarelib/bin/pip install -e .

    $ export PATH=$PATH:$HOME/vmwarelib/bin

At this point, the library can be used.

Usage
=====

You need to provide vCenter host as well credentials for all the
commands. This information can either be provided every time using
command line options or can be provided once using environment
variables:
::

    $ export VMWARECLI_HOST=1.2.3.4
    $ export VMWARECLI_USERNAME=testuser
    $ export VMWARECLI_PASSWORD=testpass

Now, we can run various commands. Note that if vCenter requires https
connection and if it is using self signed certificate, pass "-k"
option to all the commands.

To get help:
::

    $ vmwarecli --help

To find information about a VM:
::

    $ vmwarecli vm --ip <VM_IP> info
    $ vmwarecli vm --ip <INVENTORY_PATH> info

A VM can be identified by either IP or its inventory path.

To manage snapshots:
::

    $ vmwarecli vm --ip <VM_IP> list_snapshots
    $ vmwarecli vm --ip <VM_IP> create_snapshot <SNAPNAME>
    $ vmwarecli vm --ip <VM_IP> delete_snapshot <SNAPNAME>
    $ vmwarecli vm --ip <VM_IP> delete_all_snapshots

There are various other commands available with the library and they
will be documented later.
