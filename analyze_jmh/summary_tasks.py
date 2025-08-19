import pandas as pd
import os
import glob
from scipy.stats import gmean
import numpy as np
import re

def load_summary_data_from_csv(project_names):
    """
    Loads and combines benchmark summary CSVs for specified projects.
    It filters out tasks that do not have at least one LLM result to ensure
    all analyzed tasks have a valid developer vs. LLM comparison.

    Args:
        project_names (list): A list of project names to load data for.

    Returns:
        DataFrame or None: A pandas DataFrame with the cleaned and filtered data, or None.
    """
    all_dfs = []
    for project in project_names:
        csv_path = f"summary_csv/{project}_benchmark_summary.csv"
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

    # --- Filter out tasks that only have developer results ---
    # 1. Find all tasks (hashes) that have at least one LLM result.
    llm_hashes = combined_df[combined_df['model'].isin(['gpt', 'gemini'])]['hash_value'].unique()
    
    # 2. Keep only the data for those tasks (this includes developer results for those tasks).
    filtered_df = combined_df[combined_df['hash_value'].isin(llm_hashes)]
    
    if filtered_df.empty:
        print("Warning: No tasks with corresponding LLM results found after filtering.")
        return None

    return filtered_df

def gsd(x):
    """Calculates the Geometric Standard Deviation."""
    # Filter out non-positive values before log
    x_positive = x[x > 0]
    if len(x_positive) < 2:
        return 1.0 # Cannot compute GSD for less than 2 points
    return np.exp(np.std(np.log(x_positive)))

def calculate_final_scores(data):
    """
    Calculates the final performance score (GMean and GSD) for every single trial/solution.
    A solution is defined by its project, hash, model, prompt, and trial.
    This function aggregates over all benchmarks and params for that solution.
    """
    data_for_scores = data.copy()
    data_for_scores[['prompt', 'trial']] = data_for_scores[['prompt', 'trial']].fillna('N/A')
    
    # FIX: Removed 'benchmark_name' to aggregate over all benchmarks for a given solution
    final_scores = data_for_scores.groupby(['project', 'hash_value', 'model', 'prompt', 'trial']) \
                       .agg(GMean=('normalized_performance', gmean),
                            GSD=('normalized_performance', gsd)).reset_index()
    return final_scores

