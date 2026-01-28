#!/bin/bash
# For Presto test

REPO_PATH=$1
cd "$REPO_PATH" || exit 1 # Change to the repository directory

TEST_SUBMODULE=$2 # Now the second argument
UNIT_TEST_NAME=$3 # Now the third argument
./mvnw "${TEST_SUBMODULE}":test -Dtest="${UNIT_TEST_NAME}" -DfailIfNoTests=false
