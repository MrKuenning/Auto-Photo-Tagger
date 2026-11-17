"""
Auto Photo Tagger - Core Engine
Multi-model support via ONNX Runtime with GPU acceleration (CUDA / DirectML) and batch inference.
Generates booru-style and descriptive tags for images including general, character, and rating tags.
"""

import os
import sys
import csv
import subprocess

# Ensure stdout/stderr are valid streams in windowless mode (pythonw.exe / PyInstaller --windowed)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")
import concurrent.futures
import numpy as np
from PIL import Image, ImageOps
from huggingface_hub import hf_hub_download
from pathlib import Path


# ── CUDA DLL Configuration for Windows ───────────────────────────────────────

def _setup_cuda_dlls():
    """Ensure CUDA and cuDNN DLLs from system CUDA_PATH or nvidia pip packages are discoverable by ONNX Runtime."""
    try:
        candidate_dirs = []
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidate_dirs.append(exe_dir)
            candidate_dirs.append(exe_dir / "_internal")

        cuda_path = os.environ.get("CUDA_PATH")
        if cuda_path:
            candidate_dirs.append(Path(cuda_path) / "bin")

        # Also check nvidia/* pip package bin directories if installed (CUDA 12 and consolidated CUDA 13 layouts)
        for p in sys.path:
            nvidia_dir = Path(p) / "nvidia"
            if nvidia_dir.is_dir():
                for bin_dir in nvidia_dir.glob("*/bin"):
                    candidate_dirs.append(bin_dir)
                    for sub in bin_dir.iterdir():
                        if sub.is_dir():
                            candidate_dirs.append(sub)

        current_path = os.environ.get("PATH", "")
        for d in candidate_dirs:
            if d.exists():
                str_d = str(d)
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(str_d)
                    except Exception:
                        pass
                if str_d not in current_path:
                    os.environ["PATH"] = str_d + os.pathsep + current_path
                    current_path = os.environ["PATH"]
    except Exception:
        pass


_setup_cuda_dlls()


# ── Model Configuration ──────────────────────────────────────────────────────

AVAILABLE_MODELS = {
    "wd-swinv2-v3": {
        "name": "WD SwinV2 v3 (Default / Detail)",
        "repo": "SmilingWolf/wd-swinv2-tagger-v3",
        "model_file": "model.onnx",
        "label_file": "selected_tags.csv",
        "image_size": 448,
        "description": "High accuracy on fine details, clothing, accessories, and booru tags.",
    },
    "wd-convnext-v3": {
        "name": "WD ConvNeXt v3 (Fastest)",
        "repo": "SmilingWolf/wd-convnext-tagger-v3",
        "model_file": "model.onnx",
        "label_file": "selected_tags.csv",
        "image_size": 448,
        "description": "Pure ConvNet architecture. Maximum throughput in batch inference.",
    },
    "wd-vit-v3": {
        "name": "WD ViT v3 (Vision Transformer)",
        "repo": "SmilingWolf/wd-vit-tagger-v3",
        "model_file": "model.onnx",
        "label_file": "selected_tags.csv",
        "image_size": 448,
        "description": "Vision Transformer variant for broad scene and subject classification.",
    },
}

DEFAULT_MODEL = "wd-swinv2-v3"


def _resolve_models_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "models").exists():
            return exe_dir / "models"
        if hasattr(sys, "_MEIPASS") and (Path(sys._MEIPASS) / "models").exists():
            return Path(sys._MEIPASS) / "models"
        if (exe_dir / "_internal" / "models").exists():
            return exe_dir / "_internal" / "models"
        return exe_dir / "models"
    return Path(__file__).resolve().parent.parent / "models"


MODELS_BASE_DIR = _resolve_models_dir()


def is_model_installed(model_key: str) -> bool:
    """Check if the ONNX model and tag labels exist locally on disk for a given model key."""
    cfg = AVAILABLE_MODELS.get(model_key)
    if not cfg:
        return False
    model_dir = MODELS_BASE_DIR / model_key
    model_path = model_dir / cfg.get("model_file", "model.onnx")
    label_path = model_dir / cfg.get("label_file", "selected_tags.csv")
    return model_path.exists() and label_path.exists()

