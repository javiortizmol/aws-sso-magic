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

import os
import sys
import logging
import botocore
import click

from collections import namedtuple
from aws_sso_lib.sso import get_token_fetcher
from aws_sso_lib.config_file_writer import ConfigFileWriter, write_values, get_config_filename
from botocore.session import Session
from botocore.exceptions import ProfileNotFound
from .eks   import _eks_cluster_configuration
from .utils import _create_credentials_profile, _read_aws_sso_config_file, process_profile_name_formatter 
from .utils import _check_aws_v2, _check_flag_combinations
from .utils import configure_logging, get_instance, GetInstanceError
from .utils import generate_profile_name_format, get_formatter, get_process_formatter
from .utils import get_trim_formatter, get_safe_account_name, get_config_profile_list
from .utils import _set_profile_credentials, _add_prefix, _set_profile_in_use
from .utils import (
    AWS_SSO_CONFIG_ALIAS,
    AWS_SSO_CONFIG_PATH,
    AWS_DEFAULT_REGION,
    AWS_SSO_PROFILE,
    VERBOSE
)

LOGGER = logging.getLogger(__name__)

DEFAULT_SEPARATOR = "."
UTC_TIME_FORMAT = "%Y-%m-%d %H:%M UTC"
LOCAL_TIME_FORMAT = "%Y-%m-%d %H:%M %Z"

CONFIGURE_DEFAULT_START_URL_VARS  = ["AWS_CONFIGURE_SSO_DEFAULT_SSO_START_URL", "AWS_SSO_CONFIGURE_DEFAULT_SSO_START_URL", "AWS_CONFIGURE_DEFAULT_SSO_START_URL"]
CONFIGURE_DEFAULT_SSO_REGION_VARS = ["AWS_CONFIGURE_SSO_DEFAULT_SSO_REGION",    "AWS_SSO_CONFIGURE_DEFAULT_SSO_REGION",    "AWS_CONFIGURE_DEFAULT_SSO_REGION"]
CONFIGURE_DEFAULT_REGION_VARS     = ["AWS_CONFIGURE_DEFAULT_REGION", "AWS_DEFAULT_REGION"]
LOGIN_DEFAULT_START_URL_VARS      = ["AWS_SSO_LOGIN_DEFAULT_SSO_START_URL"]
LOGIN_DEFAULT_SSO_REGION_VARS     = ["AWS_SSO_LOGIN_DEFAULT_SSO_REGION"]
LOGIN_ALL_VAR = "AWS_SSO_LOGIN_ALL"

ConfigParams = namedtuple("ConfigParams", ["profile_name", "account_name", "account_id", "role_name", "region"])

@click.command()
@click.option("--eks", is_flag=True, help="The flag to use for the update-kubeconfig")
@click.option("--profile", "profile_arg", help="The main profile name to use")
@click.option("--eks-profile", "eks_profile_arg", help="The eks profile name to use")
@click.option("--cluster", "cluster_arg", help="The eks cluster name to use, this argument is only allowed using the --eks flag")
@click.option("--sso-start-url", "-u", metavar="URL", help="Your AWS SSO start URL")
@click.option("--sso-region", help="The AWS region your AWS SSO instance is deployed in")
@click.option("--region", "-r", "regions", multiple=True, metavar="REGION", help="AWS region for the profiles, can provide multiple times")
@click.option("--dry-run", is_flag=True, help="Print the config to stdout instead of writing to your config file")
@click.option("--config-default", "-c", multiple=True, metavar="KEY=VALUE", help="Additional config field to set, can provide multiple times")
@click.option("--existing-config-action", type=click.Choice(["keep", "overwrite", "discard"]), default="keep", help="Action when config defaults conflict with existing settings")
@click.option("--components", "profile_name_components", metavar="VALUE,VALUE,...", default="account_name,role_name,default_style_region", help="Profile name components to join (comma-separated)")
@click.option("--separator", "--sep", "profile_name_separator", metavar="SEP", help=f"Separator for profile name components, default is '{DEFAULT_SEPARATOR}'")
@click.option("--include-region", "profile_name_include_region", type=click.Choice(["default", "always"]), default="default", help="By default, the first region is left off the profile name")
@click.option("--region-style", "profile_name_region_style", type=click.Choice(["short", "long"]), default="short", help="Default is five character region abbreviations")
@click.option("--trim-account-name", "profile_name_trim_account_name_patterns", multiple=True, default=[], help="Regex to remove from account names, can provide multiple times")
@click.option("--trim-role-name", "profile_name_trim_role_name_patterns", multiple=True, default=[], help="Regex to remove from role names, can provide multiple times")
@click.option("--profile-name-process")
@click.option("--safe-account-names/--raw-account-names", default=True, help="In profiles, replace any character sequences not in A-Za-z0-9-._ with a single -")
@click.option("--force-refresh", is_flag=True, help="Re-login")
@click.option("--verbose", "-v", count=True)

