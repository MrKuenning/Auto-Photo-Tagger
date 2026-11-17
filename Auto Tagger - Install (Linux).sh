#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

OS_NAME="$(uname -s)"

echo "=========================================================="
echo "  Auto Photo Tagger - Installation ($OS_NAME)"
echo "=========================================================="
echo

# Check for Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python 3 is not installed or not in PATH."
    echo "Please install Python 3.10+ and re-run this installer."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Detected Python $PYTHON_VERSION"

BACKEND_CHOICE="3"
if [ "$OS_NAME" = "Darwin" ]; then
    echo "macOS detected: using ONNX Runtime (CoreML / CPU)."
    BACKEND_CHOICE="3"
else
    echo
    echo "Choose AI Inference Backend:"
    echo
    echo "  [1] NVIDIA CUDA 13 - Bundled Runtime (Fastest NVIDIA GPU)"
    echo "  [2] NVIDIA CUDA 13 - System CUDA (Requires CUDA 13 + cuDNN 9 installed)"
    echo "  [3] CPU Only (Smallest footprint)"
    echo
    read -r -p "Enter choice (1, 2, or 3) [Default: 1]: " BACKEND_CHOICE
    BACKEND_CHOICE="${BACKEND_CHOICE:-1}"
fi

# Create venv if it doesn't exist
echo
if [ ! -d "venv" ]; then
    echo "[1/5] Creating virtual environment..."
    python3 -m venv venv
else
    echo "[1/5] Virtual environment already exists."
fi

# Activate venv
# shellcheck disable=SC1091
source venv/bin/activate

# Upgrade pip
echo
echo "[2/5] Upgrading pip..."
python -m pip install --upgrade pip

# Install core dependencies
echo
echo "[3/5] Installing core dependencies from requirements.txt..."
python -m pip install -r requirements.txt

# Clean previous ONNX Runtime / NVIDIA packages and install chosen backend
echo
echo "[4/5] Configuring selected ONNX Runtime backend..."
python -m pip uninstall -y onnxruntime onnxruntime-gpu nvidia-cudnn-cu13 nvidia-cuda-runtime nvidia-cuda-nvrtc nvidia-cufft nvidia-curand nvidia-cublas >/dev/null 2>&1 || true

if [ "$OS_NAME" = "Darwin" ] || [ "$BACKEND_CHOICE" = "3" ]; then
    echo "Installing onnxruntime (CPU / CoreML)..."
    python -m pip install onnxruntime
elif [ "$BACKEND_CHOICE" = "2" ]; then
    echo "Installing onnxruntime-gpu (System CUDA 13)..."
    python -m pip install onnxruntime-gpu
else
    echo "Installing onnxruntime-gpu with bundled CUDA 13 + cuDNN 9 runtime..."
    python -m pip install "onnxruntime-gpu[cuda,cudnn]" "nvidia-cublas~=13.0"
fi

# Verify setup
echo
echo "[5/5] Verifying ONNX Runtime setup..."
python -c "import onnxruntime as ort; print(f'ONNX Runtime: {ort.__version__} (Providers: {ort.get_available_providers()})')"
du -sh venv 2>/dev/null || true

echo
echo "=========================================================="
echo "  Installation Complete!"
echo "=========================================================="
echo
if ! command -v exiftool >/dev/null 2>&1; then
    echo "  IMPORTANT: ExifTool is required for writing tags to images."
    if [ "$OS_NAME" = "Darwin" ]; then
        echo "  Install via Homebrew:  brew install exiftool"
    else
        echo "  Install via apt:       sudo apt install libimage-exiftool-perl"
        echo "  Or via dnf:            sudo dnf install perl-Image-ExifTool"
    fi
    echo
fi
echo "  To run the application:"
echo "     ./\"Auto Photo Tagger - Run (Linux).sh\""
echo "  OR:"
echo "     source venv/bin/activate && python app/main.py"
echo