def summarize_performance_by_hash(project_names, output_dir="summary_tables", data=None):
    """
    Summarizes performance for each task (hash) into a table, applying special
    selection logic for LLM solutions, grouping by project, and sorting by impact.
    Averages are calculated fairly, giving each task equal weight.
    """
    if data is None:
        data = load_summary_data_from_csv(project_names)
        if data is None: 
            print("Aborting summary as no valid data was loaded.")
            return

    # 1. Calculate final scores for ALL trials first
    final_scores = calculate_final_scores(data)

    # 2. Select the representative LLM solution from the calculated scores
    llm_scores = final_scores[final_scores['model'].isin(['gpt', 'gemini'])].copy()
    
    selected_trials = []
    # FIX: Removed 'benchmark_name' from the groupby
    for name, group in llm_scores.groupby(['hash_value', 'model', 'prompt']):
        if len(group) == 1:
            selected_trials.append(group)
        elif len(group) == 2:
            selected_trials.append(group.nsmallest(1, 'GMean'))
        elif len(group) == 3:
            sorted_group = group.sort_values('GMean')
            selected_trials.append(sorted_group.iloc[[1]])

    if not selected_trials:
        print("Warning: No LLM solutions remained after selection.")
        summary_per_task = final_scores[final_scores['model'] == 'developer'].copy()
    else:
        selected_df = pd.concat(selected_trials)
        dev_scores = final_scores[final_scores['model'] == 'developer']
        summary_per_task = pd.concat([dev_scores, selected_df])

    # 3. Pivot data into the final table structure with task details
    summary_per_task['prompt'] = summary_per_task['prompt'].fillna('N/A')
    
    if summary_per_task.empty:
        print("Warning: No data available to create the summary table.")
        return

    summary_per_task['Metric'] = summary_per_task.apply(lambda row: f"{row['GMean']:.2f} (±{row['GSD']:.2f})", axis=1)
    summary_per_task['Config'] = summary_per_task.apply(lambda row: row['model'] if row['model'] == 'developer' else f"{row['model'].upper()}-{row['prompt']}", axis=1)
    
    dev_gmean_for_sorting = summary_per_task[summary_per_task['model'] == 'developer'][['project', 'hash_value', 'GMean']].rename(columns={'GMean': 'dev_gmean'})

    final_table_details = summary_per_task.pivot_table(index=['project', 'hash_value'], columns='Config', values='Metric', aggfunc='first')
    
    # 4. Group by project, sort tasks within, and add FAIR project averages
    all_project_blocks = []
    for project in project_names:
        if project not in final_table_details.index.get_level_values('project'):
            continue
        
        project_table = final_table_details.loc[project].copy()
        project_table.reset_index(inplace=True)
        
        project_table = project_table.merge(dev_gmean_for_sorting[dev_gmean_for_sorting['project'] == project], on='hash_value', how='left')
        project_table.sort_values(by='dev_gmean', ascending=False, inplace=True)
        project_table.drop(columns=['dev_gmean', 'project'], inplace=True, errors='ignore')
        project_table.set_index('hash_value', inplace=True)
        
        project_summary_data = summary_per_task[summary_per_task['project'] == project]
        project_overall = project_summary_data.groupby('Config').agg(
            GMean=('GMean', gmean),
            GSD=('GSD', gmean)
        )
        overall_row = {
            config: f"{agg['GMean']:.2f} (±{agg['GSD']:.2f})"
            for config, agg in project_overall.iterrows()
        }
        overall_row_df = pd.DataFrame([overall_row], index=[f'{project.upper()} Average'])
        
        project_header = pd.DataFrame([None]*len(project_table.columns), index=project_table.columns, columns=[f'--- {project.upper()} ---']).T
        all_project_blocks.append(pd.concat([project_header, project_table, overall_row_df]))

    if not all_project_blocks:
        print("No data to display after processing projects.")
        return
        
    full_final_table = pd.concat(all_project_blocks)
    
    # 5. Add fair OVERALL average row at the end
    overall_summary = summary_per_task.groupby('Config').agg(
        GMean=('GMean', gmean),
        GSD=('GSD', gmean)
    )
    overall_row = {
        config: f"{agg['GMean']:.2f} (±{agg['GSD']:.2f})"
        for config, agg in overall_summary.iterrows()
    }
    overall_row_df = pd.DataFrame([overall_row], index=['Overall Average'])
    full_final_table = pd.concat([full_final_table, overall_row_df])

    # 6. Robustly reorder columns and save
    def sort_key_config(col):
        if col == 'developer':
            return (0, 0)
        match = re.search(r'(GPT|GEMINI)-prompt(\d+)', col)
        if match:
            model = match.group(1)
            prompt_num = int(match.group(2))
            model_order = 1 if model == 'GPT' else 2
            return (model_order, prompt_num)
        return (99, 99)

    sorted_cols = sorted([c for c in full_final_table.columns], key=sort_key_config)
    full_final_table = full_final_table[sorted_cols]

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    csv_filename = os.path.join(output_dir, 'hash_performance_summary_grouped_fair_avg.csv')
    full_final_table.to_csv(csv_filename)
    print(f"\nSaved fair-average grouped hash performance summary to {csv_filename}")
    print("\n--- Grouped Hash Performance Summary (GMean (±GSD)) with Fair Averages ---")
    print(full_final_table.to_string())

