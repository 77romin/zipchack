"""앱 모듈을 import하기 전에 의존성 누락을 안내한다."""
import importlib.util

REQUIRED={'langchain_text_splitters':'langchain-text-splitters','chromadb':'chromadb','langgraph':'langgraph'}

def missing_dependencies():
    return [package for module,package in REQUIRED.items() if importlib.util.find_spec(module) is None]

def check_runtime():
    missing=missing_dependencies()
    if not missing:return
    import streamlit as st
    import sys
    st.error('현재 실행 환경에 프로젝트 패키지가 없습니다: '+', '.join(missing))
    st.write('실행 중인 터미널에서 Ctrl+C로 종료한 뒤, zipchack 폴더에서 아래 명령을 실행해주세요.')
    st.code('./run.sh --server.port 8501',language='bash')
    st.caption('Git Bash 기준. PowerShell에서는 .\\run.ps1 --server.port 8501을 사용하세요.')
    st.write('현재 Python: '+sys.executable)
    st.stop()
