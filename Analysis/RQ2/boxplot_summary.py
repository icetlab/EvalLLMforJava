import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io
import re
import os

def create_plots_from_csv_file(input_path, output_dir="comparison_plots"):
    """
    Reads the median_performance_scores.csv file, processes it, and creates two box plots:
    1. A prompt-centric view comparing model performance for each prompt type.
    2. A model-centric view comparing prompt performance for each model.

    Args:
        input_path (str): The path to the median_performance_scores.csv file.
        output_dir (str): The directory to save the output plot.
    """
    # --- 1. Load and Process Data ---
    try:
        df_long = pd.read_csv(input_path)
        print(f"Successfully loaded {len(df_long)} rows from {input_path}")
    except FileNotFoundError:
        print(f"Error: The file '{input_path}' was not found.")
        return

    # --- Extract developer median score before filtering ---
    developer_df = df_long[df_long['model'] == 'developer'].copy()
    dev_median = developer_df['final_score'].median() if not developer_df.empty else None

    # Filter out the 'developer' model to focus on LLM performance for the boxplots
    df_long = df_long[df_long['model'] != 'developer'].copy()

    # Drop any rows that might have nulls in critical columns
    df_long.dropna(subset=['prompt', 'model', 'final_score'], inplace=True)

    # --- Map model and prompt names for plotting ---
    prompt_map = {
        "prompt1": "NoHint",
        "prompt2": "Problem",
        "prompt3": "Benchmark",
        "prompt4": "Both"
    }
    df_long['Prompt'] = df_long['prompt'].map(prompt_map)

    def rename_model(model_name):
        if 'gpt' in model_name.lower():
            return 'OpenAI o4 mini'
        if 'gemini' in model_name.lower():
            return 'Gemini 2.5 Pro'
        return model_name
        
    df_long['Model'] = df_long['model'].apply(rename_model)

    # --- 2. Create Plots ---
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sns.set_style("whitegrid")

    # Define Custom Color Palettes
    palette_plot1 = ["#9E9EE0", "#FFF2CC"]  # Vibrant Coral and Teal
    palette_plot2 = ["#9E9EE0", "#FFF2CC", "#D3D3D3", "#90EE90"]  # Turquoise, Gold, GreenYellow, HotPink

    # --- Plot 1: Prompt-Centric View ---
    ax1 = axes[0]
    prompt_order = ["NoHint", "Problem", "Benchmark", "Both"]
    
    sns.boxplot(data=df_long, x='Prompt', y='final_score', hue='Model', order=prompt_order, 
                showfliers=False, ax=ax1, palette=palette_plot1, width=0.5, linewidth=2)
    
    ax1.axhline(y=1.0, color='r', linestyle='--', linewidth=2, label='Baseline')
    # Add developer median line
    if dev_median is not None:
        ax1.axhline(y=dev_median, color='blue', linestyle=':', linewidth=2, label='Developer Median')
    
    # ax1.set_yscale('log')
    ax1.set_title('(a) by Prompt Strategy', fontsize=19)
    ax1.set_xlabel('', fontsize=14)
    ax1.set_ylabel('Performance (pss scores)', fontsize=19)
    ax1.tick_params(axis='x', labelsize=19)
    ax1.tick_params(axis='y', labelsize=19)
    ax1.legend(loc='upper left', fontsize=13, frameon=False)

    # --- Plot 2: Model-Centric View ---
    ax2 = axes[1]
    model_order = ['OpenAI o4 mini', 'Gemini 2.5 Pro']
    
    sns.boxplot(data=df_long, x='Model', y='final_score', hue='Prompt', order=model_order, 
                hue_order=prompt_order, showfliers=False, ax=ax2, palette=palette_plot2, width=0.5, linewidth=2)

    ax2.axhline(y=1.0, color='r', linestyle='--', linewidth=2, label='Baseline')
    # Add developer median line
    if dev_median is not None:
        ax2.axhline(y=dev_median, color='blue', linestyle=':', linewidth=2, label='Developer Median')

    # ax2.set_yscale('log')
    ax2.set_title('(b) by Model', fontsize=19)
    ax2.set_xlabel('', fontsize=14)
    ax2.set_ylabel('')
    ax2.tick_params(axis='x', labelsize=19)
    ax2.tick_params(axis='y', labelsize=19)
    ax2.legend(loc='upper left', fontsize=13, frameon=False)

    # --- Final Touches ---
    plt.tight_layout()
    
    # Save the combined plot to a file
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_filename = os.path.join(output_dir, "RQ2_performance_comparison_plot.pdf")
    try:
        plt.savefig(output_filename, bbox_inches='tight')
        print(f"Successfully saved plots to {output_filename}")
    except Exception as e:
        print(f"Could not save plot. Error: {e}")

    plt.show()


if __name__ == "__main__":
    # Define the path to your input CSV file
    input_csv_file = 'median_performance_scores.csv'
    
    # Define the directory where the output plot will be saved
    output_plot_directory = "."

    create_plots_from_csv_file(input_csv_file, output_plot_directory)

