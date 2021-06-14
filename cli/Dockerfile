FROM javiortizmol/python_awscli

WORKDIR /work

COPY src ./src
COPY pyproject.toml ./

RUN python3 -m pip install .

WORKDIR /aws