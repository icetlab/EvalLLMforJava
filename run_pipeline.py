import os
from call_llms import call_llm
from apply_llm_changes import extract_diff_blocks, apply_diff_blocks
from run_unit_test import run_unit_test

def improve_code_with_llm(repo_name, commit_id, prompt_content, model_name):
    # Call the LLM with the prompt
    llm_log = call_llm(model_name, prompt_content)

    # Apply the changes to the source code
    changes = extract_diff_blocks(llm_log)
    diff_patch = apply_diff_blocks(repo_name, commit_id, changes)

    return diff_patch

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
                prompt_content_org = f_prompt.read()

            prompt_content = prompt_content_org
            print(f"Calling {model_name} with prompt from {prompt_filename}...")

            diff_patch = improve_code_with_llm(repo_name, commit_id, prompt_content, model_name)

            # unit_test_log = ""
            # iteration = 0
            # max_iterations = 5
            # diff_patch = ""
            # while iteration < max_iterations:
            #     # Improve the code with the LLM
            #     diff_patch = improve_code_with_llm(repo_name, commit_id, prompt_content, model_name)

            #     # Build and run the unit tests
            #     unit_test_log = run_unit_test(repo_name, commit_id)

            #     if "[TEST PASSED]" in unit_test_log:
            #         print(f"Unit test passed after {iteration} iterations.")
            #         break

            #     print(f"Unit test failed after {iteration} iterations. Self-repairing...")
            #     # Self-repair if the unit test fails
            #     # todo: compile/build error
            #     feedback_prompt = f"""
            #     >>>> The unit test failed. Please fix the code.
            #     >>>> Unit test log:
            #     {unit_test_log}
            #     >>>> The prompt you used:
            #     {prompt_content_org}
            #     >>>> The changes you made:
            #     {diff_patch}
            #     >>>> Please fix the code.
            #     """
            #     prompt_content = feedback_prompt  # Use feedback as new prompt for next iteration
            #     iteration += 1

            # if iteration == max_iterations and "[TEST PASSED]" not in unit_test_log:
            #     print(f"Unit test failed after {iteration} iterations. Skipping...")
            #     continue

            # Write changes to the output_path
            with open(output_path, 'w') as f_out:
                f_out.write(diff_patch)

if __name__ == "__main__":
    main()