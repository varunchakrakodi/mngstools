#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${1:-config.yaml}"

if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "Error: Config file '$CONFIG_FILE' not found." >&2
    exit 1
fi

# Extract output_dir from YAML (handles quotes and whitespace)
OUTPUT_DIR=$(grep -E '^[[:space:]]*output_dir:' "$CONFIG_FILE" | head -n 1 | awk -F: '{print $2}' | tr -d ' "' | tr -d "'")

if [[ -z "$OUTPUT_DIR" ]]; then
    echo "Error: Could not extract 'output_dir' from $CONFIG_FILE." >&2
    exit 1
fi

if [[ ! -d "$OUTPUT_DIR" ]]; then
    echo "Directory '$OUTPUT_DIR' does not exist. Nothing to clean."
    exit 0
fi

HTML_FILE="$OUTPUT_DIR/Results.html"

if [[ ! -f "$HTML_FILE" ]]; then
    echo "Error: '$HTML_FILE' does not exist. Skipping cleanup to prevent data loss." >&2
    exit 1
fi

echo "Cleaning intermediate files in '$OUTPUT_DIR' (keeping Results.html)..."

# Delete all files except Results.html
find "$OUTPUT_DIR" -maxdepth 1 -type f ! -name "Results.html" -exec rm -f {} +

# Delete all subdirectories (e.g., downloads_*, shared_references)
find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +

echo "Cleanup complete. Preserved: $HTML_FILE"