FROM javiortizmol/python_awscli

WORKDIR /work

COPY src ./src
COPY pyproject.toml ./
COPY README.md ./

RUN apt update && \ 
    apt install -y curl && \
    curl -fsSLo /usr/share/keyrings/kubernetes-archive-keyring.gpg https://packages.cloud.google.com/apt/doc/apt-key.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | tee /etc/apt/sources.list.d/kubernetes.list && \
    apt update && \
    apt install -y kubectl

RUN python3 -m pip install .

WORKDIR /aws