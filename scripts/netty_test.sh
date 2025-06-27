#!/bin/bash
# For Netty test

REPO_PATH=$1
cd "$REPO_PATH" || exit 1 # Change to the repository directory

TEST_SUBMODULE=$2
UNIT_TEST_NAME=$3
./mvnw "${TEST_SUBMODULE}":test -Dtest="${UNIT_TEST_NAME}"
