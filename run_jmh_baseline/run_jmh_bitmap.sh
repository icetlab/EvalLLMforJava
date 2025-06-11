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

SCRIPT_DIR=$(pwd)

cd RoaringBitmap || { echo "Directory 'RoaringBitmap' not found"; exit 1; }
git clean -fd

# Read CSV file line by line, skipping the header
tail -n +2 "../$CSV_FILE" | while IFS=',' read -r repository id commit_hash source_code jmh_case unittest commit_url; do
    echo "Processing commit: $commit_hash"

    # Reset repository to specific commit
    git reset --hard "$commit_hash"

    if [ "$MODE" = "-org" ]; then
        git reset HEAD~1 && git restore --staged "$source_code" && git restore "$source_code"
    fi

    # Define JSON output file
    if [ "$MODE" = "-dev" ]; then
        JSON_DIR="$SCRIPT_DIR/jmh/RoaringBitmap/dev"
        JSON_FILE="$JSON_DIR/${jmh_case}_${id}_dev.json"
    else
        JSON_DIR="$SCRIPT_DIR/jmh/RoaringBitmap/org"
        JSON_FILE="$JSON_DIR/${jmh_case}_${id}.json"
    fi

    # Ensure output directory exists using the absolute path
    mkdir -p "$JSON_DIR"

    # Run JMH benchmark and save results
    echo "Running JMH benchmark: $jmh_case"
    ./jmh/run.sh ".*${jmh_case}.*" -rf json -rff "$JSON_FILE" < /dev/null
done