def analyze_performance_tiers(project_names, output_dir="summary_tables", data=None):
    """
    Analyzes all solutions by categorizing their final performance score
    into several tiers (e.g., Major Improvement, Regression).
    """
    if data is None:
        data = load_summary_data_from_csv(project_names)
        if data is None: return

    # --- 1. Calculate the "final score" for every single solution ---
    final_scores = calculate_final_scores(data)

    # --- 2. Redefined categorization logic ---
    def categorize_performance(score):
        if score < 0.90:
            return 'Major Regression (<0.9x)'
        elif 0.90 <= score < 0.95:
            return 'Minor Regression (0.9x-0.95x)'
        elif 0.95 <= score <= 1.05:
            return 'No Substantial Change (0.95x-1.05x)'
        elif 1.05 < score <= 1.1:
            return 'Minor Improvement (1.05x-1.1x)'
        elif 1.1 < score <= 1.50:
            return 'Major Improvement (1.1x-1.5x)'
        else: # score > 1.50
            return 'Massive Improvement (>1.5x)'

    # Use the 'GMean' column from the new calculate_final_scores function
    final_scores['Tier'] = final_scores['GMean'].apply(categorize_performance)

    final_scores['prompt'] = final_scores['prompt'].fillna('N/A')
    final_scores['Config'] = final_scores.apply(lambda row: row['model'] if row['model'] == 'developer' else f"{row['model'].upper()}-{row['prompt']}", axis=1)

    tier_counts = pd.crosstab(final_scores['Config'], final_scores['Tier'])
    
    # --- Updated list of all possible tiers ---
    all_tiers = [
        'Major Regression (<0.9x)', 
        'Minor Regression (0.9x-0.95x)', 
        'No Substantial Change (0.95x-1.05x)', 
        'Minor Improvement (1.05x-1.1x)', 
        'Major Improvement (1.1x-1.5x)', 
        'Massive Improvement (>1.5x)'
    ]
    for tier in all_tiers:
        if tier not in tier_counts.columns:
            tier_counts[tier] = 0
    tier_counts = tier_counts[all_tiers] # Enforce order

    def sort_key_config(config_name):
        if config_name == 'developer':
            return (0, 0)
        match = re.search(r'(GPT|GEMINI)-prompt(\d+)', config_name)
        if match:
            model = match.group(1)
            prompt_num = int(match.group(2))
            model_order = 1 if model == 'GPT' else 2
            return (model_order, prompt_num)
        return (99, 99)

    sorted_index = sorted(tier_counts.index, key=sort_key_config)
    tier_counts = tier_counts.reindex(sorted_index)

    tier_percentages = tier_counts.div(tier_counts.sum(axis=1), axis=0) * 100

    summary_df = pd.DataFrame()
    for tier in all_tiers:
        summary_df[f'{tier} (Count)'] = tier_counts[tier]
        summary_df[f'{tier} (%)'] = tier_percentages[tier].round(2)
        
    # --- NEW: Add a 'Total' row ---
    total_counts = tier_counts.sum()
    total_percentages = total_counts / total_counts.sum() * 100
    
    total_row = pd.DataFrame(
        {f'{tier} (Count)': [total_counts[tier]] for tier in all_tiers} | 
        {f'{tier} (%)': [total_percentages[tier].round(2)] for tier in all_tiers},
        index=['Total']
    )
    
    summary_df = pd.concat([summary_df, total_row])

    # --- 5. Save and output ---
    summary_text = summary_df.to_string()
    print("\n--- Tiered Performance Analysis (All Solutions by Final Score) ---")
    print(summary_text)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    summary_filename = os.path.join(output_dir, 'tiered_performance_summary.txt')
    with open(summary_filename, 'w') as f:
        f.write("Tiered Performance Analysis (All Solutions by Final Score)\n")
        f.write(summary_text)
    print(f"\nTiered performance summary saved to {summary_filename}")

if __name__ == "__main__":
    projects = ['kafka', 'netty', 'presto', 'RoaringBitmap']
    output_directory = "summary_tables"
    
    # Load data once
    full_data = load_summary_data_from_csv(projects)

    if full_data is not None:
        # print("--- Generating Grouped Hash Performance Summary Table (Median/Worse Solution) ---")
        # summarize_performance_by_hash(project_names=projects, output_dir=output_directory, data=full_data)
        
        # print("\n--- Generating All-Trial Performance Summary ---")
        # summarize_all_trials_by_hash(project_names=projects, output_dir=output_directory, data=full_data)

        print("\n--- Analyzing Tiered Performance (All Solutions by Final Score) ---")
        analyze_performance_tiers(project_names=projects, output_dir=output_directory, data=full_data)
