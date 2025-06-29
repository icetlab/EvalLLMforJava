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

# Prepare result CSV header if not exists (for LLM mode only)
if [[ "$MODE" == -llm* ]]; then
    RESULT_CSV="../results_${LLM_TYPE}.csv"
    if ! grep -q '^patch,build,test' "$RESULT_CSV" 2>/dev/null; then
        echo "patch,build,test" > "$RESULT_CSV"
    fi
fi

tail -n +2 "../$CSV_FILE" | while IFS=',' read -r repository id commit_hash source_code jmh_case unittest commit_url; do
    echo "Processing commit: $commit_hash"

    if [[ "$MODE" == -llm* ]]; then
        PATCH_DIR="../EvalLLMforJava/llm_output/netty/${LLM_TYPE}/${id}"

        if [ ! -d "$PATCH_DIR" ]; then
            echo "No patches found for commit $id under $PATCH_DIR"
            continue
        fi

        for patch_file in "$PATCH_DIR"/*.diff; do
            git reset --hard "$commit_hash"
            git clean -fd
            git reset HEAD~1 && git restore --staged "$source_code" && git restore "$source_code"

            # Workaround for version issue
            find . -name "*.xml" -exec sed -i 's/Final-SNAPSHOT/Final/g' {} \;
            sed -i '/<goal>check-format<\/goal>/,/<\/goals>/ {
            /<\/goals>/ a\
            <configuration>\
                <skip>true</skip>\
            </configuration>
            }' pom.xml

            sed -i 's#<maven.compiler.source>1\.6</maven.compiler.source>#<maven.compiler.source>1.7</maven.compiler.source>#g' pom.xml

            patch_name=$(basename "$patch_file")
            patch_rel_path="EvalLLMforJava/llm_output/netty/${LLM_TYPE}/${id}/${patch_name}"

            echo "Applying patch: $patch_rel_path"

            if git apply --ignore-whitespace "$patch_file"; then
                echo "Patch applied successfully: $patch_rel_path"

                # Build
                submodule=$(echo "$source_code" | cut -d'/' -f1)
                if ./mvnw -pl ${submodule} -am clean install -DskipTests -Dcheckstyle.skip=true; then
                    echo "Build succeeded for patch: $patch_rel_path"

                    TEST_RESULT="success"
                    # Run unit tests only if build succeeded
                    for test_path in $unittest; do
                        test_submodule=$(echo "$test_path" | cut -d'/' -f1)
                        test_file=$(basename "$test_path")
                        test_name="${test_file%.*}"  # Remove .java or .scala
                        if ! ./mvnw -pl "$test_submodule" test -Dtest="$test_name" -DfailIfNoTests=false -Dcheckstyle.skip=true; then
                            echo "Unit test failed: $test_name"
                            TEST_RESULT="failed"
                        fi
                    done

                    echo "${patch_rel_path},success,${TEST_RESULT}" >> "$RESULT_CSV"
                else
                    echo "Build failed for patch: $patch_rel_path"
                    echo "${patch_rel_path},failed," >> "$RESULT_CSV"
                fi
            else
                echo "Patch failed to apply: $patch_rel_path"
                echo "${patch_rel_path},failed," >> "$RESULT_CSV"
            fi
        done

    else
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

        # Non-LLM normal flow
        submodule=$(echo "$source_code" | cut -d'/' -f1)
        ./mvnw -pl ${submodule} -am clean install -DskipTests -Dcheckstyle.skip=true

        for test_path in $unittest; do
            test_submodule=$(echo "$test_path" | cut -d'/' -f1)
            test_file=$(basename "$test_path")
            test_name="${test_file%.*}"  # Remove .java or .scala
            ./mvnw -pl "$test_submodule" test -Dtest="$test_name" -DfailIfNoTests=false
        done
    fi

    # echo "Running JMH benchmark: $jmh_case"
    # cd microbench || { echo "microbench directory not found"; exit 1; }
    # ../mvnw -DskipTests=false -Dtest="$jmh_case" test -Djmh.resultFormat=JSON

    # wait

    # # Define JSON output file
    # if [ "$MODE" = "-dev" ]; then
    #     JSON_DIR="$SCRIPT_DIR/jmh/netty/dev"
    #     JSON_FILE="$JSON_DIR/${jmh_case}_${id}_dev.json"
    # else
    #     JSON_DIR="$SCRIPT_DIR/jmh/netty/org"
    #     JSON_FILE="$JSON_DIR/${jmh_case}_${id}.json"
    # fi

    # # Ensure output directory exists using the absolute path
    # mkdir -p "$JSON_DIR"

    # # Rename the JMH result file
    # if [ -f "$PERF_REPORT_DIR/${jmh_case}.json" ]; then
    #     mv "$PERF_REPORT_DIR/${jmh_case}.json" "JSON_FILE"
    # else
    #     echo "Warning: Expected result file not found: $PERF_REPORT_DIR/${jmh_case}.json"
    # fi

    # cd ..
done
