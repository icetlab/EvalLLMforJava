import os
import json
import transformers
import torch
from openai import OpenAI

persona = """You are a Java software performance assistant.
You will receive source code files and unit tests, along with optional benchmark functions, or a description of known performance issues.
Your task is to return an optimized version of the code.
Ensure that your changes preserve the original functionality and that the unit tests remain valid.
Please return the full modified source file as your response."""

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
        [f"{path}\n{read_file(path)}" for path in unittest_paths]
    )

    # Read the benchmark function
    benchmark_path = os.path.join(repo_name, json_data["jmh_case"])
    benchmark_code = extract_benchmark_function(benchmark_path)

    # Read the source code files (before developer's patch)
    os.system(f"cd {repo_dir} && git reset --hard HEAD~1")
    source_code_paths = [os.path.join(repo_dir, path.strip()) for path in json_data["source_code"].split()]
    source_code = "\n".join(
        [f"{path}\n{extract_source_code_funtion(path)}" for path in source_code_paths]
    )

    description = json_data["description"]

    prompt1 = f"The source files are:\n{source_code}\n---------\nThe unit test is:\n{unittest_code}"
    prompt2 = f"The performance issue is:\n{description}\n---------\n{prompt1}"
    prompt3 = f"{prompt1}\n---------\nThe target benchmark functions are:\n{benchmark_code}"
    prompt4 = f"{prompt2}\n---------\nThe target benchmark functions are:\n{benchmark_code}"

    return [prompt1, prompt2, prompt3, prompt4]

def improve_code_with_gpt(prompt):
    # OpenAI o4-mini
    client = OpenAI(
        api_key="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"
    )
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        top_p=0.95,
    )
    return  completion.choices[0].message.content

def improve_code_with_llama(prompt):
    # Meta-Llama-3.1
    model_id = "meta-llama/Meta-Llama-3.1-8B-Instruct"
    pipeline = transformers.pipeline(
        "text-generation",
        model=model_id,
        model_kwargs={"torch_dtype": torch.bfloat16},
        device_map="auto",
    )
    messages=[
        {"role": "system", "content": persona},
        {"role": "user", "content": prompt},
    ]
    outputs = pipeline(
        messages,
        do_sample=True,
        temperature=0.3,
        top_p=0.95,
    )
    return str(outputs[0]["generated_text"])

def improve_code_with_deepseek(prompt):
    # DeepSeek-V3
    client = OpenAI(api_key="sk-f43d955ae076497ba2ca4c507d04d8ba", base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": persona},
            {"role": "user", "content": prompt},
        ],
        stream=False,
        temperature=0.3,
        top_p=0.95,
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
    repo_name = input("Enter the repository name (kafka, netty, presto, RoaringBitmap): ")
    model_name = input("Enter the model name (gpt, deepseek, llama): ")

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
                if os.path.exists(prompt_file):
                    print(f"Prompt file {prompt_file} already exists. Skipping...")
                    continue

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