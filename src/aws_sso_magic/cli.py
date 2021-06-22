# Copyright 2020 Ben Kehoe
#
# Licensed under the Apache License, Version 2.0 (the "License"). You
# may not use this file except in compliance with the License. A copy of
# the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF
# ANY KIND, either express or implied. See the License for the specific
# language governing permissions and limitations under the License.

import click

from . import __version__

from .configure import configure
from .login import login
from .logout import logout

@click.group(name="aws-sso-magic")
@click.version_option(version=__version__, message='%(version)s')

def cli():
    pass

# @cli.group()
# def login():
#     """Commands to log-in on aws sso."""
#     pass

# menu options
cli.add_command(configure)
cli.add_command(login)
cli.add_command(logout)

_list_commands = cli.list_commands
def list_commands(ctx):
    return [c for c in _list_commands(ctx) if c != "credential-process"]

cli.list_commands = list_commands

