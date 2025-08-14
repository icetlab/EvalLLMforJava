import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

def load_and_normalize_data(project_names):
    all_dfs = []
    for project in project_names:
        csv_path = f"{project}_benchmark_summary.csv"
        try:
            df = pd.read_csv(csv_path)
            df['project'] = project
            all_dfs.append(df)
        except FileNotFoundError:
            print(f"Warning: The file '{csv_path}' was not found. Skipping this project.")
            continue
    
    if not all_dfs:
        print("Error: No data files found for the specified projects.")
        return None

    combined_df = pd.concat(all_dfs)

    grouped = combined_df.groupby(['project', 'hash_value', 'benchmark_name', 'params', 'mode'])
    processed_dfs = []
    for name, group in grouped:
        original_entry = group[group['model'] == 'original']
        if original_entry.empty:
            continue
        original_score = original_entry['mean'].iloc[0]
        if original_score == 0:
            continue
        mode = group['mode'].iloc[0]
        if mode in ['avgt', 'sample']:
            group['normalized_performance'] = original_score / group['mean']
        elif mode == 'thrpt':
            group['normalized_performance'] = group['mean'] / original_score
        processed_dfs.append(group)

    if not processed_dfs:
        print("No data to plot after processing. Ensure CSVs contain 'original' model entries.")
        return None
        
    return pd.concat(processed_dfs)

def add_dev_improvement_level(df):
    def get_dev_level(group):
        dev_perf = group[group['model'] == 'developer']['normalized_performance']
        if dev_perf.empty:
            return 'No Developer Data'
        perf_val = dev_perf.iloc[0]
        if perf_val < 1.0:
            return 'Dev Regression (<1x)'
        elif 1.0 <= perf_val < 2.0:
            return 'Dev Minor Improvement (1x-2x)'
        elif 2.0 <= perf_val < 10.0:
            return 'Dev Moderate Improvement (2x-10x)'
        else:
            return 'Dev Major Improvement (10x+)'

    levels = df.groupby(['hash_value', 'benchmark_name', 'params']).apply(get_dev_level).rename('dev_improvement_level')
    return df.merge(levels, on=['hash_value', 'benchmark_name', 'params'])

def plot_benchmark_performance(project_names, output_dir="plots", data=None):
    plot_df = data[data['model'] != 'original']

    fig, axes = plt.subplots(1, len(project_names), figsize=(22, 8), sharey=False)

    prompt_mapping = {"prompt1": "Zero-Hint", "prompt2": "Semantic-Hint", "prompt3": "Structural-Hint", "prompt4": "Hybrid-Hint"}
    plot_df['prompt'] = plot_df['prompt'].map(prompt_mapping)
    
    prompt_order = ["Zero-Hint", "Semantic-Hint", "Structural-Hint", "Hybrid-Hint"]
    model_order = ['developer', 'gpt', 'gemini']

    for i, project_name in enumerate(project_names):
        ax = axes[i]
        project_df = plot_df[plot_df['project'] == project_name]

        sns.boxplot(data=project_df, x='model', y='normalized_performance', order=model_order, showfliers=False, ax=ax)
        
        llm_df = project_df[project_df['model'].isin(['gpt', 'gemini'])]
        sns.stripplot(data=llm_df, x='model', y='normalized_performance', hue='prompt', hue_order=prompt_order, order=model_order, jitter=True, alpha=0.7, size=5, dodge=True, ax=ax)
        
        dev_df = project_df[project_df['model'] == 'developer']
        sns.stripplot(data=dev_df, x='model', y='normalized_performance', order=model_order, color='black', jitter=True, alpha=0.7, size=5, ax=ax, label='_nolegend_')

        ax.axhline(y=1.0, color='r', linestyle='--', linewidth=2, label='Original Baseline')
        ax.set_yscale('log')
        ax.set_title(project_name, fontsize=16)
        ax.set_xlabel('')
        ax.grid(True, which="both", ls="--", alpha=0.7)
        ax.set_ylabel('Normalized Performance (Higher is Better, Log Scale)', fontsize=12)
        
        if ax.get_legend() is not None:
            ax.get_legend().remove()

        if not project_df.empty:
            p98 = project_df['normalized_performance'].quantile(0.98)
            p02 = project_df['normalized_performance'].quantile(0.02)
            upper_bound = p98 * 1.2
            lower_bound = p02 * 0.8
            ax.set_ylim(bottom=lower_bound, top=upper_bound)

    handles, labels = axes[0].get_legend_handles_labels()
    legend_dict = dict(zip(labels, handles))
    
    final_handles = []
    final_labels = []
    if 'Original Baseline' in legend_dict:
        final_handles.append(legend_dict['Original Baseline'])
        final_labels.append('Original Baseline')
    for prompt in prompt_order:
        if prompt in legend_dict:
            final_handles.append(legend_dict[prompt])
            final_labels.append(prompt)

    fig.legend(handles=final_handles, labels=final_labels, title="Legend", loc='upper right')
    plt.tight_layout(rect=[0, 0, 0.9, 1])
    
    plot_filename = os.path.join(output_dir, 'all_projects_model_comparison.png')
    
    try:
        plt.savefig(plot_filename)
        print(f"Saved model comparison plot to {plot_filename}")
    except Exception as e:
        print(f"Could not save plot {plot_filename}. Error: {e}")
    plt.close()

