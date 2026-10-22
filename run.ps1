# 프로젝트의 가상환경과 app.py를 명시해 다른 실습 폴더의 서버 실행을 방지한다.
$ErrorActionPreference = 'Stop'
$zipProjectRoot = $PSScriptRoot
$zipPython = Join-Path $zipProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $zipPython)) {
    throw '프로젝트 .venv가 없습니다. 실행 가이드에 따라 가상환경과 의존성을 먼저 준비해주세요.'
}
Push-Location -LiteralPath $zipProjectRoot
try {
    & $zipPython -m streamlit run (Join-Path $zipProjectRoot 'app.py') @args
} finally {
    Pop-Location
}
