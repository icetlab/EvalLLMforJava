import pandas as pd
import io
import os
from scipy.stats import wilcoxon
import re
import glob
import numpy as np
from itertools import combinations

def vargha_delaney_a12(x, y):
    """
    Computes the Vargha-Delaney A12 effect size statistic.
    A12 > 0.5 means x is stochastically larger than y.
    """
    m, n = len(x), len(y)
    if m == 0 or n == 0: return np.nan

    r = np.sum([np.sum(i > j) + 0.5 * np.sum(i == j) for i in x for j in y])
    return r / (m * n)

def analyze_median_scores(df_long, output_dir="comparison_plots"):
    """
    Loads median score data, performs pairwise statistical tests,
    and saves the results to CSV files.
    """
    # --- 1. Process Data ---
    # Map prompt and model names to create a 'Config' column
    prompt_map = {
        "prompt1": "NoHint",
        "prompt2": "Problem",
        "prompt3": "Benchmark",
        "prompt4": "Both"
    }

    df_long['prompt'] = df_long['prompt'].map(prompt_map)
    df_long.rename(columns={'model': 'Model'}, inplace=True)
    df_long['Model'] = df_long['Model'].str.replace('gpt', 'o4-mini', case=False)
    df_long['Model'] = df_long['Model'].str.replace('gemini', 'Gemini', case=False)

    df_long['Config'] = df_long.apply(
        lambda row: 'Developer' if row['Model'] == 'developer' else f"{row['Model']}-{row['prompt']}",
        axis=1
    )

    # --- Pivot the long-format data to wide-format for comparison ---
    df_wide = df_long.pivot_table(
        index='hash_value',
        columns='Config',
        values='final_score'
    ).reset_index()

    # --- Add the Original baseline as a column of 1.0s ---
    df_wide['Original'] = 1.0

    # --- Map prompt names ---
    prompt_map = {
        "prompt1": "NoHint",
        "prompt2": "Problem",
        "prompt3": "Benchmark",
        "prompt4": "Both"
    }

    new_columns = {}
    for col in df_wide.columns:
        # Match both old (GPT/GEMINI) and new (o4-mini/Gemini) naming conventions
        match = re.match(r'(GPT|GEMINI|o4-mini|Gemini)-prompt(\d)', col)
        if match:
            model, prompt_num = match.groups()
            new_prompt_name = prompt_map.get(f"prompt{prompt_num}")
            if new_prompt_name:
                # Standardize model names
                if model == "GPT": model = "o4-mini"
                if model == "GEMINI": model = "Gemini"
                new_columns[col] = f"{model}-{new_prompt_name}"
    df_wide.rename(columns=new_columns, inplace=True)


    # --- 2. Perform Pairwise Statistical Tests ---
    print("\n--- Performing Pairwise Statistical Tests (All Tasks Combined) ---")

    all_configs = [col for col in df_wide.columns if col != 'hash_value']
    config_pairs = list(combinations(all_configs, 2))

    results = []
    for config_a, config_b in config_pairs:
        # Create pairs by aligning on the hash_value index, dropping tasks where either is missing
        pair_df = df_wide[['hash_value', config_a, config_b]].dropna().set_index('hash_value')

        if pair_df.empty or len(pair_df) < 10:
            continue

        # For this analysis, higher is always better as we are using normalized scores
        x = pair_df[config_a]
        y = pair_df[config_b]

        try:
            # Perform the two-sided Wilcoxon test
            _, p_value = wilcoxon(x=x, y=y, alternative='two-sided')

            effect_size = np.nan
            # Only calculate effect size if the result is significant
            if p_value < 0.05:
                effect_size = vargha_delaney_a12(x, y)

            results.append({
                'Config A': config_a,
                'Config B': config_b,
                'P-value': p_value,
                'A12 Effect Size': effect_size
            })
        except ValueError:
            continue

    if not results:
        print("No valid pairwise comparisons could be made.")
        return

    results_df = pd.DataFrame(results)

    # --- 3. Create symmetric matrices and save to CSV ---
    # Create full, symmetric matrices
    p_value_matrix = results_df.pivot(index='Config A', columns='Config B', values='P-value')
    effect_size_matrix = results_df.pivot(index='Config A', columns='Config B', values='A12 Effect Size')

    full_pval_matrix = p_value_matrix.combine_first(p_value_matrix.T)
    full_effect_matrix = effect_size_matrix.combine_first(1 - effect_size_matrix.T)
    np.fill_diagonal(full_pval_matrix.values, 1.0)
    np.fill_diagonal(full_effect_matrix.values, np.nan)

    # Sort and format
    def sort_key_config(config_name):
        prompt_order = ["NoHint", "Problem", "Benchmark", "Both"]
        if config_name == 'Original': return (0, 0)
        if config_name == 'Developer': return (1, 0)
        match = re.search(r'(o4-mini|Gemini)-(.+)', config_name)
        if match:
            model, prompt_name = match.groups()
            model_order = 2 if model == 'o4-mini' else 3
            try:
                prompt_order_index = prompt_order.index(prompt_name)
                return (model_order, prompt_order_index)
            except ValueError:
                return (model_order, 99)
        return (99, 99)

    sorted_index = sorted(full_pval_matrix.index, key=sort_key_config)
    full_pval_matrix = full_pval_matrix.reindex(index=sorted_index, columns=sorted_index)
    full_effect_matrix = full_effect_matrix.reindex(index=sorted_index, columns=sorted_index)

    # Round values for readability
    full_pval_matrix_rounded = full_pval_matrix.round(4)
    full_effect_matrix_rounded = full_effect_matrix.round(3)

    # --- Save results to CSV files ---
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Save pairwise comparison results (long format)
    results_output = os.path.join(output_dir, "pairwise_comparison_results.csv")
    results_df.to_csv(results_output, index=False)
    print(f"Successfully saved pairwise comparison results to {results_output}")
    
    # Save p-value matrix
    pval_output = os.path.join(output_dir, "pvalue_matrix.csv")
    full_pval_matrix_rounded.to_csv(pval_output)
    print(f"Successfully saved p-value matrix to {pval_output}")
    
    # Save effect size matrix
    effect_output = os.path.join(output_dir, "effect_size_matrix.csv")
    full_effect_matrix_rounded.to_csv(effect_output)
    print(f"Successfully saved effect size matrix to {effect_output}")
    
    # Print summary statistics
    print(f"\nTotal pairwise comparisons: {len(results_df)}")
    print(f"Significant comparisons (p < 0.05): {len(results_df[results_df['P-value'] < 0.05])}")
    print(f"\nEffect size matrix shape: {full_effect_matrix.shape}")
    print(f"P-value matrix shape: {full_pval_matrix.shape}")

