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
from itertools import combinations
from statannotations.Annotator import Annotator


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
                continue

            for config in llm_configs:
                comparison_df = project_df[[baseline_col, config, 'mode']].dropna()
                
                if not comparison_df.empty:
                    # Handle cases where a single config might have multiple modes
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
                else:
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
    # Create Model and Prompt columns for multi-level indexing
    def parse_config_for_plot(config):
        match = re.search(r'(GPT|GEMINI)-(prompt\d+)', config)
        if match:
            return match.groups()
        return None, None
    
    results_df[['Model', 'Prompt']] = results_df['Configuration'].apply(parse_config_for_plot).apply(pd.Series)
    results_df.dropna(subset=['Model', 'Prompt'], inplace=True)

    # Map prompt names to the desired labels
    prompt_map = {
        "prompt1": "NoHint",
        "prompt2": "Problem",
        "prompt3": "Benchmark",
        "prompt4": "Both"
    }
    results_df['Prompt'] = results_df['Prompt'].map(prompt_map)

    # Sort the DataFrame before pivoting to ensure correct order in the plot
    prompt_order = ["NoHint", "Problem", "Benchmark", "Both"]
    results_df['Prompt'] = pd.Categorical(results_df['Prompt'], categories=prompt_order, ordered=True)
    results_df.sort_values(by=['Model', 'Prompt'], inplace=True)

    df_vs_original = results_df[results_df['Comparison'] == 'vs. Original'].copy()
    df_vs_developer = results_df[results_df['Comparison'] == 'vs. Developer'].copy()

    category_map = {'Significant Improvement': 2, 'No Significant Improvement': 1, 'Inconclusive': np.nan}
    df_vs_original['Category'] = df_vs_original['Conclusion'].map(category_map)
    df_vs_developer['Category'] = df_vs_developer['Conclusion'].map(category_map)

    # Use a multi-level index for cleaner y-axis labels
    heatmap_orig_cat = df_vs_original.pivot_table(index=['Model', 'Prompt'], columns='Project', values='Category')
    annot_orig_pval = df_vs_original.pivot_table(index=['Model', 'Prompt'], columns='Project', values='P-value')
    
    heatmap_dev_cat = df_vs_developer.pivot_table(index=['Model', 'Prompt'], columns='Project', values='Category')
    annot_dev_pval = df_vs_developer.pivot_table(index=['Model', 'Prompt'], columns='Project', values='P-value')

    # --- 2. Custom formatter for p-values ---
    def format_p_value(p):
        if pd.isna(p):
            return ""
        return "<.0001" if p < 0.0001 else f"{p:.4f}"

    annot_orig_formatted = annot_orig_pval.applymap(format_p_value)
    annot_dev_formatted = annot_dev_pval.applymap(format_p_value)

    # --- 3. Create and save the heatmaps ---
    fig, axes = plt.subplots(1, 2, figsize=(10, 8))
    cmap = ListedColormap(['lightgray', 'lightgreen'])

    sns.heatmap(heatmap_orig_cat, ax=axes[0], annot=annot_orig_formatted, fmt="", cmap=cmap, linewidths=.5, cbar=False)
    axes[0].set_title('vs. Original Baseline', fontsize=14)
    axes[0].set_xlabel('', fontsize=12)
    axes[0].set_ylabel('', fontsize=12)

    sns.heatmap(heatmap_dev_cat, ax=axes[1], annot=annot_dev_formatted, fmt="", cmap=cmap, linewidths=.5, cbar=False)
    axes[1].set_title('vs. Developer Baseline', fontsize=14)
    axes[1].set_xlabel('', fontsize=12)
    axes[1].set_ylabel('')

    # legend_patches = [
    #     mpatches.Patch(color='lightgreen', label='Significant Improvement (p < 0.05)'),
    #     mpatches.Patch(color='lightgray', label='No Significant Improvement'),
    # ]
    # fig.legend(handles=legend_patches, loc='upper center', bbox_to_anchor=(0.5, 0.98), ncol=3, fontsize=12)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_filename = os.path.join(output_dir, "statistical_significance_heatmap.png")
    try:
        plt.savefig(output_filename, bbox_inches='tight')
        print(f"Successfully saved heatmap to {output_filename}")
    except Exception as e:
        print(f"Could not save plot. Error: {e}")
    
    plt.show()

