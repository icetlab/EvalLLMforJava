#!/bin/bash
# For Presto build

REPO_PATH=$1
cd "$REPO_PATH" || exit 1 # Change to the repository directory

BUILD_SUBMODULE=$2 # Now the second argument
./mvnw -pl "${BUILD_SUBMODULE}" -am install -DskipTests
