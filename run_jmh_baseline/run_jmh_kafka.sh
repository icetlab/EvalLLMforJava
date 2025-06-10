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

if [ "$MODE" != "-org" ] && [ "$MODE" != "-dev" ]; then
    usage
fi

cd kafka || { echo "Directory 'kafka' not found"; exit 1; }
git clean -fd

tail -n +2 "../$CSV_FILE" | while IFS=',' read -r repository id commit_hash source_code jmh_case unittest commit_url; do
    echo "Processing commit: $commit_hash"

    # Reset repository to specific commit
    git reset --hard "$commit_hash"

    # workround for grgit issue
    sed -i 's/\(grgit: "\)[0-9.]*"/\14.1.1"/' gradle/dependencies.gradle

    if [ "$MODE" = "-org" ]; then
        git reset HEAD~1 && git restore --staged "$source_code" && git restore "$source_code"
    fi

    # Define JSON output file
    if [ "$MODE" = "-dev" ]; then
        JSON_FILE="../jmh/kafka/dev/${jmh_case}_${id}_dev.json"
    else
        JSON_FILE="../jmh/kafka/org/${jmh_case}_${id}.json"
    fi

    # Ensure output directory exists
    mkdir -p "$(dirname "$JSON_FILE")"

    echo "Running JMH benchmark: $jmh_case"
    ./jmh-benchmarks/jmh.sh "$jmh_case" -rf json -rff "$JSON_FILE" < /dev/null

done
