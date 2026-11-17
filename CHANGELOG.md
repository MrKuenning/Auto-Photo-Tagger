# Changelog

All notable changes to the **Auto Photo Tagger** project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [1.4.0] - 2026-11-16

### Changed
- **Application Renamed to Auto Photo Tagger**:
  - Renamed the application title, class (`AutoPhotoTaggerApp`), AppUserModelID, launcher scripts (`Auto Photo Tagger - Install/Run...`), executable output (`Auto Photo Tagger v<version>`), and documentation from **AI Photo Tagger** to **Auto Photo Tagger**.
- **Project Directory Reorganization**:
  - Moved Python application modules (`main.py`, `tagger_engine.py`, `tag_library.py`, `metadata_handler.py`, `exiftool_installer.py`) from `src/` to `app/`.
  - Moved UI icons and graphics (`app_icon.png`, `app_icon.ico`, `check_icon.png`) from `src/` to `assets/` and updated `_resolve_asset_path()` in `app/main.py` for both source and frozen modes.
  - Kept persistent settings and tag libraries in `config/`.
- **Cross-Platform Install & Run Scripts**:
  - Renamed and capitalized Windows scripts with OS labels: `AI Tagger - Install (Windows).bat`, `AI Tagger - Run (Windows).bat`, and `AI Tagger - Run With Console (Windows).bat`.
  - Added Linux and macOS shell scripts: `AI Tagger - Install (Linux-macOS).sh` (auto-detecting NVIDIA CUDA on Linux and Apple MPS/CPU on macOS) and `AI Tagger - Run (Linux-macOS).sh`.
  - Updated `requirements.txt` for cross-platform compatibility (`onnxruntime-gpu` on Windows/Linux, `onnxruntime` on macOS, removed unused `windnd` and `customtkinter`).
- **Removed Florence-2 & PyTorch Dependencies (Major Size Reduction)**:
  - Removed `florence-2-large` from `app/tagger_engine.py` and `app/main.py` so the app focuses exclusively on structured WD v3 ONNX taggers.
  - Removed `torch`, `torchvision`, `transformers`, `timm`, and `einops` from `requirements.txt`, install scripts, and `releases/Compile EXE.bat` (~2.8–2.9 GB reduction in `venv` and compiled builds).
  - Replaced `torch.cuda.get_device_name()` with lightweight `nvidia-smi` GPU name detection and updated `_setup_cuda_dlls()` to discover system `CUDA_PATH` / `nvidia/*/bin` libraries directly for ONNX Runtime.
- **DirectML Default Windows GPU Backend**:
  - Updated `Auto Photo Tagger - Install (Windows).bat` to default to **DirectML** (`onnxruntime-directml`), providing full GPU acceleration on NVIDIA, AMD, and Intel GPUs at ~547 MB `venv` size (with optional CUDA 13 and CPU-only choices).
- **Versioned Executable Compiler (`releases/Compile EXE.bat`)**:
  - Updated `releases/Compile EXE.bat` to resolve the project root, read `APP_VERSION` dynamically from `app/main.py`, and output versioned builds directly into `releases/` (`releases/AI Photo Tagger v<version>/` or `releases/AI Photo Tagger v<version>.exe`).
- **Documentation & Repository Hygiene**:
  - Updated `README.md` with installation and launch instructions for Windows, Linux, and macOS, plus the updated project layout.
  - Expanded `.gitignore` to exclude `build/`, `dist/`, `*.spec`, `releases/`, `models/`, `config/`, local ExifTool binaries, OS metadata files (`.DS_Store`, `Thumbs.db`), and temporary/log files.

---

## [1.3.1] - 2026-11-12

