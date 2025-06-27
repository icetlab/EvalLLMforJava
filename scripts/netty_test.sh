#!/bin/bash
TEST_SUBMODULE=$1
UNIT_TEST_NAME=$2
./mvnw "${TEST_SUBMODULE}":test -Dtest="${UNIT_TEST_NAME}"
