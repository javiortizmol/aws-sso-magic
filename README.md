# aws-sso-magic cli in Docker

This is a Docker implementation mixing the  original repositories:

1. [aws-sso-util](https://github.com/benkehoe/aws-sso-util) AWS SSO has some rough edges, and aws-sso-util is here to smooth them out, hopefully temporarily until AWS makes it better.
2. [aws-sso-credentials](https://github.com/NeilJed/aws-sso-credentials) A simple Python tool to simplify getting short-term credential tokens for CLI/Boto3 operations when using AWS SSO.

## Content of the repository

- [cli](cli) - The cli code built in python 3.9., pyproject.toml, Dockerfile & docker-build.sh util.
    - [src](cli/src) - The main folder with the aws_sso_magic folder with the .py files & the requirements.txt.
        - [aws_sso_magic](cli/src/aws_sso_magic)
        - [requirements.txt](cli/src/requirements.txt)
    - [docker-build.sh](cli/docker-build.sh) - A docker build tool (Linux/MacOS) to build the docker image locally.
        ```bash
        sudo ./docker-build.sh
        ```
    - [pyproject.toml](cli/pyproject.toml) - The metadata file with the dependencies and application information.    
    - [Dockerfile](cli/Dockerfile) - The docker file with the instructions to build the aws-sso-magic cli.

- [lib](lib) - Libraries used on the cli, they exists on [aws-sso-util](https://github.com/benkehoe/aws-sso-util) too.
    - [aws_sso_lib](lib/aws_sso_lib) - Allows you to programmatically interact with AWS SSO.

## How to use

1. Once you built the docker image locally, you are able to run the following command to the aws sso configuration.

    NOTE: On this step execution, you will need to have the sso url start.

    - Linux/MacOS
        ```bash
        docker run --rm -it -v ~/.aws:/root/.aws -v $(pwd):/aws aws_sso_magic aws-sso-magic configure
        ```
    - Windows CMD
        ```bash
        docker run --rm -it -v %userprofile%\.aws:/root/.aws -v %cd%\aws aws_sso_magic configure
        ```
    - Windows PowerShell
        ```bash
        docker run --rm -it -v $env:userprofile\.aws:/root/.aws -v %cd%\aws aws_sso_magic configure
        ```         

2. Once you built the docker image locally, you are able to run the following command to the aws sso configuration.
    - Linux/MacOS
        ```bash
        docker run --rm -it -v ~/.aws:/root/.aws -v $(pwd):/aws aws_sso_magic aws-sso-magic configure
        ```
    - Windows CMD
        ```bash
        docker run --rm -it -v %userprofile%\.aws:/root/.aws -v %cd%\aws aws_sso_magic configure
        ```
    - Windows PowerShell
        ```bash
        docker run --rm -it -v $env:userprofile\.aws:/root/.aws -v %cd%\aws aws_sso_magic configure
        ```  