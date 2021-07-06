#
# aws-sso-magic tool cli 
This tool update the aws credentials file for the default profile from the aws sso login.

This solution mixed the following repositories:

1. [aws-sso-util](https://github.com/benkehoe/aws-sso-util) AWS SSO has some rough edges, and aws-sso-util is here to smooth them out, hopefully temporarily until AWS makes it better.
2. [aws-sso-credentials](https://github.com/NeilJed/aws-sso-credentials) A simple Python tool to simplify getting short-term credential tokens for CLI/Boto3 operations when using AWS SSO.

### Content of the repository

- [src](src) - The main folder with the aws_sso_magic folder with the .py files & the requirements.txt.
    - [aws_sso_magic](src/aws_sso_magic)
- [docker-build.sh](cli/docker-build.sh) - A docker build tool (Linux/MacOS) to build the docker image locally.
    ```bash
    sudo ./docker-build.sh
    ```     
- [pyproject.toml](pyproject.toml) - The metadata file with the dependencies and application information.    
- [Dockerfile](Dockerfile) - The docker file with the instructions to build the aws-sso-magic cli.
- [eks-login](utils/eks-login) - A script tool to add on the /usr/local/bin (Only for linux/macOS or Windows WSL).
    ```bash
    eks-login develop-readonly
    ```     
#
## Installation 
### Using pyp installer
#### - Prerequisites
1. [Python 3.9](https://www.python.org/downloads/) installed.
2. [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) installed, please click on the link depending of your OS.

#### - Installation

1. Follow the pyp [aw-sso-magic](https://pypi.org/project/aws-sso-magic/) project instructions to install it.

    Note: If you want upgrade it, please run this `pip install aws-sso-magic --upgrade`

### Using Docker

1. Please follow the instructions from the docker hub repository of [aws_sso_magic](https://hub.docker.com/r/javiortizmol/aws_sso_magic)

#
## Configuration Instructions
These steps will create the config files on the paths $HOME/.aws and $HOME/.aws-sso-magic.

1. Execute the following command to configure the sso tool: `aws-sso-magic configure`
2. Type the following information:
    - SSO start URL
    - SSO Region
    - Select the default profile of SSO
    - CLI default client Region
    - CLI default output format
    - CLI profile name. Eg: default
    - Enter only the name of the proxy role to use by default. Eg: MyAdminRole or just press Enter
3. Optional: In case that you want to set an account alias, you can modify the file on $HOME/.aws-sso-magic/config adding the [AliasAccounts] section with key (account name) and value (alias account) Eg:
    ```
    [AliasAccounts]
    test1 = dev
    test2 = qa
    test3 = staging
    test4 = prod
    ```
    making the above configuration, it will now show the aliases in the profile selection menu when aws-sso-magic login command is executed.
    ```
    [?] Please select an AWS config profile:    
      aws-sso
      default
      dev-admin
    > qa-admin 
      staging-admin   
      prod-admin
    ```

#
## How to use it

1. Execute the following command to select and log into the aws accounts: `aws-sso-magic login`
3. Execute the following command to log: `aws-sso-magic login` and select the profile to use or `aws-sso-login login --profile myprofile` if you already know the profile name.

## How to use it for eks support
### - Prerequisites
1. [kubectl](https://kubernetes.io/docs/tasks/tools/) installed.
2. `aws-sso-magic login` or `aws-sso-login login --profile myprofile` executed previouly.

### - Instructions
1. Go to the file $HOME/.aws-sso-magic/eks and replace the string "replacethis" on the section default-proxy-role-name if you want to use that role name for all profiles.
    ```
    [default-proxy-role-name]
    proxy_role_name = replacethis    
    ```

    or just add the profile section in the file. Eg:

    ```
    [myprofile]
    proxy_role_name = myrolename
    ```
2. Execute the following command to select and log the eks cluster: `aws-sso-magic login --eks`
3. Please select the EKS cluster
4. Copy and paste the commands according to your OS.
    
    NOTE: If you will select another profile, please first unset the AWS_PROFILE environment variable or close this terminal and open a new one
#
## Links
### - pypi.org
- [aw-sso-magic](https://pypi.org/project/aws-sso-magic/) 
### - [Docker Hub](https://hub.docker.com/u/javiortizmol)
- [aws_sso_magic](https://hub.docker.com/r/javiortizmol/aws_sso_magic)
