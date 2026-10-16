@echo off
setlocal
rem Launch code_annotations from the parent of this script's project directory.
cd /d "%~dp0.."
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python was not found in PATH.
    pause
    exit /b 1
)
echo Starting Code Annotations web interface...
python -m code_annotations.web %*
if errorlevel 1 (
    echo.
    echo [ERROR] Web interface exited with an error.
    pause
    exit /b 1
)
endlocal
