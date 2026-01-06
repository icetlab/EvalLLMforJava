import os
from call_llms import call_llm
from apply_llm_changes import apply_diff
from run_unit_test import run_unit_test
from datetime import datetime

project_root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EvalLLMforJava")

def improve_code_with_llm(repo_name, commit_id, prompt_content, model_name):
    iteration = 0
    max_iterations = 2
    llm_log = ""
    diff_patch = ""
    prompt_feedback = prompt_content
    while iteration < max_iterations:
        # Call the LLM with the prompt
        llm_log = call_llm(model_name, prompt_feedback)
        attempt = iteration + 1
        print(f">>>> LLM output [{model_name}] {repo_name}/{commit_id} attempt-{attempt}:\n{llm_log}")

        # Apply the changes to the source code
        diff_patch = apply_diff(repo_name, commit_id, llm_log)

        if "[Format Error]" not in diff_patch:
            print(f"All generated code changes successfully applied.")
            return "Success", llm_log, diff_patch

        # Self-repair if the format of generated code changes is invalid
        if "[Format Error]" in diff_patch:
            print(f"Format of output is invalid. Self-repair...")
            # Create a self-repair prompt
            prompt_feedback = f"""
            >>>> The format of your generated code changes does not meet my requirements, with the following error:
            {diff_patch}
            >>>> Your previous output is:
            {llm_log}
            >>>> Analyze the error. If the search block was not found, try to provide a more flexible search pattern or break down the changes into smaller chunks.
            Make sure to maintain the same JSON format with filepath, search, and replace fields.
            >>>> Original prompt was:
            {prompt_content}
            """
            iteration += 1

    if iteration == max_iterations and "[Format Error]" in diff_patch:
        return "Failed", llm_log, diff_patch
    
    return "Success", llm_log, diff_patch

