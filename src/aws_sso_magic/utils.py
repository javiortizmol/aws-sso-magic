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

import boto3
import hashlib
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys

from prettytable import PrettyTable
from datetime import datetime, timedelta
from pathlib import Path
from configparser import ConfigParser
from dateutil.tz import UTC, tzlocal
from dateutil.parser import parse
from aws_sso_lib.compat import shell_join
from aws_sso_lib.config import find_instances, SSOInstance
from botocore.compat import compat_shell_split as shell_split

AWS_CONFIG_PATH = f'{Path.home()}/.aws/config'
AWS_CREDENTIAL_PATH = f'{Path.home()}/.aws/credentials'
AWS_SSO_CACHE_PATH = f'{Path.home()}/.aws/sso/cache'
AWS_DEFAULT_REGION = 'us-east-1'
VERBOSE = True

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

LOGGER = logging.getLogger(__name__)

def configure_logging(logger, verbose, **config_args):
    if verbose in [False, None]:
        verbose = 0
    elif verbose == True:
        verbose = 1

    logging.basicConfig(**config_args)

    aws_sso_magic_logger = logging.getLogger("aws_sso_magic")
    aws_sso_lib_logger = logging.getLogger("aws_sso_lib")
    root_logger = logging.getLogger()

    if verbose == 0:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
        logger.setLevel(logging.INFO)
    elif verbose == 1:
        logger.setLevel(logging.DEBUG)
        aws_sso_magic_logger.setLevel(logging.INFO)
        aws_sso_lib_logger.setLevel(logging.INFO)
    elif verbose == 2:
        logger.setLevel(logging.DEBUG)
        aws_sso_magic_logger.setLevel(logging.DEBUG)
        aws_sso_lib_logger.setLevel(logging.INFO)
        root_logger.setLevel(logging.INFO)
    elif verbose == 3:
        logger.setLevel(logging.DEBUG)
        aws_sso_magic_logger.setLevel(logging.DEBUG)
        aws_sso_lib_logger.setLevel(logging.DEBUG)
        root_logger.setLevel(logging.INFO)
    elif verbose >= 4:
        logger.setLevel(logging.DEBUG)
        aws_sso_magic_logger.setLevel(logging.DEBUG)
        aws_sso_lib_logger.setLevel(logging.DEBUG)
        root_logger.setLevel(logging.DEBUG)

class GetInstanceError(Exception):
    pass

def get_instance(sso_start_url, sso_region, sso_start_url_vars=None, sso_region_vars=None):
    instances, specifier, all_instances = find_instances(
        profile_name=None,
        profile_source=None,
        start_url=sso_start_url,
        start_url_source="CLI input",
        region=sso_region,
        region_source="CLI input",
        start_url_vars=sso_start_url_vars,
        region_vars=sso_region_vars
    )

    if not instances:
        if all_instances:
            raise GetInstanceError(
                f"No AWS SSO instance matched {specifier.to_str(region=True)} " +
                f"from {SSOInstance.to_strs(all_instances)}")
        else:
            raise GetInstanceError("No AWS SSO instance found")

    if len(instances) > 1:
        raise GetInstanceError(f"Found {len(instances)} SSO instance, please specify one: {SSOInstance.to_strs(instances)}")

    return instances[0]

class Printer:
    def __init__(self, *,
            separator,
            default_separator,
            header_fields,
            disable_header=False,
            skip_repeated_values=False,
            sort_key=None,
            printer=None):
        self.separator = separator
        self.default_separator = default_separator
        self._sep = separator if separator is not None else default_separator
        self._header_sep = separator if separator is not None else " " * len(default_separator)
        self._justify = separator is None

        self.sort_key = sort_key

        self.header_fields = header_fields
        self.disable_header = disable_header

        self.skip_repeated_values = skip_repeated_values

        self.print_along = self.separator and not self.sort_key
        self.rows = [] if not self.print_along else None

        self.printer = printer or print

    def print_header_before(self):
        if self.print_along and not self.disable_header:
            self.printer(self._header_sep.join(self.header_fields))

    def add_row(self, row):
        if self.print_along:
            self.printer(self._sep.join(row))
        else:
            self.rows.append(row)

    def _process_row_skip(self, row, prev_row):
        if self.skip_repeated_values is True:
            proc = lambda v, pv: "" if v == pv else v
            return [proc(v, pv) for v, pv in zip(row, prev_row)]
        else:
            proc = lambda s, v, pv: "" if s and v == pv else v
            return [proc(s, v, pv) for s, v, pv in zip(self.skip_repeated_values, row, prev_row)]

    def print_after(self):
        if self.print_along:
            return
        if self.sort_key:
            self.rows.sort(key=self.sort_key)

        if self.disable_header:
            col_widths = [0 for _ in self.header_fields]
        else:
            col_widths = [len(h) for h in self.header_fields]

        for row in self.rows:
            col_widths = [max(cw, len(v)) for cw, v in zip(col_widths, row)]

        def just(row):
            if not self._justify:
                return row
            else:
                return [v.ljust(cw) for cw, v in zip(col_widths, row)]

        if not self.disable_header:
            self.printer(self._header_sep.join(just(self.header_fields)))

        first_loop = True
        prev_row = None
        for row in self.rows:
            if not first_loop and self.skip_repeated_values:
                row_to_print = self._process_row_skip(row, prev_row)
            else:
                row_to_print = row

            self.printer(self._sep.join(just(row_to_print)))

            prev_row = row
            first_loop = False

