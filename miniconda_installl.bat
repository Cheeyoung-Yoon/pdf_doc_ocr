@echo off
setlocal enabledelayedexpansion

set "MINICONDA_PATH=%USERPROFILE%\Miniconda3"
set "CONDA_EXE=%MINICONDA_PATH%\Scripts\conda.exe"
set "MARKER=%TEMP%\miniconda_installed.flag"

REM 이미 설치되어 있으면 그냥 스크립트2 실행
if exist "%CONDA_EXE%" (
    echo [INFO] Miniconda already installed.
    call "%~dp0post_install.bat"
    goto :eof
)

echo [INFO] Installing Miniconda...

curl -L https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe -o .\miniconda.exe
start /wait "" .\miniconda.exe /S /D=%MINICONDA_PATH%
del .\miniconda.exe

REM 환경 변수 설정
setx PATH "%MINICONDA_PATH%;%MINICONDA_PATH%\Scripts;%MINICONDA_PATH%\Library\bin;%PATH%"

REM 재실행 마커 파일 생성
echo done > "%MARKER%"

REM 콘솔 재시작
start "" cmd /c "%~f0"
exit /b
