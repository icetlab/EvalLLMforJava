import os
import json
import pandas as pd
import re

def aggregate_performance_data(root_dirs, output_csv):
    """
    Loads all raw performance data from subdirectories, processes it, and saves it to a CSV file.

    Args:
        root_dirs (list): A list of root directories to process.
        output_csv (str): The path to save the final CSV file.
    """
    all_records = []
    for root_dir in root_dirs:
        for subdir, _, files in os.walk(root_dir):
            for file in files:
                if file.endswith('.json') and '.diff.log' not in file:
                    json_path = os.path.join(subdir, file)
                    
                    if os.path.getsize(json_path) == 0:
                        print(f"Skipping empty file: {json_path}")
                        continue

                    # Extract metadata from path
                    path_parts = subdir.split(os.sep)
                    if root_dir == 'llm_output':
                        project = path_parts[-3]
                        model_version = path_parts[-2]
                        commit_hash = path_parts[-1]
                        prompt = file.split('_')[0]
                    elif root_dir == 'baseline':
                        project = path_parts[-2]
                        model_version = path_parts[-1] # dev or org
                        commit_hash = file.split('_')[0]
                        prompt = 'N/A' # No prompt for baseline
                    else:
                        continue

                    try:
                        with open(json_path, 'rb') as f:
                            raw_content = f.read()
                        content = raw_content.decode('utf-8', errors='replace')
                        # Remove newlines within the JSON file to prevent parsing errors
                        content = re.sub(r'\n\s*', ' ', content)
                        data = json.loads(content)
                    except json.JSONDecodeError as e:
                        print(f"Error decoding JSON from file {json_path}: {e}")
                        continue

                    try:
                        for record in data:
                            raw_data_batches = record.get('primaryMetric', {}).get('rawData', [])
                            for batch in raw_data_batches:
                                for raw_score in batch:
                                    all_records.append({
                                        'project': project,
                                        'model': model_version,
                                        'hash': commit_hash,
                                        'prompt': prompt,
                                        'benchmark': record.get('benchmark'),
                                        'mode': record.get('mode'),
                                        'params': str(record.get('params', {})),
                                        'score': raw_score
                                    })
                    except (KeyError, TypeError) as e:
                        print(f"Error processing data in {json_path}: {e}")

    if not all_records:
        print("No performance data found.")
        return

    df = pd.DataFrame(all_records)
    
    try:
        df.to_csv(output_csv, index=False)
        print(f"Successfully aggregated performance data to {output_csv}")
    except IOError as e:
        print(f"Error saving CSV file: {e}")

if __name__ == "__main__":
    aggregate_performance_data(['llm_output', 'baseline'], 'llm_and_baseline_performance_data_raw.csv')
