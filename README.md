#
# aws-sso-magic tool cli 

This Docker image updates the aws credentials file for the default profile from the aws sso login. At the moment you should copy/paste the url in your browser and complete the login process.

This Docker solution mixed the following repositories:

1. [aws-sso-util](https://github.com/benkehoe/aws-sso-util) AWS SSO has some rough edges, and aws-sso-util is here to smooth them out, hopefully temporarily until AWS makes it better.
2. [aws-sso-credentials](https://github.com/NeilJed/aws-sso-credentials) A simple Python tool to simplify getting short-term credential tokens for CLI/Boto3 operations when using AWS SSO.

## Content of the repository

- [src](src) - The main folder with the aws_sso_magic folder with the .py files & the requirements.txt.
    - [aws_sso_magic](src/aws_sso_magic)
- [docker-build.sh](cli/docker-build.sh) - A docker build tool (Linux/MacOS) to build the docker image locally.
    ```bash
    sudo ./docker-build.sh
    ```     
- [pyproject.toml](pyproject.toml) - The metadata file with the dependencies and application information.    
- [Dockerfile](Dockerfile) - The docker file with the instructions to build the aws-sso-magic cli.

#
# Installing aws-sso-magic tool from [pyp.org](https://pypi.org/project/aws-sso-magic/)

## Prerequisites
1. [Python 3.9](https://www.python.org/downloads/) installed.
2. [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed, please click on the link depending of your OS.

## Installation Steps
1. `pip install aws-sso-magic`

## How to use

1. Execute the following command to configure the sso tool: `aws-sso-magic configure`
2. Type the sso url, sso_region, and the rest of information.
3. Execute the following command to log: `aws-sso-magic login`
4. Select the profile to use.

## How to use with pyp installer

1. Follow the pyp [aw-sso-magic](https://pypi.org/project/aws-sso-magic/) project instructions.

    NOTE: You will need the aws cli v2 installed previously.


## Prerequisites
1. [Python 3.9](https://www.python.org/downloads/) installed.
2. [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed, please click on the link depending of your OS.

## Installation Steps
1. `pip install aws-sso-magic`

#
# How to use with Docker

1. Please follow the instructions from the docker hub repository of [aws_sso_magic](https://hub.docker.com/r/javiortizmol/aws_sso_magic)

## Docker Hub
- [All Repositories](https://hub.docker.com/u/javiortizmol)
- [aws_sso_magic](https://hub.docker.com/r/javiortizmol/aws_sso_magic)
