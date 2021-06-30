
import sys
import boto3
import subprocess
import inquirer
import logging
import logging.handlers

from .utils import _check_kubectl, configure_logging, _get_profile_name, _create_profilename_child_credentials
from .utils import _read_aws_sso_config_file, _print_error, _get_profile_in_use
from .utils import (
    AWS_SSO_EKS_CONFIG_PATH,
    VERBOSE
)

LOGGER = logging.getLogger(__name__)

def list_clusters(max_clusters=10, iter_marker=''):
    eks = boto3.client('eks')
    clusters = eks.list_clusters(maxResults=max_clusters, nextToken=iter_marker)
    marker = clusters.get('nextToken')       # None if no more clusters to retrieve
    return clusters['clusters'], marker


def _eks_list_clusters():
    clusters, marker = list_clusters()
    if not clusters:
        _print_error(f"\nNo clusters exist. Run the aws-sso-magic login and select a valid profile")
    else:
        while True:
            # Print cluster names
            # If no more clusters exist, exit loop, otherwise retrieve the next batch
            if marker is None:
                break
            clusters, marker = list_clusters(iter_marker=marker)    
    questions = [
        inquirer.List(
            'name',
            message='Please select the EKS cluster',
            choices=clusters
        ),
    ]
    answer = inquirer.prompt(questions)
    return answer['name'] if answer else sys.exit(1)

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

def _eks_profile_credentials(profile_name, parent_profile):
    profile_name = _get_profile_name(profile_name)
    role_name = _get_role_name(profile_name)
    _create_profilename_child_credentials(parent_profile, profile_name, role_name)

def _eks_update_kubeconfig(cluster_name):
    try:
        subprocess.run(['aws'] + ['eks'] + ['update-kubeconfig'] + ['--name'] + [cluster_name], stderr=sys.stderr, stdout=sys.stdout, check=True)
        LOGGER.info("kubeconfig updated successfully")
    except subprocess.CalledProcessError as e:
        LOGGER.error("Unexpected error on the logout command")
        exit(1)    

def _eks_print_instructions(profile_name):
    print("\nUse any of the following options to access eks resources programmatically or from kubectl. ")
    print("\nLinux/macOS:")
    print(f"export AWS_PROFILE={profile_name}")
    print("aws sts get-caller-identity\n")    
    print("\nWindows:")
    print(f"SET AWS_PROFILE={profile_name}")
    print("aws sts get-caller-identity\n")    
    print("\nPowerShell:")
    print(f"$Env:AWS_PROFILE={profile_name}")
    print("aws sts get-caller-identity\n")
    print("\nNOTE: If you will select another profile, please first unset the AWS_PROFILE environment variable or close this terminal and open a new one")

def _eks_cluster_configuration():
    _check_kubectl()
    cluster_name = _eks_list_clusters()
    _eks_update_kubeconfig(cluster_name)
    profile_in_use = _get_profile_in_use()    
    _eks_print_instructions(profile_in_use)