def analyze_prompt_pairwise_effect_size(df_long, output_dir="comparison_plots"):
    """
    Analyzes pairwise effect sizes between different prompt strategies.
    For each task (hash_value), compares different prompts across all models.
    """
    # --- 1. Process Data (create a copy to avoid modifying original) ---
    df = df_long.copy()
    
    prompt_map = {
        "prompt1": "NoHint",
        "prompt2": "Problem",
        "prompt3": "Benchmark",
        "prompt4": "Both"
    }
    
    # Map prompt values if they are in the original format
    if 'prompt' in df.columns:
        # Check if prompts need mapping (if they contain "prompt1", "prompt2", etc.)
        sample_prompt = df['prompt'].dropna().iloc[0] if not df['prompt'].dropna().empty else None
        if sample_prompt and isinstance(sample_prompt, str) and sample_prompt.startswith('prompt'):
            # Need to map from prompt1/prompt2 format to NoHint/Problem format
            df['prompt'] = df['prompt'].map(prompt_map)
        # If already mapped (NoHint, Problem, etc.), keep as is
    
    # Rename model column if needed
    if 'model' in df.columns:
        df.rename(columns={'model': 'Model'}, inplace=True)
    elif 'Model' not in df.columns:
        # If neither 'model' nor 'Model' exists, something is wrong
        print("Error: No model column found in data")
        return
    
    # Filter out developer and original entries, keep only LLM results
    df_llm = df[df['Model'] != 'developer'].copy()
    df_llm = df_llm[df_llm['prompt'].notna()].copy()
    
    # Debug: print available prompts
    print(f"Available prompts in data: {df_llm['prompt'].unique()}")
    print(f"Number of rows: {len(df_llm)}")
    
    # --- 2. Pivot data: each row is a task (hash_value), columns are prompts ---
    # For each task, collect all prompt scores (across all models)
    # We'll compare prompts by aggregating scores across models for each task
    df_prompt_wide = df_llm.pivot_table(
        index='hash_value',
        columns='prompt',
        values='final_score',
        aggfunc='mean'  # Average across models if multiple models have same prompt for same task
    ).reset_index()
    
    # Debug: print columns after pivot
    print(f"Columns after pivot: {df_prompt_wide.columns.tolist()}")
    
    # Get the four prompts
    prompts = ["NoHint", "Problem", "Benchmark", "Both"]
    available_prompts = [p for p in prompts if p in df_prompt_wide.columns]
    
    print(f"Available prompts for comparison: {available_prompts}")
    
    if len(available_prompts) < 2:
        print("Not enough prompts to perform pairwise comparison.")
        print(f"Expected prompts: {prompts}")
        print(f"Found prompts in data: {df_prompt_wide.columns.tolist()}")
        return
    
    # --- 3. Perform Pairwise Statistical Tests between Prompts ---
    print("\n--- Performing Pairwise Statistical Tests between Prompts ---")
    
    prompt_pairs = list(combinations(available_prompts, 2))
    results = []
    
    for prompt_a, prompt_b in prompt_pairs:
        # Create pairs by aligning on hash_value, dropping tasks where either prompt is missing
        pair_df = df_prompt_wide[['hash_value', prompt_a, prompt_b]].dropna().set_index('hash_value')
        
        if pair_df.empty or len(pair_df) < 10:
            continue
        
        x = pair_df[prompt_a]
        y = pair_df[prompt_b]
        
        try:
            # Perform the two-sided Wilcoxon test
            _, p_value = wilcoxon(x=x, y=y, alternative='two-sided')
            
            effect_size = np.nan
            # Only calculate effect size if the result is significant
            if p_value < 0.05:
                effect_size = vargha_delaney_a12(x, y)
            
            results.append({
                'Prompt A': prompt_a,
                'Prompt B': prompt_b,
                'P-value': p_value,
                'A12 Effect Size': effect_size,
                'N (tasks)': len(pair_df)
            })
        except ValueError:
            continue
    
    if not results:
        print("No valid pairwise comparisons could be made between prompts.")
        return
    
    results_df = pd.DataFrame(results)
    
    # --- 4. Create symmetric matrices and save to CSV ---
    p_value_matrix = results_df.pivot(index='Prompt A', columns='Prompt B', values='P-value')
    effect_size_matrix = results_df.pivot(index='Prompt A', columns='Prompt B', values='A12 Effect Size')
    
    # Create symmetric matrices
    full_pval_matrix = p_value_matrix.combine_first(p_value_matrix.T)
    full_effect_matrix = effect_size_matrix.combine_first(1 - effect_size_matrix.T)
    
    # Fill diagonal
    np.fill_diagonal(full_pval_matrix.values, 1.0)
    np.fill_diagonal(full_effect_matrix.values, np.nan)
    
    # Sort by prompt order
    prompt_order = ["NoHint", "Problem", "Benchmark", "Both"]
    sorted_prompts = [p for p in prompt_order if p in full_pval_matrix.index]
    full_pval_matrix = full_pval_matrix.reindex(index=sorted_prompts, columns=sorted_prompts)
    full_effect_matrix = full_effect_matrix.reindex(index=sorted_prompts, columns=sorted_prompts)
    
    # Round values
    full_pval_matrix_rounded = full_pval_matrix.round(4)
    full_effect_matrix_rounded = full_effect_matrix.round(3)
    
    # --- 5. Save results to CSV files ---
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Save pairwise comparison results (long format)
    prompt_results_output = os.path.join(output_dir, "prompt_pairwise_comparison_results.csv")
    results_df.to_csv(prompt_results_output, index=False)
    print(f"Successfully saved prompt pairwise comparison results to {prompt_results_output}")
    
    # Save p-value matrix
    prompt_pval_output = os.path.join(output_dir, "prompt_pvalue_matrix.csv")
    full_pval_matrix_rounded.to_csv(prompt_pval_output)
    print(f"Successfully saved prompt p-value matrix to {prompt_pval_output}")
    
    # Save effect size matrix
    prompt_effect_output = os.path.join(output_dir, "prompt_effect_size_matrix.csv")
    full_effect_matrix_rounded.to_csv(prompt_effect_output)
    print(f"Successfully saved prompt effect size matrix to {prompt_effect_output}")
    
    # Print summary statistics
    print(f"\nTotal prompt pairwise comparisons: {len(results_df)}")
    print(f"Significant comparisons (p < 0.05): {len(results_df[results_df['P-value'] < 0.05])}")
    print(f"\nPrompt effect size matrix shape: {full_effect_matrix.shape}")
    print(f"Prompt p-value matrix shape: {full_pval_matrix.shape}")

if __name__ == "__main__":
    # Define the path to your input file
    input_csv_path = '../preprocessing/summary_tables/median_performance_scores.csv'
    output_directory = "comparison_plots"

    try:
        # Load the data from the specified CSV file
        df_from_file = pd.read_csv(input_csv_path)
        print(f"Successfully loaded data from {input_csv_path}")
        # Run the analysis using the loaded data
        analyze_median_scores(df_from_file.copy(), output_dir=output_directory)
        
        # Also analyze prompt pairwise comparisons (reload to ensure original format)
        print("\n" + "="*80)
        df_from_file_fresh = pd.read_csv(input_csv_path)
        analyze_prompt_pairwise_effect_size(df_from_file_fresh, output_dir=output_directory)
    except FileNotFoundError:
        print(f"Error: The file '{input_csv_path}' was not found. Please ensure it exists in the correct path.")
    except Exception as e:
        print(f"An error occurred: {e}")