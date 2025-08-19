import pandas as pd
import os
from scipy.stats import wilcoxon
import re
import glob
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
import matplotlib.patches as mpatches

def load_raw_data_from_csvs(project_names):
    """
    Loads and combines the raw benchmark summary CSVs for specified projects.
    """
    all_dfs = []
    for project in project_names:
        csv_path = f"../summary_csv/{project}_benchmark_summary.csv"
        try:
            df = pd.read_csv(csv_path)
            df['params'] = df['params'].str.strip('"')
            df['project'] = project
            all_dfs.append(df)
        except FileNotFoundError:
            print(f"Warning: The file '{csv_path}' was not found. Skipping.")
            continue
    
    if not all_dfs:
        print("Error: No CSV files found for the specified projects.")
        return None

    return pd.concat(all_dfs)

def perform_statistical_analysis(data):
    """
    Performs Wilcoxon signed-rank tests for multiple comparisons and returns
    a structured DataFrame with the results.
    """
    if data is None:
        print("No data provided to the test function.")
        return None

    # --- 1. Prepare one comprehensive paired DataFrame ---
    data['Config'] = data.apply(
        lambda row: row['model'] if row['model'] in ['original', 'developer'] 
                      else f"{row['model'].upper()}-{row['prompt']}",
        axis=1
    )
    id_vars = ['project', 'hash_value', 'benchmark_name', 'params', 'mode']
    paired_df = data.pivot_table(index=id_vars, columns='Config', values='mean').reset_index()

    if paired_df.empty:
        print("Could not create a paired DataFrame for testing.")
        return None

    # --- 2. Iterate through projects and perform tests ---
    projects = paired_df['project'].dropna().unique()
    results = []

    for project in projects:
        project_df = paired_df[paired_df['project'] == project]
        
        # --- Comparisons ---
        comparisons = {'vs. Original': 'original', 'vs. Developer': 'developer'}
        llm_configs = sorted([c for c in project_df.columns if 'GPT' in c or 'GEMINI' in c])

        for comp_name, baseline_col in comparisons.items():
            if baseline_col not in project_df.columns:
                # Add inconclusive results for all configs if baseline is missing for this project
                for config in llm_configs:
                    results.append({
                        'Project': project, 'Comparison': comp_name,
                        'Configuration': config, 'P-value': np.nan,
                        'Conclusion': 'Inconclusive'
                    })
                continue

            for config in llm_configs:
                comparison_df = project_df[[baseline_col, config, 'mode']].dropna()
                
                if not comparison_df.empty:
                    # Group by mode in case a single config was run against benchmarks with different modes
                    for mode, mode_group in comparison_df.groupby('mode'):
                        if len(mode_group) < 10:
                            results.append({
                                'Project': project, 'Comparison': comp_name,
                                'Configuration': config, 'P-value': np.nan,
                                'Conclusion': 'Inconclusive'
                            })
                            continue

                        alternative = 'greater' if mode == 'thrpt' else 'less'
                        try:
                            _, p_value = wilcoxon(x=mode_group[config], y=mode_group[baseline_col], alternative=alternative)
                            conclusion = 'Significant Improvement' if p_value < 0.05 else 'No Significant Improvement'
                            results.append({
                                'Project': project, 'Comparison': comp_name,
                                'Configuration': config, 'P-value': p_value,
                                'Conclusion': conclusion
                            })
                        except ValueError as e:
                            results.append({
                                'Project': project, 'Comparison': comp_name,
                                'Configuration': config, 'P-value': np.nan,
                                'Conclusion': 'Test Error'
                            })
                else: # If there are no paired values for this config
                     results.append({
                        'Project': project, 'Comparison': comp_name,
                        'Configuration': config, 'P-value': np.nan,
                        'Conclusion': 'Inconclusive'
                    })
                        
    return pd.DataFrame(results)

