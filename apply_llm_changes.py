import os
import json
import re
import subprocess
from pathlib import Path

def extract_changes_to_json(llm_log):
    # Try to find a JSON code block (```json ... ```)
    code_block_match = re.search(r"```json\s*(\{.*?\})\s*```", llm_log, re.DOTALL)
    if code_block_match:
        json_str = code_block_match.group(1)
    else:
        # Try to find any code block (``` ... ```)
        code_block_match = re.search(r"```(.*?)```", llm_log, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1)
        else:
            # Fallback: try to find the first '{' and last '}' and extract
            first_brace = llm_log.find('{')
            last_brace = llm_log.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = llm_log[first_brace:last_brace+1]
            else:
                raise ValueError("No JSON object found in LLM log.")

    # Remove any leading/trailing whitespace
    json_str = json_str.strip()

    # Try to parse the JSON
    try:
        data = json.loads(json_str)
    except Exception:
        # Try to fix common issues: single quotes, trailing commas, etc.
        json_str_fixed = json_str.replace("'", '"')
        json_str_fixed = re.sub(r",\s*}", "}", json_str_fixed)
        json_str_fixed = re.sub(r",\s*]", "]", json_str_fixed)
        data = json.loads(json_str_fixed)

    return data

def apply_changes_to_file(repo_name, commit_id, changes):
    repo_path = os.path.join("../", repo_name)
    os.system(f"cd {repo_path} && git reset --hard {commit_id} && git reset --hard HEAD~1")
    for file_change in changes.get("file_changes", []):
        filepath = file_change["filepath"]
        abs_path = os.path.join(repo_path, filepath)
        if not os.path.exists(abs_path):
            print(f"Warning: File {abs_path} does not exist. Skipping.")
            continue

        # Read the file as a list of lines
        with open(abs_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # We'll accumulate all changes to apply, and apply them in reverse order of line numbers
        # to avoid messing up line numbers for subsequent changes.
        # For each change, compute a tuple (sort_key, change_dict)
        # sort_key: for "insert_at_line" and "add_method", use line number;
        # for "replace_block" and "delete_lines", use start_line.
        # For deletions/replacements, sort descending; for insertions, sort ascending.
        # We'll collect all changes, then sort and apply.

        # Prepare a list of (sort_key, change, change_type) for sorting
        change_ops = []
        for change in file_change.get("changes", []):
            ctype = change["type"]
            if ctype in ("replace_block", "delete_lines"):
                # These should be applied from bottom to top
                sort_key = -change["start_line"]
            elif ctype in ("insert_at_line", "add_method"):
                # These should be applied from top to bottom
                sort_key = change.get("line", change.get("insert_after_line", 0))
            else:
                sort_key = 0
            change_ops.append((sort_key, change, ctype))

        # Sort: deletions/replacements descending, insertions ascending
        change_ops.sort()

        # Apply changes
        for _, change, ctype in change_ops:
            if ctype == "replace_block":
                start = change["start_line"] - 1
                end = change["end_line"]
                new_code = [line + "\n" if not line.endswith("\n") else line for line in change["new_code"]]
                lines = lines[:start] + new_code + lines[end:]
            elif ctype == "add_method":
                insert_after = change["insert_after_line"]
                new_code = [line + "\n" if not line.endswith("\n") else line for line in change["new_code"]]
                # insert_after is 1-based; insert after that line
                lines = lines[:insert_after] + new_code + lines[insert_after:]
            elif ctype == "insert_at_line":
                line_num = change["line"] - 1
                new_code = [line + "\n" if not line.endswith("\n") else line for line in change["new_code"]]
                lines = lines[:line_num] + new_code + lines[line_num:]
            elif ctype == "delete_lines":
                start = change["start_line"] - 1
                end = change["end_line"]
                lines = lines[:start] + lines[end:]
            else:
                print(f"Unknown change type: {ctype}")

        # Write the modified lines back to the file
        with open(abs_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    # Get diff patch
    try:
        diff_patch = subprocess.check_output(
            ["git", "diff"],
            cwd=repo_path,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        print(f"Error running git diff: {e}")
        diff_patch = ""

    return diff_patch
