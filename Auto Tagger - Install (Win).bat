@echo off
chcp 65001 >nul
title Auto Photo Tagger - Installer (Windows)
cd /d "%~dp0"

echo ==========================================================
echo   Auto Photo Tagger - Installation (Windows)
echo ==========================================================
echo.

REM Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Choose AI Inference Backend:
echo.
echo   [1] DirectML - Universal Windows GPU (RECOMMENDED, ~547 MB venv)
echo       - Works on NVIDIA, AMD, and Intel GPUs via DirectX 12
echo       - Same speed as CUDA with no large CUDA/cuDNN downloads
echo.
echo   [2] NVIDIA CUDA 13 - Bundled Runtime (~2.23 GB venv)
echo       - Dedicated NVIDIA CUDA 13 + cuDNN 9 runtime
echo.
echo   [3] CPU Only (~458 MB venv)
echo       - Smallest footprint, works on any PC without a GPU
echo.

set /p BACKEND_CHOICE="Enter choice (1, 2, or 3) [Default: 1]: "
if "%BACKEND_CHOICE%"=="" set BACKEND_CHOICE=1

:: Create venv if it doesn't exist
echo.
if not exist "venv" (
    echo [1/5] Creating virtual environment...
    python -m venv venv
) else (
    echo [1/5] Virtual environment already exists.
)

:: Activate venv
call venv\Scripts\activate.bat

:: Upgrade pip
echo.
echo [2/5] Upgrading pip...
python -m pip install --upgrade pip

:: Install core dependencies
echo.
echo [3/5] Installing core dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install core dependencies.
    pause
    exit /b 1
)

:: Clean previous ONNX Runtime / NVIDIA packages so switching backends gives an accurate size
echo.
echo [4/5] Configuring selected ONNX Runtime backend...
python -m pip uninstall -y onnxruntime onnxruntime-gpu onnxruntime-directml nvidia-cudnn-cu13 nvidia-cuda-runtime nvidia-cuda-nvrtc nvidia-cufft nvidia-curand nvidia-cublas >nul 2>&1

if "%BACKEND_CHOICE%"=="2" (
    echo Installing onnxruntime-gpu with bundled CUDA 13 + cuDNN 9 runtime...
    python -m pip install "onnxruntime-gpu[cuda,cudnn]" "nvidia-cublas~=13.0"
) else if "%BACKEND_CHOICE%"=="3" (
    echo Installing onnxruntime ^(CPU Only^)...
    python -m pip install onnxruntime
) else (
    echo Installing onnxruntime-directml ^(Universal Windows GPU^)...
    python -m pip install onnxruntime-directml
)

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install ONNX Runtime backend.
    pause
    exit /b 1
)

:: Verify ONNX Runtime & show venv size
echo.
echo [5/5] Verifying ONNX Runtime setup...
python -c "import onnxruntime as ort; print(f'ONNX Runtime: {ort.__version__} (Providers: {ort.get_available_providers()})')"
powershell -NoProfile -Command "$b=(Get-ChildItem 'venv' -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum; Write-Host ('Total venv size: {0:N1} MB' -f ($b/1MB))"

echo.
echo ==========================================================
echo   Installation Complete!
echo ==========================================================
echo.
echo   IMPORTANT: You need ExifTool installed for tag writing.
echo   You can install it automatically from inside the app,
echo   or download it from: https://exiftool.org/
echo.
echo   To run the application:
echo      1. Double-click "Auto Photo Tagger - Run (Windows).bat"
echo      OR
echo      2. Double-click "Auto Photo Tagger - Run With Console (Windows).bat"
echo      OR
echo      3. Activate venv: venv\Scripts\activate
echo         Then run: python app\main.py
echo.
pause
