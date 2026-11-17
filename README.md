# Auto Photo Tagger

<p align="center">
  <img src="assets/app_icon.png" width="160" height="160" alt="Auto Photo Tagger App Icon" />
</p>

An AI-powered desktop application for intelligent image analysis, booru-style tag classification, tag vocabulary standardization, and safe metadata embedding into image files.

Built with **PyQt6** and **ONNX Runtime**, Auto Photo Tagger leverages modern vision models (WD SwinV2, ConvNeXt, ViT) with dynamic hardware acceleration (DirectML on Windows GPUs, CUDA on NVIDIA GPUs, or CPU fallback).

![Version](https://img.shields.io/badge/version-1.4.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![PyQt6](https://img.shields.io/badge/UI-PyQt6-green)
![ONNX Runtime](https://img.shields.io/badge/Inference-ONNX%20Runtime-orange)
![ExifTool](https://img.shields.io/badge/Metadata-ExifTool-purple)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

---

## ✨ Features

### 🧠 Vision AI Inference & Models
- **Multi-Model Support**:
  - `WD SwinV2 v3 (Default / Detail)`: High accuracy on clothing, accessories, character details, poses, and objects.
  - `WD ConvNeXt v3 (Fastest)`: Maximum batch throughput with pure convolutional architecture.
  - `WD ViT v3 (Vision Transformer)`: Vision Transformer variant for broad scene and subject classification.
- **On-Demand Model Downloader**: Missing models and label vocabularies download automatically from Hugging Face Hub in the background.
- **Batch & Single-Image Inference**: Analyze hundreds of images concurrently or perform quick single-image inspections via "Analyze Current".
- **Dynamic Hardware Acceleration**:
  - Automatically identifies available hardware at runtime (`⚡ CUDA (RTX 5090)`, `⚡ CUDA (GTX 1660)`, `⚡ DirectML GPU`, or `💻 CPU`) via ONNX Runtime.
- **EXIF Orientation Transposition**:
  - Automatically respects camera EXIF orientation flags (`exif_transpose`) so rotated or portrait images render and infer upright without being distorted sideways.

### 📚 Smart Tag Library, Aliases & Advanced Tags
- **Custom Categories**: Add, remove, and rename categories on the fly via the top toolbar button, column headers, or directly when approving pending tags.
- **Embedded Alias / Translation System**:
  - Raw AI model tags are seamlessly mapped to standardized parent tags (e.g., raw tag `tree` automatically translates to approved parent tag `plant`).
  - Right-click any detected, existing, or library tag to set it as an alias, change its category, mark it as Advanced, or block it.
  - **Alias-to-Tag Conversion**: Right-click any alias chip in the **Tag Libraries** alias panel (or translated chip in **Detected Tags**) and choose **Make Tag** to convert it back into a standalone approved tag.
  - **Sub-Alias Carry-Over**: When converting an existing tag with aliases into an alias of another tag, all of its existing aliases automatically carry over to the new parent tag.
- **Toggleable Advanced Tags (`◆ Advanced: ON / OFF`)**:
  - Flag any tag as an **Advanced Tag** (stored in `config/advanced_tags.json`) while keeping it inside its normal category.
  - When **ON**, Advanced tags are highlighted in red (`◆ tag_name`), flagged with **`◆ [N ADV]`** badges in the file list, and filterable via **`◆ Adv`**.
  - When **OFF**, Advanced tags are discreetly hidden from Detected Tags and Tag Libraries and excluded from image metadata writes.
- **Category View Toggle (`In Categories`)**:
  - **Checked**: Shows translated tags inline inside their respective categories (`orig → final`).
  - **Unchecked**: Shows the final tags inside their categories above and lists the `orig → final` translations in a dedicated section below.
- **Blocked & Pending Review**:
  - Blocked tags are automatically suppressed; unapproved pending tags are highlighted in orange (`⚠️ Pending`), strictly excluded from writes until approved, and filterable in the file list.

### 🏷️ Non-Destructive Metadata Writing (ExifTool)
- **Comprehensive Metadata Embedding**: Writes tags using ExifTool to standard industry containers:
  - `IPTC:Keywords`
  - `XMP:Subject`
  - `XPKeywords`
- **Smart Merge & Deduplication**: Discovers existing image tags, merges them with newly accepted tags, removes duplicates, and saves them in clean alphabetical order.
- **Interactive Tag Skipping / Removal**:
  - Left-click any detected or existing tag chip to cross it out / grey it out, preventing it from being written to that image.
  - Quick "Clear All" and "Restore All" controls for existing tags.
- **Preserve File Modification Dates**:
  - Captures exact file timestamps (`st_mtime_ns`) prior to writing and restores them afterward (`os.utime`), keeping your file system sorting intact.
- **Safety Confirmations**: Prevents unintended writes with a confirmation dialog summarizing image count and pending actions.
- **Built-in ExifTool Auto-Installer**: Automatically checks for local ExifTool installations, with one-click automated winget and web download fallback.

### 🖥️ Modern Workspace UI
- **Drag-and-Drop**: Drop individual image files, multiple selections, or full folders directly into the application window.
- **Customizable Layout**:
  - Resizable split-pane divider between the image preview and tag workspace.
  - Toggle preview position between Top (vertical split) or Left (horizontal split).
  - Adjustable thumbnail size slider and thumbnail toggle.
- **Status Bar Badges**: Live ExifTool status indicator and active hardware provider badge neatly docked at the bottom right.
- **Console-Free Launch**: Launch quietly via `Auto Photo Tagger - Run (Windows).bat` (`pythonw.exe`), with diagnostics via `Auto Photo Tagger - Run With Console (Windows).bat`, or on Linux/macOS via `Auto Photo Tagger - Run (Linux).sh`.

---

## 🚀 Quick Start

### Prerequisites
- **Windows 10 / 11 (64-bit)**, **Linux**, or **macOS** (Apple Silicon & Intel)
- **Python 3.10+**
- *(Optional but recommended)* NVIDIA GPU with up-to-date drivers for CUDA acceleration (Windows/Linux), or Apple Silicon for MPS acceleration (macOS). Runs on CPU if no discrete GPU is present.

### Windows

1. **Install**:
   Double-click or run:
   ```bat
   "Auto Photo Tagger - Install (Windows).bat"
   ```
   This creates `venv/`, installs `onnxruntime-directml` (universal Windows GPU for NVIDIA/AMD/Intel by default, with optional CUDA 13 or CPU-only modes) and application dependencies from `requirements.txt`, and verifies your ONNX Runtime setup.
2. **Run**:
   - **Standard (No Console Window)**: Double-click `Auto Photo Tagger - Run (Windows).bat`
   - **Debug / Diagnostic Mode**: Double-click `Auto Photo Tagger - Run With Console (Windows).bat`
   - **Manual**: `venv\Scripts\activate` then `python app\main.py`
3. **ExifTool**:
   - Can be installed automatically from inside the app, or downloaded from [exiftool.org](https://exiftool.org/).

### Linux & macOS

1. **Make scripts executable** (first time only):
   ```bash
   chmod +x "Auto Photo Tagger - Install (Linux).sh" "Auto Photo Tagger - Run (Linux).sh"
   ```
2. **Install**:
   ```bash
   ./"Auto Photo Tagger - Install (Linux).sh"
   ```
   This creates `venv/` and installs `onnxruntime` / `onnxruntime-gpu` and application dependencies from `requirements.txt`.
3. **Install ExifTool** (required for writing metadata):
   - **macOS (Homebrew)**: `brew install exiftool`
   - **Ubuntu / Debian**: `sudo apt install libimage-exiftool-perl`
   - **Fedora / RHEL**: `sudo dnf install perl-Image-ExifTool`
4. **Run**:
   ```bash
   ./"Auto Photo Tagger - Run (Linux).sh"
   ```
   Or manually:
   ```bash
   source venv/bin/activate && python app/main.py
   ```

### Compiling to Standalone Executable (.exe on Windows)
- **One-Click Compiler**: Double-click `releases\Compile EXE.bat`
- Automatically reads `APP_VERSION` from `app/main.py` and builds into `releases/`:
  - **Option 1 (Recommended)**: Standalone folder distribution (`releases\Auto Photo Tagger v<version>\`) for instant startup and easy portability.
  - **Option 2**: Single self-contained executable file (`releases\Auto Photo Tagger v<version>.exe`).

---

## 📖 Usage Guide

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ [Model Dropdown] [Confidence Slider] [📁 Folder] [🔍 Current] [⚡ Batch]    [📚 Libs] [💾 Write]│
├──────────────────────────────┬─────────────────────────────────────────────────────────┤
│ Image List / Thumbnails      │ Preview Pane                                            │
│                              │ ─────────────────────────────────────────────────────── │
│                              │ Existing Tags: [tag1] [tag2 (greyed)] [Clear] [Restore] │
│                              │ Detected Tags:                                          │
│                              │   [General]    [Clothing]    [Body]    [Character]      │
│                              │   • Left-click: Toggle skip (cross-out)                 │
│                              │   • Right-click: Set as alias for existing tag         │
├──────────────────────────────┴─────────────────────────────────────────────────────────┤
│ Ready — 12 images loaded                           [Progress Bar]  [ExifTool ✓] [⚡ GPU]│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **Load Images**: Click **📁 Select Folder** or drag-and-drop images or folders anywhere onto the window.
2. **Select Model & Confidence**: Choose your preferred model from the top dropdown (defaults to `WD SwinV2 v3`) and adjust the confidence threshold slider.
3. **Analyze**:
   - Click **⚡ Analyze Batch** to queue and process all loaded images.
   - Or click **🔍 Analyze Current** to analyze only the active photo.
4. **Curate Tags**:
   - **Skip / Cross-Out**: Left-click any tag chip to disable it for that image.
   - **Alias Mapping**: Right-click any tag chip to map it as an alias to a library tag.
   - **Tweak Existing Tags**: Click existing tags to exclude them, or use "Clear All" to strip existing tags upon writing.
5. **Manage Libraries**: Click **📚 Tag Libraries** to view the 5-column Category manager, search tags, add custom tags, or modify alias chains.
6. **Save Tags**: Click **💾 Write Tags to Images** (top right) and confirm the prompt to write all merged tags to your files without altering file timestamps.

---

## 📁 Project Structure

```
App1 - AI - Photo Tagger/
├── Auto Photo Tagger - Install (Windows).bat          # Windows virtualenv & dependency setup
├── Auto Photo Tagger - Install (Linux).sh             # Linux/macOS virtualenv & dependency setup
├── Auto Photo Tagger - Run (Windows).bat              # Windows silent launcher (pythonw app\main.py)
├── Auto Photo Tagger - Run With Console (Windows).bat # Windows terminal launcher for debugging
├── Auto Photo Tagger - Run (Linux).sh                 # Linux/macOS launcher (python app/main.py)
├── CHANGELOG.md                               # Version & build history
├── requirements.txt                           # Cross-platform Python dependencies
├── app/                                       # Core Python application modules
│   ├── main.py                                # Main PyQt6 UI and application logic
│   ├── tagger_engine.py                       # ONNX Runtime / Florence-2 inference & model manager
│   ├── tag_library.py                         # Approved, alias, blocked, and advanced tag manager
│   ├── metadata_handler.py                    # ExifTool wrapper for tag reading and writing
│   └── exiftool_installer.py                  # ExifTool discovery, verification, and auto-install
├── assets/                                    # UI icons and graphics
│   ├── app_icon.png                           # Application window icon
│   ├── app_icon.ico                           # Multi-resolution Windows executable icon
│   └── check_icon.png                         # Checkbox indicator icon
├── config/                                    # Persistent settings & tag libraries
│   ├── config.json                            # User preferences, window state, & paths
│   ├── approved_tags.json                     # Approved tags, categories, & aliases
│   ├── blocked_tags.json                      # Blocked/suppressed tags
│   └── advanced_tags.json                     # Toggleable Advanced tag list
├── models/                                    # Downloaded model weights and tag CSVs
└── releases/                                  # Compiled executables & PyInstaller build script
    └── Compile EXE.bat                        # Builds versioned .exe into releases/
```

---

## ⚙️ Configuration (`config/config.json`)

Key application settings persist automatically:
```json
{
  "threshold": 0.35,
  "model": "wd-swinv2-v3",
  "exiftool_path": "C:\\Program Files\\ExifTool\\exiftool.exe",
  "thumbnail_size": 36,
  "show_thumbnails": true,
  "preview_orientation": "horizontal",
  "show_translated_in_categories": true,
  "advanced_tags_enabled": true,
  "tag_chip_size": "default"
}
```

---

## 🛡️ License

This project is licensed under the [MIT License](LICENSE).
Model weights and tag mappings are distributed in accordance with SmilingWolf's WD-Tagger model licenses.

