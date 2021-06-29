import os
import sys
import boto3
import hashlib
import json
import logging
import logging.handlers

from .utils import configure_logging, _get_profile_name, _create_profilename_child_credentials, _read_aws_sso_config_file, _print_error
from .utils import (
    AWS_SSO_PROFILE,
    AWS_SSO_EKS_CONFIG_PATH,
    VERBOSE
)

LOGGER = logging.getLogger(__name__)


def _get_role_name(profile_name):
    configure_logging(LOGGER, False)
    role_name = ""
    section = "default-proxy-role-name"
    role_name_key="proxy_role_name"
    config_profile = _read_aws_sso_config_file(AWS_SSO_EKS_CONFIG_PATH, profile_name)
    config_proxy_role_default = _read_aws_sso_config_file(AWS_SSO_EKS_CONFIG_PATH, section)
    res = bool(config_profile)
    result = bool(config_proxy_role_default)
    
    if res:
        config = config_profile
        section = profile_name
    else:
        if result:
            config = config_proxy_role_default
        else:
            _print_error(f"\nERROR: EKS login error! please in the [{section}] section, configure the {role_name_key} key on the file {AWS_SSO_EKS_CONFIG_PATH}")

    key_list = list(config.keys())
    val_list = list(config.values())

    if not role_name_key in key_list :
       _print_error(f"\nERROR: EKS login error! please in the [{section}] section, configure the {role_name_key} key on the file {AWS_SSO_EKS_CONFIG_PATH}")
    else:
        role_position = key_list.index(role_name_key)
        role_name = val_list[role_position]            

    return role_name

def _eks(profile_name, parent_profile):
    profile_name = _get_profile_name(profile_name)
    role_name = _get_role_name(profile_name)
    _create_profilename_child_credentials(parent_profile, profile_name, role_name)

if __name__ == "__main__":
    _eks(prog_name="python -m aws_sso_magic.eks")  #pylint: disable=unexpected-keyword-arg,no-value-for-parameter    