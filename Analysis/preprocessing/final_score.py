import pandas as pd
import os
import glob
from scipy.stats import gmean
import numpy as np
import re

def load_summary_data_from_csv(project_names, summary_csv_dir):
    """
    Loads and combines benchmark summary CSVs for specified projects.
    These CSVs are expected to have the 'normalized_performance' column.

    Args:
        project_names (list): A list of project names to load data for.
        summary_csv_dir (str): The directory containing the summary CSV files.

    Returns:
        DataFrame or None: A pandas DataFrame with the combined data, or None if no data is found.
    """
    all_dfs = []
    for project in project_names:
        csv_path = os.path.join(summary_csv_dir, f"{project}_benchmark_summary.csv")
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
    combined_df = combined_df[combined_df['model'] != 'original'].copy()
    combined_df.dropna(subset=['normalized_performance'], inplace=True)
    return combined_df

def calculate_representative_benchmark_scores(data, output_path):
    """
    Calculates the final score for each solution based on a "representative benchmark"
    for each task. The representative benchmark is the one where the developer
    achieved their highest performance score.
    """
    if data is None:
        print("No data provided to calculate scores.")
        return

    # --- Pre-filter to only include tasks that have a developer solution ---
    dev_hashes = data[data['model'] == 'developer']['hash_value'].unique()
    filtered_data = data[data['hash_value'].isin(dev_hashes)].copy()
    print(f"Found {len(dev_hashes)} tasks with developer solutions to analyze.")

    # --- FIX: Handle NaN values in the 'params' column to correctly match benchmarks without parameters ---
    # By filling NaN with an empty string, we ensure that NaN == NaN comparisons work as expected.
    filtered_data['params'].fillna('', inplace=True)

    # --- 1. Identify the representative benchmark for each task ---
    developer_data = filtered_data[filtered_data['model'] == 'developer'].copy().reset_index(drop=True)
    
    # Find the index of the row with the maximum performance for each task (hash_value)
    idx = developer_data.groupby(['hash_value'])['normalized_performance'].idxmax()
    representative_benchmarks_df = developer_data.loc[idx]
    
    # Keep only the columns needed to identify the representative benchmark
    representative_benchmarks = representative_benchmarks_df[['hash_value', 'benchmark_name', 'params']].copy()
    representative_benchmarks.rename(columns={'benchmark_name': 'rep_benchmark', 'params': 'rep_params'}, inplace=True)
    
    print(f"Identified {len(representative_benchmarks)} unique representative benchmarks.")

    # --- 2. Merge this information back to the main dataframe ---
    merged_data = pd.merge(filtered_data, representative_benchmarks, on='hash_value', how='left')
    
    # --- 3. Filter to keep only the scores from the representative benchmark for each task ---
    final_scores_df = merged_data[
        (merged_data['benchmark_name'] == merged_data['rep_benchmark']) &
        (merged_data['params'] == merged_data['rep_params'])
    ].copy()
    
    # --- 4. Clean up and format the final DataFrame ---
    final_scores_df.rename(columns={'normalized_performance': 'final_score'}, inplace=True)
    
    # Select and reorder columns
    output_cols = ['project', 'hash_value', 'model', 'prompt', 'trial', 'final_score']
    final_scores_df = final_scores_df.reindex(columns=output_cols)
    
    # Sort for readability
    final_scores_df.sort_values(by=['project', 'hash_value', 'model', 'prompt', 'trial'], inplace=True)

    # Save to CSV
    try:
        final_scores_df.to_csv(output_path, index=False, float_format='%.4f')
        print(f"\nSuccessfully calculated and saved {len(final_scores_df)} representative scores to {output_path}")
        print("\n--- Representative Scores (Snippet) ---")
        print(final_scores_df.head().to_string())
    except Exception as e:
        print(f"Error saving file to {output_path}: {e}")


if __name__ == "__main__":
    projects = ['kafka', 'netty', 'presto', 'RoaringBitmap']
    
    # Define the paths to your data directories and files
    base_dir = os.getcwd()
    summary_csv_directory = os.path.join(base_dir, 'summary_csv')
    output_directory = os.path.join(base_dir, 'summary_tables')

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # Define the name for the new output file
    output_file_path = os.path.join(output_directory, 'representative_benchmark_scores.csv')

    # 1. Load the data
    normalized_data = load_summary_data_from_csv(projects, summary_csv_directory)
    
    # 2. Calculate and save the final scores based on the new logic
    if normalized_data is not None:
        calculate_representative_benchmark_scores(normalized_data, output_file_path)
