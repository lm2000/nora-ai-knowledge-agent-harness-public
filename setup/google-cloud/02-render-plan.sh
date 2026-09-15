#!/usr/bin/env bash
# ------------------------------------------------------------
# Render an offline deployment plan based on config.env.
# No network calls are made; the script only validates input and
# creates a local text file describing the intended resources.

set -euo pipefail

CONFIG_FILE="$(dirname "$0")/config.env"
PLAN_DIR="$(dirname "$0")/plan-output"
PLAN_FILE="$PLAN_DIR/plan.txt"
PYTHON_HELPER="$(dirname "$0")/helpers.py"

# Ensure config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "❌ Configuration file $CONFIG_FILE not found. Copy config.env.example and fill it out first." >&2
  exit 1
fi

# Create output directory if it does not exist (preserve existing files)
mkdir -p "$PLAN_DIR"

# Run the Python helper to validate and generate the plan
# The helper uses exclusive file creation, so it will abort if $PLAN_FILE already exists.
python3 "$PYTHON_HELPER" "$CONFIG_FILE" "$PLAN_FILE"

echo "✅ Plan rendered to $PLAN_FILE"
