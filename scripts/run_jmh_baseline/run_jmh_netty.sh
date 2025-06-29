#!/bin/bash

# Usage info
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

PERF_REPORT_DIR="target/reports/performance"
SCRIPT_DIR=$(pwd)

cd netty || { echo "Directory 'netty' not found"; exit 1; }
git clean -fd

if [ ! -f ./mvnw ]; then
    echo "mvnw not found, generating Maven wrapper..."
    mvn -N io.takari:maven:wrapper
else
    echo "mvnw already exists."
fi

tail -n +2 "../$CSV_FILE" | while IFS=',' read -r repository id commit_hash source_code jmh_case unittest commit_url; do
    echo "Processing commit: $commit_hash"

    # Reset repository to specific commit
    git reset --hard "$commit_hash"

    # Restore only the necessary source files in org mode
    if [ "$MODE" = "-org" ]; then
        git reset HEAD~1 && git restore --staged "$source_code" && git restore "$source_code"
    fi

    # Workaround for version issue
    find . -name "*.xml" -exec sed -i 's/Final-SNAPSHOT/Final/g' {} \;
    sed -i '/<goal>check-format<\/goal>/,/<\/goals>/ {
    /<\/goals>/ a\
    <configuration>\
        <skip>true</skip>\
    </configuration>
    }' pom.xml

    # Compile
    submodule=$(echo "$source_code" | cut -d'/' -f1)
    ./mvnw -pl ${submodule} -am clean install -DskipTests -Dcheckstyle.skip=true

    # Run unit test before benchmarking
    # For each test file, extract the submodule and test class, and run them individually
    # Run unit tests for each test file in the $unittest variable (space-separated list)
    for test_path in $unittest; do
        test_submodule=$(echo "$test_path" | cut -d'/' -f1)
        test_file=$(basename "$test_path")
        test_name="${test_file%.*}"  # Remove .java or .scala
        ./mvnw -pl "$test_submodule" test -Dtest="$test_name" -DfailIfNoTests=false
    done

    echo "Running JMH benchmark: $jmh_case"
    cd microbench || { echo "microbench directory not found"; exit 1; }
    ../mvnw -DskipTests=false -Dtest="$jmh_case" test -Djmh.resultFormat=JSON

    wait

    # Define JSON output file
    if [ "$MODE" = "-dev" ]; then
        JSON_DIR="$SCRIPT_DIR/jmh/netty/dev"
        JSON_FILE="$JSON_DIR/${jmh_case}_${id}_dev.json"
    else
        JSON_DIR="$SCRIPT_DIR/jmh/netty/org"
        JSON_FILE="$JSON_DIR/${jmh_case}_${id}.json"
    fi

    # Ensure output directory exists using the absolute path
    mkdir -p "$JSON_DIR"

    # Rename the JMH result file
    if [ -f "$PERF_REPORT_DIR/${jmh_case}.json" ]; then
        mv "$PERF_REPORT_DIR/${jmh_case}.json" "JSON_FILE"
    else
        echo "Warning: Expected result file not found: $PERF_REPORT_DIR/${jmh_case}.json"
    fi

    cd ..
done
