
import click

class Context(object):
    def __init__(self):
        self.host = ""
        self.username = ""

pass_context = click.make_pass_decorator(Context, ensure=True)

