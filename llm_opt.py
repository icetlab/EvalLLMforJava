import os
import json

persona = "You are a software performance assistant. Your task is to improve the performance of the source code."

def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def generate_prompts(json_data, repo_dir):
    os.chdir(repo_dir)
    source_code_path = os.path.join(repo_dir, json_data["source_code"])
    unittest_path = os.path.join(repo_dir, json_data["unittest"])
    benchmark_path = os.path.join(repo_dir, json_data["jmh_case"])

    source_code = read_file(source_code_path)
    unittest_code = read_file(unittest_path)
    benchmark_code = read_file(benchmark_path)

    description = json_data["description"]

    prompt1 = f"{persona}\nThe source file to be improved is:\n{source_code}\nThe unit test is:\n{unittest_code}"
    prompt2 = f"{persona}\nThe performance issue is:\n{description}\nThe source file to be improved is:\n{source_code}\nThe unit test is:\n{unittest_code}"
    prompt3 = f"{prompt1}\nThe target benchmark functions are:\n{benchmark_code}"
    prompt4 = f"{prompt2}\nThe target benchmark functions are:\n{benchmark_code}"

    return [prompt1, prompt2, prompt3, prompt4]

def improve_code_with_gpt(prompt):
    response = "call gpt"  # Placeholder for actual GPT call
    return response

def improve_code_with_llama(prompt):
    response = "call llama"  # Placeholder for actual Llama call
    return response

def improve_code_with_deepseek(prompt):
    response = "call deepseek"  # Placeholder for actual DeepSeek call
    return response

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

    prompts_dir = os.path.join("prompts", repo_name)
    if not os.path.exists(prompts_dir):
        print(f"Error: Directory {prompts_dir} does not exist.")
        return

    output_dir = os.path.join("output", repo_name)
    os.makedirs(output_dir, exist_ok=True)

    for json_file in os.listdir(prompts_dir):
        if json_file.endswith(".json"):
            json_path = os.path.join(prompts_dir, json_file)
            with open(json_path, 'r') as file:
                json_data = json.load(file)

            prompts = generate_prompts(json_data, repo_name)

            for i, prompt in enumerate(prompts, start=1):
                print(f"Calling {model_name} with prompt {i} for {json_file}...")
                improved_code = call_llm(model_name, prompt)

                output_file = os.path.join(output_dir, f"{json_data['id']}_prompt{i}_improved.java")
                with open(output_file, 'w') as out_file:
                    out_file.write(improved_code)

                print(f"Improved code saved to {output_file}")

if __name__ == "__main__":
    main()