import os
import re
import subprocess

# Counting is hard for LLMs. Instead of having it generate diffs directly, tell it to output the old code block before the edit, then write a program that converts that to a diff by finding the original block in the code file.
# The trick is really to forget about the ai knowing why lines it’s adding and removing, and focus on the chunks of code it wants to change.
# https://github.com/Aider-AI/aider/blob/main/aider/coders/udiff_prompts.py
# https://github.com/carlrobertoh/ProxyAI/tree/master/src/main/resources/prompts

def extract_diff_blocks(llm_log):
    """
    Extracts all SEARCH/REPLACE diff blocks from the LLM log according to the persona format in persona.txt.
    Returns a list of dicts: [{'filepath': ..., 'search': ..., 'replace': ...}, ...]
    """
    # The persona format is:
    # ```diff:[full_file_path]
    # <<<<<<< SEARCH
    # ...search...
    # =======
    # ...replace...
    # >>>>>>> REPLACE
    # ```
    pattern = re.compile(
        r"```diff:([^\n]+)\n"
        r"<<<<<<< SEARCH\n(.*?)=======\n(.*?)>>>>>>> REPLACE\n"
        r"```",
        re.DOTALL
    )
    matches = pattern.findall(llm_log)
    blocks = []
    for filepath, search, replace in matches:
        blocks.append({
            "filepath": filepath.strip(),
            "search": search.rstrip('\n'),
            "replace": replace.rstrip('\n')
        })
    return blocks

def apply_diff_blocks(repo_name, commit_id, llm_log):
    """
    Applies SEARCH/REPLACE diff blocks extracted from the LLM log to the source files,
    following the persona format in persona.txt.
    Returns the git diff patch as a string.
    """
    repo_path = os.path.join("../", repo_name)
    os.system(f"cd {repo_path} && git reset --hard {commit_id} && git reset --hard HEAD~1")

    blocks = extract_diff_blocks(llm_log)
    file_to_blocks = {}
    for block in blocks:
        rel_path = block["filepath"]
        rel_path = rel_path.lstrip("/")
        file_to_blocks.setdefault(rel_path, []).append(block)

    for rel_path, blocks in file_to_blocks.items():
        abs_path = os.path.join(repo_path, rel_path)
        if not os.path.exists(abs_path):
            print(f"Warning: File {abs_path} does not exist. Skipping.")
            continue
        with open(abs_path, "r", encoding="utf-8") as f:
            file_text = f.read()

        for block in blocks:
            search = block["search"]
            replace = block["replace"]
            # Try to find the search block in the file (strip leading/trailing newlines for robustness)
            search_stripped = search.strip("\n")
            idx = file_text.find(search_stripped)
            if idx == -1:
                # Try with original search (with newlines)
                idx = file_text.find(search)
                if idx == -1:
                    print(f"SEARCH block not found in {rel_path}. Skipping this block.")
                    continue
                search_to_use = search
            else:
                search_to_use = search_stripped
            # Replace only the first occurrence
            file_text = file_text.replace(search_to_use, replace, 1)

        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(file_text)

    # Get diff patch
    try:
        diff_patch = subprocess.check_output(
            os.chdir(repo_path)
            ["git", "diff"],
            cwd=repo_path,
            encoding="utf-8",
            errors="replace"
        )
    except Exception as e:
        print(f"Error running git diff: {e}")
        diff_patch = ""

    return diff_patch