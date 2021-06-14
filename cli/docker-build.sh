#!/bin/bash

set +xe

DOCKER_IMAGE_NAME="aws_sso_magic"
VERSION_FILE_PATH="src/aws_sso_magic/__init__.py"

VERSION=$(cat $VERSION_FILE_PATH)
VERSION=${VERSION%#*}
VERSION=$(echo $VERSION | perl -pe '($_)=/([0-9]+([.][0-9]+)+)/')
VERSION=$(echo "$VERSION")

echo "INFO: Docker build $VERSION"

docker build -t $DOCKER_IMAGE_NAME .

docker tag $DOCKER_IMAGE_NAME $DOCKER_IMAGE_NAME:$VERSION >/dev/null
docker tag $DOCKER_IMAGE_NAME $DOCKER_IMAGE_NAME:latest >/dev/null