#!/bin/bash
# For RoaringBitmap build

REPO_PATH=$1
cd "$REPO_PATH" || exit 1 # Change to the repository directory

./gradlew build -x test