def plot_statistical_heatmap(results_df, output_dir="comparison_plots"):
    """
    Takes a DataFrame of statistical results and creates two heatmaps
    to visualize the conclusions.
    """
    if results_df is None or results_df.empty:
        print("No statistical results to plot.")
        return

    # --- 1. Prepare data for two separate heatmaps ---
    df_vs_original = results_df[results_df['Comparison'] == 'vs. Original'].copy()
    df_vs_developer = results_df[results_df['Comparison'] == 'vs. Developer'].copy()

    # Map conclusions to numerical categories for coloring
    category_map = {
        'Significant Improvement': 2, 
        'No Significant Improvement': 1, 
        'Inconclusive': 0
    }
    df_vs_original['Category'] = df_vs_original['Conclusion'].map(category_map)
    df_vs_developer['Category'] = df_vs_developer['Conclusion'].map(category_map)

    # --- Ensure all projects are represented as columns, even if all values are NaN ---
    all_projects = results_df['Project'].unique()
    all_configs = results_df['Configuration'].unique()

    heatmap_orig_cat = df_vs_original.pivot_table(index='Configuration', columns='Project', values='Category')
    annot_orig_pval = df_vs_original.pivot_table(index='Configuration', columns='Project', values='P-value')
    
    heatmap_dev_cat = df_vs_developer.pivot_table(index='Configuration', columns='Project', values='Category')
    annot_dev_pval = df_vs_developer.pivot_table(index='Configuration', columns='Project', values='P-value')

    # Reindex to ensure all projects and configs are present
    heatmap_orig_cat = heatmap_orig_cat.reindex(index=all_configs, columns=all_projects)
    annot_orig_pval = annot_orig_pval.reindex(index=all_configs, columns=all_projects)
    heatmap_dev_cat = heatmap_dev_cat.reindex(index=all_configs, columns=all_projects)
    annot_dev_pval = annot_dev_pval.reindex(index=all_configs, columns=all_projects)


    # --- 2. Custom formatter for p-values ---
    def format_p_value(p):
        if pd.isna(p):
            return ""
        return "<.0001" if p < 0.0001 else f"{p:.4f}"

    annot_orig_formatted = annot_orig_pval.applymap(format_p_value)
    annot_dev_formatted = annot_dev_pval.applymap(format_p_value)

    # --- 3. Sort the index (rows) for readability ---
    def sort_key_config(config_name):
        match = re.search(r'(GPT|GEMINI)-prompt(\d+)', config_name)
        if match:
            model, prompt_num = match.groups()
            model_order = 1 if model == 'GPT' else 2
            return (model_order, int(prompt_num))
        return (99, 99)

    if not heatmap_orig_cat.index.empty:
        sorted_index = sorted(heatmap_orig_cat.index, key=sort_key_config)
        heatmap_orig_cat = heatmap_orig_cat.reindex(sorted_index)
        annot_orig_formatted = annot_orig_formatted.reindex(sorted_index)
    
    if not heatmap_dev_cat.index.empty:
        sorted_index_dev = sorted(heatmap_dev_cat.index, key=sort_key_config)
        heatmap_dev_cat = heatmap_dev_cat.reindex(sorted_index_dev)
        annot_dev_formatted = annot_dev_formatted.reindex(sorted_index_dev)

    # --- 4. Create and save the heatmaps ---
    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    
    # Define a custom colormap: 0 -> lightyellow, 1 -> lightgray, 2 -> lightgreen
    cmap = ListedColormap(['#FEFDE3', 'lightgray', 'lightgreen'])

    # Plot 1: vs. Original
    sns.heatmap(heatmap_orig_cat, ax=axes[0], annot=annot_orig_formatted, fmt="", cmap=cmap, linewidths=.5, cbar=False, square=True)
    axes[0].set_title('Significance vs. Original Baseline', fontsize=16)
    axes[0].set_xlabel('Project', fontsize=12)
    axes[0].set_ylabel('LLM Configuration', fontsize=12)

    # Plot 2: vs. Developer
    sns.heatmap(heatmap_dev_cat, ax=axes[1], annot=annot_dev_formatted, fmt="", cmap=cmap, linewidths=.5, cbar=False, square=True)
    axes[1].set_title('Significance vs. Developer Baseline', fontsize=16)
    axes[1].set_xlabel('Project', fontsize=12)
    axes[1].set_ylabel('')

    # Create a shared legend for the figure
    legend_patches = [
        mpatches.Patch(color='lightgreen', label='Significant Improvement (p < 0.05)'),
        mpatches.Patch(color='lightgray', label='No Significant Improvement'),
        mpatches.Patch(color='#FEFDE3', ec='black', label='Inconclusive (N < 10)')
    ]
    fig.legend(handles=legend_patches, loc='upper center', bbox_to_anchor=(0.5, 0.98), ncol=3, fontsize=12)

    plt.tight_layout(rect=[0, 0, 1, 0.95]) # Adjust layout to make space for the legend
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_filename = os.path.join(output_dir, "statistical_significance_heatmap.png")
    try:
        plt.savefig(output_filename, bbox_inches='tight')
        print(f"Successfully saved heatmap to {output_filename}")
    except Exception as e:
        print(f"Could not save plot. Error: {e}")
    
    plt.show()


if __name__ == "__main__":
    projects = ['kafka', 'netty', 'presto', 'RoaringBitmap']
    output_directory = "comparison_plots"
    
    # 1. Load the raw data from the CSV files
    raw_data = load_raw_data_from_csvs(projects)

    if raw_data is not None:
        # 2. Perform the statistical analysis to get a results DataFrame
        statistical_results = perform_statistical_analysis(raw_data)
        
        # 3. Save the intermediate statistical results to a file
        if statistical_results is not None and not statistical_results.empty:
            if not os.path.exists(output_directory):
                os.makedirs(output_directory)
            summary_filename = os.path.join(output_directory, "statistical_summary.csv")
            statistical_results.to_csv(summary_filename, index=False)
            print(f"\nSaved intermediate statistical results to {summary_filename}")
        
        # 4. Plot the results as a heatmap
        plot_statistical_heatmap(statistical_results, output_dir=output_directory)
