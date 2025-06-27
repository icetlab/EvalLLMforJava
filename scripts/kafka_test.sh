#!/bin/bash
# For Kafka test

REPO_PATH=$1
cd "$REPO_PATH" || exit 1 # Change to the repository directory

TEST_SUBMODULE=$2 # Now the second argument
UNIT_TEST_NAME=$3 # Now the third argument
./gradlew "${TEST_SUBMODULE}":test --tests "${UNIT_TEST_NAME}"