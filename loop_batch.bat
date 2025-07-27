@echo off
setlocal enableextensions enabledelayedexpansion


set "CONDA_ROOT=C:\ProgramData\miniconda3"
set "CONDA_ENV=whisper"

:: 현재 bat 파일 기준 루트 경로 설정
set "SCRIPT_DIR=%~dp0"
:: %~dp0는 현재 .bat 파일이 위치한 폴더 경로 (마지막 \ 포함)

:: 상대 경로 지정
set "WORK_DIR=%SCRIPT_DIR%code"
set "DATA_PATH=%SCRIPT_DIR%raw"
:loop
cls
echo =====================================
echo Starting OCR Pipeline
echo =====================================

:: Conda 환경 활성화 및 python 실행
call "%CONDA_ROOT%\Scripts\activate.bat" %CONDA_ENV%
cd /d "%WORK_DIR%"
python batch_loop.py --work_path "%DATA_PATH%"

:: 실패 시 재시작
if errorlevel 1 (
    echo ❌ Python process crashed. Restarting in 10 seconds...
    timeout /t 10
    goto loop
) else (
    echo ✅ Process completed normally.
    timeout /t 5
    exit /b 0
)
