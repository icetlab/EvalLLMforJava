import os
from call_llms import call_llm
from apply_llm_changes import apply_changes_to_file, extract_changes_to_json

def main():
    repo_name = input("Enter the repository name (kafka, netty, presto, RoaringBitmap): ")
    model_name = input("Enter the model name (gpt, deepseek, llama, gemini, claude): ")

    prompts_input_dir = os.path.join("prompts_combinations", repo_name)
    if not os.path.exists(prompts_input_dir):
        print(f"Error: Directory {prompts_input_dir} does not exist.")
        return

    output_dir = os.path.join("llm_output", repo_name, model_name)
    os.makedirs(output_dir, exist_ok=True)

    for prompt_filename in os.listdir(prompts_input_dir):
        if "_prompt" in prompt_filename and prompt_filename.endswith(".txt"):
            base_name = prompt_filename[:-4]
            print(f">>>> Processing prompt file: {prompt_filename}")

            try:
                commit_id, prompt_num_str = base_name.rsplit('_prompt', 1)
            except ValueError:
                print(f"Warning: Skipping file with unexpected name format: {prompt_filename}")
                continue

            current_prompt_file_path = os.path.join(prompts_input_dir, prompt_filename)

            # Define the output diff file path, e.g., "llm_output/repo/model/commitid_prompt1.diff"
            output_filename = f"{commit_id}_prompt{prompt_num_str}.diff"
            output_path = os.path.join(output_dir, output_filename)

            if os.path.exists(output_path):
                print(f"Output file {output_path} already exists. Skipping LLM call.")
                continue

            with open(current_prompt_file_path, 'r') as f_prompt:
                prompt_content = f_prompt.read()

            print(f"Calling {model_name} with prompt from {prompt_filename}...")

            # Call the LLM with the prompt
            llm_log = call_llm(model_name, prompt_content)
            changes = extract_changes_to_json(llm_log)

            # Apply the changes to the source code
            diff_patch = apply_changes_to_file(repo_name, commit_id, changes)

            # Run the unit tests
            # Self-repair if unit test fails

            # Write changes to the output_path
            with open(output_path, 'w') as f_out:
                f_out.write(diff_patch)

if __name__ == "__main__":
    main()