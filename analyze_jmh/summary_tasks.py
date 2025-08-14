import pandas as pd
import os
import glob
from scipy.stats import gmean
import numpy as np

def load_summary_data_from_csv(project_names):
    """
    Loads and combines benchmark summary CSVs for specified projects.
    These CSVs are expected to have the 'normalized_performance' column already.

    Args:
        project_names (list): A list of project names to load data for.

    Returns:
        DataFrame or None: A pandas DataFrame with the combined data, or None if no data is found.
    """
    all_dfs = []
    for project in project_names:
        csv_path = f"{project}_benchmark_summary.csv"
        try:
            df = pd.read_csv(csv_path)
            # Clean up params column if it has quotes from the previous script
            df['params'] = df['params'].str.strip('"')
            df['project'] = project
            all_dfs.append(df)
        except FileNotFoundError:
            print(f"Warning: The file '{csv_path}' was not found. Skipping.")
            continue
    
    if not all_dfs:
        print("Error: No CSV files found for the specified projects.")
        return None

    combined_df = pd.concat(all_dfs)
    
    # Filter out original model as it's not needed for this summary
    combined_df = combined_df[combined_df['model'] != 'original'].copy()
    
    # Drop rows where normalization might have failed (is NaN)
    combined_df.dropna(subset=['normalized_performance'], inplace=True)

    return combined_df

def summarize_performance_by_hash(project_names, output_dir="summary_tables", data=None):
    """
    Summarizes performance for each task (hash) into a table, applying special
    selection logic for LLM solutions based on their trials.
    """
    if data is None:
        data = load_summary_data_from_csv(project_names)
        if data is None: return

    # 1. Select the representative LLM solution
    llm_data = data[data['model'].isin(['gpt', 'gemini'])].copy()
    
    # 1.1: Calculate a single performance score (GMean) for each individual solution (trial).
    solution_gmeans = llm_data.groupby(['hash_value', 'benchmark_name', 'model', 'prompt', 'trial']) \
                              .agg(gmean_perf=('normalized_performance', gmean)).reset_index()

    # 1.2: Apply the selection logic to choose the BEST solution.
    selected_trials = []
    # for name, group in solution_gmeans.groupby(['hash_value', 'benchmark_name', 'model', 'prompt']):
    #     best_solution = group.nlargest(1, 'gmean_perf')
    #     selected_trials.append(best_solution)
    for name, group in solution_gmeans.groupby(['hash_value', 'benchmark_name', 'model', 'prompt']):
        if len(group) == 1:
            selected_trials.append(group)
        elif len(group) == 2:
            # Select the trial with the worse (lower) GMean performance
            selected_trials.append(group.nsmallest(1, 'gmean_perf'))
        elif len(group) == 3:
            # Select the trial with the median GMean performance
            sorted_group = group.sort_values('gmean_perf')
            selected_trials.append(sorted_group.iloc[[1]])

    if not selected_trials:
        print("Warning: No LLM solutions remained after selection.")
        final_llm_data = pd.DataFrame()
    else:
        selected_df = pd.concat(selected_trials)
        # Use the selected trials to filter the main dataframe
        final_llm_data = data.merge(selected_df[['hash_value', 'benchmark_name', 'model', 'prompt', 'trial']],
                                    on=['hash_value', 'benchmark_name', 'model', 'prompt', 'trial'])

    # 2. Combine with developer data and calculate final metrics ---
    dev_data = data[data['model'] == 'developer']
    final_data = pd.concat([dev_data, final_llm_data])

    prompt_mapping = {"prompt1": "Zero-Hint", "prompt2": "Semantic-Hint", "prompt3": "Structural-Hint", "prompt4": "Hybrid-Hint"}
    final_data['prompt'] = final_data['prompt'].map(prompt_mapping).fillna('N/A')

    # Step 2.1: Aggregate all data points for a task to get the final GMean and Median.
    summary = final_data.groupby(['hash_value', 'model', 'prompt']) \
                        .agg(GMean=('normalized_performance', gmean),
                             Median=('normalized_performance', 'median')).reset_index()

    # 3. Pivot data into the final table structure ---
    if summary.empty:
        print("Warning: No data available to create the summary table.")
        return

    summary['Metric'] = summary.apply(lambda row: f"{row['GMean']:.2f} ({row['Median']:.2f})", axis=1)
    summary['Config'] = summary.apply(lambda row: row['model'] if row['model'] == 'developer' else f"{row['model'].upper()}-{row['prompt']}", axis=1)
    
    final_table = summary.pivot_table(index='hash_value', columns='Config', values='Metric', aggfunc='first')

    # 4. Robustly reorder columns ---
    new_order = []
    if 'developer' in final_table.columns:
        new_order.append('developer')
    
    gpt_cols = sorted([c for c in final_table.columns if 'GPT' in c])
    gemini_cols = sorted([c for c in final_table.columns if 'GEMINI' in c])
    
    new_order.extend(gpt_cols)
    new_order.extend(gemini_cols)
    
    existing_cols = [col for col in new_order if col in final_table.columns]
    final_table = final_table[existing_cols]

    # 5. Save and output ---
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    csv_filename = os.path.join(output_dir, 'hash_performance_summary_medium_solution.csv')
    final_table.to_csv(csv_filename)
    print(f"\nSaved hash performance summary (best solution) to {csv_filename}")

    print(final_table.head().to_string())

if __name__ == "__main__":
    projects = ['kafka', 'netty', 'presto', 'RoaringBitmap']
    output_directory = "summary_tables"
    
    summarize_performance_by_hash(project_names=projects, output_dir=output_directory)