def plot_prompt_performance(project_names, output_dir="plots", data=None):
    plot_df = data[data['model'] != 'original']
    prompt_mapping = {"prompt1": "Zero-Hint", "prompt2": "Semantic-Hint", "prompt3": "Structural-Hint", "prompt4": "Hybrid-Hint"}
    plot_df['prompt'] = plot_df['prompt'].map(prompt_mapping).fillna('Developer')

    fig, axes = plt.subplots(1, len(project_names), figsize=(22, 8), sharey=False)
    
    x_axis_order = ["Developer", "Zero-Hint", "Semantic-Hint", "Structural-Hint", "Hybrid-Hint"]
    model_palette = {"gpt": "#008fd5", "gemini": "#fc4f30"}

    for i, project_name in enumerate(project_names):
        ax = axes[i]
        project_df = plot_df[plot_df['project'] == project_name]
        
        llm_df = project_df[project_df['model'].isin(['gpt', 'gemini'])]
        dev_df = project_df[project_df['model'] == 'developer']
        
        sns.boxplot(data=dev_df, x='prompt', y='normalized_performance', order=x_axis_order, color="lightgray", showfliers=False, ax=ax)
        sns.boxplot(data=llm_df, x='prompt', y='normalized_performance', hue='model', order=x_axis_order, hue_order=['gpt', 'gemini'], showfliers=False, ax=ax)
        sns.stripplot(data=dev_df, x='prompt', y='normalized_performance', order=x_axis_order, color='black', jitter=True, alpha=0.7, size=5, ax=ax, label='_nolegend_')
        sns.stripplot(data=llm_df, x='prompt', y='normalized_performance', hue='model', order=x_axis_order, hue_order=['gpt', 'gemini'], palette=model_palette, jitter=True, alpha=0.7, size=5, dodge=True, ax=ax)

        ax.axhline(y=1.0, color='r', linestyle='--', linewidth=2, label='Original Baseline')
        ax.set_yscale('log')
        ax.set_title(project_name, fontsize=16)
        ax.set_xlabel('')
        ax.grid(True, which="both", ls="--", alpha=0.7)
        ax.set_ylabel('Normalized Performance (Higher is Better, Log Scale)', fontsize=12)
        ax.tick_params(axis='x', rotation=45)
        
        if ax.get_legend() is not None:
            ax.get_legend().remove()

        if not project_df.empty:
            p98 = project_df['normalized_performance'].quantile(0.98)
            p02 = project_df['normalized_performance'].quantile(0.02)
            upper_bound = p98 * 1.2
            lower_bound = p02 * 0.8
            ax.set_ylim(bottom=lower_bound, top=upper_bound)

    handles, labels = axes[0].get_legend_handles_labels()
    legend_dict = dict(zip(labels, handles))
    
    final_handles = []
    final_labels = []
    if 'Original Baseline' in legend_dict:
        final_handles.append(legend_dict['Original Baseline'])
        final_labels.append('Original Baseline')
    for model in ['gpt', 'gemini']:
        if model in legend_dict:
            final_handles.append(legend_dict[model])
            final_labels.append(model.upper())

    fig.legend(handles=final_handles, labels=final_labels, title="Legend", loc='upper right')
    plt.tight_layout(rect=[0, 0, 0.9, 1])
    
    plot_filename = os.path.join(output_dir, 'all_projects_prompt_comparison.png')
    
    try:
        plt.savefig(plot_filename)
        print(f"Saved prompt comparison plot to {plot_filename}")
    except Exception as e:
        print(f"Could not save plot {plot_filename}. Error: {e}")
    plt.close()

