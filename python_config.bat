@echo off
setlocal

set "MARKER=%TEMP%\miniconda_installed.flag"
set "CONDA_ROOT=C:\ProgramData\miniconda3"
set "CONDA_ENV=imga"
set "SCRIPT_DIR=%~dp0"
set "WORK_DIR=%SCRIPT_DIR%code"

if exist "%MARKER%" (
    del "%MARKER%"
    echo [INFO] Restarted. Now running post-install step...

    REM conda 환경 만들기
    "%CONDA_ROOT%\Scripts\conda.exe" create -n %CONDA_ENV% python=3.12 -y

    REM conda 환경 활성화
    call "%CONDA_ROOT%\Scripts\activate.bat" %CONDA_ENV%

    REM 작업 디렉토리로 이동
    cd /d "%WORK_DIR%"

    REM 의존성 설치 및 파이썬 실행
    pip install -r requirements.txt
    python install.py

    echo [INFO] Setup complete.
)
