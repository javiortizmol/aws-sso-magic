import hashlib
import json
import re
import os
import subprocess
import sys
import logging
import boto3
import botocore
import click

from collections import namedtuple
from configparser import ConfigParser
from datetime import datetime, timedelta
from pathlib import Path
from dateutil.parser import parse
from dateutil.tz import UTC, tzlocal
from dateutil.parser import parse
from dateutil.tz import tzlocal
from aws_sso_lib.compat import shell_join
from aws_sso_lib.sso import get_token_fetcher
from aws_sso_lib.config_file_writer import ConfigFileWriter, write_values, get_config_filename, process_profile_name
from botocore.session import Session
from botocore.exceptions import ProfileNotFound
from botocore.compat import compat_shell_split as shell_split
from .utils import configure_logging, get_instance, GetInstanceError

LOGGER = logging.getLogger(__name__)

DEFAULT_SEPARATOR = "."
UTC_TIME_FORMAT = "%Y-%m-%d %H:%M UTC"
LOCAL_TIME_FORMAT = "%Y-%m-%d %H:%M %Z"
VERBOSE_MODE = True

CONFIGURE_DEFAULT_START_URL_VARS  = ["AWS_CONFIGURE_SSO_DEFAULT_SSO_START_URL", "AWS_SSO_CONFIGURE_DEFAULT_SSO_START_URL", "AWS_CONFIGURE_DEFAULT_SSO_START_URL"]
CONFIGURE_DEFAULT_SSO_REGION_VARS = ["AWS_CONFIGURE_SSO_DEFAULT_SSO_REGION",    "AWS_SSO_CONFIGURE_DEFAULT_SSO_REGION",    "AWS_CONFIGURE_DEFAULT_SSO_REGION"]
CONFIGURE_DEFAULT_REGION_VARS     = ["AWS_CONFIGURE_DEFAULT_REGION", "AWS_DEFAULT_REGION"]
LOGIN_DEFAULT_START_URL_VARS      = ["AWS_SSO_LOGIN_DEFAULT_SSO_START_URL"]
LOGIN_DEFAULT_SSO_REGION_VARS     = ["AWS_SSO_LOGIN_DEFAULT_SSO_REGION"]
LOGIN_ALL_VAR = "AWS_SSO_LOGIN_ALL"
KNOWN_COMPONENTS = [
    "account_name",
    "account_id",
    "account_number",
    "role_name",
    "region",
    "short_region",
]
PROCESS_FORMATTER_ARGS = [
    "account_name",
    "account_id",
    "role_name",
    "region",
    "short_region",
    "region_index",
    "num_regions",
]

AWS_CONFIG_PATH = f'{Path.home()}/.aws/config'
AWS_CREDENTIAL_PATH = f'{Path.home()}/.aws/credentials'
AWS_SSO_CACHE_PATH = f'{Path.home()}/.aws/sso/cache'
AWS_DEFAULT_REGION = 'us-east-1'

ConfigParams = namedtuple("ConfigParams", ["profile_name", "account_name", "account_id", "role_name", "region"])

class Colour:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def get_short_region(region):
    area, direction, num = region.split("-")
    dir_abbr = {
        "north": "no",
        "northeast": "ne",
        "east": "ea",
        "southeast": "se",
        "south": "so",
        "southwest": "sw",
        "west": "we",
        "northwest": "nw",
        "central": "ce",
    }
    return "".join([area, dir_abbr.get(direction, direction), num])

def generate_profile_name_format(input, separator, region_style):
    def process_component(c):
        if c == "default_style_region":
            if region_style == "short":
                c = "short_region"
            else:
                c = "region"
        if c in KNOWN_COMPONENTS:
            return "{" + c + "}"
        else:
            return c
    region_format = separator.join(process_component(c) for c in input.split(","))
    no_region_format = separator.join(process_component(c) for c in input.split(",") if c not in ["default_style_region", "region", "short_region"])
    return region_format, no_region_format

