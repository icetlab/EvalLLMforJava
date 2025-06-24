import os
import json

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def extract_function(file_path, function_name):
    source_code = read_file(file_path)
    # Extract the specific function from the file
    start_marker = f"{function_name}("
    start_index = source_code.find(start_marker)
    if start_index != -1:
        # Extract the specific function by finding its boundaries
        brace_count = 0
        end_index = start_index
        while end_index < len(source_code):
            char = source_code[end_index]
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
            end_index += 1
            if brace_count == 0:
                break
        source_code = source_code[start_index:end_index].strip()
    else:
        raise ValueError(f"Function {function_name} not found in {file_path}")

    return source_code

def extract_benchmark_function(benchmark_path):
    if "." in benchmark_path:
        file_path, function_name = benchmark_path.rsplit(".", 1)
        file_path = os.path.join("../", file_path+".java")
        benchmark_code = extract_function(file_path, function_name)
    else:
        benchmark_path = os.path.join("../", benchmark_path+".java")
        benchmark_code = read_file(benchmark_path)
    return benchmark_code

def extract_source_code_funtion(source_code_path):
    if not source_code_path.endswith((".java", ".scala")):
        file_path, function_name = source_code_path.rsplit(".", 1)
        file_path = os.path.join(file_path + ".java")
        source_code = extract_function(file_path, function_name)
    else:
        source_code = read_file(source_code_path)
    return source_code

def generate_prompts(json_data, repo_name):
    repo_dir = os.path.join("../", repo_name)
    if not os.path.exists(repo_dir):
        print(f"Error: Directory {repo_dir} does not exist.")
        return
    # reset the git repository to the specified commit
    commit_hash = json_data["commit_hash"]
    os.system(f"cd {repo_dir} && git reset --hard {commit_hash}")

    # Read the unit test
    unittest_paths = [os.path.join(repo_dir, path.strip()) for path in json_data["unittest"].split()]
    unittest_code = "\n".join(
        [f">>> file_path: {path}\n{read_file(path)}" for path in unittest_paths]
    )

    # Read the benchmark function
    benchmark_path = os.path.join(repo_name, json_data["jmh_case"])
    benchmark_code = extract_benchmark_function(benchmark_path)

    # Read the source code files (before developer's patch)
    os.system(f"cd {repo_dir} && git reset --hard HEAD~1")
    source_code_paths = [os.path.join(repo_dir, path.strip()) for path in json_data["source_code"].split()]
    source_code = "\n".join(
        [f">>> file_path: {path}\n{extract_source_code_funtion(path)}" for path in source_code_paths]
    )

    description = json_data["description"]

    prompt1 = f">> The source files are:\n{source_code}\n---------\n>> The unit tests are:\n{unittest_code}\n"
    prompt2 = f">> The performance issue is:\n{description}\n---------\n{prompt1}\n"
    prompt3 = f"{prompt1}\n---------\n>> The target benchmark functions are:\n{benchmark_code}\n"
    prompt4 = f"{prompt2}\n---------\n>> The target benchmark functions are:\n{benchmark_code}\n"

    return [prompt1, prompt2, prompt3, prompt4]

def main():
    repo_name = input("Enter the repository name (e.g., kafka, netty, presto, RoaringBitmap): ")
    current_prompts_dir_for_repo = os.path.join("prompts_source", repo_name)
    if not os.path.isdir(current_prompts_dir_for_repo):
        print(f"Error: Prompts directory for repository '{repo_name}' not found at '{current_prompts_dir_for_repo}'.")
        return

    print(f"Processing repository: {repo_name}")
    
    output_repo_dir = os.path.join("prompts_combinations", repo_name)
    os.makedirs(output_repo_dir, exist_ok=True)
    
    json_filenames = os.listdir(current_prompts_dir_for_repo)
    for json_filename in json_filenames:
        if json_filename.endswith(".json"):
            json_file_path = os.path.join(current_prompts_dir_for_repo, json_filename)

            with open(json_file_path, 'r') as file_handle:
                json_data = json.load(file_handle)
            
            commit_id = json_data['id'] 
            prompts = generate_prompts(json_data, repo_name)

            # Create a subdirectory for this commit_id
            commit_output_dir = os.path.join(output_repo_dir, commit_id)
            os.makedirs(commit_output_dir, exist_ok=True)

            for i, prompt_content in enumerate(prompts, start=1):
                output_prompt_filename = f"prompt{i}.txt"
                output_prompt_filepath = os.path.join(commit_output_dir, output_prompt_filename)

                if os.path.exists(output_prompt_filepath):
                    print(f"Prompt file {output_prompt_filepath} already exists. Skipping...")
                    continue

                with open(output_prompt_filepath, 'w') as prompt_out_file:
                    prompt_out_file.write(prompt_content)
                print(f"Prompt saved to {output_prompt_filepath}")
                    

if __name__ == "__main__":
    main()