#!/usr/bin/env python
#-*- mode: Python;-*-

import atexit
import json
import logging
import os
import sys
import tempfile
import traceback

import click

from vmwarelib.cli import util
from vmwarelib.sdk import core

cmd_folder = os.path.abspath(os.path.join(os.path.dirname(__file__), 'commands'))

class MyCLI(click.MultiCommand):
    def list_commands(self, ctx):
        rv = []
        for filename in os.listdir(cmd_folder):
            if filename.endswith('.py') and filename.startswith('cmd_'):
                rv.append(filename[4:-3])
        rv.sort()
        return rv

    def get_command(self, ctx, name):
        try:
            if sys.version_info[0] == 2:
                name = name.encode('ascii', 'replace')

            mod = __import__('vmwarelib.cli.commands.cmd_' + name, None, None, ['cli'])
        except ImportError:
            logging.error(traceback.format_exc())
            return

        return mod.cli

@click.command(cls=MyCLI)
@click.version_option('0.42')
@click.option('--host', envvar="VMWARECLI_HOST", help='vSphere server or ESX. ')
@click.option('--username', envvar="VMWARECLI_USERNAME", help='User name.')
@click.option('--password', envvar="VMWARECLI_PASSWORD", help='Password.')
@click.option('-k', is_flag=True, help='When set, certificate warnings are ignored. ')
@util.pass_context
def cli(ctx, host, username, password, k=False):
    """vmwarecli is a command line tool for vSphere.
    """

    if not host or not username or not password:
        raise Exception("host, user name, and password are required. ")

    # Login and store session instance.
    ctx.server = core.Server(host, username, password, ignore_cert_warnings=k)

    atexit.register(ctx.server.cleanup)

def init_logging():
    fd, logfile = tempfile.mkstemp(suffix='.txt', prefix='vmwarecli')
    os.close(fd)
    logging.basicConfig(filename=logfile, level=logging.DEBUG, format='%(asctime)-15s: %(levelname)s: %(message)s')

def main():
    init_logging()

    try:
        cli()
    except Exception as e:
        logging.error(traceback.format_exc())

        exctype, value = sys.exc_info()[:2]
        click.secho(traceback.format_exception_only(exctype, value)[0], fg='red')
