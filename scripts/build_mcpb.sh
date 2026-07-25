#!/usr/bin/env bash
# Build a .mcpb bundle for local-llm-mcp.
#
# EXPERIMENTAL / secondary distribution path.
# The uv-type MCPB runtime is still labeled experimental
# upstream (known issues: Windows first-run venv-build race condition,
# user_config/env not always reaching the server). This targets running
# local-llm-mcp on NATIVE WINDOWS against the native Windows Ollama install —
# there is no supported way to make an .mcpb shell into WSL, since the host
# manages uv-type execution itself. For the WSL-hosted setup this project
# actually uses, prefer the wsl.exe stdio config in README.md / the uvx
# one-liner instead of this bundle.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v mcpb >/dev/null 2>&1; then
  echo "Installing @anthropic-ai/mcpb CLI..."
  npm install -g @anthropic-ai/mcpb
fi

mcpb validate manifest.json
mcpb pack . "dist/local-llm-mcp.mcpb"
echo "Built dist/local-llm-mcp.mcpb"
