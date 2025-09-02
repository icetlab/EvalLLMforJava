import pandas as pd
import os
import re

def analyze_performance_tiers_from_scores(scores_csv_path, output_dir="summary_tables"):
    """
    Loads the representative benchmark scores and categorizes them into several tiers.
    """
    try:
        final_scores = pd.read_csv(scores_csv_path)
    except FileNotFoundError:
        print(f"Error: The scores file was not found at '{scores_csv_path}'")
        return

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

    final_scores['Tier'] = final_scores['final_score'].apply(categorize_performance)

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
        
    # --- Add a 'Total' row ---
    total_counts = tier_counts.sum()
    total_percentages = total_counts / total_counts.sum() * 100
    
    total_row_data = {}
    for tier in all_tiers:
        total_row_data[f'{tier} (Count)'] = [total_counts[tier]]
        total_row_data[f'{tier} (%)'] = [total_percentages[tier].round(2)]

    total_row = pd.DataFrame(total_row_data, index=['Total'])
    
    summary_df = pd.concat([summary_df, total_row])

    # --- 5. Save and output ---
    summary_text = summary_df.to_string()
    print("\n--- Tiered Performance Analysis (Representative Scores) ---")
    print(summary_text)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    summary_filename = os.path.join(output_dir, 'tiered_performance_summary_representative.txt')
    with open(summary_filename, 'w') as f:
        f.write("Tiered Performance Analysis (Representative Scores)\n")
        f.write(summary_text)
    print(f"\nTiered performance summary saved to {summary_filename}")


if __name__ == "__main__":
    # Define the paths to your data directories and files
    base_dir = os.getcwd()
    output_directory = os.path.join(base_dir, 'summary_tables')
    scores_file_path = os.path.join(output_directory, 'representative_benchmark_scores.csv')

    analyze_performance_tiers_from_scores(scores_file_path, output_dir=output_directory)
