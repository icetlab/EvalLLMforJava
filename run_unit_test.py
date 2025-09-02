import subprocess
import os
import json

def run_unit_test(repo_name, commit_id):
    # Read unit test info
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    prompts_file = f"Prompts/prompts_source/{repo_name}/{commit_id}.json"
    with open(prompts_file, "r") as f:
        data = json.load(f)
        unit_test_paths = data.get("unittest", "")
        source_code_paths = data.get("source_code", "")

    unit_test_paths = unit_test_paths.strip().split()
    source_code_paths = source_code_paths.strip().split()

    build_submodule = source_code_paths[0].split('/')[0]
    test_submodule = unit_test_paths[0].split('/')[0]
    unit_test_name = os.path.splitext(os.path.basename(unit_test_paths[0]))[0]

    # Construct the absolute path to the repository
    repo_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../", repo_name))

    # Helper to run a shell command and capture output
    def run_cmd(cmd):
        result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return result.returncode, result.stdout

    # Define paths to the shell scripts
    build_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"Scripts/{repo_name}_build.sh")
    test_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"Scripts/{repo_name}_test.sh")

    # Determine the arguments to pass to the build and test scripts,
    # always starting with repo_path
    build_script_args = f" {repo_path}"
    test_script_args = f" {repo_path}"

    if repo_name in ["netty", "presto", "kafka"]:
        build_script_args += f" {build_submodule}"
        test_script_args += f" {test_submodule} {unit_test_name}"
    elif repo_name == "RoaringBitmap":
        # RoaringBitmap build and test scripts do not use submodule arguments
        test_script_args += f" {unit_test_name}"
    else:
        raise ValueError(f"Unsupported repository name: {repo_name}")

    # Execute build script
    build_code, build_log = run_cmd(f"{build_script}{build_script_args}")
    if build_code != 0:
        return f"[BUILD FAILED]\n{build_log}"

    # Execute test script
    test_code, test_log = run_cmd(f"{test_script}{test_script_args}")

    if test_code == 0:
        return f"[TEST PASSED]\n{test_log}"
    else:
        return f"[TEST FAILED]\n{test_log}"