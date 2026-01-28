import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import io
import numpy as np
import os

# --- 1. Read and Clean Data ---
try:
    df = pd.read_csv('qualitative_coding_results_merged.csv')
except FileNotFoundError:
    print("Error: The file 'qualitative_coding_results.csv' was not found. Please ensure it exists in the correct path.")
    exit() # Exit the script if the file is not found

df_filtered = df[df['model'] != 'developer'].copy()
# Filter out entries without final_score (they should not participate in statistics)
df_filtered = df_filtered[df_filtered['final_score'].notna()].copy()
df_filtered.dropna(subset=['prompt', 'trial', 'classification'], inplace=True)
df_filtered['trial'] = df_filtered['trial'].astype(int)

# Map prompt names to new labels (abbreviated)
prompt_mapping = {
    'prompt1': 'NoHint',
    'prompt2': 'Prob',
    'prompt3': 'Bench',
    'prompt4': 'Both'
}
df_filtered['prompt'] = df_filtered['prompt'].map(prompt_mapping)

project_mapping = {
    'kafka': 'Kafka',
    'netty': 'Netty',
    'presto': 'Presto',
    'RoaringBitmap': 'RB'
}
df_filtered['project'] = df_filtered['project'].map(project_mapping).fillna(df_filtered['project'])


# --- 2. Statistical Analysis ---
# --- Analysis 1: By Prompt ---
analysis_by_prompt = df_filtered.groupby(['prompt', 'classification']).size().unstack(fill_value=0)
classification_order = ['Strategy Match', 'Strategy Alignment', 'Strategy Divergence']
analysis_by_prompt = analysis_by_prompt.reindex(columns=classification_order, fill_value=0)
prompt_order = ['NoHint', 'Bench', 'Prob', 'Both']
analysis_by_prompt = analysis_by_prompt.reindex(index=prompt_order, fill_value=0)

# --- Analysis 2: By Project ---
analysis_by_project = df_filtered.groupby(['project', 'classification']).size().unstack(fill_value=0)
analysis_by_project = analysis_by_project.reindex(columns=classification_order, fill_value=0)
project_order = ['Kafka', 'Netty', 'Presto', 'RB']
analysis_by_project = analysis_by_project.reindex(index=project_order, fill_value=0)

# --- Analysis 3: By Model ---
analysis_by_model = df_filtered.groupby(['model', 'classification']).size().unstack(fill_value=0)
analysis_by_model = analysis_by_model.reindex(columns=classification_order, fill_value=0)
# Rename the model names for the plot (abbreviated)
analysis_by_model.rename(index={
    'gemini': 'Gemini',
    'gpt': 'o4-mini',
    'deepseek-v3': 'DS-V3',
    'deepseek-r1': 'DS-R1'
}, inplace=True)
model_order = ['o4-mini', 'Gemini', 'DS-V3', 'DS-R1']
analysis_by_model = analysis_by_model.reindex(index=model_order, fill_value=0)

# --- Print Statistics for Bar Charts ---
print("\n" + "="*80)
print("Statistics for Bar Charts")
print("="*80)

print("\n--- Analysis by Prompt (Counts) ---")
print(analysis_by_prompt.to_string())
print("\n--- Analysis by Prompt (Percentages) ---")
analysis_by_prompt_pct = analysis_by_prompt.div(analysis_by_prompt.sum(axis=1), axis=0) * 100
print(analysis_by_prompt_pct.round(1).to_string())

print("\n--- Analysis by Project (Counts) ---")
print(analysis_by_project.to_string())
print("\n--- Analysis by Project (Percentages) ---")
analysis_by_project_pct = analysis_by_project.div(analysis_by_project.sum(axis=1), axis=0) * 100
print(analysis_by_project_pct.round(1).to_string())

print("\n--- Analysis by Model (Counts) ---")
print(analysis_by_model.to_string())
print("\n--- Analysis by Model (Percentages) ---")
analysis_by_model_pct = analysis_by_model.div(analysis_by_model.sum(axis=1), axis=0) * 100
print(analysis_by_model_pct.round(1).to_string())

# --- 3. Visualize the Results (Bar Charts) ---
# Define the custom color scheme
custom_colors = ['#8C8CC8', 'lightgrey', 'lightgreen']

# Create a figure with three subplots, side-by-side
# Adjust width ratios to accommodate 4 models instead of 2
fig, axes = plt.subplots(1, 3, figsize=(20, 7), gridspec_kw={'width_ratios': [4, 4, 4]})

# --- Plot 1: Distribution by Project (Percentage) ---
analysis_by_project_pct = analysis_by_project.div(analysis_by_project.sum(axis=1), axis=0) * 100
analysis_by_project_pct.plot(kind='bar', stacked=True, ax=axes[0], color=custom_colors, edgecolor='white', width=0.8)
axes[0].set_title('(a) by Project', fontsize=22, pad=20)
axes[0].set_ylabel('Percentage of Solutions (%)', fontsize=22)
axes[0].set_xlabel('', fontsize=22)
axes[0].tick_params(axis='x', rotation=0, labelsize=22)
axes[0].tick_params(axis='y', labelsize=22)
axes[0].grid(axis='y', linestyle='--', alpha=0.7)
axes[0].get_legend().remove()
for c in axes[0].containers:
    labels = [f'{v.get_height():.0f}%' if v.get_height() > 5 else '' for v in c]
    axes[0].bar_label(c, labels=labels, label_type='center', color='black', fontsize=22)

