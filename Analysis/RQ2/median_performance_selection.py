import pandas as pd
import os
from scipy.stats import gmean

def select_median_scores(input_csv_path, output_csv_path, project_avg_path):
    """
    Loads scores, selects the representative trial for each model-prompt 
    combination, adds a comparison flag column, sorts tasks by developer performance,
    and calculates final project and overall averages.

    Args:
        input_csv_path (str): Path to the 'representative_benchmark_scores.csv' file.
        output_csv_path (str): Path to save the new CSV with median scores and flags.
        project_avg_path (str): Path to save the calculated project averages.
    """
    # --- 1. Load the pre-calculated scores ---
    try:
        df = pd.read_csv(input_csv_path)
        print(f"Successfully loaded {len(df)} rows from {input_csv_path}")
    except FileNotFoundError:
        print(f"Error: The scores file was not found at '{input_csv_path}'.")
        return

    # --- 2. Separate developer data from LLM data ---
    developer_df = df[df['model'] == 'developer'].copy()
    llm_scores = df[df['model'] != 'developer'].copy()
    
    # --- 3. Apply the selection logic for LLM solutions ---
    selected_trials = []
    llm_scores['prompt'] = llm_scores['prompt'].fillna('N/A')
    
    for name, group in llm_scores.groupby(['hash_value', 'model', 'prompt']):
        # --- UPDATED SELECTION LOGIC ---
        if len(group) == 1:
            # If there's only one trial, use it.
            selected_trials.append(group)
        elif len(group) == 2:
            # If there are two trials, conservatively use the worse-performing one.
            selected_trials.append(group.nsmallest(1, 'final_score'))
        elif len(group) == 3:
            # If there are three trials, use the median-performing one.
            sorted_group = group.sort_values('final_score')
            selected_trials.append(sorted_group.iloc[[1]])
        # Note: This logic assumes no more than 3 trials per group.

    if not selected_trials:
        print("Warning: No LLM solutions remained after selection.")
        median_llm_df = pd.DataFrame()
    else:
        median_llm_df = pd.concat(selected_trials)

    # --- 4. Combine developer and selected LLM data ---
    final_df = pd.concat([developer_df, median_llm_df])
    
    # --- 5. Add the comparison flag column ---
    dev_score_map = developer_df.set_index('hash_value')['final_score'].to_dict()

    def apply_flags(row):
        if row['model'] == 'developer':
            return ''
        llm_score = row['final_score']
        dev_score = dev_score_map.get(row['hash_value'])
        if dev_score is not None and llm_score > dev_score:
            return 'outperforms_developer'
        elif llm_score < 1.0:
            return 'worse_than_original'
        return ''

    final_df['comparison_flag'] = final_df.apply(apply_flags, axis=1)
    
    # --- 6. Sort the final dataframe ---
    final_df['dev_sort_score'] = final_df['hash_value'].map(dev_score_map)
    final_df.sort_values(
        by=['project', 'dev_sort_score', 'model', 'prompt'],
        ascending=[True, False, True, True],
        inplace=True
    )
    final_df.drop(columns=['dev_sort_score'], inplace=True)

    try:
        # Save the DataFrame to the CSV file
        final_df.to_csv(output_csv_path, index=False, float_format='%.2f')
        print(f"\nSuccessfully selected representative scores, added flags, and saved {len(final_df)} rows to {output_csv_path}")
        
        # --- 7. Verification Step ---
        print("\n--- Verifying the saved file ---")
        saved_df = pd.read_csv(output_csv_path)
        print(f"Columns found in the saved file: {saved_df.columns.tolist()}")
        
        if 'comparison_flag' in saved_df.columns:
            print("Verification successful: 'comparison_flag' column is present in the saved CSV file.")
        else:
            print("Verification failed: 'comparison_flag' column is MISSING from the saved CSV file.")

        print("\n--- Representative Scores with Flags (Snippet from memory) ---")
        print(final_df.head().to_string())

    except Exception as e:
        print(f"Error during file operation: {e}")

    # --- 8. Calculate and save project and overall averages ---
    print("\n--- Calculating Project and Overall Averages ---")
    # Create a consistent 'Config' column for grouping
    final_df['Config'] = final_df.apply(
        lambda row: 'developer' if row['model'] == 'developer' else f"{row['model']}-{row['prompt']}",
        axis=1
    )
    
    # Calculate geometric mean for each project-config group
    project_averages = final_df.groupby(['project', 'Config'])['final_score'].apply(gmean).reset_index()
    
    # Pivot the table to get a wide format for project averages
    project_averages_pivot = project_averages.pivot(index='project', columns='Config', values='final_score')
    
    # Calculate the overall average across all projects
    overall_averages = final_df.groupby('Config')['final_score'].apply(gmean)
    overall_averages.name = 'Overall Average' # Rename the series
    
    # Append the overall average as a new row
    project_averages_pivot = pd.concat([project_averages_pivot, pd.DataFrame(overall_averages).T])

    # Sort columns for readability
    sorted_columns = sorted(project_averages_pivot.columns, key=lambda x: (x.split('-')[0], x.split('-')[1] if '-' in x else ''))
    project_averages_pivot = project_averages_pivot[sorted_columns]

    try:
        project_averages_pivot.to_csv(project_avg_path, float_format='%.2f')
        print(f"\nSuccessfully calculated and saved project and overall averages to {project_avg_path}")
        print("\n--- Project and Overall Average Scores ---")
        print(project_averages_pivot.to_string())
    except Exception as e:
        print(f"Error saving project averages: {e}")


if __name__ == "__main__":
    # Define the paths to your data directories and files
    base_dir = os.getcwd()
    summary_directory = os.path.join(base_dir, 'summary_tables')

    # Define the input and output file paths
    input_file = os.path.join(summary_directory, 'representative_benchmark_scores.csv')
    output_file = os.path.join(summary_directory, 'median_performance_scores.csv')
    project_averages_file = os.path.join(summary_directory, 'project_average_scores.csv')

    # Run the analysis
    select_median_scores(input_file, output_file, project_averages_file)
