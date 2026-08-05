#!/usr/bin/env bash
#
# Install the Z — Clarity Gate plugin into Claude Code from this directory.
# Registers this repo as a local plugin marketplace, then installs the `z` plugin.
#
# Usage:  ./install.sh
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v claude >/dev/null 2>&1; then
  echo "error: 'claude' CLI not found on PATH. Install Claude Code first: https://claude.com/claude-code" >&2
  exit 1
fi

echo "→ Registering local plugin marketplace: $HERE"
claude plugin marketplace add "$HERE"

echo "→ Installing plugin: z@z"
claude plugin install z@z

echo "✓ Z — Clarity Gate installed. Try:  z gate \"<goal>\""
