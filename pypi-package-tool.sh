#!/bin/bash

# Prerequisites 
#1. pip install build
#2. pip install twine

set -e

#Global Variables
python_repo="pypi"
python_test_repo="testpypi"
build_folder="dist"
build_path="$build_folder/*"
python_version="python3.9"

if [ "$1" == "" ]; then
    echo "ERROR: Please send an option; build, test, upload. Eg: ./pypi-package-tool.sh upload"
fi

buid_path_delete(){
    if [ -d $build_folder ]; then
        echo "INFO: Deleting $build_folder"
        rm -rf $build_folder
        sleep 3
    else
        echo "INFO: $build_folder folder not found"
    fi
}

build(){
    echo "INFO: Building the artifacts.."
    $python_version -m build
    sleep 5
    echo "INFO: the Artifacts was  built successfully"
}

upload(){
    test="$1"
    if [ "$test" == "True" ]; then
        artifact_repository=$python_test_repo
    else
        artifact_repository=$python_repo
    fi
    echo "INFO: Uploading the artifacts to the $artifact_repository repository.."
    $python_version -m twine upload --repository $artifact_repository $build_path
}

full_upload(){
    buid_path_delete
    build 
    upload "$1"
}

if [ "$1" == "build" ]; then
    buid_path_delete
    build
fi 

if [ "$1" == "test" ]; then
    full_upload "True"
fi

if [ "$1" == "upload" ]; then
    full_upload
fi