def get_formatter(include_region, region_format, no_region_format):
    def proc_kwargs(kwargs):
        kwargs["short_region"] = get_short_region(kwargs["region"])
        kwargs["account_number"] = kwargs["account_id"]
        return kwargs
    if include_region == "default":
        def formatter(i, n, **kwargs):
            kwargs = proc_kwargs(kwargs)
            if i == 0:
                return no_region_format.format(**kwargs)
            else:
                return region_format.format(**kwargs)
        return formatter
    elif include_region == "always":
        def formatter(i, n, **kwargs):
            kwargs = proc_kwargs(kwargs)
            return region_format.format(**kwargs)
        return formatter
    else:
        raise ValueError("Unknown include_region value {}".format(include_region))

def get_process_formatter(command):
    def formatter(i, n, **kwargs):
        kwargs["region_index"] = str(i)
        kwargs["num_regions"] = str(n)
        kwargs["short_region"] = get_short_region(kwargs["region"])
        run_args = shell_split(command)
        for component in PROCESS_FORMATTER_ARGS:
            run_args.append(kwargs[component])
        try:
            result = subprocess.run(shell_join(run_args), shell=True, stdout=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            lines = [
                "Profile name process failed ({})".format(e.returncode)
            ]
            if e.stdout:
                lines.append(e.stdout.decode("utf-8"))
            if e.stderr:
                lines.append(e.stderr.decode("utf-8"))
            LOGGER.error("\n".join(lines))
            raise e
        return result.stdout.decode("utf-8").strip()
    return formatter

def get_trim_formatter(account_name_patterns, role_name_patterns, formatter):
    def trim_formatter(i, n, **kwargs):
        for pattern in account_name_patterns:
            kwargs["account_name"] = re.sub(pattern, "", kwargs["account_name"])
        for pattern in role_name_patterns:
            kwargs["role_name"] = re.sub(pattern, "", kwargs["role_name"])
        return formatter(i, n, **kwargs)
    return trim_formatter

def get_safe_account_name(name):
    return re.sub(r"[\s\[\]]+", "-", name).strip("-")

def get_config_profile_list(configs):
    print(" ")
    print("*****************************************")
    print("*******  AWS CLI CONFIG PROFILES  *******" )
    print("*****************************************")
    print(" ")
    print("Option - Profile ")
    for c in configs:
        conf_number = configs.index(c) + 1
        LOGGER.info("   {}   - {}".format(conf_number, c.profile_name))
    print(" ")
    print("*****************************************")
    print(" ")
    config_option = int(input('Enter the config profile option: '))
    config_option = config_option - 1
    try:
        config_profile = configs[config_option].profile_name
    except IndexError as e:
        raise click.UsageError("Option selected not valid")
    return config_profile

def _set_profile_credentials(profile_name, use_default=False):
    profile_opts = _get_aws_profile(profile_name)
    cache_login = _get_sso_cached_login(profile_opts)
    credentials = _get_sso_role_credentials(profile_opts, cache_login)

    if not use_default:
        _store_aws_credentials(profile_name, profile_opts, credentials)
    else:
        _store_aws_credentials('default', profile_opts, credentials)
        _copy_to_default_profile(profile_name)

def _copy_to_default_profile(profile_name):
    _print_msg(f'Copying profile [{profile_name}] to [default]')

    config = _read_config(AWS_CONFIG_PATH)

    if config.has_section('default'):
        config.remove_section('default')

    config.add_section('default')

    for key, value in config.items(profile_name):
        config.set('default', key, value)

    _write_config(AWS_CONFIG_PATH, config)

def _get_aws_profile(profile_name):
    _print_msg(f'\nReading profile: [{profile_name}]')
    config = _read_config(AWS_CONFIG_PATH)
    profile_opts = config.items(profile_name)
    profile = dict(profile_opts)
    return profile

def _get_sso_cached_login(profile):
    _print_msg('\nChecking for SSO credentials...')

    cache = hashlib.sha1(profile["sso_start_url"].encode("utf-8")).hexdigest()
    sso_cache_file = f'{AWS_SSO_CACHE_PATH}/{cache}.json'

    if not Path(sso_cache_file).is_file():
        _print_error(
            'Current cached SSO login is invalid/missing. Login with the AWS CLI tool or use --login')

    else:
        data = _load_json(sso_cache_file)
        now = datetime.now().astimezone(UTC)
        expires_at = parse(data['expiresAt']).astimezone(UTC)

        if data.get('region') != profile['sso_region']:
            _print_error(
                'SSO authentication region in cache does not match region defined in profile')

        if now > expires_at:
            _print_error(
                'SSO credentials have expired. Please re-validate with the AWS CLI tool or --login option.')

        if (now + timedelta(minutes=15)) >= expires_at:
            _print_warn('Your current SSO credentials will expire in less than 15 minutes!')

        _print_success(f'Found credentials. Valid until {expires_at.astimezone(tzlocal())}')
        return data

def _get_sso_role_credentials(profile, login):
    _print_msg('\nFetching short-term CLI/Boto3 session token...')
    client = boto3.client('sso', region_name=profile['sso_region'])
    response = client.get_role_credentials(
        roleName=profile['sso_role_name'],
        accountId=profile['sso_account_id'],
        accessToken=login['accessToken'],
    )
    expires = datetime.utcfromtimestamp(response['roleCredentials']['expiration'] / 1000.0).astimezone(UTC)
    _print_success(f'Got session token. Valid until {expires.astimezone(tzlocal())}')
    return response["roleCredentials"]

def _store_aws_credentials(profile_name, profile_opts, credentials):
    _print_msg(f'\nAdding to credential files under [{profile_name}]')
    region = profile_opts.get("region", AWS_DEFAULT_REGION)
    config = _read_config(AWS_CREDENTIAL_PATH)
    if config.has_section(profile_name):
        config.remove_section(profile_name)

    config.add_section(profile_name)
    config.set(profile_name, "region", region)
    config.set(profile_name, "aws_access_key_id", credentials["accessKeyId"])
    config.set(profile_name, "aws_secret_access_key ", credentials["secretAccessKey"])
    config.set(profile_name, "aws_session_token", credentials["sessionToken"])
    _write_config(AWS_CREDENTIAL_PATH, config)

def _write_config(path, config):
    with open(path, "w") as destination:
        config.write(destination)    

def _read_config(path):
    config = ConfigParser()
    config.read(path)
    return config

def _add_prefix(name):
    return f'profile {name}' if name != 'default' else 'default'

def _load_json(path):
    try:
        with open(path) as context:
            return json.load(context)
    except ValueError:
        pass  # skip invalid json    

def _print_colour(colour, message, always=False):
    if always or VERBOSE_MODE:
        if os.environ.get('CLI_NO_COLOR', False):
            print(message)
        else:
            print(''.join([colour, message, Colour.ENDC]))    

def _print_msg(message):
    _print_colour(Colour.OKBLUE, message)

def _print_warn(message):
    _print_colour(Colour.WARNING, message, always=True) 

def _print_error(message):
    _print_colour(Colour.FAIL, message, always=True)
    sys.exit(1)

def _print_success(message):
    _print_colour(Colour.OKGREEN, message)    

@click.command("login")
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
    """Log in to an AWS SSO instance.

    Note this only needs to be done once for a given SSO instance (i.e., start URL),
    as all profiles sharing the same start URL will share the same login.
    """
    configure_logging(LOGGER, verbose)

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
                "[profile {}]".format(process_profile_name(profile_name))
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

    profile = _add_prefix(get_config_profile_list(configs))

    LOGGER.info(f"AWS config profile option selected: {profile}")

    global VERBOSE_MODE

    _set_profile_credentials(profile, True)


if __name__ == "__main__":
    login(prog_name="python -m aws_sso_magic.login")  #pylint: disable=unexpected-keyword-arg,no-value-for-parameter
