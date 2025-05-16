import os
import json
from openai import OpenAI

persona = """You are a Java software performance assistant.
You will receive a single source code file and unit tests, along with optional benchmark functions, or a description of known performance issues.
Your task is to return an optimized version of the code.
Ensure that your changes preserve the original functionality and that the unit tests remain valid.
Please return the full modified source file as your response."""

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def extract_benchmark_function(benchmark_path):
    if "." in benchmark_path:
        file_path, function_name = benchmark_path.rsplit(".", 1)
        benchmark_path = os.path.join("../", file_path+".java")
        benchmark_code = read_file(file_path)
        # Extract the specific function from the file
        start_marker = f"{function_name}("
        start_index = benchmark_code.find(start_marker)
        if start_index != -1:
            # Extract the specific function by finding its boundaries
            brace_count = 0
            end_index = start_index
            while end_index < len(benchmark_code):
                char = benchmark_code[end_index]
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                end_index += 1
                if brace_count == 0:
                    break
            benchmark_code = benchmark_code[start_index:end_index].strip()
        else:
            raise ValueError(f"Function {function_name} not found in {file_path}")
    else:
        benchmark_path = os.path.join("../", benchmark_path+".java")
        benchmark_code = read_file(benchmark_path)
    benchmark_code = read_file(benchmark_path)

    return benchmark_code

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
        [f"{path}\n{read_file(path)}" for path in unittest_paths]
    )

    # Read the benchmark function
    benchmark_path = os.path.join(repo_name, json_data["jmh_case"])
    benchmark_code = extract_benchmark_function(benchmark_path) if benchmark_path else ""

    # Read the source code files (before developer's patch)
    os.system(f"cd {repo_dir} && git reset --hard HEAD~1")
    source_code_paths = [os.path.join(repo_dir, path.strip()) for path in json_data["source_code"].split()]
    source_code = "\n".join(
        [f"{path}\n{read_file(path)}" for path in source_code_paths]
    )

    description = json_data["description"]

    prompt1 = f"The source files are:\n{source_code}\n---------\nThe unit test is:\n{unittest_code}"
    prompt2 = f"The performance issue is:\n{description}\n---------\n{prompt1}"
    prompt3 = f"{prompt1}\n---------\nThe target benchmark functions are:\n{benchmark_code}"
    prompt4 = f"{prompt2}\n---------\nThe target benchmark functions are:\n{benchmark_code}"

    return [prompt1, prompt2, prompt3, prompt4]

def improve_code_with_gpt(prompt):
    response = "call gpt"  # Placeholder for actual GPT call
    return response

def improve_code_with_llama(prompt):
    response = "call llama"  # Placeholder for actual Llama call
    return response

def improve_code_with_deepseek(prompt):
    client = OpenAI(api_key="sk-f43d955ae076497ba2ca4c507d04d8ba", base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        stream=False
    )
    return response.choices[0].message.content

def call_llm(model_name, prompt):
    if model_name == "gpt":
        return improve_code_with_gpt(prompt)
    elif model_name == "llama":
        return improve_code_with_llama(prompt)
    elif model_name == "deepseek":
        return improve_code_with_deepseek(prompt)
    else:
        raise ValueError("Unsupported model name. Choose from 'gpt', 'llama', or 'deepseek'.")

def main():
    model_name = input("Enter the model name (e.g., gpt): ")
    repo_name = input("Enter the repository name (e.g., kafka): ")

    # model_name = "deepseek"
    # repo_name = "RoaringBitmap"

    prompts_dir = os.path.join("prompts", repo_name)
    if not os.path.exists(prompts_dir):
        print(f"Error: Directory {prompts_dir} does not exist.")
        return

    output_dir = os.path.join("LLMOpt", repo_name, model_name)
    os.makedirs(output_dir, exist_ok=True)

    for json_file in os.listdir(prompts_dir):
        if json_file.endswith(".json"):
            json_path = os.path.join(prompts_dir, json_file)
            with open(json_path, 'r') as file:
                json_data = json.load(file)

            prompts = generate_prompts(json_data, repo_name)

            for i, prompt in enumerate(prompts, start=1):
                print(f"Calling {model_name} with prompt {i} for {json_file}...")

                prompt_file = os.path.join(output_dir, f"{json_data['id']}_prompt{i}.txt")
                with open(prompt_file, 'w') as prompt_out:
                    prompt_out.write(prompt)
                print(f"Prompt saved to {prompt_file}")
 
                # Call the LLM with the prompt
                improved_code = call_llm(model_name, prompt)

                output_file = os.path.join(output_dir, f"{json_data['id']}_prompt{i}.log")
                with open(output_file, 'w') as out_file:
                    out_file.write(improved_code)
                print(f"Improved code saved to {output_file}")

if __name__ == "__main__":
    main()