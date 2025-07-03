#!/bin/bash

# Usage info
usage() {
    echo "Usage:"
    echo "  $0 [-org|-dev] <csv_file>"
    echo "  $0 -llm {gpt|gemini} <csv_file>"
    exit 1
}

# Handle arguments
if [ "$#" -eq 1 ]; then
    MODE="-org"
    CSV_FILE="$1"
elif [ "$#" -eq 2 ]; then
    MODE="$1"
    CSV_FILE="$2"
elif [ "$#" -eq 3 ] && [ "$1" = "-llm" ]; then
    MODE="-llm $2"
    CSV_FILE="$3"
else
    usage
fi

# Validate mode
if [ "$MODE" != "-org" ] && \
   [ "$MODE" != "-dev" ] && \
   [[ "$MODE" != -llm* ]]; then
    usage
fi

if [[ "$MODE" == -llm* ]]; then
    LLM_TYPE=$(echo "$MODE" | cut -d' ' -f2)
    echo "LLM_TYPE: $LLM_TYPE"
fi

SCRIPT_DIR=$(pwd)

cd kafka || { echo "Directory 'kafka' not found"; exit 1; }
git clean -fd

tail -n +2 "$SCRIPT_DIR/$CSV_FILE" | while IFS=',' read -r repository id commit_hash source_code jmh_case unittest commit_url; do
    echo "Processing commit: $commit_hash"

    if [["$MODE" == -llm*]]; then
        PATCH_DIR="$SCRIPT_DIR/EvalLLMforJava/llm_output/kafka/${LLM_TYPE}/${id}"

        if [ ! -d "$PATCH_DIR" ]; then
            echo "No patches found for commit $id under $PATCH_DIR"
            continue
        fi

        # Apply patches from the directory
        for patch_file in "$PATCH_DIR"/*.diff; do
            git reset --hard "$commit_hash"
            git clean -fd
            git reset HEAD~1 && git restore --staged $source_code && git restore $source_code

            patch_name=$(basename "$patch_file")
            patch_rel_path="$PATCH_DIR/${patch_name}"

            echo "Applying patch: $patch_rel_path"
            if git apply --ignore-space-change --ignore-whitespace "$patch_file"; then
                echo "Patch applied successfully: $patch_rel_path"
                # Define JSON output file
                patch_base_name="${patch_name%.diff}"
                JSON_FILE="$PATCH_DIR/${patch_base_name}_${jmh_case}.json"

                # Skip if JSON file already exists
                if [ -f "$JSON_FILE" ]; then
                    echo "JSON file already exists: $JSON_FILE, skipping."
                    continue
                fi
                # workarounds
                sed -i 's/\(grgit: "\)[0-9.]*"/\14.1.1"/' gradle/dependencies.gradle
                if [ "$id" = "59a75f4" ]; then
                    sed -i 's/spotbugsPlugin: *"[0-9.]*"/spotbugsPlugin: "2.0.0"/' gradle/dependencies.gradle
                    sed -i -E 's/^\s*(additionalSourceDirs|sourceDirectories|classDirectories|executionData)\s*=\s*files\((.*)\)/\1.setFrom(files(\2))/' build.gradle
                    gradle
                fi

                echo "Running JMH benchmark: $jmh_case"
                ./jmh-benchmarks/jmh.sh -wi 10 -i 50 -f 1 -r 1s -w 1s "$jmh_case" -rf json -rff "$JSON_FILE" < /dev/null
            else
                echo "Patch failed to apply: $patch_rel_path"
            fi
        done

    else
        # Reset repository to specific commit
        git reset --hard "$commit_hash"

        if [ "$MODE" = "-org" ]; then
            git reset HEAD~1 && git restore --staged $source_code && git restore $source_code
        fi

        # workarounds
        sed -i 's/\(grgit: "\)[0-9.]*"/\14.1.1"/' gradle/dependencies.gradle
        if [ "$id" = "59a75f4" ]; then
            sed -i 's/spotbugsPlugin: *"[0-9.]*"/spotbugsPlugin: "2.0.0"/' gradle/dependencies.gradle
            sed -i -E 's/^\s*(additionalSourceDirs|sourceDirectories|classDirectories|executionData)\s*=\s*files\((.*)\)/\1.setFrom(files(\2))/' build.gradle
            gradle
        fi

        # Compile and run unit test before benchmarking
        submodule=$(echo "$source_code" | cut -d'/' -f1)
        ./gradlew ${submodule}:build -x test < /dev/null

        # Run unit test(s) before benchmarking
        # For each test file, extract the submodule and test class, and run them individually
        for test_path in $unittest; do
            test_submodule=$(echo "$test_path" | awk -F'/' '{print $1}')
            test_file=$(basename "$test_path")
            test_name="${test_file%.*}"  # Remove .java or .scala
            ./gradlew ${test_submodule}:test --tests "$test_name" < /dev/null
        done

        # Define JSON output file
        if [ "$MODE" = "-dev" ]; then
            JSON_DIR="$SCRIPT_DIR/jmh/kafka/dev"
            JSON_FILE="$JSON_DIR/${jmh_case}_${id}_dev.json"
        else
            JSON_DIR="$SCRIPT_DIR/jmh/kafka/org"
            JSON_FILE="$JSON_DIR/${jmh_case}_${id}.json"
        fi

        # Ensure output directory exists using the absolute path
        mkdir -p "$JSON_DIR"

        echo "Running JMH benchmark: $jmh_case"
        ./jmh-benchmarks/jmh.sh -wi 10 -i 50 -f 1 -r 1s -w 1s "$jmh_case" -rf json -rff "$JSON_FILE" < /dev/null
    fi
done
