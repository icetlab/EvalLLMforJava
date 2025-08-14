import json
import os
import re
import glob
from collections import defaultdict
import csv

def extract_score_data(file_path):
    """
    Parses a JSON file containing benchmark data and extracts relevant metrics.
    It can handle different JSON structures and aggregates results.
    """
    with open(file_path, "r") as f:
        try:
            content = f.read()
            # Remove newlines within the JSON file to prevent parsing errors
            content = re.sub(r'\n\s*', ' ', content)
            data = json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Failed to parse {file_path}: {e}")
            return []

    # The JSON data can be a list of benchmarks or a dictionary containing them.
    if isinstance(data, list):
        benchmarks = data
    elif isinstance(data, dict) and "benchmarks" in data:
        benchmarks = data["benchmarks"]
    else:
        benchmarks = [data]

    result = []
    for entry in benchmarks:
        bench_name = entry.get("benchmark", "")
        mode = entry.get("mode", "unknown")
        metric = entry.get("primaryMetric", {})
        score = metric.get("score", None)
        error = metric.get("scoreError", None)
        unit = metric.get("scoreUnit", "unknown")

        params = entry.get("params", {})
        if params:
            # Create a consistent string representation of parameters.
            params_str = ",".join(f"{k}={params[k]}" for k in sorted(params.keys()))
        else:
            params_str = ""

        if bench_name and score is not None:
            result.append({
                "benchmark": bench_name,
                "score": score,
                "error": error,
                "unit": unit,
                "mode": mode,
                "params": params_str
            })

    # Aggregate results for the same benchmark configuration.
    aggregated = defaultdict(list)
    for entry in result:
        key = (entry["benchmark"], entry["mode"], entry["unit"], entry["params"])
        aggregated[key].append(entry)

    merged_result = []
    for (bench_name, mode, unit, params), entries in aggregated.items():
        avg_score = sum(e["score"] for e in entries) / len(entries)
        errors = [e["error"] for e in entries if e["error"] is not None]
        avg_error = sum(errors) / len(errors) if errors else None

        merged_result.append({
            "benchmark": bench_name,
            "score": avg_score,
            "error": avg_error,
            "unit": unit,
            "mode": mode,
            "params": params
        })

    return merged_result


def parse_version_from_filename(file_path):
    """
    Parses model, prompt, and trial number from the file path.
    Returns a dictionary with the parsed information.
    """
    if "/org/" in file_path:
        return {"model": "original", "prompt": "", "trial": ""}
    if "/dev/" in file_path:
        return {"model": "developer", "prompt": "", "trial": ""}
    
    # Regex to capture model-trial (e.g., gpt-1) and prompt number
    # Example path: ../llm_output/kafka/gpt-1/4fa5bdc/prompt1_AclAuthorizerBenchmark.json
    match = re.search(r'/(gpt|gemini)-(\d+)/.*?/(prompt\d+)_', file_path)
    if match:
        model = match.group(1)
        trial = match.group(2)
        prompt = match.group(3)
        return {"model": model, "prompt": prompt, "trial": trial}

    return {"model": "unknown", "prompt": "", "trial": ""}


def get_hash_from_filename(file_path):
    """
    Extracts a git hash-like string from the file path using regex.
    """
    match = re.search(r"([0-9a-f]{7,})", file_path)
    return match.group(1) if match else "unknown"


def print_results(results, output_path="benchmark_summary.csv"):
    header = ['hash_value', 'benchmark_name', 'params', 'mode', 'unit', 'model', 'prompt', 'trial', 'mean', 'error', 'normalized_performance']

    with open(output_path, "w", newline="", encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for (hash_value, benchmark_name, params), entries in results.items():
            if not entries:
                continue

            originals = [e for e in entries if e["model"] == "original"]
            developers = [e for e in entries if e["model"] == "developer"]

            if not originals or not developers:
                continue

            org_mean = sum(e["score"] for e in originals) / len(originals)
            dev_mean = sum(e["score"] for e in developers) / len(developers)

            mode = entries[0].get("mode", "unknown")

            improvement = 0.0
            if org_mean > 0:
                if mode in ["avgt", "sample"]:
                    improvement = (org_mean - dev_mean) / org_mean
                elif mode == "thrpt":
                    improvement = (dev_mean - org_mean) / org_mean

            if improvement < 0.05:
                continue

            unit = entries[0].get("unit", "unknown")
            params_str = f'"{params}"' if params else ""

            for entry in entries:
                # Calculate normalized performance for the current entry
                normalized_value = ""
                if org_mean > 0 and entry.get("score") is not None and entry["score"] > 0:
                    if mode in ["avgt", "sample"]:
                        normalized_value = org_mean / entry["score"]
                    elif mode == "thrpt":
                        normalized_value = entry["score"] / org_mean
                
                writer.writerow([
                    hash_value,
                    benchmark_name,
                    params_str,
                    mode,
                    unit,
                    entry["model"],
                    entry["prompt"],
                    entry["trial"],
                    entry["score"],
                    entry["error"],
                    normalized_value
                ])


if __name__ == "__main__":

    project_name = "presto"

    org_files = glob.glob(f"../baseline/{project_name}/org/*.json", recursive=True)
    dev_files = glob.glob(f"../baseline/{project_name}/dev/*.json", recursive=True)
    llm_files = glob.glob(f"../llm_output/{project_name}/**/*.json", recursive=True)

    files = org_files + dev_files + llm_files
    all_results = defaultdict(list)

    for file in files:
        data = extract_score_data(file)
        parsed_info = parse_version_from_filename(file)
        hash_value = get_hash_from_filename(file)

        for d in data:
            benchmark_name = d["benchmark"]
            params = d.get("params", "")
            key = (hash_value, benchmark_name, params)
            all_results[key].append({
                "model": parsed_info["model"],
                "prompt": parsed_info["prompt"],
                "trial": parsed_info["trial"],
                "score": d["score"],
                "error": d["error"],
                "unit": d["unit"],
                "mode": d["mode"],
                "params": params
            })

    output_filename = f"{project_name}_benchmark_summary.csv"
    print_results(all_results, output_path=output_filename)
    print(f"Benchmark summary has been saved to {output_filename}")
