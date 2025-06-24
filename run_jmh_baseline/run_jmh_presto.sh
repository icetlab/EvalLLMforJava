#!/bin/bash

# Usage function
usage() {
    echo "Usage: $0 [-org|-dev] <csv_file>"
    exit 1
}

# Handle arguments
if [ "$#" -eq 1 ]; then
    MODE="-org"
    CSV_FILE=$1
elif [ "$#" -eq 2 ]; then
    MODE=$1
    CSV_FILE=$2
else
    usage
fi

# Validate mode
if [ "$MODE" != "-org" ] && [ "$MODE" != "-dev" ]; then
    usage
fi

SCRIPT_DIR=$(pwd)

cd presto || { echo "Directory 'presto' not found"; exit 1; }
git clean -fd

if [ ! -f ./mvnw ]; then
    echo "mvnw not found, generating Maven wrapper..."
    mvn -N io.takari:maven:wrapper
else
    echo "mvnw already exists."
fi

# Read CSV file line by line, skipping the header
tail -n +2 "../$CSV_FILE" | while IFS=',' read -r repository id commit_hash source_code jmh_case unittest commit_url; do
    echo -e "\n Processing commit: $commit_hash"

    # Reset repository to specific commit
    git reset --hard "$commit_hash"

    if [ "$MODE" = "-org" ]; then
        git reset HEAD~1 && git restore --staged "$source_code" && git restore "$source_code"
    fi

    # Compile
    submodule=$(echo "$source_code" | cut -d'/' -f1)
    ./mvnw -pl ${submodule} -am clean install -DskipTests -Dcheckstyle.skip=true

    # Run unit test before benchmarking
    # For each test file, extract the submodule and test class, and run them individually
    for test_path in $unittest; do
        test_submodule=$(echo "$test_path" | awk -F'/' '{print $1}')
        test_file=$(basename "$test_path")
        test_name="${test_file%.*}"  # Remove .java or .scala
        ./mvnw -pl "$test_submodule" test -Dtest="$test_name"
    done

    # Define JSON output file
    if [ "$MODE" = "-dev" ]; then
        JSON_DIR="$SCRIPT_DIR/jmh/presto/dev"
        JSON_FILE="$JSON_DIR/${jmh_case}_${id}_dev.json"
    else
        JSON_DIR="$SCRIPT_DIR/jmh/presto/org"
        JSON_FILE="$JSON_DIR/${jmh_case}_${id}.json"
    fi

    # Ensure output directory exists using the absolute path
    mkdir -p "$JSON_DIR"

    # Build benchmark target only
    cd "$submodule" || { echo "Directory '$submodule' not found"; exit 1; }

    ../mvnw clean install -DskipTests

    # Run JMH benchmark and save results
    java -cp "target/jmh-benchmarks.jar:target/classes:target/test-classes:$(../mvnw dependency:build-classpath -Dmdep.scope=test -q -DincludeScope=test -Dsilent=true -Dmdep.outputFile=/dev/stdout | tail -n1)" \
        org.openjdk.jmh.Main ".*$jmh_case.*" -rff "$JSON_FILE" -rf json

    cd ..
done
