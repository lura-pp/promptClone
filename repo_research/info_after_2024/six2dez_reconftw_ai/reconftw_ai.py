#!/usr/bin/env python3

import ollama
import os
import argparse
import glob
import sys
import subprocess
import shutil
import json
from datetime import datetime
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
import uuid

# Default configuration
DEFAULT_RECONFTW_RESULTS_DIR = "./reconftw_output"
DEFAULT_OUTPUT_DIR = "./reconftw_ai_output"
DEFAULT_MODEL_NAME = "llama3"
DEFAULT_OUTPUT_FORMAT = "txt"
DEFAULT_REPORT_TYPE = "executive"
DEFAULT_PROMPTS_FILE = "prompts.json"

REPORT_TYPES = ["executive", "brief", "bughunter"]
OUTPUT_FORMATS = ["txt", "md"]
CATEGORIES = ["osint", "subdomains", "hosts", "webs"]

def load_prompts(prompts_file: str) -> Dict:
    try:
        with open(prompts_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ERROR] Prompts file '{prompts_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in prompts file: {e}")
        sys.exit(1)

def ensure_ollama_running():
    try:
        subprocess.run(["ollama", "list"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError:
        print("[!] Ollama is not running. Attempting to start it in background...")
        if shutil.which("ollama") is None:
            print("[ERROR] Ollama not installed or not in PATH.")
            sys.exit(1)
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def ensure_model_available(model_name):
    try:
        output = subprocess.check_output(["ollama", "list"], encoding="utf-8")
        if model_name not in output:
            print(f"[*] Model '{model_name}' not found. Downloading with 'ollama pull {model_name}'...")
            subprocess.run(["ollama", "pull", model_name], check=True)
    except Exception as e:
        print(f"[ERROR] Could not verify or pull model: {e}")
        sys.exit(1)

def read_files(category: str, results_dir: str) -> str:
    combined_data = ""
    category_dir = os.path.join(results_dir, category)

    if not os.path.isdir(category_dir):
        return f"[Error] Directory {category_dir} does not exist."

    file_paths = glob.glob(os.path.join(category_dir, "**/*"), recursive=True)

    for file_path in file_paths:
        if os.path.isfile(file_path):
            relative_path = os.path.relpath(file_path, results_dir)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    combined_data += f"--- {relative_path} ---\n{f.read().strip()}\n"
            except Exception as e:
                combined_data += f"[Error] Failed to read {relative_path}: {str(e)}\n"

    if not combined_data:
        return f"[Info] No files found in {category_dir}."

    return combined_data.strip()

def process_category(category: str, data: str, model_name: str, report_type: str, base_prompts: Dict) -> str:
    if not data:
        return f"[Error] No data available for {category}."

    prompt_template = base_prompts.get(report_type, {}).get(category, "Analyze this data:\n{data}")
    prompt = prompt_template.format(data=data)

    try:
        response = ollama.generate(model=model_name, prompt=prompt)
        return response.get("response", "[Error] Empty response from model.")
    except Exception as e:
        return f"[Error] Failed to process {category} with model '{model_name}': {str(e)}"

def save_results(results: Dict[str, str], output_dir: str, model_name: str, output_format: str, report_type: str):
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = "md" if output_format == "md" else "txt"
    output_file = os.path.join(output_dir, f"reconftw_analysis_{report_type}_{timestamp}.{extension}")

    with open(output_file, "w", encoding="utf-8") as f:
        if output_format == "md":
            f.write(f"# ReconFTW-AI Analysis\n\n")
            f.write(f"- **Model Used**: `{model_name}`\n")
            f.write(f"- **Report Type**: `{report_type}`\n")
            f.write(f"- **Date**: `{timestamp}`\n\n")
            for category, interpretation in results.items():
                f.write(f"## {category.upper()}\n\n{interpretation}\n\n")
        else:
            f.write(f"ReconFTW-AI Analysis\nModel: {model_name}\nReport Type: {report_type}\nDate: {timestamp}\n")
            f.write("=" * 60 + "\n\n")
            for category, interpretation in results.items():
                f.write(f"=== {category.upper()} ===\n{interpretation}\n\n")

    print(f"[*] Results saved to '{output_file}'")

def analyze_reconftw_results(results_dir: str, model_name: str, report_type: str, base_prompts: Dict) -> Dict[str, str]:
    results = {}
    all_data = ""

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(read_files, category, results_dir): category
            for category in CATEGORIES
        }

        raw_data_per_category = {}
        for future in as_completed(futures):
            category = futures[future]
            raw_data = future.result()
            raw_data_per_category[category] = raw_data

    with ThreadPoolExecutor() as executor:
        futures = {
            executor.submit(process_category, category, raw_data_per_category[category], model_name, report_type, base_prompts): category
            for category in CATEGORIES
        }

        for future in as_completed(futures):
            category = futures[future]
            interpretation = future.result()
            results[category] = interpretation
            all_data += f"{category.upper()}:\n{raw_data_per_category[category]}\n\n"

    results["overview"] = process_category("overview", all_data, model_name, report_type, base_prompts)
    return results

def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> bool:
    if not os.path.isdir(args.results_dir):
        print(f"[Error] Results directory '{args.results_dir}' does not exist.")
        parser.print_help()
        return False
    if args.output_format not in OUTPUT_FORMATS:
        print(f"[Error] Invalid format '{args.output_format}'. Choose from: {', '.join(OUTPUT_FORMATS)}")
        return False
    if args.report_type not in REPORT_TYPES:
        print(f"[Error] Invalid report type '{args.report_type}'. Choose from: {', '.join(REPORT_TYPES)}")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="ReconFTW-AI: Use LLMs to interpret ReconFTW results")
    parser.add_argument("--results-dir", default=DEFAULT_RECONFTW_RESULTS_DIR, help="Directory with ReconFTW results.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Where to save the analysis.")
    parser.add_argument("--model", default=DEFAULT_MODEL_NAME, help="Ollama model name to use (e.g. llama3).")
    parser.add_argument("--output-format", choices=OUTPUT_FORMATS, default=DEFAULT_OUTPUT_FORMAT, help="Output format: txt or md.")
    parser.add_argument("--report-type", choices=REPORT_TYPES, default=DEFAULT_REPORT_TYPE, help="Type of report to generate.")
    parser.add_argument("--prompts-file", default=DEFAULT_PROMPTS_FILE, help="JSON file containing prompt templates.")

    args = parser.parse_args()

    if not validate_args(args, parser):
        sys.exit(1)

    base_prompts = load_prompts(args.prompts_file)

    ensure_ollama_running()
    ensure_model_available(args.model)

    print(f"[*] Analyzing with model '{args.model}' using report type '{args.report_type}'...")
    results = analyze_reconftw_results(args.results_dir, args.model, args.report_type, base_prompts)

    for category, content in results.items():
        print(f"\n=== {category.upper()} ===\n{content[:500]}{'...' if len(content) > 500 else ''}")

    save_results(results, args.output_dir, args.model, args.output_format, args.report_type)

if __name__ == "__main__":
    main()