#!/bin/bash
# For RoaringBitmap test

REPO_PATH=$1
cd "$REPO_PATH" || exit 1 # Change to the repository directory

UNIT_TEST_NAME=$2 # Now the second argument
./gradlew test --tests "${UNIT_TEST_NAME}"