def calculate_outperformance_by_config(project_names, output_dir="plots", data=None):
    plot_df = data.copy()
    prompt_mapping = {"prompt1": "Zero-Hint", "prompt2": "Semantic-Hint", "prompt3": "Structural-Hint", "prompt4": "Hybrid-Hint"}
    plot_df['prompt'] = plot_df['prompt'].map(prompt_mapping)

    summary_lines = ["Outperformance Analysis by Configuration: Comparing each LLM run against the developer run with the same params."]
    
    overall_wins = {}
    overall_totals = {}

    for project in project_names:
        project_df = plot_df[plot_df['project'] == project]
        summary_lines.append(f"\n--- {project.upper()} ---")
        
        project_wins = {}
        project_totals = {}

        benchmark_groups = project_df.groupby(['hash_value', 'benchmark_name', 'params'])

        for _, group in benchmark_groups:
            dev_entry = group[group['model'] == 'developer']
            llm_entries = group[group['model'].isin(['gpt', 'gemini'])]

            if dev_entry.empty or llm_entries.empty:
                continue

            dev_score = dev_entry['normalized_performance'].iloc[0]

            for _, llm_row in llm_entries.iterrows():
                config_name = f"{llm_row['model'].upper()}-{llm_row['prompt']}"
                
                project_totals[config_name] = project_totals.get(config_name, 0) + 1
                overall_totals[config_name] = overall_totals.get(config_name, 0) + 1

                if llm_row['normalized_performance'] > dev_score:
                    project_wins[config_name] = project_wins.get(config_name, 0) + 1
                    overall_wins[config_name] = overall_wins.get(config_name, 0) + 1
        
        summary_lines.append(f"Comparable benchmark runs: {sum(project_totals.values())}")
        for config in sorted(project_totals.keys()):
            wins = project_wins.get(config, 0)
            total = project_totals[config]
            rate = (wins / total) * 100 if total > 0 else 0
            summary_lines.append(f"  - {config}: Won {wins}/{total} times ({rate:.2f}%)")
        
    summary_lines.append("\n--- OVERALL SUMMARY ---")
    summary_lines.append(f"Total comparable benchmark runs across all projects: {sum(overall_totals.values())}")
    for config in sorted(overall_totals.keys()):
        wins = overall_wins.get(config, 0)
        total = overall_totals[config]
        rate = (wins / total) * 100 if total > 0 else 0
        summary_lines.append(f"  - {config}: Won {wins}/{total} times ({rate:.2f}%)")

    summary_text = "\n".join(summary_lines)
    print(summary_text)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    summary_filename = os.path.join(output_dir, 'outperformance_by_config_summary.txt')
    with open(summary_filename, 'w') as f:
        f.write(summary_text)
    print(f"Summary saved to {summary_filename}")

