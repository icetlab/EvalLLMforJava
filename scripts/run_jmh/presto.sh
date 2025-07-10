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

cd presto || { echo "Directory 'presto' not found"; exit 1; }
git clean -fd

if [ ! -f ./mvnw ]; then
    echo "mvnw not found, generating Maven wrapper..."
    mvn -N io.takari:maven:wrapper
fi

# # Prepare result CSV header if not exists (for LLM mode only)
# if [[ "$MODE" == -llm* ]]; then
#     RESULT_CSV="../results_${LLM_TYPE}.csv"
#     if ! grep -q '^patch,build,test' "$RESULT_CSV" 2>/dev/null; then
#         echo "patch,build,test" > "$RESULT_CSV"
#     fi
# fi

# Read CSV file line by line, skipping the header
tail -n +2 "$SCRIPT_DIR/$CSV_FILE" | while IFS=',' read -r repository id commit_hash source_code jmh_case unittest commit_url; do
    echo -e "\n Processing commit: $commit_hash"

    if [[ "$MODE" == -llm* ]]; then
        PATCH_DIR="$SCRIPT_DIR/EvalLLMforJava/llm_output/presto/${LLM_TYPE}/${id}"

        if [ ! -d "$PATCH_DIR" ]; then
            echo "No patches found for commit $id under $PATCH_DIR"
            continue
        fi

        for patch_file in "$PATCH_DIR"/*.diff; do
            git reset --hard "$commit_hash"
            git clean -fd
            git reset HEAD~1 && git restore --staged $source_code && git restore $source_code

            # Workaround
            sed -i '/^sphinx\([<=>!~]*[0-9.]*\)*$/s/.*/sphinx>=5.0/' presto-docs/requirements.txt

            patch_name=$(basename "$patch_file")
            patch_rel_path="$PATCH_DIR/${patch_name}"

            echo "Applying patch: $patch_rel_path"

            if git apply --ignore-whitespace "$patch_file"; then
                echo "Patch applied successfully: $patch_rel_path"

                if [ ! -f ./mvnw ]; then
                    echo "mvnw not found, generating Maven wrapper..."
                    mvn -N io.takari:maven:wrapper
                fi
                # Define JSON output file
                patch_base_name="${patch_name%.diff}"
                JSON_FILE="$PATCH_DIR/${patch_base_name}_${jmh_case}.json"
                # Skip if JSON file already exists
                if [ -f "$JSON_FILE" ]; then
                    echo "JSON file already exists: $JSON_FILE, skipping."
                    continue
                fi

                # Build
                submodule=$(echo "$source_code" | cut -d'/' -f1)
                cd "$submodule" || { echo "Directory '$submodule' not found"; exit 1; }
                if ../mvnw clean install -DskipTests -Dcheckstyle.skip=true; then
                    echo "Build succeeded for patch: $patch_rel_path"

                    # TEST_RESULT="success"
                    # # Run unit tests only if build succeeded
                    # for test_path in $unittest; do
                    #     test_submodule=$(echo "$test_path" | cut -d'/' -f1)
                    #     test_file=$(basename "$test_path")
                    #     test_name="${test_file%.*}"  # Remove .java or .scala
                    #     if ! ./mvnw -pl "$test_submodule" test -Dtest="$test_name" -DfailIfNoTests=false -Dcheckstyle.skip=true; then
                    #         echo "Unit test failed: $test_name"
                    #         TEST_RESULT="failed"
                    #     fi
                    # done
                    # echo "${patch_rel_path},success,${TEST_RESULT}" >> "$RESULT_CSV"

                    # Run JMH benchmark and save results
                    echo "Running JMH benchmark: $jmh_case"
                    if [ "$id" = "297b089" ]; then
                        JMH_OPTS="-p withNulls=NONE -wi 5 -i 20 -f 1 -r 1s -w 1s"
                    else
                        JMH_OPTS="-wi 10 -i 50 -f 1 -r 1s -w 1s"
                    fi
                    java -cp "target/jmh-benchmarks.jar:target/classes:target/test-classes:$(../mvnw dependency:build-classpath -Dmdep.scope=test -q -DincludeScope=test -Dsilent=true -Dmdep.outputFile=/dev/stdout | tail -n1)" \
                        org.openjdk.jmh.Main ".*$jmh_case.*" $JMH_OPTS -rff "$JSON_FILE" -rf json
                else
                    echo "Build failed for patch: $patch_rel_path"
                    # echo "${patch_rel_path},failed," >> "$RESULT_CSV"
                fi
                cd ..
            else
                echo "Patch failed to apply: $patch_rel_path"
                # echo "${patch_rel_path},failed," >> "$RESULT_CSV"
            fi
        done
    else
        # Reset repository to specific commit
        git reset --hard "$commit_hash"

        if [ "$MODE" = "-org" ]; then
            git reset HEAD~1 && git restore --staged $source_code && git restore $source_code
        fi

        # Workaround
        sed -i '/^sphinx\([<=>!~]*[0-9.]*\)*$/s/.*/sphinx>=5.0/' presto-docs/requirements.txt

        # # Run unit test before benchmarking
        # # For each test file, extract the submodule and test class, and run them individually
        # for test_path in $unittest; do
        #     test_submodule=$(echo "$test_path" | awk -F'/' '{print $1}')
        #     test_file=$(basename "$test_path")
        #     test_name="${test_file%.*}"  # Remove .java or .scala
        #     ./mvnw -pl "$test_submodule" test -Dtest="$test_name" -DfailIfNoTests=false
        # done

        # Define JSON output file
        if [ "$MODE" = "-dev" ]; then
            JSON_DIR="$SCRIPT_DIR/jmh/dev"
        else
            JSON_DIR="$SCRIPT_DIR/jmh/org"
        fi
        JSON_FILE="$JSON_DIR/${jmh_case}_${id}.json"

        # Ensure output directory exists using the absolute path
        mkdir -p "$JSON_DIR"

        # Build benchmark target only
        cd "$submodule" || { echo "Directory '$submodule' not found"; exit 1; }

        ../mvnw clean install -DskipTests

        # Run JMH benchmark and save results
        if [ "$id" = "297b089" ]; then
            JMH_OPTS="-p withNulls=NONE -wi 5 -i 20 -f 1 -r 1s -w 1s"
        else
            JMH_OPTS="-wi 10 -i 50 -f 1 -r 1s -w 1s"
        fi
        java -cp "target/jmh-benchmarks.jar:target/classes:target/test-classes:$(../mvnw dependency:build-classpath -Dmdep.scope=test -q -DincludeScope=test -Dsilent=true -Dmdep.outputFile=/dev/stdout | tail -n1)" \
            org.openjdk.jmh.Main ".*$jmh_case.*" $JMH_OPTS -rff "$JSON_FILE" -rf json

        cd ..
    fi
done
