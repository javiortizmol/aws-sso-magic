
import subprocess
import logging
import click

LOGGER = logging.getLogger(__name__)

@click.command("logout")

def logout():
    """Log out of an AWS SSO instance.

    Note this only needs to be done once for a given SSO instance (i.e., start URL),
    as all profiles sharing the same start URL will share the same login.
    """    
    cmd = ['aws']
    try:
        subprocess.run(cmd + [ 'sso', 'logout'], capture_output=True)
    except subprocess.CalledProcessError as e:
        LOGGER.error("Unexpected error on the logout command")

    LOGGER.info("Logout command executed")

if __name__ == "__main__":
    logout(prog_name="python -m aws_sso_magic.logout")  #pylint: disable=unexpected-keyword-arg,no-value-for-parameter