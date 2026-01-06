import os
import re
import subprocess

def extract_diff_json(llm_log: str):
    """
    Extracts JSON-formatted diff blocks from the LLM log.
    Expected format is a JSON array of objects with filepath, search, and replace fields.
    """
    # Try to find JSON block between ```json and ```
    json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
    if not isinstance(llm_log, (str, bytes)):
        print("LLM log is not a string or bytes-like object")
        return f"[Format Error] LLM log is not a string or bytes-like object."
    match = json_pattern.search(llm_log)

    if not match:
        print("No valid JSON array found in LLM log")
        return f"[Format Error] No valid JSON array found."

    try:
        import json
        blocks = json.loads(match.group(1))

        # Validate each block has required fields
        valid_blocks = []
        for block in blocks:
            if all(key in block for key in ['filepath', 'search', 'replace']):
                valid_blocks.append(block)
            else:
                print(f"Skipping invalid block: {block}")
                return f"[Format Error] Following block is invalid: \n {block}"

        return valid_blocks

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return f"[Format Error] Invalid JSON format."

def normalize_code(code: str) -> str:
    """
    Normalize code by stripping and collapsing whitespace and line formatting.
    """
    # Strip leading/trailing spaces per line, remove empty lines
    lines = [line.strip() for line in code.strip().splitlines() if line.strip()]
    return "\n".join(lines)


def apply_diff(repo_name, commit_id, llm_log):
    """
    Applies JSON-formatted diff blocks from the LLM log to the source files.
    """
    repo_path = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../", repo_name))
    os.system(f"cd {repo_path} && git reset --hard {commit_id} && git reset --hard HEAD~1")

    blocks = extract_diff_json(llm_log)
    if "[Format Error]" in blocks:
        print("No valid diff blocks to apply")
        return blocks

    for block in blocks:
        filepath = block['filepath']
        search = block['search']
        replace = block['replace']

        try:
            # Read file content
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # format-insensitive
            if normalize_code(search) in normalize_code(content):
                new_content = content.replace(search, replace)

                # Write changes back to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                print(f"Applied changes to {filepath}")
            else:
                print(f"Search block not found in {filepath}")
                return f"[Format Error] Following search block not found in {filepath}\n : {search}"

        except Exception as e:
            print(f"Error applying changes to {filepath}: {e}")

    """
    Returns the git diff patch for the given commit.
    """
    try:
        # Get the diff patch using git diff
        diff_patch = subprocess.check_output(
            ["git", "diff", "-w"],
            cwd=repo_path,
            universal_newlines=True
        )
        if not diff_patch.strip():
            return "[Format Error] No code changes detected."
        return diff_patch
    except subprocess.CalledProcessError as e:
        print(f"Error getting diff patch: {e}")
        return None

def batch_generate_diff(base_dir: str, repo_name: str, model_name: str):
    """
    Traverse llm_output/<repo_name>/<model_name> and parse each *.diff.log to generate *.diff.
    Skips if the corresponding *.diff already exists.
    """
    model_dir = os.path.join(base_dir, repo_name, model_name)
    if not os.path.isdir(model_dir):
        print(f"Model directory {model_dir} does not exist.")
        return

    for commit_id in os.listdir(model_dir):
        commit_path = os.path.join(model_dir, commit_id)
        if not os.path.isdir(commit_path):
            continue

        for filename in os.listdir(commit_path):
            if filename.endswith(".diff.log"):
                diff_log_path = os.path.join(commit_path, filename)
                diff_file_name = filename.replace(".diff.log", ".diff")
                diff_file_path = os.path.join(commit_path, diff_file_name)

                # Skip if .diff already exists
                if os.path.exists(diff_file_path):
                    print(f"Skipped {diff_file_path}, already exists.")
                    continue

                print(f"Processing {diff_log_path} ...")

                # Read LLM log
                with open(diff_log_path, 'r', encoding='utf-8') as f:
                    llm_log = f.read()

                # Apply diff
                patch_result = apply_diff(repo_name, commit_id, llm_log)

                if patch_result and not patch_result.startswith("[Format Error]"):
                    with open(diff_file_path, 'w', encoding='utf-8') as f:
                        f.write(patch_result)
                    print(f"Generated {diff_file_path}")
                else:
                    print(f"Failed to generate diff for {diff_log_path}: {patch_result}")

if __name__ == "__main__":
    repo_name = "netty"
    base_dir = "Dataset/llm_output_raw"
    for model_name in os.listdir(os.path.join(base_dir, repo_name)):
        batch_generate_diff(base_dir, repo_name, model_name)