# Check Utils
def _check_aws_v2():
    # validate aws v2
    try:
        aws_version = subprocess.run(['aws']+ ['--version'], capture_output=True).stdout.decode('utf-8')
        if 'aws-cli/2' not in aws_version:
            _print_error('\nAWS CLI Version 2 not found. Please install. Exiting.')
            exit(1)
        else:
            print('\nAWS CLI Version 2 found. ')
    except Exception as e:
        _print_error(
            f'\nAn error occured trying to find AWS CLI version. Do you have AWS CLI Version 2 installed?\n{e}')
        exit(1)            

# AWS SSO Login Utils
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
    configure_logging(LOGGER, VERBOSE)
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
    configure_logging(LOGGER, False)
    result = PrettyTable()
    result.field_names = ["Option", "Role"]
    for c in configs:
        profile = c.profile_name
        profile = profile.replace("DevelopmentNew", "Develop")
        conf_number = configs.index(c) + 1
        result.add_row([conf_number, profile])
    print (result)
    try:
        config_option = int(input('Enter the role option: '))
        config_option = config_option - 1
    except ValueError:
        _print_error('Please enter a number')
        sys.exit(1)        
    try:
        config_profile = configs[config_option].profile_name
        print(f"\nAWS config profile option selected: {config_profile}")
    except IndexError as e:
        _print_error('Option selected not valid')
        sys.exit(1) 
    return config_profile


# Credentials Utils
def _read_config(path):
    config = ConfigParser()
    config.read(path)
    return config

def _write_config(path, config):
    with open(path, "w") as destination:
        config.write(destination)

def _load_json(path):
    try:
        with open(path) as context:
            return json.load(context)
    except ValueError:
        pass  # skip invalid json            

class Colour:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


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
    print(f'Copying profile [{profile_name}] to [default]')

    config = _read_config(AWS_CONFIG_PATH)

    if config.has_section('default'):
        config.remove_section('default')

    config.add_section('default')

    for key, value in config.items(profile_name):
        config.set('default', key, value)

    _write_config(AWS_CONFIG_PATH, config)
    print("\nCredentials copied successfully") 

def _get_aws_profile(profile_name):
    print(f'\nReading profile: [{profile_name}]')
    config = _read_config(AWS_CONFIG_PATH)
    profile_opts = config.items(profile_name)
    profile = dict(profile_opts)
    return profile

def _get_sso_cached_login(profile):
    print('\nChecking for SSO credentials...')

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

        print(f'Found credentials. Valid until {expires_at.astimezone(tzlocal())}')
        return data

def _get_sso_role_credentials(profile, login):
    print('\nFetching short-term CLI/Boto3 session token...')
    client = boto3.client('sso', region_name=profile['sso_region'])
    response = client.get_role_credentials(
        roleName=profile['sso_role_name'],
        accountId=profile['sso_account_id'],
        accessToken=login['accessToken'],
    )
    expires = datetime.utcfromtimestamp(response['roleCredentials']['expiration'] / 1000.0).astimezone(UTC)
    print(f'Got session token. Valid until {expires.astimezone(tzlocal())}')
    return response["roleCredentials"]

def _store_aws_credentials(profile_name, profile_opts, credentials):
    print(f'\nAdding to credential files under [{profile_name}]')
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

def _add_prefix(name):
    return f'profile {name}' if name != 'default' else 'default'

def _print_colour(colour, message, always=False):
    if always or VERBOSE:
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
