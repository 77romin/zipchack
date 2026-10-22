@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Project .venv not found. See docs setup guide.
    exit /b 1
)
".venv\Scripts\python.exe" -c "import streamlit, langchain_text_splitters, chromadb, langgraph"
if errorlevel 1 (
    echo Install dependencies: .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py %*