def main():
    # repo_name = input("Enter the repository name (kafka, netty, presto, RoaringBitmap): ")
    # model_name = input("Enter the model name (gpt, deepseek, llama, gemini, claude): ")
    repo_name = "RoaringBitmap"
    model_name = "deepseek"

    prompts_input_dir = os.path.join(project_root, "Prompts", repo_name)
    if not os.path.exists(prompts_input_dir):
        print(f"Error: Directory {prompts_input_dir} does not exist.")
        return

    total_try = 0
    good_try = 0
    build_fail_count = 0
    test_fail_count = 0
    format_fail_count = 0
    pass_count = 0

    stats_dir = os.path.join(project_root, "Dataset", "stats", repo_name, model_name)
    os.makedirs(stats_dir, exist_ok=True)
    stats_file = os.path.join(stats_dir, "progress.csv")
    if not os.path.exists(stats_file):
        with open(stats_file, 'w') as sf:
            sf.write("timestamp,repo,model,commit,prompt,status,failure_type,total_try,pass_count,build_fail_count,test_fail_count,format_fail_count,pass_rate\n")

    def write_stats(commit_id, prompt_num_str, status, failure_type):
        pr = (pass_count / total_try) if total_try else 0.0
        with open(stats_file, 'a') as sf:
            sf.write(f"{datetime.utcnow().isoformat()},{repo_name},{model_name},{commit_id},prompt{prompt_num_str},{status},{failure_type},{total_try},{pass_count},{build_fail_count},{test_fail_count},{format_fail_count},{pr}\n")

    def save_failed_patch(commit_id, prompt_num_str, iteration, diff_patch, llm_log, build_test_log, failure_type):
        base_dir = os.path.join(project_root, "Dataset", "llm_output_failed", repo_name, model_name, commit_id)
        os.makedirs(base_dir, exist_ok=True)
        prefix = os.path.join(base_dir, f"prompt{prompt_num_str}.iter{iteration}.{failure_type}")
        if diff_patch:
            with open(prefix + ".diff", 'w') as f_out:
                f_out.write(diff_patch)
        if llm_log:
            with open(prefix + ".llm.log", 'w') as f_out:
                f_out.write(llm_log)
        if build_test_log:
            with open(prefix + ".build.log", 'w') as f_out:
                f_out.write(build_test_log)

    # Traverse each commit_id subdirectory
    for commit_id in os.listdir(prompts_input_dir):
        commit_dir = os.path.join(prompts_input_dir, commit_id)
        if not os.path.isdir(commit_dir):
            continue

        # Output directory for this commit_id
        output_commit_dir = os.path.join(project_root, "Dataset/llm_output", repo_name, model_name, commit_id)
        os.makedirs(output_commit_dir, exist_ok=True)

        # # Test before calling LLM
        # repo_path = os.path.join("../", repo_name)
        # os.system(f"cd {repo_path} && git reset --hard {commit_id} && git reset --hard HEAD~1")
        # build_test_log = run_unit_test(repo_name, commit_id)
        # print(build_test_log)

        for prompt_filename in os.listdir(commit_dir):
            if prompt_filename.startswith("prompt") and prompt_filename.endswith(".txt"):
                # prompt_filename: prompt1.txt, prompt2.txt, etc.
                prompt_num_str = prompt_filename[len("prompt"):-len(".txt")]
                total_try += 1
                print(f">>>> {total_try}: Processing prompt file: {commit_id}/{prompt_filename}")

                current_prompt_file_path = os.path.join(commit_dir, prompt_filename)

                output_filename = f"prompt{prompt_num_str}.diff"
                output_path = os.path.join(output_commit_dir, output_filename)

                if os.path.exists(output_path):
                    print(f"Output file {output_path} already exists. Skipping LLM call.")
                    good_try += 1
                    pass_count += 1
                    write_stats(commit_id, prompt_num_str, "pass_existing", "")
                    continue

                with open(current_prompt_file_path, 'r') as f_prompt:
                    prompt_content = f_prompt.read()

                prompt_feedback = prompt_content
                print(f"Calling {model_name} with prompt from {commit_id}/{prompt_filename}...")

                iteration = 0
                max_iterations = 3
                diff_patch = ""
                llm_log = ""
                last_failure_type = ""
                while iteration < max_iterations:
                    iteration += 1
                    status, llm_log, diff_patch = improve_code_with_llm(repo_name, commit_id, prompt_feedback, model_name)
                    if status == "Failed":
                        build_test_log = f"[APPLIED FAILED] Not all generated code changes successfully applied!"
                        print(f"Not all generated code changes successfully applied!")
                        format_fail_count += 1
                        last_failure_type = "format_failed"
                        save_failed_patch(commit_id, prompt_num_str, iteration, diff_patch, llm_log, build_test_log, last_failure_type)
                        continue

                    build_test_log = run_unit_test(repo_name, commit_id)

                    if "[TEST PASSED]" in build_test_log:
                        print(f"Unit test passed after iteration-{iteration}.")
                        break

                    # Self-repair if build/test fails
                    if "[BUILD FAILED]" in build_test_log:
                        failed_prompt = "Build failed"
                        build_fail_count += 1
                        last_failure_type = "build_failed"
                        save_failed_patch(commit_id, prompt_num_str, iteration, diff_patch, llm_log, build_test_log, last_failure_type)
                    elif "[TEST FAILED]" in build_test_log:
                        failed_prompt = "The unit test failed"
                        test_fail_count += 1
                        last_failure_type = "test_failed"
                        save_failed_patch(commit_id, prompt_num_str, iteration, diff_patch, llm_log, build_test_log, last_failure_type)

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

                if "[TEST PASSED]" not in build_test_log:
                    print(f"Build/test failed after {max_iterations} iterations. Skipping...")
                    write_stats(commit_id, prompt_num_str, "fail", last_failure_type)
                    continue

                good_try += 1
                pass_count += 1
                print(f"Build/test pass rate is {good_try}/{total_try}")
                # Save good code changes
                with open(output_path, 'w') as f_out:
                    f_out.write(diff_patch)
                # Also original log
                log_path = output_path + ".log"
                with open(log_path, 'w') as f_out:
                    f_out.write(llm_log)
                write_stats(commit_id, prompt_num_str, "pass", "")

if __name__ == "__main__":
    main()
