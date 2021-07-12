
import sys
import boto3
import botocore
import subprocess
import logging
import logging.handlers
import os

from PyInquirer import prompt, Separator
from .utils import _check_kubectl, _print_warn
from .utils import _get_role_name, _print_error, _get_profile_in_use

LOGGER = logging.getLogger(__name__)

def list_clusters(profile_in_use, max_clusters=10, iter_marker=''):
    os.environ["AWS_PROFILE"] = profile_in_use
    eks = boto3.client('eks')
    try:
        clusters = eks.list_clusters(maxResults=max_clusters, nextToken=iter_marker)
        marker = clusters.get('nextToken')       # None if no more clusters to retrieve
        return clusters['clusters'], marker
    except botocore.exceptions.ClientError as e:
        _print_error("Unset the AWS_PROFILE environment variable or close this terminal and open a new one\n")

def _eks_list_clusters(profile_in_use):
    clusters, marker = list_clusters(profile_in_use)
    if not clusters:
        _print_error(f"\nNo clusters exist. Run the aws-sso-magic login and select a valid profile")
    else:
        while True:
            # Print cluster names
            # If no more clusters exist, exit loop, otherwise retrieve the next batch
            if marker is None:
                break
            clusters, marker = list_clusters(profile_in_use, iter_marker=marker)
    questions = [{
        'type': 'list',
        'name': 'name',
        'message': 'Please select the EKS cluster',
        'choices': clusters
    }]            
    answer = prompt(questions)
    return answer['name'] if answer else sys.exit(1)

def _eks_update_kubeconfig(cluster_name, profile_in_use):
    os.environ["AWS_PROFILE"] = profile_in_use
    try:
        subprocess.run(['aws'] + ['eks'] + ['update-kubeconfig'] + ['--name'] + [cluster_name], stderr=sys.stderr, stdout=sys.stdout, check=True)
        LOGGER.info("kubeconfig updated successfully")
    except subprocess.CalledProcessError as e:
        LOGGER.error("Unexpected error on the logout command")
        exit(1)    

def _eks_print_instructions(profile_name):
    _print_warn("\nUse any of the following options to access eks resources programmatically or from kubectl")
    _print_warn("Copy and paste the commands according to your OS. ")
    _print_warn("\nLinux/macOS:")
    _print_warn(f"export AWS_PROFILE={profile_name}")
    _print_warn("aws sts get-caller-identity\n")    
    _print_warn("\nWindows:")
    _print_warn(f"SET AWS_PROFILE={profile_name}")
    _print_warn("aws sts get-caller-identity\n")    
    _print_warn("\nPowerShell:")
    _print_warn(f"$Env:AWS_PROFILE={profile_name}")
    _print_warn("aws sts get-caller-identity\n")
    _print_warn("\nNOTE: If you will select another profile, please first unset the AWS_PROFILE environment variable or close this terminal and open a new one\n")

def _eks_cluster_configuration(cluster_arg, eks_profile_arg):
    _check_kubectl()
    profile_in_use = eks_profile_arg
    cluster_name = cluster_arg
    if eks_profile_arg == None:
        profile_in_use = _get_profile_in_use()
    _get_role_name(profile_in_use, "eks")
    if cluster_arg == None:
        cluster_name = _eks_list_clusters(profile_in_use)
    _eks_update_kubeconfig(cluster_name, profile_in_use)
    _eks_print_instructions(profile_in_use)    