# Tag category indices from the CSV
TAG_CATEGORY_GENERAL = 0
TAG_CATEGORY_CHARACTER = 4
TAG_CATEGORY_RATING = 9

# Default thresholds
DEFAULT_GENERAL_THRESHOLD = 0.35
DEFAULT_CHARACTER_THRESHOLD = 0.80
DEFAULT_RATING_THRESHOLD = 0.50
DEFAULT_BATCH_SIZE = 16


# ── GPU Name Detection ───────────────────────────────────────────────────────

def _get_nvidia_gpu_name() -> str:
    """Query the NVIDIA GPU model name via nvidia-smi without requiring PyTorch."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=flags,
        )
        if res.returncode == 0 and res.stdout.strip():
            raw_name = res.stdout.strip().splitlines()[0].strip()
            return raw_name.replace("NVIDIA GeForce ", "").replace("NVIDIA ", "")
    except Exception:
        pass
    return ""


class TaggerEngine:
    """
    Core tagging engine supporting multiple ONNX vision models and batch inference.
    Uses CUDA 13.0 on RTX 5090 Blackwell for high-speed hardware acceleration.
    """

    def __init__(
        self,
        model_key: str = DEFAULT_MODEL,
        general_threshold: float = DEFAULT_GENERAL_THRESHOLD,
        character_threshold: float = DEFAULT_CHARACTER_THRESHOLD,
        batch_size: int = DEFAULT_BATCH_SIZE,
        use_gpu: bool = True,
    ):
        self.model_key = model_key if model_key in AVAILABLE_MODELS else DEFAULT_MODEL
        self.general_threshold = general_threshold
        self.character_threshold = character_threshold
        self.batch_size = batch_size
        self.use_gpu = use_gpu
        self.session = None
        self.tag_names = []
        self.rating_tags = []
        self.general_tags = []
        self.character_tags = []
        self._provider_name = "Unknown"

    @property
    def model_config(self) -> dict:
        return AVAILABLE_MODELS[self.model_key]

    @property
    def image_size(self) -> int:
        return self.model_config["image_size"]

    # ── Model Management ──────────────────────────────────────────────────

    def is_model_installed(self, model_key: str = None) -> bool:
        """Check if the active or specified model is installed on disk."""
        return is_model_installed(model_key or self.model_key)

    def download_model(self, progress_callback=None):
        """Download model and tag labels for the active model."""
        cfg = self.model_config
        model_dir = MODELS_BASE_DIR / self.model_key
        model_dir.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / cfg["model_file"]
        label_path = model_dir / cfg["label_file"]

        if not model_path.exists():
            if progress_callback:
                progress_callback(f"Downloading {cfg['name']} model (~380MB)...")
            hf_hub_download(
                repo_id=cfg["repo"],
                filename=cfg["model_file"],
                local_dir=str(model_dir),
            )

        if not label_path.exists():
            if progress_callback:
                progress_callback(f"Downloading tag labels for {cfg['name']}...")
            hf_hub_download(
                repo_id=cfg["repo"],
                filename=cfg["label_file"],
                local_dir=str(model_dir),
            )

        return model_path, label_path

    def load_model(self, progress_callback=None):
        """Load the model and tag labels."""
        cfg = self.model_config
        if progress_callback:
            progress_callback(f"Checking model files ({cfg['name']})...")
        model_path, label_path = self.download_model(progress_callback)

        if progress_callback:
            progress_callback("Loading tag labels...")
        self._load_labels(label_path)

        if progress_callback:
            progress_callback("Initializing AI engine on GPU...")
        self._create_session(model_path, progress_callback)

    def switch_model(self, new_model_key: str, progress_callback=None):
        """Switch to a different model and re-initialize session."""
        if new_model_key not in AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {new_model_key}")

        if new_model_key == self.model_key and self.session is not None:
            return

        self.model_key = new_model_key
        # Free old model memory
        self.session = None

        self.load_model(progress_callback)

    def _load_labels(self, label_path: Path):
        """Parse selected_tags.csv to categorize tags."""
        self.tag_names = []
        self.rating_tags = []
        self.general_tags = []
        self.character_tags = []

        with open(label_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tag_name = row["name"]
                tag_category = int(row["category"])
                self.tag_names.append(tag_name)

                if tag_category == TAG_CATEGORY_RATING:
                    self.rating_tags.append(len(self.tag_names) - 1)
                elif tag_category == TAG_CATEGORY_GENERAL:
                    self.general_tags.append(len(self.tag_names) - 1)
                elif tag_category == TAG_CATEGORY_CHARACTER:
                    self.character_tags.append(len(self.tag_names) - 1)

    def _create_session(self, model_path: Path, progress_callback=None):
        """Create ONNX Runtime inference session with CUDA 13 acceleration."""
        import onnxruntime as ort

        try:
            ort.set_default_logger_severity(3)
        except Exception:
            pass

        if self.use_gpu and hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls(cuda=True, cudnn=True)
            except Exception:
                pass

        providers = []

        if self.use_gpu:
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                if progress_callback:
                    progress_callback("Configuring CUDA GPU acceleration...")
                try:
                    providers.append(("CUDAExecutionProvider", {
                        "device_id": 0,
                        "arena_extend_strategy": "kSameAsRequested",
                        "cudnn_conv_algo_search": "HEURISTIC",
                    }))
                    providers.append("CPUExecutionProvider")

                    sess_options = ort.SessionOptions()
                    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    sess_options.log_severity_level = 3

                    self.session = ort.InferenceSession(
                        str(model_path),
                        sess_options=sess_options,
                        providers=providers,
                    )

                    actual = self.session.get_providers()[0]
                    if actual == "CUDAExecutionProvider":
                        gpu_name = _get_nvidia_gpu_name()
                        if gpu_name:
                            self._provider_name = f"CUDA ({gpu_name})"
                        else:
                            self._provider_name = "CUDA GPU"
                        if progress_callback:
                            progress_callback(f"CUDA GPU acceleration active ({self._provider_name}) ✓")
                        return
                    else:
                        self.session = None

                except Exception as e:
                    if progress_callback:
                        progress_callback(f"CUDA session failed ({e}), trying alternatives...")
                    self.session = None
                    providers = []

            if "DmlExecutionProvider" in available and self.session is None:
                try:
                    providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
                    sess_options = ort.SessionOptions()
                    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                    sess_options.log_severity_level = 3

                    self.session = ort.InferenceSession(
                        str(model_path),
                        sess_options=sess_options,
                        providers=providers,
                    )

                    actual = self.session.get_providers()[0]
                    if actual == "DmlExecutionProvider":
                        self._provider_name = "DirectML GPU"
                        return
                except Exception:
                    self.session = None

        # CPU Fallback
        if self.session is None:
            self._provider_name = "CPU (ONNX GPU unavailable)" if self.use_gpu else "CPU"
            providers = ["CPUExecutionProvider"]

            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.log_severity_level = 3

            self.session = ort.InferenceSession(
                str(model_path),
                sess_options=sess_options,
                providers=providers,
            )

        actual = self.session.get_providers()[0]
        if progress_callback:
            progress_callback(f"Model loaded on: {actual}")

    @property
    def provider_info(self) -> str:
        return self._provider_name

    # ── Image Preprocessing ───────────────────────────────────────────────

    def _preprocess_single(self, image_path: str) -> np.ndarray:
        """Preprocess a single image into (image_size, image_size, 3) BGR float32."""
        size = self.image_size
        with Image.open(image_path) as raw_img:
            # Respect EXIF Orientation so portrait images are not passed sideways to the model
            img = ImageOps.exif_transpose(raw_img)
            if img is None:
                img = raw_img
            img = img.convert("RGBA")

            # Create white background for transparent images
            background = Image.new("RGBA", img.size, (255, 255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background.convert("RGB")

            # Letterbox padding
            max_dim = max(img.size)
            padded = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
            offset = ((max_dim - img.size[0]) // 2, (max_dim - img.size[1]) // 2)
            padded.paste(img, offset)
            padded = padded.resize((size, size), Image.BICUBIC)

            arr = np.array(padded, dtype=np.float32)
            arr = arr[:, :, ::-1]  # RGB -> BGR
            return arr

    def _preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess single image with batch dimension (1, H, W, C)."""
        arr = self._preprocess_single(image_path)
        return np.expand_dims(arr, axis=0)

    # ── Inference (Single & Batch) ────────────────────────────────────────

    def _parse_probabilities(self, probabilities: np.ndarray) -> dict:
        """Convert a 1D probability array into categorized tag dictionary."""
        ratings = {}
        for idx in self.rating_tags:
            ratings[self.tag_names[idx]] = float(probabilities[idx])

        general = {}
        for idx in self.general_tags:
            conf = float(probabilities[idx])
            if conf >= self.general_threshold:
                general[self.tag_names[idx]] = conf

        characters = {}
        for idx in self.character_tags:
            conf = float(probabilities[idx])
            if conf >= self.character_threshold:
                characters[self.tag_names[idx]] = conf

        all_tags_with_conf = list(general.items()) + list(characters.items())
        all_tags_with_conf.sort(key=lambda x: x[1], reverse=True)
        all_tags = [tag for tag, _ in all_tags_with_conf]

        return {
            "rating": ratings,
            "general": general,
            "character": characters,
            "all_tags": all_tags,
        }

    def tag_image(self, image_path: str) -> dict:
        """Run inference on a single image."""
        if self.session is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        input_data = self._preprocess_image(image_path)
        input_name = self.session.get_inputs()[0].name
        output = self.session.run(None, {input_name: input_data})
        probabilities = output[0][0]
        return self._parse_probabilities(probabilities)

    def tag_images_batch(self, image_paths: list, batch_size: int = None, progress_callback=None) -> dict:
        """
        Run high-speed batch inference on a list of images using multi-threaded
        preprocessing and batched GPU tensor execution.
        """
        if self.session is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if batch_size is None:
            batch_size = self.batch_size

        results = {}
        total = len(image_paths)
        if total == 0:
            return results

        input_name = self.session.get_inputs()[0].name

        # Process in chunks of batch_size
        for chunk_start in range(0, total, batch_size):
            chunk_paths = image_paths[chunk_start : chunk_start + batch_size]
            
            # Preprocess images in parallel using CPU threads
            preprocessed = []
            valid_paths = []
            
            def load_and_prep(p):
                try:
                    return p, self._preprocess_single(p), None
                except Exception as ex:
                    return p, None, ex

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(chunk_paths))) as executor:
                for path, arr, err in executor.map(load_and_prep, chunk_paths):
                    if err is not None:
                        results[path] = {"error": str(err), "all_tags": []}
                    else:
                        preprocessed.append(arr)
                        valid_paths.append(path)

            if preprocessed:
                batch_tensor = np.stack(preprocessed, axis=0)
                # Single GPU batch inference call
                batch_outputs = self.session.run(None, {input_name: batch_tensor})[0]

                for p, probs in zip(valid_paths, batch_outputs):
                    results[p] = self._parse_probabilities(probs)

            # Update progress
            done_count = min(chunk_start + len(chunk_paths), total)
            if progress_callback:
                last_path = chunk_paths[-1]
                progress_callback(done_count, total, last_path, f"Processed {done_count}/{total} images")

        return results

    def tag_images(self, image_paths: list, progress_callback=None) -> dict:
        """Compatibility wrapper that runs batch inference."""
        return self.tag_images_batch(image_paths, batch_size=self.batch_size, progress_callback=progress_callback)


# ── Utility ───────────────────────────────────────────────────────────────────

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif", ".gif"}


def find_images_in_folder(folder_path: str) -> list:
    """Recursively find all supported image files in a folder."""
    images = []
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return images

    for f in sorted(folder.rglob("*")):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
            images.append(str(f))

    return images


def format_tag(tag: str) -> str:
    """Format a tag for display (replace underscores with spaces)."""
    return tag.replace("_", " ")


def normalize_tag(tag: str) -> str:
    """Normalize a tag for comparison (lowercase, strip, underscores)."""
    return tag.strip().lower().replace(" ", "_")
