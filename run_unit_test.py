import subprocess
import os
import json

def run_unit_test(repo_name, commit_id):
    # Read unit test info
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    prompts_file = f"prompts_source/{repo_name}/{commit_id}.json"
    with open(prompts_file, "r") as f:
        data = json.load(f)
        unit_test_paths = data.get("unittest", "")
        source_code_paths = data.get("source_code", "")

    unit_test_paths = unit_test_paths.strip().split()
    source_code_paths = source_code_paths.strip().split()
    build_submodule = source_code_paths[0].split('/')[0]
    test_submodule = unit_test_paths[0].split('/')[0]
    unit_test_names = [os.path.splitext(os.path.basename(path))[0] for path in unit_test_paths]
    unit_test_name = " ".join(unit_test_names)

    repo_path = os.path.join("../", repo_name)
    os.chdir(repo_path)

    # Helper to run a shell command and capture output
    def run_cmd(cmd):
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return result.returncode, result.stdout

    # Build and test, then capture output
    if repo_name in ["netty", "presto"]:
        if repo_name == "netty":
            # Workaround for version issue
            run_cmd('find . -name "*.xml" -exec sed -i \'s/Final-SNAPSHOT/Final/g\' {}')
        build_cmd = f"./mvnw -pl {build_submodule} -am clean install -DskipTests"
        test_cmd = f"./mvnw test -Dtest={unit_test_name}"
    elif repo_name in ["kafka", "RoaringBitmap"]:
        if repo_name == "kafka":
            # workaround for grgit issue
            run_cmd('sed -i \'s/\\(grgit: "\\)[0-9.]*"/\\14.1.1"/\' gradle/dependencies.gradle')
        build_cmd = f"./gradlew {build_submodule}:build -x test"
        test_cmd = f"./gradlew {test_submodule}:test --tests {unit_test_name}"
    else:
        raise ValueError(f"Unsupported repository name: {repo_name}")

    build_code, build_log = run_cmd(build_cmd)
    if build_code != 0:
        return f"[BUILD FAILED]\n{build_log}"

    test_code, test_log = run_cmd(test_cmd)

    if test_code == 0:
        return "[TEST PASSED]\n" + test_log
    else:
        return f"[TEST FAILED]\n{test_log}"
