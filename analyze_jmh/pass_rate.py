import os
import re
import pandas as pd

# Configuration
base_dir = '../llm_output'
projects = ['netty', 'kafka', 'presto', 'RoaringBitmap']
prompt_map = {
    'prompt1': 'Zero-Hint',
    'prompt2': 'Semantic-Hint',
    'prompt3': 'Structural-Hint',
    'prompt4': 'Hybrid-Hint'
}
models = {
    'gpt': 'OpenAI o4 mini',
    'gemini': 'Gemini 2.5 Pro'
}
# Fixed number of tasks per project
project_task_count = {
    'netty': 16,
    'kafka': 16,
    'presto': 27,
    'RoaringBitmap': 6
}

re_prompt_file = re.compile(r'(prompt\d+)\.diff\.log$')

data = []

for project in projects:
    project_dir = os.path.join(base_dir, project)
    if not os.path.isdir(project_dir):
        continue

    num_tasks = project_task_count.get(project, 0)
    total_runs = num_tasks * 3  # 3 executions per task

    grouped_counts = {}  # (model_name) -> {prompt_key -> count}

    for subdir in os.listdir(project_dir):
        subdir_path = os.path.join(project_dir, subdir)
        if not os.path.isdir(subdir_path):
            continue

        model_key = None
        for prefix in models:
            if subdir.startswith(prefix):
                model_key = prefix
                break
        if model_key is None:
            continue

        model_name = models[model_key]
        if model_name not in grouped_counts:
            grouped_counts[model_name] = {k: 0 for k in prompt_map.keys()}

        for task_id in os.listdir(subdir_path):
            task_path = os.path.join(subdir_path, task_id)
            if not os.path.isdir(task_path):
                continue

            for fname in os.listdir(task_path):
                match = re_prompt_file.match(fname)
                if match:
                    prompt_key = match.group(1)
                    if prompt_key in grouped_counts[model_name]:
                        grouped_counts[model_name][prompt_key] += 1

    # Convert to data entries
    for model_name, prompt_counts in grouped_counts.items():
        row = {
            'Project': project.capitalize(),
            'Model': model_name
        }
        for prompt_key, count in prompt_counts.items():
            prompt_name = prompt_map[prompt_key]
            success_rate = count / total_runs if total_runs > 0 else 0.0
            row[prompt_name] = f"{count} ({success_rate:.2%})"
        data.append(row)

# Build dataframe
df = pd.DataFrame(data)
cols = ['Project', 'Model'] + list(prompt_map.values())
df = df[cols]
df = df.sort_values(by=['Project', 'Model'])
print(df.to_string(index=False))


# # Pivot for heatmap
# pivot_df = df.pivot_table(
#     index='Prompt',
#     columns=['Project', 'Model'],
#     values='SuccessRate'
# )

# # Keep original columns for annotation generation
# original_columns = pivot_df.columns

# # Annotations (count + %)
# annot_df_display = pd.DataFrame(index=pivot_df.index, columns=original_columns)

# for row in pivot_df.index:
#     for proj, model in original_columns:
#         rate = pivot_df.loc[row, (proj, model)]
#         if pd.isna(rate):
#             annot_df_display.loc[row, (proj, model)] = ""
#         else:
#             count = df[
#                 (df['Prompt'] == row) &
#                 (df['Project'] == proj) &
#                 (df['Model'] == model)
#             ]['PatchCount'].values[0]
#             annot_df_display.loc[row, (proj, model)] = f"{int(count)}\n({rate:.2%})"

# # Now update column labels with formatted string (slanted model name)
# pivot_df.columns = [
#     fr"{proj} - $\it{{{model}}}$" for proj, model in original_columns
# ]
# annot_df_display.columns = pivot_df.columns


# # Plot heatmap
# plt.figure(figsize=(12, 5))
# sns.set(style="whitegrid")
# sns.set_context("notebook", font_scale=0.9)

# ax = sns.heatmap(
#     pivot_df,
#     annot=annot_df_display,
#     fmt='',
#     cmap='Blues',
#     cbar=False,
#     linewidths=0.6,
#     linecolor='white',
#     square=False,
#     annot_kws={"size": 9, "va": "center", "ha": "center"}
# )

# plt.xticks(rotation=20, ha='right')
# plt.yticks(rotation=0)
# ax.set_xlabel("")
# ax.set_ylabel("")

# plt.subplots_adjust(left=0.2, right=0.9, top=0.8, bottom=0.4)

# plt.show()