def perform_pairwise_llm_tests(data, output_dir="comparison_plots"):
    """
    Performs pairwise one-sided Wilcoxon signed-rank tests between all LLM configurations.
    """
    if data is None:
        print("No data provided for pairwise LLM tests.")
        return None

    # --- 1. Prepare the paired DataFrame ---
    prompt_map = {
        "prompt1": "NoHint", "prompt2": "Problem",
        "prompt3": "Benchmark", "prompt4": "Both"
    }
    data_copy = data.copy()
    data_copy['prompt_name'] = data_copy['prompt'].map(prompt_map)
    data_copy['Config'] = data_copy.apply(
        lambda row: f"{row['model'].upper()}-{row['prompt_name']}", axis=1
    )
    id_vars = ['project', 'hash_value', 'benchmark_name', 'params', 'mode']
    paired_df = data_copy.pivot_table(index=id_vars, columns='Config', values='mean').reset_index()

    llm_configs = sorted([c for c in paired_df.columns if 'GPT' in c or 'GEMINI' in c])
    
    # --- 2. Perform pairwise one-sided tests ---
    print("\n\n--- Pairwise LLM Configuration Tests (All Projects) ---")
    
    config_pairs = list(combinations(llm_configs, 2))
    
    results = []
    for config_a, config_b in config_pairs:
        pair_df = paired_df[[config_a, config_b, 'mode']].dropna()
        if pair_df.empty: continue

        # We assume a consistent mode for this high-level comparison
        mode = pair_df['mode'].iloc[0]
        alternative_greater = 'greater' if mode == 'thrpt' else 'less'
        alternative_less = 'less' if mode == 'thrpt' else 'greater'

        try:
            # Test if A is better than B
            p_greater = wilcoxon(x=pair_df[config_a], y=pair_df[config_b], alternative=alternative_greater).pvalue
            # Test if B is better than A
            p_less = wilcoxon(x=pair_df[config_a], y=pair_df[config_b], alternative=alternative_less).pvalue
            
            conclusion = 'No Significant Difference'
            p_value = min(p_greater, p_less) # Report the smaller p-value
            
            if p_greater < 0.05:
                conclusion = f'{config_a} > {config_b}'
                p_value = p_greater
            elif p_less < 0.05:
                conclusion = f'{config_b} > {config_a}'
                p_value = p_less

            results.append({'Config A': config_a, 'Config B': config_b, 'P-value': p_value, 'Conclusion': conclusion})
        except ValueError:
            results.append({'Config A': config_a, 'Config B': config_b, 'P-value': np.nan, 'Conclusion': 'Test Error'})
            
    if not results:
        print("No valid pairwise comparisons could be made.")
        return None

    return pd.DataFrame(results)

def plot_pairwise_heatmap(results_df, output_dir="comparison_plots"):
    """
    Visualizes the pairwise comparison matrix as a heatmap with directional results.
    """
    if results_df is None or results_df.empty:
        print("No pairwise comparison matrix to plot.")
        return

    # --- 1. Prepare data for plotting ---
    # Map conclusions to numerical categories for coloring
    def map_conclusion_to_category(row):
        if row['Conclusion'] == 'No Significant Difference':
            return 0
        # If Config A (the index) is the winner
        if row['Config A'] in row['Conclusion']:
            return 1 # Row > Column
        # If Config B (the column) is the winner
        if row['Config B'] in row['Conclusion']:
            return -1 # Column > Row
        return np.nan

    results_df['Category'] = results_df.apply(map_conclusion_to_category, axis=1)
    
    # Pivot for both color and annotation
    p_value_matrix = results_df.pivot(index='Config A', columns='Config B', values='P-value')
    category_matrix = results_df.pivot(index='Config A', columns='Config B', values='Category')
    
    # --- 2. Create the full, symmetric matrices ---
    full_cat_matrix = category_matrix.combine_first(-category_matrix.T)
    full_pval_matrix = p_value_matrix.combine_first(p_value_matrix.T)

    # --- 3. Sort and format ---
    def sort_key_config(config_name):
        prompt_order = ["NoHint", "Problem", "Benchmark", "Both"]
        match = re.search(r'(GPT|GEMINI)-(.+)', config_name)
        if match:
            model, prompt_name = match.groups()
            model_order = 1 if model == 'GPT' else 2
            try:
                prompt_order_index = prompt_order.index(prompt_name)
                return (model_order, prompt_order_index)
            except ValueError: return (model_order, 99)
        return (99, 99)

    sorted_index = sorted(full_cat_matrix.index, key=sort_key_config)
    full_cat_matrix = full_cat_matrix.reindex(index=sorted_index, columns=sorted_index)
    full_pval_matrix = full_pval_matrix.reindex(index=sorted_index, columns=sorted_index)

    # --- 4. Create the heatmap ---
    plt.figure(figsize=(10, 8))
    cmap = ListedColormap(['#A9CCE3', 'lightgray', '#A9DFBF']) # Blue, Gray, Green
    
    sns.heatmap(
        full_cat_matrix, 
        annot=full_pval_matrix, # Annotate with the actual p-values
        fmt=".4f",
        cmap=cmap,
        linewidths=.5,
        cbar=False,
        square=True
    )
    
    plt.title('Pairwise Significance Matrix (p-values)', fontsize=16)
    plt.xlabel('')
    plt.ylabel('')
    
    legend_patches = [
        mpatches.Patch(color='#A9DFBF', label='Row > Column (p < 0.05)'),
        mpatches.Patch(color='#A9CCE3', label='Column > Row (p < 0.05)'),
        mpatches.Patch(color='lightgray', label='No Significant Difference'),
    ]
    plt.legend(handles=legend_patches, loc='upper left', bbox_to_anchor=(1.05, 1))

    plt.tight_layout()
    
    # --- 5. Save the plot ---
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_filename = os.path.join(output_dir, "pairwise_significance_heatmap_directional.png")
    try:
        plt.savefig(output_filename, bbox_inches='tight')
        print(f"Successfully saved directional pairwise heatmap to {output_filename}")
    except Exception as e:
        print(f"Could not save plot. Error: {e}")
    
    plt.show()

