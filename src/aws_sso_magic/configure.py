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

from .utils import _check_aws_v2, configure_logging
from .utils import (
    AWS_CONFIG_PATH
)

LOGGER = logging.getLogger(__name__)

@click.command("configure")

def configure():
    """Configure the AWS SSO instance.

    Note this only needs to be done once for a given SSO instance (i.e., start URL),
    as all profiles sharing the same start URL will share the same login.
    """    
    configure_logging(LOGGER, False)
    _check_aws_v2()
    
    try:
        subprocess.run(['aws'] + [ 'configure', 'sso'], stderr=sys.stderr, stdout=sys.stdout, check=True)
        LOGGER.info("aws configure sso command executed successfully")
    except subprocess.CalledProcessError as e:
        LOGGER.error("Unexpected error on the configure command")
        exit(1)
    
    LOGGER.info("Done!, please check the aws cli config on {}".format(AWS_CONFIG_PATH))

if __name__ == "__main__":
    configure(prog_name="python -m aws_sso_magic.configure") 