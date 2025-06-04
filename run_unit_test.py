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

    unit_test_paths = unit_test_paths.strip().split()
    unit_test_names = [os.path.splitext(os.path.basename(path))[0] for path in unit_test_paths]
    unit_test_name = " ".join(unit_test_names)

    repo_path = os.path.join("../", repo_name)
    os.chdir(repo_path)  # Change to repo directory

    # Helper to run a shell command and capture output
    def run_cmd(cmd):
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return result.returncode, result.stdout

    # Run and capture output
    if repo_name in ["netty", "presto"]:
        cmd = f"mvn test -Dtest={unit_test_name}"
    elif repo_name in ["kafka", "RoaringBitmap"]:
        gradle_submodule = unit_test_paths[0].split('/')[0]
        build_cmd = f"./gradlew {gradle_submodule}:build"
        test_cmd = f"./gradlew {gradle_submodule}:test --tests {unit_test_name}"

        build_code, build_log = run_cmd(build_cmd)
        if build_code != 0:
            return f"[BUILD FAILED]\n{build_log}"

        cmd = test_cmd
    else:
        raise ValueError(f"Unsupported repository name: {repo_name}")

    test_code, test_log = run_cmd(cmd)

    if test_code == 0:
        return "[TEST PASSED]\n" + test_log
    else:
        return f"[TEST FAILED]\n{test_log}"