def create_final_plot_with_stats(data, output_dir="comparison_plots"):
    """
    Creates a final boxplot comparing all LLM configurations and adds statistical
    annotations to show significant differences between pairs.
    """
    if data is None:
        print("No data provided for plotting.")
        return

    # --- 1. Prepare data ---
    # We only need the LLM data for this plot
    plot_data = data[data['model'].isin(['gpt', 'gemini'])].copy()

    prompt_map = {
        "prompt1": "NoHint",
        "prompt2": "Problem",
        "prompt3": "Benchmark",
        "prompt4": "Both"
    }
    plot_data['Prompt'] = plot_data['prompt'].map(prompt_map)
    plot_data['Model'] = plot_data['model'].apply(lambda x: x.upper())
    plot_data['Config'] = plot_data['Model'] + '-' + plot_data['Prompt']

    # --- 2. Create the plot ---
    plt.figure(figsize=(15, 8))
    
    # Define a clear order for the x-axis
    prompt_order = ["NoHint", "Problem", "Benchmark", "Both"]
    config_order = [f"GPT-{p}" for p in prompt_order] + [f"GEMINI-{p}" for p in prompt_order]

    ax = sns.boxplot(data=plot_data, x='Config', y='normalized_performance', order=config_order, showfliers=False)
    
    # --- 3. Add statistical annotations ---
    # Define the pairs you want to compare
    box_pairs = [
        ("GPT-NoHint", "GEMINI-NoHint"),
        ("GPT-Problem", "GEMINI-Problem"),
        ("GPT-Benchmark", "GEMINI-Benchmark"),
        ("GPT-Both", "GEMINI-Both"),
        ("GPT-NoHint", "GPT-Both"),
        ("GEMINI-NoHint", "GEMINI-Both"),
    ]

    # Use the statannotations library to add significance bars and stars
    # Note: You may need to install it first: pip install statannotations
    try:
        # Pass the 'ax' and 'box_pairs' to the Annotator
        annotator = Annotator(ax, box_pairs, data=plot_data, x='Config', y='normalized_performance', order=config_order)
        # Configure the test and annotations
        # FIX 2: Added id='hash_value' to specify pairing for the Wilcoxon test
        annotator.configure(test='Wilcoxon', text_format='star', loc='inside', verbose=2, id='hash_value', test_short_name='Wilcoxon')
        # Apply the annotations
        annotator.apply_and_annotate()
    except ImportError:
        print("\n[Warning] 'statannotations' library not found. Skipping statistical annotations on the plot.")
        print("To install it, run: pip install statannotations")
    except Exception as e:
        print(f"\n[Warning] An error occurred during statistical annotation: {e}")


    # --- 4. Finalize and save the plot ---
    ax.axhline(y=1.0, color='r', linestyle='--', linewidth=2, label='Baseline')
    ax.set_yscale('log')
    ax.set_title('Overall Performance Comparison of LLM Configurations', fontsize=18)
    ax.set_xlabel('')
    ax.set_ylabel('Normalized Performance (Log Scale)', fontsize=14)
    # FIX 1: Removed the invalid 'ha' parameter
    ax.tick_params(axis='x', rotation=45, labelsize=12)
    ax.tick_params(axis='y', labelsize=12)
    ax.legend(loc='upper left')

    plt.tight_layout()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_filename = os.path.join(output_dir, "final_comparison_with_stats.png")
    try:
        plt.savefig(output_filename, bbox_inches='tight')
        print(f"\nSuccessfully saved final plot to {output_filename}")
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

        # 5. Perform and plot pairwise tests between LLM configurations
        pairwise_results = perform_pairwise_llm_tests(raw_data, output_dir=output_directory)
        plot_pairwise_heatmap(pairwise_results, output_dir=output_directory)

        # create_final_plot_with_stats(raw_data, output_dir=output_directory)

