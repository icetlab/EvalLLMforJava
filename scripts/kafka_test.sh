#!/bin/bash
# For Kafka test
TEST_SUBMODULE=$1
UNIT_TEST_NAME=$2
./gradlew "${TEST_SUBMODULE}":test --tests "${UNIT_TEST_NAME}"
