import os
from call_llms import call_llm
from apply_llm_changes import apply_diff
from run_unit_test import run_unit_test

project_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EvalLLMforJava")

def improve_code_with_llm(repo_name, commit_id, prompt_content, model_name, output_path):
    # Call the LLM with the prompt
    llm_log = call_llm(model_name, prompt_content)

    # Write LLM log to file
    log_path = f"{output_path}.log"
    with open(log_path, 'w') as f_log:
        f_log.write(llm_log)

    # Apply the changes to the source code
    diff_patch = apply_diff(repo_name, commit_id, llm_log)

    # todo: also do a Self-repair if diff patch generation error


    with open(output_path, 'w') as f_out:
        f_out.write(diff_patch)

    return diff_patch

def main():
    repo_name = input("Enter the repository name (kafka, netty, presto, RoaringBitmap): ")
    model_name = input("Enter the model name (gpt, deepseek, llama, gemini, claude): ")

    prompts_input_dir = os.path.join(project_root, "prompts_combinations", repo_name)
    if not os.path.exists(prompts_input_dir):
        print(f"Error: Directory {prompts_input_dir} does not exist.")
        return

    output_dir = os.path.join(project_root, "llm_output", repo_name, model_name)
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

            build_test_log = ""
            failed_prompt = ""
            iteration = 0
            max_iterations = 5
            diff_patch = ""
            while iteration < max_iterations:
                # Improve the code with the LLM
                diff_patch = improve_code_with_llm(repo_name, commit_id, prompt_content, model_name, output_path)

                # Build and run the unit tests
                build_test_log = run_unit_test(repo_name, commit_id)

                if "[TEST PASSED]" in build_test_log:
                    print(f"Unit test passed after {iteration} iterations.")
                    break

                # Self-repair if build/test fails
                if "[BUILD FAILED]" in build_test_log:
                    failed_prompt = "Build failed"
                elif "[TEST FAILED]" in build_test_log:
                    failed_prompt = "The unit test failed"

                print(f"{failed_prompt} after {iteration} iterations. Self-repairing...")

                feedback_prompt = f"""
                The previous code changes you generated did not pass. Please fix the code.
                >>>> {failed_prompt}. Error log:
                {build_test_log}
                >>>> Original instruction prompt:
                {prompt_content_org}
                >>>> Code changes applied (diff patch):
                {diff_patch}
                >>>> Please fix the code.
                """
                prompt_content = feedback_prompt  # Use feedback as new prompt for next iteration
                iteration += 1

            if iteration == max_iterations and "[TEST PASSED]" not in build_test_log:
                print(f"Build/test failed after {iteration} iterations. Skipping...")
                continue

            # Write changes to the output_path
            with open(output_path, 'w') as f_out:
                f_out.write(diff_patch)

if __name__ == "__main__":
    main()