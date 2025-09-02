import pandas as pd
import io
import os
from scipy.stats import wilcoxon
import re
import glob
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
import matplotlib.patches as mpatches
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
    and visualizes the results as two heatmaps.
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

    # --- 3. Plot the Heatmap ---
    # Create full, symmetric matrices
    p_value_matrix = results_df.pivot(index='Config A', columns='Config B', values='P-value')
    effect_size_matrix = results_df.pivot(index='Config A', columns='Config B', values='A12 Effect Size')

    full_pval_matrix = p_value_matrix.combine_first(p_value_matrix.T)
    full_effect_matrix = effect_size_matrix.combine_first(1 - effect_size_matrix.T)
    print(full_effect_matrix.to_string())
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
    rounded_effect_matrix = full_effect_matrix.round(2)

    # --- Define custom colormap and categorization function ---
    def classify_effect_size(a12):
        if pd.isna(a12):
            return np.nan
        
        if 0.44 < a12 < 0.56:
            return 0  # Negligible
        elif 0.56 <= a12 < 0.64 or 0.36 < a12 <= 0.44:
            return 0  # Small
        elif 0.64 <= a12 < 0.71 or 0.29 < a12 <= 0.36:
            return 1  # Medium
        else: # (a12 >= 0.71 or a12 <= 0.29)
            return 2  # Large

    effect_category_matrix = rounded_effect_matrix.applymap(classify_effect_size)
    effect_cmap = ListedColormap(['#D4D4E9', '#8C8CC8', '#7059C8'])


    # --- Create the Effect Size Heatmap ---
    fig, ax = plt.subplots(1, 1, figsize=(12, 10))

    ax.set_facecolor('white')
    sns.heatmap(
        effect_category_matrix, # Use category matrix for colors
        ax=ax,
        annot=rounded_effect_matrix, # Use original matrix for annotations
        fmt=".2f",
        cmap=effect_cmap, # Use the custom colormap
        linewidths=.5,
        annot_kws={"size": 15},
        square=True,
        cbar=False # Disable the default colorbar
    )
    ax.set_title("Effect Size (Vargha-Delaney A12)", fontsize=19, pad=20)
    ax.set_xlabel('')
    ax.set_ylabel('')
    
    # --- MODIFICATION: Rotate x-axis labels to be vertical ---
    ax.tick_params(axis='x', labelsize=17, rotation=90)
    ax.tick_params(axis='y', labelsize=17, rotation=0)

    legend_patches = [
        mpatches.Patch(color='#7059C8', label='Large\n(A ≤ 0.29 or A ≥ 0.71)'),
        mpatches.Patch(color='#8C8CC8', label='Medium\n(0.29 < A ≤ 0.36 or 0.64 ≤ A < 0.71)'),
        mpatches.Patch(color='#D4D4E9', label='Small\n(0.36 < A ≤ 0.44 or 0.56 ≤ A < 0.64)'),
        mpatches.Patch(color='#EAEAF3', label='Negligible\n(0.44 < A < 0.56)')
    ]
    ax.legend(
        handles=legend_patches,
        loc='center left', 
        bbox_to_anchor=(1.02, 0.5),
        ncol=1,
        frameon=False,
        fontsize=15
    )

    plt.tight_layout()

    # --- Save the plot ---
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_filename = os.path.join(output_dir, "final_pairwise_statistical_heatmaps.pdf")
    try:
        # Use bbox_inches='tight' to ensure labels and legend are not cut off
        plt.savefig(output_filename, bbox_inches='tight')
        print(f"Successfully saved final pairwise heatmaps to {output_filename}")
    except Exception as e:
        print(f"Could not save plot. Error: {e}")

    plt.show()

if __name__ == "__main__":
    # Define the path to your input file
    input_csv_path = '../summary_tables/median_performance_scores.csv'
    output_directory = "comparison_plots"

    try:
        # Load the data from the specified CSV file
        df_from_file = pd.read_csv(input_csv_path)
        print(f"Successfully loaded data from {input_csv_path}")
        # Run the analysis using the loaded data
        analyze_median_scores(df_from_file, output_dir=output_directory)
    except FileNotFoundError:
        print(f"Error: The file '{input_csv_path}' was not found. Please ensure it exists in the correct path.")
    except Exception as e:
        print(f"An error occurred: {e}")