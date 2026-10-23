#!/usr/bin/env bash
set -e
zip_project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$zip_project_root"
zip_python="$zip_project_root/.venv/Scripts/python.exe"
if [[ ! -f "$zip_python" ]]; then
  zip_python="$zip_project_root/.venv/bin/python"
fi
if [[ ! -f "$zip_python" ]]; then
  echo 'Project .venv not found. See docs setup guide.' >&2
  exit 1
fi
if ! "$zip_python" -c 'import streamlit, langchain_text_splitters, chromadb, langgraph'; then
  echo 'Install requirements.txt using the project .venv Python first.' >&2
  exit 1
fi
exec "$zip_python" -m streamlit run "$zip_project_root/app.py" "$@"