def login(
        eks,
        profile_arg,
        eks_profile_arg,
        cluster_arg,
        sso_start_url,
        sso_region,    
        regions,
        dry_run,
        config_default,
        existing_config_action,
        profile_name_components,
        profile_name_separator,
        profile_name_include_region,
        profile_name_region_style,
        profile_name_trim_account_name_patterns,
        profile_name_trim_role_name_patterns,
        profile_name_process,
        safe_account_names,
        force_refresh,
        verbose):
    """Log in to the AWS SSO instance.

    Note this only needs to be done once for a given SSO instance (i.e., start URL),
    as all profiles sharing the same start URL will share the same login.
    """
    configure_logging(LOGGER, verbose)
    _check_flag_combinations(eks, profile_arg, cluster_arg, eks_profile_arg)
    _check_aws_v2()

    missing = []

    try:
        instance = get_instance(
            sso_start_url,
            sso_region,
            sso_start_url_vars=CONFIGURE_DEFAULT_START_URL_VARS,
            sso_region_vars=CONFIGURE_DEFAULT_SSO_REGION_VARS,)
    except GetInstanceError as e:
        LOGGER.fatal(str(e))
        sys.exit(1)

    if not regions:
        for var_name in CONFIGURE_DEFAULT_REGION_VARS:
            value = os.environ.get(var_name)
            if value:
                LOGGER.debug(f"Got default region {value} from {var_name}")
                regions = [value]
                break
    if not regions:
        regions = [AWS_DEFAULT_REGION]
        LOGGER.info(f"Using the region default value {regions}")

    if missing:
        raise click.UsageError("Missing arguments: {}".format(", ".join(missing)))

    if config_default:
        config_default = dict(v.split("=", 1) for v in config_default)
    else:
        config_default = {}

    if not profile_name_separator:
        profile_name_separator = os.environ.get("AWS_CONFIGURE_SSO_DEFAULT_PROFILE_NAME_SEPARATOR") or DEFAULT_SEPARATOR

    if profile_name_process:
        profile_name_formatter = get_process_formatter(profile_name_process)
    else:
        region_format, no_region_format = generate_profile_name_format(profile_name_components, profile_name_separator, profile_name_region_style)
        LOGGER.debug("Profile name format (region):    {}".format(region_format))
        LOGGER.debug("Profile name format (no region): {}".format(no_region_format))
        profile_name_formatter = get_formatter(profile_name_include_region, region_format, no_region_format)
        if profile_name_trim_account_name_patterns or profile_name_trim_role_name_patterns:
            profile_name_formatter = get_trim_formatter(profile_name_trim_account_name_patterns, profile_name_trim_role_name_patterns, profile_name_formatter)

    try:
        profile_name_formatter(0, 1, account_name="foo", account_id="bar", role_name="baz", region="us-east-1")
    except Exception as e:
        raise click.UsageError("Invalid profile name format: {}".format(e))

    session = Session()

    token_fetcher = get_token_fetcher(session,
            instance.region,
            interactive=True,
            )

    LOGGER.info(f"Logging in to {instance.start_url}")
    token = token_fetcher.fetch_token(instance.start_url, force_refresh=force_refresh)

    LOGGER.debug("Token: {}".format(token))

    config = botocore.config.Config(
        region_name=instance.region,
        signature_version=botocore.UNSIGNED,
    )
    client = session.create_client("sso", config=config)

    LOGGER.info("Gathering accounts and roles")

    aws_sso_magic_conf = _read_aws_sso_config_file(AWS_SSO_CONFIG_PATH, AWS_SSO_CONFIG_ALIAS)
    res = bool(aws_sso_magic_conf)
    if res:
        LOGGER.info(f"Section: {AWS_SSO_CONFIG_ALIAS} found on the file {AWS_SSO_CONFIG_PATH}")
    else:
        LOGGER.info(f"No section: {AWS_SSO_CONFIG_ALIAS} found on the file {AWS_SSO_CONFIG_PATH}")        

    accounts = []
    list_accounts_args = {
        "accessToken": token["accessToken"]
    }
    while True:
        response = client.list_accounts(**list_accounts_args)

        accounts.extend(response["accountList"])

        next_token = response.get("nextToken")
        if not next_token:
            break
        else:
            list_accounts_args["nextToken"] = response["nextToken"]

    LOGGER.debug("Account list: {} {}".format(len(accounts), accounts))

    configs = []
    for account in accounts:
        if not account.get("accountName"):
            account["accountName"] = account["accountId"]

        LOGGER.debug("Getting roles for {}".format(account["accountId"]))
        list_role_args = {
            "accessToken": token["accessToken"],
            "accountId": account["accountId"],
        }

        num_regions = len(regions)
        while True:
            response = client.list_account_roles(**list_role_args)

            for role in response["roleList"]:
                for i, region in enumerate(regions):
                    if safe_account_names:
                        account_name_for_profile = get_safe_account_name(account["accountName"])
                    else:
                        account_name_for_profile = account["accountName"]

                    profile_name = profile_name_formatter(i, num_regions,
                        account_name=account_name_for_profile,
                        account_id=account["accountId"],
                        role_name=role["roleName"],
                        region=region,
                    )
                    profile_name = process_profile_name_formatter(profile_name)
                    if profile_name == "SKIP":
                        continue
                    configs.append(ConfigParams(profile_name, account["accountName"], account["accountId"], role["roleName"], region))

            next_token = response.get("nextToken")
            if not next_token:
                break
            else:
                list_role_args["nextToken"] = response["nextToken"]


    configs.sort(key=lambda v: v.profile_name)

    LOGGER.debug("Got configs: {}".format(configs))

    if not dry_run:
        LOGGER.info("Writing {} profiles to {}".format(len(configs), get_config_filename(session)))

        config_writer = ConfigFileWriter()
        def write_config(profile_name, config_values):
            # discard because we're already loading the existing values
            write_values(session, profile_name, config_values, existing_config_action="discard", config_file_writer=config_writer)
    else:
        LOGGER.info("Dry run for {} profiles".format(len(configs)))
        def write_config(profile_name, config_values):
            lines = [
                "[profile {}]".format(process_profile_name_formatter(profile_name))
            ]
            for key, value in config_values.items():
                lines.append("{} = {}".format(key, value))
            lines.append("")
            print("\n".join(lines))

    for config in configs:
        LOGGER.debug("Processing config: {}".format(config))
        config_values = {}
        existing_profile = False
        existing_config = {}
        if existing_config_action != "discard":
            try:
                existing_config = Session(profile=config.profile_name).get_scoped_config()
                config_values.update(existing_config)
                existing_profile = True
            except ProfileNotFound:
                pass

        config_values.update({
            "sso_start_url": instance.start_url,
            "sso_region": instance.region,
        })
        if config.account_name != config.account_id:
            config_values["sso_account_name"] = config.account_name
        config_values.update({
            "sso_account_id": config.account_id,
            "sso_role_name": config.role_name,
            "region": config.region,
        })
        for k, v in config_default.items():
            if k in existing_config and existing_config_action in ["keep"]:
                continue
            config_values[k] = v
        LOGGER.debug("Config values for profile {}: {}".format(config.profile_name, config_values))
        write_config(config.profile_name, config_values)

    global VERBOSE

    default_profile = 'default'

    _create_credentials_profile(configs)

    if not eks:
        if profile_arg == None:
            profile = _add_prefix(get_config_profile_list())
        else:
            profile = _add_prefix(profile_arg)
        _set_profile_credentials(profile, default_profile)
        _set_profile_in_use(profile)
    else:
        _eks_cluster_configuration(cluster_arg, eks_profile_arg)

if __name__ == "__main__":
    login(prog_name="python -m aws_sso_magic.login")  #pylint: disable=unexpected-keyword-arg,no-value-for-parameter