def plot_faceted_by_dev_performance_model_view(project_names, output_dir="plots", data=None):
    plot_df = add_dev_improvement_level(data)
    plot_df = plot_df[plot_df['model'] != 'original']

    level_order = ['Dev Minor Improvement (1x-2x)', 'Dev Moderate Improvement (2x-10x)', 'Dev Major Improvement (10x+)']
    plot_df = plot_df[plot_df['dev_improvement_level'].isin(level_order)]
    
    g = sns.FacetGrid(plot_df, col="dev_improvement_level", col_wrap=3, height=7, aspect=1, col_order=level_order, sharey=False)
    g.map_dataframe(sns.boxplot, x='model', y='normalized_performance', order=['developer', 'gpt', 'gemini'], showfliers=False)
    
    g.map(plt.axhline, y=1.0, color='r', linestyle='--', linewidth=2)
    g.set_titles(col_template="{col_name}", size=14)
    g.set_axis_labels("", "Normalized Performance (Log Scale)")
    g.set(yscale="log")
    
    fig = g.fig
    fig.suptitle('Model Performance by Developer Improvement Level', fontsize=20, y=1.05)
    
    for ax, level in zip(g.axes.flat, level_order):
        facet_df = plot_df[plot_df['dev_improvement_level'] == level]
        if not facet_df.empty:
            if level == 'Dev Minor Improvement (1x-2x)':
                p98 = facet_df['normalized_performance'].quantile(0.98)
                p02 = facet_df['normalized_performance'].quantile(0.02)
                ax.set_ylim(bottom=p02 * 0.9, top=min(p98 * 1.2, 3.0)) 
            else:
                view_df = facet_df[facet_df['model'] != 'developer']
                if not view_df.empty:
                     p98 = view_df['normalized_performance'].quantile(0.98)
                     p02 = view_df['normalized_performance'].quantile(0.02)
                     upper_bound = p98 * 1.5
                     lower_bound = p02 * 0.5
                     ax.set_ylim(bottom=lower_bound, top=upper_bound)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    
    plot_filename = os.path.join(output_dir, 'faceted_performance_by_dev_level_model_view.png')
    try:
        plt.savefig(plot_filename)
        print(f"Saved faceted plot (Model View) to {plot_filename}")
    except Exception as e:
        print(f"Could not save plot {plot_filename}. Error: {e}")
    plt.close()

def plot_faceted_by_dev_performance_prompt_view(project_names, output_dir="plots", data=None):
    plot_df = add_dev_improvement_level(data)
    plot_df = plot_df[~plot_df['model'].isin(['original', 'developer'])]
    
    prompt_mapping = {"prompt1": "Zero-Hint", "prompt2": "Semantic-Hint", "prompt3": "Structural-Hint", "prompt4": "Hybrid-Hint"}
    plot_df['prompt'] = plot_df['prompt'].map(prompt_mapping)

    level_order = ['Dev Minor Improvement (1x-2x)', 'Dev Moderate Improvement (2x-10x)', 'Dev Major Improvement (10x+)']
    plot_df = plot_df[plot_df['dev_improvement_level'].isin(level_order)]
    
    g = sns.FacetGrid(plot_df, col="dev_improvement_level", col_wrap=3, height=7, aspect=1, col_order=level_order, sharey=False)

    x_axis_order = ["Zero-Hint", "Semantic-Hint", "Structural-Hint", "Hybrid-Hint"]
    
    g.map_dataframe(sns.boxplot, x='prompt', y='normalized_performance', hue='model', order=x_axis_order, hue_order=['gpt', 'gemini'], showfliers=False)

    g.map(plt.axhline, y=1.0, color='r', linestyle='--', linewidth=2)
    g.set_titles(col_template="{col_name}", size=14)
    g.set_axis_labels("", "Normalized Performance (Log Scale)")
    g.set(yscale="log")
    g.set_xticklabels(rotation=45)
    
    g.add_legend(title='Model')
    fig = g.fig
    fig.suptitle('LLM Prompt Performance by Developer Improvement Level', fontsize=20, y=1.05)

    for ax, level in zip(g.axes.flat, level_order):
        facet_df = plot_df[plot_df['dev_improvement_level'] == level]
        if not facet_df.empty:
            if level == 'Dev Minor Improvement (1x-2x)':
                p98 = facet_df['normalized_performance'].quantile(0.98)
                p02 = facet_df['normalized_performance'].quantile(0.02)
                ax.set_ylim(bottom=p02 * 0.9, top=min(p98 * 1.2, 3.0))
            else:
                 p98 = facet_df['normalized_performance'].quantile(0.98)
                 p02 = facet_df['normalized_performance'].quantile(0.02)
                 upper_bound = p98 * 1.5
                 lower_bound = p02 * 0.5
                 ax.set_ylim(bottom=lower_bound, top=upper_bound)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    
    plot_filename = os.path.join(output_dir, 'faceted_performance_by_dev_level_prompt_view.png')
    try:
        plt.savefig(plot_filename)
        print(f"Saved faceted plot (Prompt View) to {plot_filename}")
    except Exception as e:
        print(f"Could not save plot {plot_filename}. Error: {e}")
    plt.close()

