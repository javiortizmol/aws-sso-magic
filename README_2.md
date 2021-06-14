# aws-sso-magic cli in Docker

This is a Docker implementation of the originals repositories:

1. [aws-sso-util](https://github.com/benkehoe/aws-sso-util) AWS SSO has some rough edges, and aws-sso-util is here to smooth them out, hopefully temporarily until AWS makes it better.
2. [aws-sso-credentials](https://github.com/NeilJed/aws-sso-credentials) A simple Python tool to simplify getting short-term credential tokens for CLI/Boto3 operations when using AWS SSO.

## Content of the repository

- [cli](openvpn-v2.4.9-aws.patch) - patch required to build
AWS compatible OpenVPN v2.4.9, based on the
[AWS source code](https://amazon-source-code-downloads.s3.amazonaws.com/aws/clientvpn/osx-v1.2.5/openvpn-2.4.5-aws-2.tar.gz) (thanks to @heprotecbuthealsoattac) for the link.
- [lib](openvpn-v2.5.1-aws.patch) - patch for  OpenVPN v2.5.1, based on the
[AWS source code](https://amazon-source-code-downloads.s3.amazonaws.com/aws/clientvpn/osx-v1.2.5/openvpn-2.4.5-aws-2.tar.gz) (thanks to @heprotecbuthealsoattac) for the link.

## How to use

1. Place AWS configuration file at the same folder of `docker-compose.yml`, naming it `vpn.conf`
1. Execute `docker-compose up` (Better to not use `-d` option, for getting the login URL in the logs and stopping the container in a easier way)