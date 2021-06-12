# aws-sso-magic
## Making life with AWS SSO a little easier

[AWS SSO](https://aws.amazon.com/single-sign-on/) has some rough edges, and `aws-sso-magic` is here to smooth them out, hopefully temporarily until AWS makes it better.

`aws-sso-magic` contains utilities for the following:
* Configuring `.aws/config`
* Logging in/out

The underlying Python library for AWS SSO authentication is [`aws-sso-lib`](https://pypi.org/project/aws-sso-lib/), which has useful functions like interactive login, creating a boto3 session for specific a account and role, and the programmatic versions of the `lookup` functions in `aws-sso-magic`.

## Quickstart

I recommended you install python 3.9 and pip.

1. Install 
On this folder, please execute the following command: 
```bash
python3 -m pip install .
```
2. Learn to know the available options.
```bash
    `aws-sso-magic` 
```

## Documentation

See the full docs at [https://github.com/javiortizmol/aws-sso-magic](https://github.com/javiortizmol/aws-sso-magic)
