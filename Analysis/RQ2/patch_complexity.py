import os
import re
import glob
import csv
import json
import statistics
from collections import defaultdict
from typing import Dict, List, Tuple, Set

def parse_diff_file(diff_path: str) -> Dict:
    """
    Parse a diff file and extract complexity metrics:
    - LOC Modified: lines added + lines removed
    - Hunks: number of @@ blocks
    - Methods Involved: methods that intersect with the patch (simplified by extracting method signatures from context)
    """
    try:
        with open(diff_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {diff_path}: {e}")
        return None

    if not content.strip():
        return None

    lines = content.split('\n')
    
    # Count LOC Modified (lines starting with + or -, excluding +++ and ---)
    loc_added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
    loc_removed = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
    loc_modified = loc_added + loc_removed
    
    # Calculate Added/Removed Ratio (avoid division by zero)
    added_removed_ratio = loc_added / loc_removed if loc_removed > 0 else (loc_added if loc_added > 0 else 0)
    
    # Calculate Cyclomatic Complexity Change (ΔCC)
    # Branch keywords that increase CC: if, for, while, case, catch, &&, ||, ?
    # Each occurrence of these keywords increases/decreases complexity by 1
    branch_keywords = ['if', 'for', 'while', 'case', 'catch']
    branch_operators = ['&&', '||', '?']  # Ternary operator and logical operators
    
    def count_branch_elements(text):
        """Count branch keywords and operators in text."""
        count = 0
        # Remove leading + or - from diff lines for analysis
        clean_text = text
        
        # Count keywords (as whole words to avoid false positives)
        for keyword in branch_keywords:
            # Use word boundaries to match whole words only
            pattern = r'\b' + re.escape(keyword) + r'\b'
            count += len(re.findall(pattern, clean_text, re.IGNORECASE))
        
        # Count operators (need to be careful with context)
        for operator in branch_operators:
            # Count occurrences, but avoid counting && and || when they're part of other operators
            if operator == '?':
                # Ternary operator: match ? followed by something (not just ? alone)
                # Pattern: something ? something : something
                # Avoid matching in comments (// ? or /* ?)
                # Use lookahead to ensure it's not followed by / (comment)
                count += len(re.findall(r'\?\s*[^/\n]', clean_text))
            elif operator == '&&':
                count += clean_text.count('&&')
            elif operator == '||':
                count += clean_text.count('||')
        
        return count
    
    # Count branch elements in added lines
    added_lines = [line[1:] for line in lines if line.startswith('+') and not line.startswith('+++')]
    added_text = '\n'.join(added_lines)
    branch_elements_added = count_branch_elements(added_text)
    
    # Count branch elements in removed lines
    removed_lines = [line[1:] for line in lines if line.startswith('-') and not line.startswith('---')]
    removed_text = '\n'.join(removed_lines)
    branch_elements_removed = count_branch_elements(removed_text)
    
    # Calculate ΔCC: complexity added - complexity removed
    delta_cc = branch_elements_added - branch_elements_removed
    
    # Count hunks (blocks starting with @@)
    hunks = sum(1 for line in lines if line.startswith('@@'))
    
    # Count files modified (lines starting with "diff --git")
    files_modified = sum(1 for line in lines if line.startswith('diff --git'))
    
    # Calculate hunk sizes (lines per hunk)
    hunk_sizes = []
    current_hunk_size = 0
    in_hunk = False
    
    for line in lines:
        if line.startswith('@@'):
            # Save previous hunk size if any
            if in_hunk and current_hunk_size > 0:
                hunk_sizes.append(current_hunk_size)
            current_hunk_size = 0
            in_hunk = True
            continue
        elif line.startswith('diff --git'):
            # End of hunk context
            if in_hunk and current_hunk_size > 0:
                hunk_sizes.append(current_hunk_size)
                current_hunk_size = 0
            in_hunk = False
            continue
        elif in_hunk and (line.startswith(' ') or line.startswith('-') or line.startswith('+')):
            # Count context and modified lines in hunk
            current_hunk_size += 1
    
    # Save last hunk if any
    if in_hunk and current_hunk_size > 0:
        hunk_sizes.append(current_hunk_size)
    
    avg_hunk_size = statistics.mean(hunk_sizes) if hunk_sizes else 0
    max_hunk_size = max(hunk_sizes) if hunk_sizes else 0
    
    # Extract methods involved by finding:
    # 1. Method definitions that are modified (method declarations in diff context)
    # 2. Method calls in the modified code (method invocations)
    methods_involved = set()
    
    # Pattern 1: Method declarations/definitions in Java/Scala
    # Matches: def methodName(... or public/private methodName(... or override def methodName(...)
    method_def_pattern = re.compile(
        r'(?:^\s*(?:public|private|protected|override\s+def|def|final|static)\s+)?'  # modifiers
        r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*'  # method name
        r'\([^)]*\)\s*[:\{=]',  # parameters and return type/body start
        re.MULTILINE
    )
    
    # Pattern 2: Method calls/invocations
    # Matches: methodName(... or object.methodName(... or this.methodName(...)
    # Exclude common keywords and constructors (new, return, if, for, while, etc.)
    method_call_pattern = re.compile(
        r'(?:^|\s|[.;])([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(',  # method name followed by (
        re.MULTILINE
    )
    
    # Keywords to exclude from method calls (they might match the pattern but aren't methods)
    excluded_keywords = {
        'if', 'for', 'while', 'switch', 'catch', 'return', 'new', 'import', 'package',
        'class', 'interface', 'extends', 'implements', 'throws', 'super', 'this',
        'val', 'var', 'def', 'object', 'trait', 'case', 'match', 'try', 'finally',
        'yield', 'throw', 'do', 'else', 'when', 'with'
    }
    
    # Collect all code from modified lines (both removed and added)
    modified_code_lines = []
    in_hunk_context = False
    
    for line in lines:
        if line.startswith('@@'):
            in_hunk_context = True
            continue
        elif line.startswith('diff --git') or line.startswith('index ') or line.startswith('---') or line.startswith('+++'):
            in_hunk_context = False
            continue
        
        if in_hunk_context:
            # Collect both removed (-) and added (+) lines to get full context
            # Also include context lines (starting with space) around the changes
            if line.startswith(' ') or line.startswith('-') or line.startswith('+'):
                # Remove leading +, -, or space to get the actual code
                code_line = line[1:] if line.startswith((' ', '-', '+')) else line
                modified_code_lines.append(code_line)
    
    # Combine all modified code into one text block for analysis
    methods_modified = set()  # Only method definitions that are modified
    if modified_code_lines:
        modified_code_text = '\n'.join(modified_code_lines)
        
        # Extract method definitions (methods being modified)
        def_matches = method_def_pattern.findall(modified_code_text)
        methods_involved.update(def_matches)
        methods_modified.update(def_matches)
        
        # Extract method calls (methods being called in modified code)
        call_matches = method_call_pattern.findall(modified_code_text)
        # Filter out only obvious keywords, include all potential method calls
        # (as per requirement: "代码中调用或者修改的method全部算为involved")
        for match in call_matches:
            method_name = match.strip()
            # Only exclude if it's a known keyword or single lowercase letter (likely loop variable like i, j, k)
            if (method_name not in excluded_keywords and 
                not (len(method_name) == 1 and method_name.islower())):
                methods_involved.add(method_name)
    
    return {
        'loc_modified': loc_modified,
        'loc_added': loc_added,
        'loc_removed': loc_removed,
        'added_removed_ratio': added_removed_ratio,
        'files_modified': files_modified if files_modified > 0 else 1,  # At least 1 file if there's a diff
        'hunks': hunks,
        'avg_hunk_size': avg_hunk_size,
        'max_hunk_size': max_hunk_size,
        'delta_cc': delta_cc,
        'branch_elements_added': branch_elements_added,
        'branch_elements_removed': branch_elements_removed,
        'methods_involved': len(methods_involved),
        'methods_modified': len(methods_modified),  # Distinct methods whose definitions are modified
        'method_names': sorted(methods_involved)
    }


def get_model_and_source_from_path(diff_path: str) -> Tuple[str, str]:
    """
    Extract model name and source (developer/llm) from diff file path.
    Returns: (model_name, source)
    - For developer: ("developer", "developer")
    - For LLM: (model_name, "llm")
    """
    if '/baseline_raw/' in diff_path and '/dev/' in diff_path:
        return ("developer", "developer")
    elif '/llm_output/' in diff_path or '/llm_output_raw/' in diff_path:
        # Extract model name from path
        # Format: .../llm_output/{project}/{model}/{commit}/prompt*.diff
        # or: .../llm_output_raw/{project}/{model-trial}/{commit}/prompt*.diff
        match = re.search(r'(?:llm_output|llm_output_raw)/[^/]+/([^/]+)/', diff_path)
        if match:
            model_name = match.group(1)
            # For old format (gpt-1, gemini-1), extract base name
            if '-' in model_name and model_name.split('-')[0] in ['gpt', 'gemini']:
                base_model = model_name.split('-')[0]
                return (base_model, "llm")
            else:
                # New format (deepseek-r1, deepseek-v3) or already base name
                return (model_name, "llm")
    return ("unknown", "unknown")


def collect_all_patches() -> Dict[str, List[Dict]]:
    """
    Collect all diff files from baseline_raw and llm_output directories.
    Returns a dictionary mapping (project, commit_id, model) to patch metrics.
    """
    projects = ['kafka', 'netty', 'presto', 'RoaringBitmap']
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    all_patches = defaultdict(list)  # key: (project, commit_id, model), value: list of patch metrics
    
    for project in projects:
        # Developer patches
        dev_pattern = os.path.join(base_dir, 'Dataset', 'baseline_raw', project, 'dev', '*.diff')
        for diff_file in glob.glob(dev_pattern):
            commit_id = os.path.basename(diff_file).replace('.diff', '')
            metrics = parse_diff_file(diff_file)
            if metrics:
                model, source = get_model_and_source_from_path(diff_file)
                all_patches[(project, commit_id, model)].append({
                    **metrics,
                    'source': source,
                    'prompt': '',
                    'trial': ''
                })
        
        # LLM patches (new format: llm_output)
        llm_pattern = os.path.join(base_dir, 'Dataset', 'llm_output', project, '*', '*', '*.diff')
        for diff_file in glob.glob(llm_pattern):
            # Extract commit_id and prompt from path
            # Format: .../llm_output/{project}/{model}/{commit}/prompt*.diff
            parts = diff_file.split(os.sep)
            model = parts[-3]
            commit_id = parts[-2]
            prompt_match = re.search(r'prompt(\d+)', os.path.basename(diff_file))
            prompt = f"prompt{prompt_match.group(1)}" if prompt_match else ""
            trial = "1"  # deepseek models always have trial 1
            
            metrics = parse_diff_file(diff_file)
            if metrics:
                all_patches[(project, commit_id, model)].append({
                    **metrics,
                    'source': 'llm',
                    'prompt': prompt,
                    'trial': trial
                })
        
        # LLM patches (old format: llm_output_raw)
        llm_raw_pattern = os.path.join(base_dir, 'Dataset', 'llm_output_raw', project, '*', '*', '*.diff')
        for diff_file in glob.glob(llm_raw_pattern):
            # Extract model, trial, commit_id, and prompt from path
            # Format: .../llm_output_raw/{project}/{model-trial}/{commit}/prompt*.diff
            parts = diff_file.split(os.sep)
            model_trial = parts[-3]
            commit_id = parts[-2]
            
            # Parse model-trial (e.g., "gpt-1" -> model="gpt", trial="1")
            if '-' in model_trial:
                model, trial = model_trial.rsplit('-', 1)
            else:
                model = model_trial
                trial = ""
            
            prompt_match = re.search(r'prompt(\d+)', os.path.basename(diff_file))
            prompt = f"prompt{prompt_match.group(1)}" if prompt_match else ""
            
            metrics = parse_diff_file(diff_file)
            if metrics:
                all_patches[(project, commit_id, model)].append({
                    **metrics,
                    'source': 'llm',
                    'prompt': prompt,
                    'trial': trial
                })
    
    return all_patches


def calculate_statistics_by_model(patches_by_key: Dict[str, List[Dict]]) -> Dict[str, Dict]:
    """
    Calculate statistics (mean, median, max) for each model.
    Groups by model name (aggregating across projects, commits, prompts, trials).
    """
    model_stats = defaultdict(lambda: {
        'loc_modified': [],
        'hunks': [],
        'delta_cc': []
    })
    
    for (project, commit_id, model), patches in patches_by_key.items():
        for patch in patches:
            model_stats[model]['loc_modified'].append(patch['loc_modified'])
            model_stats[model]['hunks'].append(patch['hunks'])
            model_stats[model]['delta_cc'].append(patch['delta_cc'])
    
    # Calculate statistics
    result = {}
    for model, data in model_stats.items():
        if data['loc_modified']:  # Only include models with data
            result[model] = {
                'loc_modified_mean': statistics.mean(data['loc_modified']),
                'loc_modified_std': statistics.stdev(data['loc_modified']) if len(data['loc_modified']) > 1 else 0.0,
                'loc_modified_max': max(data['loc_modified']),
                'loc_modified_min': min(data['loc_modified']),
                'hunks_mean': statistics.mean(data['hunks']),
                'hunks_std': statistics.stdev(data['hunks']) if len(data['hunks']) > 1 else 0.0,
                'hunks_max': max(data['hunks']),
                'hunks_min': min(data['hunks']),
                'delta_cc_mean': statistics.mean(data['delta_cc']),
                'delta_cc_std': statistics.stdev(data['delta_cc']) if len(data['delta_cc']) > 1 else 0.0,
                'delta_cc_max': max(data['delta_cc']),
                'delta_cc_min': min(data['delta_cc'])
            }
    
    return result


def generate_table_data() -> List[Dict]:
    """
    Generate table data in the format needed for LaTeX table.
    Groups models as specified:
    - Developer (developer)
    - OpenAI o4-mini (gpt)
    - Gemini 2.5 Pro (gemini)
    - DeepSeek V3 (deepseek-v3)
    - DeepSeek R1 (deepseek-r1)
    """
    all_patches = collect_all_patches()
    stats = calculate_statistics_by_model(all_patches)
    
    # Map model names to display names
    model_display_map = {
        'developer': 'Developer',
        'gpt': 'OpenAI o4-mini',
        'gemini': 'Gemini 2.5 Pro',
        'deepseek-v3': 'DeepSeek V3',
        'deepseek-r1': 'DeepSeek R1'
    }
    
    result = []
    
    # Define order for table
    model_order = ['Developer', 'OpenAI o4-mini', 'Gemini 2.5 Pro', 'DeepSeek V3', 'DeepSeek R1']
    
    for display_name in model_order:
        # Find corresponding model key
        model_key = None
        for key, display in model_display_map.items():
            if display == display_name:
                model_key = key
                break
        
        if model_key and model_key in stats:
            s = stats[model_key]
            result.append({
                'Source': display_name,
                'LOC Modified Mean': f"{s['loc_modified_mean']:.1f}",
                'LOC Modified Std': f"{s['loc_modified_std']:.1f}",
                'LOC Modified Max': f"{s['loc_modified_max']}",
                'LOC Modified Min': f"{s['loc_modified_min']}",
                'Hunks Mean': f"{s['hunks_mean']:.1f}",
                'Hunks Std': f"{s['hunks_std']:.1f}",
                'Hunks Max': f"{s['hunks_max']}",
                'Hunks Min': f"{s['hunks_min']}",
                'Delta CC Mean': f"{s['delta_cc_mean']:.1f}",
                'Delta CC Std': f"{s['delta_cc_std']:.1f}",
                'Delta CC Max': f"{s['delta_cc_max']}",
                'Delta CC Min': f"{s['delta_cc_min']}"
            })
        else:
            # No data for this model
            result.append({
                'Source': display_name,
                'LOC Modified Mean': '--',
                'LOC Modified Std': '--',
                'LOC Modified Max': '--',
                'LOC Modified Min': '--',
                'Hunks Mean': '--',
                'Hunks Std': '--',
                'Hunks Max': '--',
                'Hunks Min': '--',
                'Delta CC Mean': '--',
                'Delta CC Std': '--',
                'Delta CC Max': '--',
                'Delta CC Min': '--'
            })
    
    return result


def save_to_csv(output_path: str):
    """
    Save the complexity metrics to a CSV file.
    """
    table_data = generate_table_data()
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        if table_data:
            writer = csv.DictWriter(f, fieldnames=table_data[0].keys())
            writer.writeheader()
            writer.writerows(table_data)
    
    print(f"Patch complexity metrics saved to {output_path}")
    
    # Print summary
    print("\n=== Patch Complexity Summary ===")
    for row in table_data:
        if row['LOC Modified Mean'] != '--':
            print(f"\n{row['Source']}:")
            print(f"  LOC Modified - Mean: {row['LOC Modified Mean']} (Std: {row['LOC Modified Std']}), Max: {row['LOC Modified Max']}, Min: {row['LOC Modified Min']}")
            print(f"  Hunks - Mean: {row['Hunks Mean']} (Std: {row['Hunks Std']}), Max: {row['Hunks Max']}, Min: {row['Hunks Min']}")
            print(f"  ΔCC - Mean: {row['Delta CC Mean']} (Std: {row['Delta CC Std']}), Max: {row['Delta CC Max']}, Min: {row['Delta CC Min']}")


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(base_dir, 'patch_complexity_metrics.csv')
    save_to_csv(output_path)
