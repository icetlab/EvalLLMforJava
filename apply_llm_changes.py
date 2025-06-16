import os
import re
import subprocess

# Counting is hard for LLMs. Instead of having it generate diffs directly, tell it to output the old code block before the edit, then write a program that converts that to a diff by finding the original block in the code file.
# The trick is really to forget about the ai knowing why lines it’s adding and removing, and focus on the chunks of code it wants to change.
# https://github.com/Aider-AI/aider/blob/main/aider/coders/udiff_prompts.py
# https://github.com/carlrobertoh/ProxyAI/tree/master/src/main/resources/prompts


def extract_diff_json(llm_log: str):
    """
    Extracts JSON-formatted diff blocks from the LLM log.
    Expected format is a JSON array of objects with filepath, search, and replace fields.
    """
    # print("LLM Log:")
    # print(llm_log)
    # print("\nExtracting JSON diff blocks...")

    # Try to find JSON block between ```json and ```
    json_pattern = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
    match = json_pattern.search(llm_log)

    if not match:
        print("No valid JSON array found in LLM log")
        return []

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

        # print("Extracted blocks:")
        # for block in valid_blocks:
        #     print(f"\nFile: {block['filepath']}")
        #     print("Search:")
        #     print(block['search'])
        #     print("\nReplace:")
        #     print(block['replace'])
        #     print("-" * 80)

        return valid_blocks

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return []

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
    repo_path = os.path.join("../", repo_name)
    os.system(f"cd {repo_path} && git reset --hard {commit_id} && git reset --hard HEAD~1")

    blocks = extract_diff_json(llm_log)
    if not blocks:
        print("No valid diff blocks to apply")
        return

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

        except Exception as e:
            print(f"Error applying changes to {filepath}: {e}")

    """
    Returns the git diff patch for the given commit.
    """
    try:
        # Get the diff patch using git diff
        diff_patch = subprocess.check_output(
            ["git", "diff"],
            cwd=repo_path,
            universal_newlines=True
        )
        return diff_patch
    except subprocess.CalledProcessError as e:
        print(f"Error getting diff patch: {e}")
        return None

# def test():
#     # Test case 1: Valid JSON with multiple blocks
#     test_log_1 = r'''
#     here is an improvement from LLMs.
#     ```json
#     [
#     {
#         "filepath": "src/com/example/AuthService.java",
#         "search": "if (user != null) {\n    if (user.isActive()) {\n        return true;\n    }\n}",
#         "replace": "if (user == null || !user.isActive()) return false;\nreturn true;"
#     },
#     {
#         "filepath": "src/com/example/AuthService.java",
#         "search": "boolean isAdmin = role.equals(\"admin\") || role.equals(\"superuser\");",
#         "replace": "boolean isAdmin = Set.of(\"admin\", \"superuser\").contains(role);"
#     }
#     ]
#     ```
#     '''

#     # Test case 2: Invalid JSON
#     test_log_2 = "Invalid JSON content"

#     # Test extract_diff_json
#     print("Testing extract_diff_json:")
#     print("\nTest case 1 - Valid JSON:")
#     blocks = extract_diff_json(test_log_1)
#     print(f"Extracted {len(blocks)} blocks")

#     print("\nTest case 2 - Invalid JSON:")
#     blocks = extract_diff_json(test_log_2)
#     print(f"Extracted {len(blocks)} blocks")

# if __name__ == "__main__":
#     test()
