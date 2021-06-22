# Copyright 2020 Javier Ortiz
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

import subprocess
import logging
import click
import sys

from .utils import _check_aws_v2, configure_logging, _read_config, _write_config
from .utils import (
    AWS_CREDENTIAL_PATH
)

LOGGER = logging.getLogger(__name__)


def _default_profile_exists(config):
    if config.has_section('default'):
        config.remove_section('default')
        return True
    return False

@click.command("logout")

def logout():
    """Log out of the AWS SSO instance.

    Note this only needs to be done once for a given SSO instance (i.e., start URL),
    as all profiles sharing the same start URL will share the same login.
    """    
    configure_logging(LOGGER, False)
    _check_aws_v2()
    
    try:
        subprocess.run(['aws'] + [ 'sso', 'logout'], stderr=sys.stderr, stdout=sys.stdout, check=True)
        LOGGER.info("aws sso logout command executed successfully")
    except subprocess.CalledProcessError as e:
        LOGGER.error("Unexpected error on the logout command")
        exit(1)

    config = _read_config(AWS_CREDENTIAL_PATH)

    if _default_profile_exists(config):
        _write_config(AWS_CREDENTIAL_PATH, config)
        LOGGER.info("default profile credentials deleted")
    else:
        LOGGER.info("Nothing to do, default profile credentials not found")
    
    LOGGER.info("Done!, please use the aws-sso-magic login command to come back again")

if __name__ == "__main__":
    logout(prog_name="python -m aws_sso_magic.logout") 