#!/bin/bash
# For Presto build
BUILD_SUBMODULE=$1
./mvnw -pl "${BUILD_SUBMODULE}" -am install -DskipTests
