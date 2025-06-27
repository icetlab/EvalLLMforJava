#!/bin/bash
# For RoaringBitmap test
UNIT_TEST_NAME=$1
./gradlew test --tests "${UNIT_TEST_NAME}"
