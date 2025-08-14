import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.backends.backend_pdf import PdfPages
import ast
import math

def create_report(csv_path, output_pdf):
    """
    Generates a PDF with boxplots for each benchmark and parameter combination.

    Args:
        csv_path (str): Path to the input CSV file.
        output_pdf (str): Path to the output PDF file.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"Error: The file {csv_path} was not found.")
        return

    # Filter for gpt-1 and gemini-1 models
    df = df[df['model'].isin(['org', 'dev']) | df['model'].str.endswith('-1')]

    # Create a model configuration column for the x-axis of the plots
    df['model_config'] = df.apply(
        lambda row: f"{row['model']}-{row['prompt']}" if pd.notna(row['prompt']) and row['prompt'] != 'N/A' else row['model'],
        axis=1
    )

    # Define the order for the boxplots
    order = [
        'org', 'dev',
        'gpt-1-prompt1', 'gpt-1-prompt2', 'gpt-1-prompt3', 'gpt-1-prompt4',
        'gemini-1-prompt1', 'gemini-1-prompt2', 'gemini-1-prompt3', 'gemini-1-prompt4'
    ]

    with PdfPages(output_pdf) as pdf:
        # Group by project
        for project, project_df in df.groupby('project'):
            # Add a title page for the project
            fig = plt.figure(figsize=(11.69, 8.27))
            fig.clf()
            fig.text(0.5, 0.5, f'Project: {project}', transform=fig.transFigure, size=24, ha="center")
            pdf.savefig()
            plt.close()

            # Group by benchmark
            for benchmark, benchmark_df in project_df.groupby('benchmark'):
                params_list = benchmark_df['params'].unique()
                n_params = len(params_list)
                facets_per_page = 4
                n_pages = math.ceil(n_params / facets_per_page)

                for page_num in range(n_pages):
                    start_index = page_num * facets_per_page
                    end_index = start_index + facets_per_page
                    params_chunk = params_list[start_index:end_index]
                    
                    n_facets_on_page = len(params_chunk)
                    n_cols = 2
                    n_rows = math.ceil(n_facets_on_page / n_cols)

                    fig, axes = plt.subplots(n_rows, n_cols, figsize=(11.69, 8.27), squeeze=False)
                    fig.suptitle(f'Benchmark: {benchmark}', fontsize=16, y=0.98)
                    axes = axes.flatten()

                    for i, params_str in enumerate(params_chunk):
                        ax = axes[i]
                        params_df = benchmark_df[benchmark_df['params'] == params_str]
                        
                        sns.boxplot(x='model_config', y='score', data=params_df, ax=ax, order=order)

                        ax.axvline(x=1.5, color='k', linestyle='-')
                        ax.axvline(x=5.5, color='k', linestyle='-')

                        # Calculate and draw average lines for org and dev
                        org_avg = params_df[params_df['model_config'] == 'org']['score'].median()
                        dev_avg = params_df[params_df['model_config'] == 'dev']['score'].median()

                        if pd.notna(org_avg):
                            ax.axhline(org_avg, color='r', linestyle='--', label=f'org avg: {org_avg:.2f}')
                        if pd.notna(dev_avg):
                            ax.axhline(dev_avg, color='g', linestyle='--', label=f'dev avg: {dev_avg:.2f}')
                        
                        if pd.notna(org_avg) or pd.notna(dev_avg):
                            ax.legend(fontsize=8)

                        ax.set_title(f'Params: {params_str}', fontsize=8)
                        ax.set_xlabel('')
                        ax.set_ylabel('Score')
                        ax.tick_params(axis='x', rotation=90, labelsize=8)

                    # Hide unused subplots
                    for i in range(n_facets_on_page, len(axes)):
                        axes[i].set_visible(False)

                    plt.tight_layout(rect=[0, 0, 1, 0.96])
                    pdf.savefig(fig)
                    plt.close()

    print(f"Successfully created PDF report: {output_pdf}")

if __name__ == '__main__':
    create_report('llm_and_baseline_performance_data_raw.csv', 'results_raw.pdf')