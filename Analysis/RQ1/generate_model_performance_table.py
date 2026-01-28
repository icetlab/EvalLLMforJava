#!/usr/bin/env python3
"""
Generate a performance summary table using pure Python (no pandas/scipy).
"""

import csv
import math
from collections import defaultdict

# Read CSV
csv_path = '../preprocessing/representative_benchmark_scores.csv'
print(f"Reading {csv_path}")

data = defaultdict(list)
dev_data = {}

with open(csv_path, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        model = row['model']
        project = row['project']
        hash_val = row['hash_value']
        prompt = row['prompt']
        trial = row['trial']
        score_str = row['final_score']
        
        if not score_str:
            continue
            
        try:
            score = float(score_str)
        except:
            continue
        
        if model == 'developer':
            dev_data[(project, hash_val)] = score
        else:
            # Store as (trial, score) for sorting
            try:
                trial_num = float(trial) if trial else 0
            except:
                trial_num = 0
            
            data[(project, hash_val, model, prompt)].append((trial_num, score))

print(f"Loaded {len(dev_data)} developer entries")
print(f"Loaded {len(data)} LLM entries")

# Select median trial for each model-prompt-task combo
# - 1 trial: select that one
# - 2 trials: select the smaller score
# - 3+ trials: select the median score
selected = {}
for key, trials_scores in data.items():
    if len(trials_scores) == 1:
        # Only one trial, select it
        selected[key] = trials_scores[0][1]
    elif len(trials_scores) == 2:
        # Two trials, select the smaller score
        trials_scores.sort(key=lambda x: x[1])
        selected[key] = trials_scores[0][1]
    else:
        # Three or more trials, select median by score
        trials_scores.sort(key=lambda x: x[1])
        idx = len(trials_scores) // 2
        selected[key] = trials_scores[idx][1]

print(f"Selected {len(selected)} median entries")

# Organize by project
projects = sorted(set(p for p, _, _, _ in selected.keys()))
# Use all four models
models = ['gpt', 'gemini', 'deepseek-v3', 'deepseek-r1']
prompts = ['prompt1', 'prompt3', 'prompt2', 'prompt4']  # Order: NH, Bench, Prob, Both

# Generate LaTeX
latex = []
latex.append("\\begin{table}[h!]")
latex.append("\\centering")
latex.append("\\scriptsize")
latex.append("\\caption{$pss$ scores by task, grouped by project and sorted by magnitude of the developer improvement.}")
latex.append("\\label{tab:hash_performance_summary}")
latex.append("\\resizebox{0.9\\textwidth}{!}{%")
latex.append("\\begin{tabular}{@{}c l l " + "c " * 16 + "@{}}")
latex.append("\\toprule")
latex.append("& \\multicolumn{2}{c}{\\textbf{ }} & \\multicolumn{4}{c}{\\textbf{o4-mini}} & \\multicolumn{4}{c}{\\textbf{Gemini 2.5 Pro}} & \\multicolumn{4}{c}{\\textbf{DeepSeek V3}} & \\multicolumn{4}{c}{\\textbf{DeepSeek R1}} \\\\")
latex.append("\\cmidrule(lr){4-7} \\cmidrule(lr){8-11} \\cmidrule(lr){12-15} \\cmidrule(lr){16-19}")
latex.append("\\textbf{Project} & \\textbf{Hash} & \\textbf{Dev} & NH & Bench & Prob & Both & NH & Bench & Prob & Both & NH & Bench & Prob & Both & NH & Bench & Prob & Both \\\\")
latex.append("\\midrule")

# Overall accumulators across all projects (only tasks with LLM data)
overall_dev_scores = []
overall_all_scores = defaultdict(list)  # key: (model, prompt) -> list of scores
overall_num_tasks = 0

for proj in projects:
    # Get all tasks for this project
    tasks = []
    for (p, hash_val), dev_score in dev_data.items():
        if p == proj:
            # Calculate average LLM score
            llm_scores = []
            for model in models:
                for prompt in prompts:
                    key = (p, hash_val, model, prompt)
                    if key in selected:
                        llm_scores.append(selected[key])
            
            # Only include tasks that have at least one LLM result
            if llm_scores:
                avg_llm = sum(llm_scores) / len(llm_scores)
                if avg_llm > 0:
                    improvement = dev_score / avg_llm
                else:
                    improvement = 0
                
                tasks.append({
                    'hash': hash_val,
                    'dev_score': dev_score,
                    'improvement': improvement,
                    'has_llm_data': True
                })
    
    # Sort by dev_score (developer performance) descending
    tasks.sort(key=lambda x: x['dev_score'], reverse=True)
    
    if not tasks:
        continue
    
    # Collect scores for averaging
    all_scores = defaultdict(list)
    
    proj_name = proj.capitalize() if proj != 'RoaringBitmap' else 'RoaringBitmap'
    first = True
    
    for task_idx, task in enumerate(tasks):
        hash_val = task['hash']
        dev_score = task['dev_score']
        
        cells = []
        
        if first:
            num_rows = len(tasks) + 1
            cells.append(f"\\multirow{{{num_rows}}}{{*}}{{\\rotatebox[origin=c]{{90}}{{\\textbf{{{proj_name}}}}}}}")
            first = False
        else:
            cells.append("")
        
        # Build GitHub link
        repo_map_short = {
            'RoaringBitmap': 'RoaringBitmap/RoaringBitmap',
            'kafka': 'apache/kafka',
            'netty': 'netty/netty',
            'presto': 'prestodb/presto'
        }
        repo = repo_map_short.get(proj, proj)
        github_url = f"https://github.com/{repo}/commit/{hash_val}"
        cells.append(f"\\href{{{github_url}}}{{{hash_val[:7]}}}")
        cells.append(f"{dev_score:.2f}")

        # Accumulate for overall averages
        overall_dev_scores.append(dev_score)
        overall_num_tasks += 1
        
        # Add scores for each model-prompt
        for model in models:
            for prompt in prompts:
                key = (proj, hash_val, model, prompt)
                if key in selected:
                    score = selected[key]
                    all_scores[(model, prompt)].append(score)
                    overall_all_scores[(model, prompt)].append(score)
                    
                    # Color: green if > dev_score, red if < 1.0
                    if score > dev_score:
                        cells.append(f"\\cellcolor{{lightgreen}}{{{score:.2f}}}")
                    elif score < 1.0:
                        cells.append(f"\\cellcolor{{lightred}}{{{score:.2f}}}")
                    else:
                        cells.append(f"{score:.2f}")
                else:
                    cells.append("-")
        
        latex.append(" & ".join(cells) + " \\\\")
    
    # Average row with geometric mean (only include tasks with LLM data)
    avg_cells = ["", "Avg"]
    
    # Filter tasks that have LLM data
    tasks_with_data = [task for task in tasks if task.get('has_llm_data', True)]
    
    # Add geometric mean for developer scores (only tasks with LLM data)
    dev_scores_project = [task['dev_score'] for task in tasks_with_data]
    if dev_scores_project:
        product = 1.0
        for s in dev_scores_project:
            product *= s
        dev_gmean = product ** (1.0 / len(dev_scores_project))
        avg_cells.append(f"{dev_gmean:.2f}")
    else:
        avg_cells.append("-")
    
    # Add geometric means for each model-prompt pair
    # Only count tasks that have LLM data
    num_tasks_with_data = len(tasks_with_data)
    for model in models:
        for prompt in prompts:
            scores = all_scores[(model, prompt)]
            
            if not scores:
                # All values missing - result is 0
                avg_cells.append("0.00")
            else:
                # Include 0 for missing values in tasks with LLM data
                # Geometric mean: (prod of all values) ^ (1 / num_tasks_with_data)
                product = 1.0
                for s in scores:
                    product *= s
                gmean = product ** (1.0 / num_tasks_with_data)
                avg_cells.append(f"{gmean:.2f}")
    
    latex.append(" & ".join(avg_cells) + " \\\\")
    latex.append("\\midrule")

# --- Overall average row across all projects ---
overall_cells = ["", "Overall"]

# Overall geometric mean for developer scores
if overall_dev_scores:
    prod_dev = 1.0
    for s in overall_dev_scores:
        prod_dev *= s
    overall_dev_gmean = prod_dev ** (1.0 / len(overall_dev_scores))
    overall_cells.append(f"{overall_dev_gmean:.2f}")
else:
    overall_cells.append("-")

# Overall geometric means for each model-prompt pair
for model in models:
    for prompt in prompts:
        scores = overall_all_scores[(model, prompt)]
        if not scores or overall_num_tasks == 0:
            overall_cells.append("0.00")
        else:
            prod = 1.0
            for s in scores:
                prod *= s
            gmean = prod ** (1.0 / overall_num_tasks)
            overall_cells.append(f"{gmean:.2f}")

latex.append(" & ".join(overall_cells) + " \\\\")

latex.append("\\bottomrule")
latex.append("\\end{tabular}")
latex.append("}")
latex.append("\\end{table}")

# Save
output_path = 'model_performance_table.tex'
with open(output_path, 'w') as f:
    f.write('\n'.join(latex))

print(f"Saved to {output_path}")
print(f"Total lines: {len(latex)}")