# --- Plot 2: Distribution by Prompt (Percentage) ---
analysis_by_prompt_pct = analysis_by_prompt.div(analysis_by_prompt.sum(axis=1), axis=0) * 100
analysis_by_prompt_pct.plot(kind='bar', stacked=True, ax=axes[1], color=custom_colors, edgecolor='white', width=0.8)
axes[1].set_title('(b) by Prompt', fontsize=22, pad=20)
axes[1].set_xlabel('', fontsize=22)
axes[1].tick_params(axis='x', rotation=0, labelsize=22)
axes[1].tick_params(axis='y', labelsize=22)
axes[1].grid(axis='y', linestyle='--', alpha=0.7)
axes[1].get_legend().remove()
for c in axes[1].containers:
    # Always show labels for non-zero segments in (b) so small Divergence values (e.g., for Both) are visible
    labels = [f'{v.get_height():.0f}%' if v.get_height() > 0 else '' for v in c]
    axes[1].bar_label(c, labels=labels, label_type='center', color='black', fontsize=22)

# --- Plot 3: Distribution by Model (Percentage) ---
analysis_by_model_pct = analysis_by_model.div(analysis_by_model.sum(axis=1), axis=0) * 100
analysis_by_model_pct.plot(kind='bar', stacked=True, ax=axes[2], color=custom_colors, edgecolor='white', width=0.8)
axes[2].set_title('(c) by Model', fontsize=22, pad=20)
axes[2].set_xlabel('', fontsize=22)
axes[2].tick_params(axis='x', rotation=0, labelsize=22)
axes[2].tick_params(axis='y', labelsize=22)
axes[2].grid(axis='y', linestyle='--', alpha=0.7)
axes[2].get_legend().remove()
for c in axes[2].containers:
    labels = [f'{v.get_height():.0f}%' if v.get_height() > 5 else '' for v in c]
    axes[2].bar_label(c, labels=labels, label_type='center', color='black', fontsize=22)

# --- Create and place a single legend at the bottom of the bar chart figure ---
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.5, 0), ncol=3, fontsize=22, frameon=False)

# Adjust layout to prevent overlap and make space for the legend
fig.tight_layout(rect=[0, 0.08, 1, 1])

# Save the combined bar chart to a file
output_filename_bar = 'prompt_classification_analysis.pdf'
plt.savefig(output_filename_bar)


# --- Print Statistics for Box Plot ---
print("\n" + "="*80)
print("Statistics for Box Plot (by Classification)")
print("="*80)

# Calculate statistics for each classification
for cls in classification_order:
    cls_data = df_filtered[df_filtered['classification'] == cls]['final_score']
    if len(cls_data) > 0:
        print(f"\n--- {cls} ---")
        print(f"  Count: {len(cls_data)}")
        print(f"  Mean: {cls_data.mean():.4f}")
        print(f"  Median: {cls_data.median():.4f}")
        print(f"  Std: {cls_data.std():.4f}")
        print(f"  Min: {cls_data.min():.4f}")
        print(f"  Max: {cls_data.max():.4f}")
        print(f"  Q1 (25%): {cls_data.quantile(0.25):.4f}")
        print(f"  Q3 (75%): {cls_data.quantile(0.75):.4f}")

# Overall statistics
print("\n--- Overall Statistics ---")
print(f"Total entries: {len(df_filtered)}")
print(f"Mean final_score: {df_filtered['final_score'].mean():.4f}")
print(f"Median final_score: {df_filtered['final_score'].median():.4f}")

# --- 4. Visualize Score by Classification (Horizontal Box Plot in a Separate Figure) ---
fig_box, ax_box = plt.subplots(figsize=(15, 3.6))

sns.boxplot(y='classification', x='final_score', data=df_filtered, order=classification_order, ax=ax_box, palette=custom_colors, width=0.5, showfliers=False, orient='h')
ax_box.set_title('', fontsize=22, pad=20)
ax_box.set_xlabel('Performance (pss scores)', fontsize=22)
ax_box.set_ylabel('') # Remove the y-axis label
ax_box.set_yticklabels(['Match', 'Alignment', 'Divergence']) # Set custom labels for the y-axis
ax_box.tick_params(axis='x', labelsize=22)
ax_box.tick_params(axis='y', labelsize=22)
ax_box.grid(axis='x', linestyle='--', alpha=0.7)
line = ax_box.axvline(x=1.0, color='r', linestyle='--')

# Add median labels to the horizontal boxplot
medians = df_filtered.groupby(['classification'])['final_score'].median().reindex(classification_order)
horizontal_offset = 0.1  # Adjust this value for better label positioning

for ytick in ax_box.get_yticks():
    median_val = medians[classification_order[ytick]]
    ax_box.text(median_val + horizontal_offset, ytick, f'{median_val:.2f}', 
                 verticalalignment='center', color='black', fontsize=14)

ax_box.legend(handles=[line], labels=['Baseline Score = 1.0'], loc='lower right', fontsize=18, frameon=False)
fig_box.tight_layout()
output_filename_box = 'boxplot_classification_analysis.pdf'
plt.savefig(output_filename_box)

# output_filename_txt = 'qualitative_analysis_summary.txt'
# with open(output_filename_txt, 'w') as f:
#     f.write("--- Analysis of Project vs. Classification ---\n")
#     f.write(analysis_by_project.to_string())
#     f.write("\n\n" + "-"*50 + "\n\n")

#     f.write("--- Analysis of Prompt vs. Classification ---\n")
#     f.write(analysis_by_prompt.to_string())
#     f.write("\n\n" + "-"*50 + "\n\n")

#     f.write("--- Analysis of Model vs. Classification ---\n")
#     f.write(analysis_by_model.to_string())
#     f.write("\n\n" + "-"*50 + "\n\n")

#     f.write("--- Summary Statistics for Score by Classification ---\n")
#     f.write(df_filtered.groupby('classification')['final_score'].describe().to_string())
