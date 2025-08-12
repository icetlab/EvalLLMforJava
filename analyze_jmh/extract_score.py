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
    Determines the 'version' (e.g., Original, Developer, gpt-prompt1)
    based on the file path.
    """
    file = os.path.basename(file_path)

    if "/org/" in file_path:
        return "Original"
    if "/dev/" in file_path:
        return "Developer"
    if "llm_output/" in file_path:
        path_parts = file_path.split(os.sep)
        try:
            idx = path_parts.index("llm_output")
            # Extracts model from path like 'llm_output/RoaringBitmap/gpt/...'
            llm_model = path_parts[idx + 2]
        except (ValueError, IndexError):
            llm_model = ""

        # Extracts prompt number from the filename.
        prompt_match = re.search(r"(prompt\d+)", file)
        prompt = prompt_match.group(1) if prompt_match else ""

        version = llm_model
        if prompt:
            version += f"-{prompt}"
        return version if version else "Unknown"

    return "Unknown"


def get_hash_from_filename(file_path):
    """
    Extracts a git hash-like string from the file path using regex.
    """
    match = re.search(r"([0-9a-f]{7,})", file_path)
    return match.group(1) if match else "unknown"


def print_results(results, output_path="benchmark_summary.csv"):
    """
    Saves the benchmark results to a CSV file in the specified format.
    If the performance improvement of the developer version over the original is
    less than 5%, this group of data will be skipped.
    
    Args:
        results (dict): A dictionary containing the aggregated benchmark results.
        output_path (str): The path to the output CSV file.
    """
    header = ['hash_value', 'benchmark_name', 'params', 'mode', 'unit', 'model', 'prompt', 'mean', 'error']

    with open(output_path, "w", newline="", encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(header)

        for (hash_value, benchmark_name, params), entries in results.items():
            if not entries:
                continue

            # 1. Find original and developer entries
            originals = [e for e in entries if e["version"].lower() == "original"]
            developers = [e for e in entries if e["version"].lower() == "developer"]

            # If either is missing, comparison is not possible, so skip this group
            if not originals or not developers:
                continue

            # 2. Calculate the average score
            org_mean = sum(e["score"] for e in originals) / len(originals)
            dev_mean = sum(e["score"] for e in developers) / len(developers)

            mode = entries[0].get("mode", "unknown")

            # 3. Calculate performance improvement based on the mode
            improvement = 0.0
            # Ensure org_mean is not zero to avoid division by zero error
            if org_mean > 0:
                if mode == "avgt" or mode == "sample":  # avgt/sample: lower score is better
                    improvement = (org_mean - dev_mean) / org_mean
                elif mode == "thrpt":  # thrpt: higher score is better
                    improvement = (dev_mean - org_mean) / org_mean

            # 4. Apply 5% filter: if improvement is less than 5%, skip the entire group
            if improvement < 0.05:
                continue

            # 5. If the filter is passed, write all entries of the group to the CSV
            unit = entries[0].get("unit", "unknown")
            params_str = f'"{params}"' if params else ""

            for entry in entries:
                version = entry.get("version", "").lower()
                score = entry.get("score")
                error = entry.get("error")

                model = ""
                prompt = ""

                if version == "original":
                    model = "original"
                elif version == "developer":
                    model = "developer"
                else:
                    model_match = re.search(r"(gpt|gemini)", version)
                    prompt_match = re.search(r"(prompt\d+)", version)
                    if model_match:
                        model = model_match.group(1)
                    if prompt_match:
                        prompt = prompt_match.group(1)
                
                writer.writerow([
                    hash_value,
                    benchmark_name,
                    params_str,
                    mode,
                    unit,
                    model,
                    prompt,
                    score,
                    error
                ])


if __name__ == "__main__":

    project_name = "netty"

    org_files = glob.glob(f"../baseline/{project_name}/org/*.json", recursive=True)
    dev_files = glob.glob(f"../baseline/{project_name}/dev/*.json", recursive=True)
    llm_files = glob.glob(f"../llm_output/{project_name}/**/*.json", recursive=True)

    files = org_files + dev_files + llm_files
    all_results = defaultdict(list)

    for file in files:
        data = extract_score_data(file)
        version = parse_version_from_filename(file)
        hash_value = get_hash_from_filename(file)

        for d in data:
            benchmark_name = d["benchmark"]
            params = d.get("params", "")
            key = (hash_value, benchmark_name, params)
            all_results[key].append({
                "version": version,
                "score": d["score"],
                "error": d["error"],
                "unit": d["unit"],
                "mode": d["mode"],
                "params": params
            })

    output_filename = f"{project_name}_benchmark_summary.csv"
    print_results(all_results, output_path=output_filename)
    print(f"Benchmark summary has been saved to {output_filename}")
