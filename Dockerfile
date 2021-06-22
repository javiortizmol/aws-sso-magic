FROM javiortizmol/python_awscli

WORKDIR /work

COPY src ./src
COPY pyproject.toml ./
COPY README.md ./

RUN python3 -m pip install .

WORKDIR /aws