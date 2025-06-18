import os
from call_llms import call_llm
from apply_llm_changes import apply_diff
from run_unit_test import run_unit_test

project_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EvalLLMforJava")

def improve_code_with_llm(repo_name, commit_id, prompt_content, model_name):
    iteration = 0
    max_iterations = 8
    llm_log = ""
    diff_patch = ""
    prompt_feedback = prompt_content
    while iteration < max_iterations:
        # Call the LLM with the prompt
        llm_log = call_llm(model_name, prompt_feedback)

        # Apply the changes to the source code
        diff_patch = apply_diff(repo_name, commit_id, llm_log)

        if "[Format Error]" not in diff_patch:
            print(f"All generated code changes successfully applied.")
            return "good", llm_log, diff_patch

        # Self-repair if the format of generated code changes is invalid
        if "[Format Error]" in diff_patch:
            print(f"Format of output is invalid. Self-repair...")
            # Create a self-repair prompt
            prompt_feedback = f"""
            >>>> The format of your generated code changes does not meet my requirements, with the following error:
            {diff_patch}
            >>>> Your previous output is:
            {llm_log}
            >>>> Analyze the error and provide a corrected version. If the search block was not found,
            try to provide a more flexible search pattern or break down the changes into smaller chunks.
            Make sure to maintain the same JSON format with filepath, search, and replace fields.
            >>>> Original prompt was:
            {prompt_content}
            """
            iteration += 1

    if iteration == max_iterations and "[Format Error]" in diff_patch:
        print(f"Warning: not all generated code changes successfully applied!")
        return "bad"
    
    return "good", llm_log, diff_patch

def main():
    repo_name = input("Enter the repository name (kafka, netty, presto, RoaringBitmap): ")
    model_name = input("Enter the model name (gpt, deepseek, llama, gemini, claude): ")

    prompts_input_dir = os.path.join(project_root, "prompts_combinations", repo_name)
    if not os.path.exists(prompts_input_dir):
        print(f"Error: Directory {prompts_input_dir} does not exist.")
        return

    output_dir = os.path.join(project_root, "llm_output", repo_name, model_name)
    os.makedirs(output_dir, exist_ok=True)

    total_try = 0
    good_try = 0
    for prompt_filename in os.listdir(prompts_input_dir):
        if "_prompt" in prompt_filename and prompt_filename.endswith(".txt"):
            base_name = prompt_filename[:-4]
            total_try += 1
            print(f">>>> {total_try}: Processing prompt file: {prompt_filename}")

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

            prompt_feedback = prompt_content
            print(f"Calling {model_name} with prompt from {prompt_filename}...")

            iteration = 0
            max_iterations = 5
            diff_patch = ""
            llm_log = ""
            while iteration < max_iterations:
                result, llm_log, diff_patch = improve_code_with_llm(repo_name, commit_id, prompt_feedback, model_name)
                if result == "bad":
                    break

                build_test_log = run_unit_test(repo_name, commit_id)

                if "[TEST PASSED]" in build_test_log:
                    print(f"Unit test passed after iteration-{iteration}.")
                    break

                # Self-repair if build/test fails
                if "[BUILD FAILED]" in build_test_log:
                    failed_prompt = "Build failed"
                elif "[TEST FAILED]" in build_test_log:
                    failed_prompt = "The unit test failed"

                print(f"{failed_prompt} after iteration-{iteration}. Self-repairing...")

                prompt_feedback = f"""
                The previous code changes you generated did not pass. Please fix the code.
                >>>> {failed_prompt}. Error log:
                {build_test_log}
                >>>> Original prompt was:
                {prompt_content}
                >>>> Your previous output is:
                {llm_log}
                >>>> Please fix the code.
                """
                iteration += 1

            if "[TEST PASSED]" not in build_test_log:
                print(f"Build/test failed after {max_iterations} iterations. Skipping...")
                continue

            good_try += 1
            print(f"Build/test rate is {good_try}/{total_try}")
            # Save good code changes
            with open(output_path, 'w') as f_out:
                f_out.write(diff_patch)
            # Also original log
            log_path = output_path + ".log"
            with open(log_path, 'w') as f_out:
                f_out.write(llm_log)

if __name__ == "__main__":
    main()
