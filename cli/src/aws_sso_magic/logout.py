
import subprocess
import logging
import click
import sys

from configparser import ConfigParser
from pathlib import Path
from .utils import configure_logging

LOGGER = logging.getLogger(__name__)

AWS_CONFIG_PATH = f'{Path.home()}/.aws/config'
AWS_CREDENTIAL_PATH = f'{Path.home()}/.aws/credentials'

def _default_profile_exists(config):
    if config.has_section('default'):
        config.remove_section('default')
        return True
    return False

def _read_config(path):
    config = ConfigParser()
    config.read(path)
    return config

def _write_config(path, config):
    with open(path, "w") as destination:
        config.write(destination)   

@click.command("logout")

def logout():
    """Log out of an AWS SSO instance.

    Note this only needs to be done once for a given SSO instance (i.e., start URL),
    as all profiles sharing the same start URL will share the same login.
    """    
    configure_logging(LOGGER, True)

    cmd = ['aws']
    
    try:
        subprocess.run(cmd + [ 'sso', 'logout'], stderr=sys.stderr, stdout=sys.stdout, check=True)
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
    logout(prog_name="python -m aws_sso_magic.logout")  #pylint: disable=unexpected-keyword-arg,no-value-for-parameter