def calculate_strict_outperformance(project_names, output_dir="plots", data=None):
    plot_df = data.copy()
    prompt_mapping = {"prompt1": "Zero-Hint", "prompt2": "Semantic-Hint", "prompt3": "Structural-Hint", "prompt4": "Hybrid-Hint"}
    plot_df['prompt'] = plot_df['prompt'].map(prompt_mapping)

    summary_lines = ["Strict Outperformance Analysis: LLM wins only if it's better across ALL params for a given benchmark."]
    
    overall_wins = {}
    overall_comparable_benchmarks = 0

    for project in project_names:
        project_df = plot_df[plot_df['project'] == project]
        summary_lines.append(f"\n--- {project.upper()} ---")
        
        project_wins = {}
        project_comparable_benchmarks = 0

        benchmark_groups = project_df.groupby(['hash_value', 'benchmark_name'])

        for _, group in benchmark_groups:
            dev_entries = group[group['model'] == 'developer']
            llm_entries = group[group['model'].isin(['gpt', 'gemini'])]

            if dev_entries.empty or llm_entries.empty:
                continue
            
            project_comparable_benchmarks += 1
            
            dev_scores = pd.Series(dev_entries.normalized_performance.values, index=dev_entries.params).to_dict()
            
            llm_configs = llm_entries.groupby(['model', 'prompt'])
            
            for (model, prompt), config_group in llm_configs:
                config_name = f"{model.upper()}-{prompt}"
                
                is_consistent_win = True
                
                if not set(dev_scores.keys()).issubset(set(config_group.params)):
                    is_consistent_win = False
                else:
                    for param, dev_score in dev_scores.items():
                        llm_score = config_group[config_group.params == param].normalized_performance.iloc[0]
                        if llm_score <= dev_score:
                            is_consistent_win = False
                            break
                
                if is_consistent_win:
                    project_wins[config_name] = project_wins.get(config_name, 0) + 1
                    overall_wins[config_name] = overall_wins.get(config_name, 0) + 1

        summary_lines.append(f"Total comparable benchmarks: {project_comparable_benchmarks}")
        if project_comparable_benchmarks > 0:
            for config, wins in sorted(project_wins.items()):
                rate = (wins / project_comparable_benchmarks) * 100
                summary_lines.append(f"  - {config}: Won {wins} times ({rate:.2f}%)")
        
        overall_comparable_benchmarks += project_comparable_benchmarks

    summary_lines.append("\n--- OVERALL SUMMARY ---")
    summary_lines.append(f"Total comparable benchmarks across all projects: {overall_comparable_benchmarks}")
    if overall_comparable_benchmarks > 0:
        for config, wins in sorted(overall_wins.items()):
            rate = (wins / overall_comparable_benchmarks) * 100
            summary_lines.append(f"  - {config}: Won {wins} times ({rate:.2f}%)")

    summary_text = "\n".join(summary_lines)
    print(summary_text)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    summary_filename = os.path.join(output_dir, 'strict_outperformance_summary.txt')
    with open(summary_filename, 'w') as f:
        f.write(summary_text)
    print(f"Summary saved to {summary_filename}")


if __name__ == "__main__":
    projects_to_plot = ['kafka', 'netty', 'presto', 'RoaringBitmap']
    output_directory = "comparison_plots"
    
    normalized_data = load_and_normalize_data(projects_to_plot)
    
    if normalized_data is not None:
        # plot_benchmark_performance(projects_to_plot, output_dir=output_directory, data=normalized_data)
        # plot_prompt_performance(projects_to_plot, output_dir=output_directory, data=normalized_data)
        # calculate_outperformance_by_config(projects_to_plot, output_dir=output_directory, data=normalized_data)
        # calculate_strict_outperformance(projects_to_plot, output_dir=output_directory, data=normalized_data)

        plot_faceted_by_dev_performance_model_view(projects_to_plot, output_dir=output_directory, data=normalized_data)
        plot_faceted_by_dev_performance_prompt_view(projects_to_plot, output_dir=output_directory, data=normalized_data)
