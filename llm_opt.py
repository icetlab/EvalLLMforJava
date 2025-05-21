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

    prompts_input_dir = os.path.join("prompts_combinations", repo_name)
    if not os.path.exists(prompts_input_dir):
        print(f"Error: Directory {prompts_input_dir} does not exist.")
        return

    output_dir = os.path.join("LLMOpt", repo_name, model_name)
    os.makedirs(output_dir, exist_ok=True)

    for prompt_filename in os.listdir(prompts_input_dir):
        if "_prompt" in prompt_filename and prompt_filename.endswith(".txt"):
            base_name = prompt_filename[:-4]
            
            try:
                commit_id, prompt_num_str = base_name.rsplit('_prompt', 1)
            except ValueError:
                print(f"Warning: Skipping file with unexpected name format: {prompt_filename}")
                continue

            current_prompt_file_path = os.path.join(prompts_input_dir, prompt_filename)
            
            # Define the output log file path, e.g., "LLMOpt/repo/model/commitid_prompt1.log"
            output_log_filename = f"{commit_id}_prompt{prompt_num_str}.log"
            output_log_path = os.path.join(output_dir, output_log_filename)

            print(f"Processing prompt file: {prompt_filename}")
            if os.path.exists(output_log_path):
                print(f"Output file {output_log_path} already exists. Skipping LLM call.")
                continue
            
            with open(current_prompt_file_path, 'r') as f_prompt:
                prompt_content = f_prompt.read()

            print(f"Calling {model_name} with prompt from {prompt_filename}...")
 
            # Call the LLM with the prompt
            improved_code = call_llm(model_name, prompt_content)

            with open(output_log_path, 'w') as out_file:
                out_file.write(improved_code)

if __name__ == "__main__":
    main()