#!/usr/bin/env bash
# ------------------------------------------------------------
# Check that required command‑line tools are installed.
# This script does not modify any cloud configuration.

set -euo pipefail

# Helper to print status messages
status() {
  echo "✅ $*"
}

error() {
  echo "❌ $*" >&2
  exit 1
}

# Capture version without using a pipeline (avoids SIGPIPE under pipefail)
check_cmd() {
  local cmd="$1"
  local version_arg="${2:---version}"
  if command -v "$cmd" >/dev/null 2>&1; then
    local ver_output
    ver_output=$($cmd $version_arg 2>&1)
    # Keep only the first line of output
    local ver="${ver_output%%$'\n'*}"
    status "$cmd version $ver"
  else
    error "$cmd is not installed or not in PATH. Install it before proceeding."
  fi
}

echo "Checking required tools..."
check_cmd gcloud "--version"
check_cmd python3 "--version"
# Terraform is optional – warn instead of error
if command -v terraform >/dev/null 2>&1; then
  check_cmd terraform "--version"
else
  echo "⚠️ terraform not found – required only for future IaC steps."
fi

echo "All required tools are available."