### Added
- **Windows Executable Compiler & PyInstaller Pipeline**:
  - Added **`AI Tagger - Compile EXE.bat`** for one-click compilation of the application into a standalone Windows binary.
  - Added **`compile_exe.spec`** containing comprehensive bundling rules, hidden import declarations, and dynamic library collection for PyTorch, ONNX Runtime GPU, Transformers, Timm, and PyQt6.
  - Added dual build modes:
    - **Standalone Folder Distribution** (`dist\AI Photo Tagger\`): Recommended for lightning-fast sub-second startup without unpacking overhead.
    - **Single-File Executable** (`dist\AI Photo Tagger.exe`): Self-contained single-file portable binary.
  - Updated path resolution across `src/main.py`, `src/tagger_engine.py`, `src/tag_library.py`, and `src/exiftool_installer.py` with runtime detection (`sys.frozen` / `sys._MEIPASS`) so `config.json`, `models/`, `tag_libraries/`, and app icons resolve properly in both source mode and compiled binary mode.
- **Custom Modern Application Icon**:
  - Designed and generated a 3D desktop icon featuring a glowing camera aperture lens fused with an AI microchip metadata tag and luminescent cyan and emerald green circuit traces against a beveled obsidian space-navy glassmorphism background.
  - Rendered and bundled in both high-resolution PNG format ([src/app_icon.png](file:///c:/Users/Brady/Projects/AI%20-%20Photo%20Tagger/App1%20-%20AI%20-%20Photo%20Tagger/src/app_icon.png)) and multi-resolution Windows ICO format ([app_icon.ico](file:///c:/Users/Brady/Projects/AI%20-%20Photo%20Tagger/App1%20-%20AI%20-%20Photo%20Tagger/app_icon.ico), containing 16x16, 32x32, 48x48, 64x64, 128x128, and 256x256 mipmaps).
  - Integrated into the desktop window frame, the top controls bar next to the application title, and registered with Windows Taskbar (`SetCurrentProcessExplicitAppUserModelID`).
- **High-Visibility Pending Tag Indicators & Dedicated Filter in Image List**:
  - Replaced the subtle plain-text bracket suffix with unmissable visual indicators across the file list so users can scan large batches and immediately identify images requiring attention:
    - **Prominent Prefix Badge**: Images with unapproved pending tags display **`⚠️ [?{n} PENDING] <filename> (✓{n})`** at the very front of the row (ensuring visibility even on long filenames).
    - **Row Highlight & Warning Color**: Pending items are styled with a warm amber background tint (`rgba(210, 153, 34, 40)`), bright amber foreground text (`#f0883e`), and bold font weight.
    - **Header Warning Counter**: The file count header displays total pending images (e.g. `120 images [⚠️ 8 pending]`).
    - **One-Click `⚠️ Pending` Filter**: Added a toggle button in the left panel toolbar that instantly filters the list to show only images containing pending tags.
    - **Synchronized Updates**: Approving, aliasing, or blocking tags immediately updates the row styling, badges, and counters in real time.
- **Visual Distinction for Detected Tags Matching Existing Metadata**:
  - When an image already has embedded metadata tags that match AI-detected tags, matching chips in the **Detected Tags** panel are dynamically colored Cyan (`#38bdf8`) rather than standard newly detected Green (`#3fb950`).
  - Distinguishes tags that already exist on the image (e.g., `lemon`) from newly detected tags to be written (e.g., `fruit`, `yellow`).
  - Supports direct tag matches and alias-translated matches, updating seamlessly upon asynchronous metadata loading or tag toggling.
  - Updated the legend bar to clearly reflect **`● Existing / Match`** in Cyan and **`● Approved (New)`** in Green.
- **Build Number & In-App Version Badge**:
  - Incremented application release to **`v1.3.1 (Build 14)`**.
  - Added a dedicated monospace version badge (**`v1.3.1 (Build 14)`**) in the top toolbar directly next to the application logo.
  - Included version and build details in the window title bar (`AI Photo Tagger v1.3.1 (Build 14) — <Hardware Provider>`).
- **Toggleable Advanced Tags System**:
  - Added `config/advanced_tags.json` and `TagLibrary` support (`is_advanced`, `set_advanced`, `toggle_advanced`) to flag any tag as an **Advanced Tag** while keeping it inside its normal category.
  - Auto-migrated existing `"Category +"` categories (`Body +`, `Clothing +`, `Pose +`) into their base categories and registered their tags in `config/advanced_tags.json`.
  - Added a global **`◆ Advanced: ON` / `◇ Advanced: OFF`** toggle in the top toolbar (persisted in `config/config.json`). When `OFF`, Advanced Tags are hidden from Detected Tags and Tag Libraries and excluded from image metadata writes.
  - Styled Advanced Tag chips in red (`◆ tag_name`, matching standard approved chip geometry), added **`◆ [N ADV]`** badges and red row tints in the file list, added a **`◆ Adv`** filter button in the left panel, and added **`◆ Mark as Advanced`** / **`◇ Remove Advanced`** to tag right-click menus and the Tag Libraries manager.
- **Tag Libraries Context Menu & Alias-to-Tag Conversion (Build 14)**:
  - Added a right-click context menu to tags inside the **Tag Libraries** columns (`Make Alias of Another Tag`, `Add Alias to This Tag`, `Move Category`, `Mark/Unmark Advanced`, `Block Tag`, `Remove Tag`).
  - Added right-click **`🏷️ Make Tag`** conversion on alias chips in both the **Tag Libraries** alias panel and translated chips in **Detected Tags** to convert an alias back into a standalone approved tag in a chosen category.
- **Root Directory Cleanup (`config/` Consolidation)**:
  - Consolidated `config.json`, `approved_tags.json`, and `blocked_tags.json` (alongside `advanced_tags.json`) into the `config/` directory, and moved `app_icon.png` / `app_icon.ico` into `src/`.

### Changed
- **`In Categories` Toggle Behavior (Build 14)**:
  - When **`In Categories`** is unchecked, final translated tags now still appear in their respective categories above (as normal approved chips), while the full `orig → final` mappings appear in the dedicated **⇄ Translated Tags** section below.

### Fixed
- **Model Downloader `'NoneType' object has no attribute 'write'` Error (Build 12)**:
  - Fixed a crash during HuggingFace model downloads (`hf_hub_download` / `snapshot_download`) when running without a console window (`AI Tagger - Run.bat` via `pythonw.exe` or the compiled `--windowed` `.exe`), where `sys.stdout` and `sys.stderr` are `None` and `tqdm` progress bars failed on `.write()`.
  - Added automatic `os.devnull` stream fallbacks for `None` `sys.stdout`/`sys.stderr` at startup in `src/main.py` and `src/tagger_engine.py`.
- **Missing `sys` Imports in Frozen Executable Mode (Build 11)**:
  - Fixed `NameError: name 'sys' is not defined` crash in `src/tagger_engine.py` during `_resolve_models_dir()` and `_setup_cuda_dlls()`.
  - Added missing `import sys` to `src/exiftool_installer.py` for frozen app directory detection (`_resolve_app_dir()`).
  - Validated all frozen resolution paths via simulation.
- **Exclusion of Unapproved Pending Tags from Metadata Writing**:
  - Fixed metadata tag compilation in `_start_batch_write` so only verified library tags (`proc['final_tags']`, encompassing directly approved tags and aliases translated to approved tags) are written to image files.
  - Pending/unapproved tags (`proc['pending']`) are now strictly excluded and ignored during write operations until explicitly approved or mapped via alias.
  - Updated write confirmation dialog and the Pending Approval section header to clearly state that pending tags are excluded from file writes.

## [1.3.0] - 2026-11-11

### Added
- **Multi-Option Tag Chip Right-Click Context Menu**:
  - Replaced the direct alias prompt on tag right-click with an intuitive context menu featuring three essential actions:
    - **`🔗 Set as alias`**: Opens the alias dialog to map the tag under an approved canonical tag.
    - **`🚫 Block Tag`**: Adds the tag directly to the blocked/disabled tag library and immediately removes it from active tags.
    - **`📁 Change Category`**: Opens a category picker to instantly move the tag to a different category (or approve it if pending).
  - Context menu is enabled uniformly across approved tags, translated tags, pending tags, and existing image tags.
- **Resolution-Adaptive Tag Size Setting**:
  - Added a **`Size:`** dropdown selector above the Detected Tags panel offering four scaling options: **Small (10px)**, **Default (11px)**, **Large (13px)**, and **Extra Large (15px)**.
  - Dynamically recalculates chip font sizing, padding margins, and action button dimensions to optimize legibility across high-DPI and standard resolution displays.
  - Preference automatically persists in `config.json` under `"tag_chip_size"` and re-renders active chips in real time upon selection.
- **Fluid Tag Line-Wrapping (Zero Horizontal Scrolling)**:
  - Completely eliminated sideways horizontal scrollbars in the Detected Tags and Existing Tags scroll areas by overriding `FlowContainer.minimumSizeHint()` and `FlowLayout.minimumSize()` to report flexible minimum width (`QSize(0, 0)`).
  - Enforced `ScrollBarAlwaysOff` horizontally while maintaining full vertical fluid auto-wrapping across window resize and splitter movements.
- **Sub-Alias Carry-Over on Alias Conversion**:
  - Converting an existing approved tag with aliases into an alias of another tag (e.g., aliasing `shorts` with alias `blue shorts` under `pants`) now automatically gathers and migrates all existing sub-aliases.
  - Sub-aliases are registered directly under the new parent tag (`pants`), preventing accidental loss of alias relationships when restructuring tags.
- **Dynamic Add Alias Button Text**:
  - The "+ Add Alias" button in the Tag Library Manager now updates in real time based on both the selected tag and any text typed into the alias input box.
  - If `hat` is selected and `cap` is typed, the button dynamically reads: **`Add "cap" as an alias under "hat"`**.
  - When the input is blank, it displays **`+ Add Alias under "hat"`**; when no tag is selected, it disables gracefully as `+ Add Alias`.
- **Microsoft Florence-2-Large Vision Foundation Model**:
  - Added **`Florence-2 Large (Microsoft / Natural)`** to the Model selector dropdown for photorealistic and real-world digital camera photos.
  - Combines `<OD>` (Object Detection) for discrete real-world objects and `<MORE_DETAILED_CAPTION>` for rich descriptive scene attributes.
  - Generates natural keyword tags alongside full narrative scene captions displayed directly in the UI.
  - Fully accelerated with PyTorch CUDA (FP16) on the NVIDIA GeForce RTX 5090 Blackwell GPU with sub-0.10s execution.
  - Includes automated model download and validation support with on-disk caching in `models/florence-2-large`.
- **Dual Dynamic Alias Linking Buttons in Library**:
  - Replaced the static alias linking button with two complementary, dynamically labeled buttons:
    - **`Select tag to use as Alias under "<tag>"`**: Converts an existing external tag into an alias under the selected tag (migrating any existing sub-aliases).
    - **`Use "<tag>" as alias under existing tag`**: Converts the selected tag into an alias under another existing approved tag, automatically removing it from its current category and preserving sub-aliases.
  - Buttons automatically adapt their labels and tooltips to the currently selected tag (e.g. `hat` → `Select tag to use as Alias under "hat"` and `Use "hat" as alias under existing tag`), and disable gracefully when no tag is selected.
- **Library Search Clear Buttons**:
  - Added a dedicated **`✕ Clear`** button next to the search input in the Tag Library Manager for one-click query reset and refocus.
  - Enabled native inline clear icons (`setClearButtonEnabled(True)`) for instant text clearing.
  - Added matching filter clear button to the Blocked / Disabled Tags tab.
- **Add Tag Dialog Category Dropdown Box**:
  - Converted the category field in the "Add New Tag" popup into a styled, non-editable dropdown box.
  - Added inline **`➕ + Add New Category...`** item to the dropdown, allowing on-the-fly category creation without leaving the dialog.
- **Expanded Clothing Color Aliases in Tag Library**:
  - Added 890+ color variations as aliases to generic clothing items (Shirt, Pants, Dress, Skirt, Shorts, Jacket, Coat, Sweater, Hoodie, Blouse, Vest, Suit, Blazer, Boots, Shoes, Socks, Hat, Scarf, Gloves, etc.) in `approved_tags.json`.
  - Full color coverage: Black, White, Grey/Gray, Blue, Red, Green, Yellow, Orange, Purple, Pink, Silver, Gold, Brown, Tan, Navy, and Beige.
  - AI detections like `navy_dress`, `black_shirt`, or `beige_pants` automatically map to their approved parent tags under Clothing.
- **Custom Category Management (Add, Remove & Rename Categories)**:
  - Added **`📁 + Add Category`** button to the Tag Library Manager to easily create custom categories.
  - Added dedicated **Delete (`✕`)** button to each category column header with confirmation prompt.
  - Added right-click context menu to category columns with options to add tags, rename categories, or delete them.
  - Added **`+ New Category...`** action directly inside the tag approval popup, allowing inline category creation while tagging images.
  - Enhanced `TagLibrary` with `add_category()`, `remove_category()`, and `rename_category()` methods.
- **Dynamic Hardware & GPU Detection**:
  - Dynamically inspects host hardware using PyTorch CUDA device name queries (`torch.cuda.get_device_name(0)`).
  - Accurate device badge display: `⚡ CUDA (<GPU Model>)`, `⚡ DirectML GPU`, or `💻 CPU`.
  - Dynamically updates the main window title to match the active inference engine.
- **Top Bar & Status Bar Overhaul**:
  - Moved **ExifTool status badge** and **Device badge** to the bottom right of the status bar next to the progress bar.
  - Repositioned **"💾 Write Tags to Images"** button to the far right of the top toolbar for clear visual hierarchy.
- **File Modification Date Preservation**:
  - Captures original file timestamps (`st_mtime_ns`) before writing metadata.
  - Automatically restores timestamps using `os.utime()` after ExifTool operations, preventing image file modified dates from changing.
- **EXIF Orientation Auto-Transposition**:
  - Integrated `ImageOps.exif_transpose` and `QImageReader.setAutoTransform(True)`.
  - Portrait and rotated photos now display and infer upright rather than appearing sideways.
- **Interactive Existing Tags Chip Panel**:
  - Displays loaded IPTC/XMP/EXIF tags as interactive chips.
  - Left-click existing tags to grey out / cross them out, safely excluding them from writing.
  - Added **"✕ Clear All"** and **"↺ Restore All"** buttons for one-click mass exclusion or restoration.
  - Compact, auto-scrolling flow layout prevents wasted vertical space in the preview workspace.
- **Direct Tag Chip Alias Creation**:
  - Right-click any detected or existing tag chip to open the alias popup and map it directly to an approved library tag.
- **Translated Tags View Toggle**:
  - Added **`[✓] In Categories`** toggle checkbox.
  - Supports rendering translated tags either directly within their respective category groups or in a separate dedicated section.
- **Batch Write Confirmation**:
  - Added confirmation modal prompt before writing metadata to disk, detailing target file count.
- **Silent Background Model Scanning**:
  - Replaced blocking modal popups during model checks with non-intrusive status bar updates.
- **Silent Launcher**:
  - Added `AI Tagger - Run.bat` utilizing `pythonw.exe` to run the GUI cleanly without an active console window.
  - Preserved `AI Tagger - Run with console.bat` for debugging and logging.

### Changed
- **Root Directory Cleanup & Modular Restructuring**:
  - Moved core Python modules (`main.py`, `tagger_engine.py`, `tag_library.py`, `metadata_handler.py`, `exiftool_installer.py`) into the `src/` directory.
  - Moved obsolete `main_customtkinter.py` into the `Extra/` archive directory.
  - Updated all internal module and file path resolvers (`config.json`, `models/`, `tag_libraries/`) to use parent project root paths.
  - Updated launcher scripts (`AI Tagger - Run.bat`, `AI Tagger - Run with console.bat`, `AI Tagger - Install.bat`) to execute from `src/main.py`.

### Fixed
- Fixed alias loss when moving a tag between categories by implementing `TagLibrary.move_tag()`, ensuring all existing aliases move seamlessly with their parent tag to the new category.
- Fixed UI formatting defects, overlapping elements, and dark rectangle background patches:
  - **Divider Overlap Prevention**: Added 10px right margin to the preview header (`prev_header`), completely preventing the `⬍ Top/Bottom View` button border from overlapping the central splitter divider.
  - **In Categories Checkbox Proximity**: Replaced the wide stretch separating `Detected Tags` and `[✓] In Categories` with a clean 14px gap (`addSpacing(14)`), grouping the toggle directly with its section title while pushing empty space to the right.
  - **Left Edge Padding & Margins**: Added 12px left padding to `tag_edit_layout` and 4px padding to `tags_vlayout`, ensuring categories, chips, legend, and rating cards have comfortable breathing room and are no longer squished against the left splitter edge.
  - **Resizable Existing Tags Panel**: Implemented a vertical `QSplitter` (`tags_existing_splitter`) between the Detected Tags scroll area and the Existing Tags card, removing artificial 80px height caps and allowing users to freely drag and resize the existing tags drawer to any preferred height.
  - **Pane Header Alignment**: Aligned "Detected Tags" header row horizontally with "Image Preview" (consistent 26px height and margins), preventing section titles from shifting or sitting misaligned.
  - **Dynamic Wrapping & Overlap Elimination**: Implemented `FlowContainer` wrapper for `FlowLayout` that dynamically calculates and advertises `heightForWidth` to Qt's layout engine, completely preventing wrapped tag chips from overlapping headers or clipping into adjacent rows.
  - **Organized Category Section Layout**: Wrapped each category in a self-contained container with balanced padding (8px bottom margin, 4px spacing), bright white category headings (`#e6edf3`), and tag count badges (`📁 Body (6)`), ensuring clear visual distinction between categories.
  - **Dedicated Rating & Caption Card**: Moved safety ratings (`General`, `Sensitive`, `Questionable`, `Explicit`) and Florence-2 narrative captions into a styled pill-card banner below the legend bar with formatted color badges and word-wrapping, eliminating unpadded text floating at the top of the pane.
  - **Balanced Tag Chip Padding**: Added symmetrical horizontal padding (`(8, 4, 8, 4)`) for non-pending tag chips, preventing text from colliding with the right border while preserving compact margins for pending chips with action buttons.
  - Removed cascading `QWidget` dark background styling that created pitch-black rectangular patches behind labels and frames inside cards.
  - Added clean antialiased checkmark icon to `QCheckBox` indicator so checkboxes show a visible checkmark instead of a solid flat square.
  - Re-spaced and formatted buttons (`Select All`, `✕ Clear`, `✕ Clear All`, `↺ Restore All`, etc.) with consistent 26px height and balanced horizontal padding to eliminate squashed/overlapping text.
  - Split Detected Tags header and color legend into a clean two-row layout with a dedicated pill-style legend container to prevent horizontal collision.
  - Added badge styling to confidence threshold label (`#21262d` pill with Consolas font).
  - Cleaned up Existing Image Tags card styling and placeholder margins.
  - Polished footer status bar margins and alignment.
- Fixed hardcoded "RTX 5090" badge string when running on non-NVIDIA or CPU-only hardware.
- Fixed `NameError: name 'MetaReadWorker' is not defined` during drag-and-drop batch imports.
- Fixed issue where clicking translated tags failed to grey out / toggle disabled state due to translated label string mismatch.
- Fixed ExifTool installer 404 / non-zip archive errors by adding `winget` installation support with direct download fallback.

---

## [1.2.0] - 2026-11-09

### Added
- **Automated ExifTool Management**:
  - Built-in installer (`exiftool_installer.py`) with support for automated `winget` installation, local path discovery, and manual folder selection.
  - Real-time ExifTool verification and status badge in UI.
- **Safe Metadata Merging**:
  - Multi-container tag writing to `IPTC:Keywords`, `XMP:Subject`, and `XPKeywords`.
  - Non-destructive tag ingestion: reads existing tags, merges with newly detected tags, removes duplicates, and sorts alphabetically.
- **Single Image Inference**:
  - Added **"🔍 Analyze Current"** button to analyze only the active photo without triggering a full batch run.

---

## [1.1.0] - 2026-11-05

### Added
- **Integrated Tag Library & Alias Architecture**:
  - Merged translations directly into approved categories as aliases (`{category: {tag: [aliases]}}`).
  - Added 5-column Category manager with real-time text search and filter.
  - In-place category assignment popup for pending tags.
- **Drag-and-Drop Ingestion**:
  - Full drag-and-drop support for single files, image batches, and nested folders.
- **Preview & Thumbnail Customization**:
  - Resizable split divider between image preview and tagging workspace.
  - Orientation toggle to switch between horizontal (side-by-side) and vertical (top-bottom) preview layouts.
  - Slider controls for thumbnail scaling and visibility toggle.

---

## [1.0.0] - 2026-11-01

### Added
- Initial release of **AI Photo Tagger**.
- Support for WD SwinV2 v3, WD ConvNeXt v3, and WD ViT v3 ONNX models.
- GPU acceleration via ONNX Runtime with CUDA 13.0 execution provider.
- Booru-style tag classification across General, Character, and Rating categories.
- Basic tag curation workflow with Approved and Blocked lists.
- Metadata writing via ExifTool.

