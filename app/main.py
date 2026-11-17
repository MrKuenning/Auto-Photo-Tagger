"""
Auto Photo Tagger - Modern Desktop UI (PyQt6)
High-performance virtualized image browser with GPU-accelerated WD SwinV2/ConvNeXt tagger,
batch inference, persistent ExifTool metadata writing, and 5-column tag library management.
"""

import sys
import os
import json
from pathlib import Path

# Ensure stdout/stderr are valid streams in windowless mode (pythonw.exe / PyInstaller --windowed)
# Prevents "'NoneType' object has no attribute 'write'" in libraries like tqdm / huggingface_hub
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

# Ensure app directory is on sys.path
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from PIL import Image, ImageOps

from PyQt6.QtCore import (
    Qt, QThread, pyqtSignal, QRunnable, QThreadPool, QSize,
    QPoint, QRect, QObject, QItemSelectionModel
)
from PyQt6.QtGui import (
    QPixmap, QImage, QImageReader, QIcon, QFont, QColor, QPainter, QBrush, QPen,
    QAction, QCursor
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLabel, QPushButton,
    QSlider, QComboBox, QLineEdit, QTextEdit, QProgressBar, QFrame,
    QFileDialog, QMessageBox, QMenu, QTabWidget, QScrollArea,
    QGridLayout, QSizePolicy, QDialog, QStackedWidget, QAbstractItemView,
    QLayout, QCheckBox, QInputDialog
)

from tagger_engine import (
    TaggerEngine, AVAILABLE_MODELS, DEFAULT_MODEL, SUPPORTED_EXTENSIONS,
    is_model_installed, find_images_in_folder, format_tag, normalize_tag
)
from tag_library import TagLibrary
from metadata_handler import MetadataHandler
from exiftool_installer import (
    find_exiftool, verify_exiftool, download_and_install_exiftool, install_via_winget
)

# ── Version Info ──────────────────────────────────────────────────────────
APP_VERSION = "1.4.0"
APP_BUILD_STRING = f"v{APP_VERSION}"

# ── Color Palette & Stylesheet ───────────────────────────────────────────────

def _resolve_asset_path(filename: str) -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if hasattr(sys, "_MEIPASS"):
            meipass_assets = Path(sys._MEIPASS) / "assets" / filename
            if meipass_assets.exists():
                return meipass_assets
            meipass_p = Path(sys._MEIPASS) / filename
            if meipass_p.exists():
                return meipass_p
        for base in (exe_dir / "assets", exe_dir, exe_dir / "_internal" / "assets"):
            candidate = base / filename
            if candidate.exists():
                return candidate
    return Path(__file__).resolve().parent.parent / "assets" / filename


CHECK_ICON_PATH = _resolve_asset_path("check_icon.png").resolve().as_posix()
APP_ICON_PNG = _resolve_asset_path("app_icon.png").resolve()
APP_ICON_ICO = _resolve_asset_path("app_icon.ico").resolve()

DARK_STYLE = f"""
QMainWindow {{
    background-color: #0d1117;
}}

QWidget {{
    color: #e6edf3;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
    font-size: 13px;
}}

QLabel {{
    background-color: transparent;
    color: #e6edf3;
}}

QFrame {{
    background-color: transparent;
    border: none;
}}

QFrame.card, #existingTagsCard {{
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
}}

QFrame.panel {{
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
}}

QPushButton {{
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #30363d;
    border-color: #8b949e;
}}
QPushButton:pressed {{
    background-color: #161b22;
}}
QPushButton:disabled {{
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}}

QPushButton.primary {{
    background-color: #238636;
    border-color: #2ea043;
    color: #ffffff;
}}
QPushButton.primary:hover {{
    background-color: #2ea043;
}}
QPushButton.primary:disabled {{
    background-color: #161b22;
    color: #484f58;
    border-color: #21262d;
}}

QPushButton.accent {{
    background-color: #1f6feb;
    border-color: #388bfd;
    color: #ffffff;
}}
QPushButton.accent:hover {{
    background-color: #388bfd;
}}

QPushButton.danger {{
    background-color: #da3633;
    border-color: #f85149;
    color: #ffffff;
}}
QPushButton.danger:hover {{
    background-color: #f85149;
}}

QComboBox {{
    background-color: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: 500;
}}
QComboBox:hover {{
    border-color: #58a6ff;
}}
QComboBox QAbstractItemView {{
    background-color: #161b22;
    color: #e6edf3;
    border: 1px solid #30363d;
    selection-background-color: #1f6feb;
    selection-color: #ffffff;
}}

QLineEdit {{
    background-color: #0d1117;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
}}
QLineEdit:focus {{
    border-color: #58a6ff;
}}

QTextEdit {{
    background-color: #0d1117;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-family: Consolas, monospace;
    font-size: 11px;
}}

QListWidget {{
    background-color: transparent;
    border: none;
    outline: none;
}}
QListWidget::item {{
    background-color: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    margin: 2px 4px;
    padding: 4px;
}}
QListWidget::item:hover {{
    background-color: #21262d;
    border-color: #30363d;
}}
QListWidget::item:selected {{
    background-color: #1f6feb22;
    border-color: #58a6ff;
}}

QProgressBar {{
    background-color: #161b22;
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: #58a6ff;
    border-radius: 3px;
}}

QScrollBar:vertical {{
    background: #0d1117;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #30363d;
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: #58a6ff;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QTabWidget::pane {{
    border: 1px solid #30363d;
    background-color: #161b22;
    border-radius: 8px;
}}
QTabBar::tab {{
    background-color: #21262d;
    color: #8b949e;
    border: 1px solid #30363d;
    border-bottom: none;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background-color: #161b22;
    color: #58a6ff;
    border-color: #30363d;
}}
QTabBar::tab:hover:!selected {{
    background-color: #30363d;
    color: #e6edf3;
}}

QSplitter::handle {{
    background-color: #21262d;
    border-radius: 2px;
}}
QSplitter::handle:hover {{
    background-color: #58a6ff;
}}
QSplitter::handle:horizontal {{
    width: 6px;
}}
QSplitter::handle:vertical {{
    height: 6px;
}}

QCheckBox {{
    color: #e6edf3;
    spacing: 6px;
    background-color: transparent;
    font-size: 12px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #30363d;
    background-color: #21262d;
}}
QCheckBox::indicator:hover {{
    border-color: #58a6ff;
}}
QCheckBox::indicator:checked {{
    background-color: #1f6feb;
    border-color: #388bfd;
    image: url({CHECK_ICON_PATH});
}}
"""

def _resolve_config_file() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "config" / "config.json").exists():
            return exe_dir / "config" / "config.json"
        if (exe_dir / "config.json").exists():
            return exe_dir / "config.json"
        if hasattr(sys, "_MEIPASS") and (Path(sys._MEIPASS) / "config" / "config.json").exists():
            return Path(sys._MEIPASS) / "config" / "config.json"
        if (exe_dir / "_internal" / "config" / "config.json").exists():
            return exe_dir / "_internal" / "config" / "config.json"
        return exe_dir / "config" / "config.json"
    return Path(__file__).resolve().parent.parent / "config" / "config.json"


CONFIG_FILE = _resolve_config_file()


# ── Background Worker Threads ────────────────────────────────────────────────

class BatchAnalyzeWorker(QThread):
    """Background worker for batch AI inference."""
    progress = pyqtSignal(int, int, str, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, engine: TaggerEngine, image_paths: list, batch_size: int = 16):
        super().__init__()
        self.engine = engine
        self.image_paths = image_paths
        self.batch_size = batch_size

    def run(self):
        try:
            def cb(current, total, path, status):
                self.progress.emit(current, total, path, status)

            results = self.engine.tag_images_batch(
                self.image_paths,
                batch_size=self.batch_size,
                progress_callback=cb
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class BatchWriteWorker(QThread):
    """Background worker for ExifTool batch metadata writing."""
    progress = pyqtSignal(int, int, str, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, metadata_handler: MetadataHandler, tag_map: dict):
        super().__init__()
        self.handler = metadata_handler
        self.tag_map = tag_map

    def run(self):
        try:
            def cb(current, total, path, status):
                self.progress.emit(current, total, path, status)

            results = self.handler.write_tags_batch(
                self.tag_map,
                progress_callback=cb
            )
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class MetaReadWorker(QThread):
    """Background worker to read existing metadata tags from loaded images without blocking UI."""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, metadata_handler: MetadataHandler, image_paths: list):
        super().__init__()
        self.handler = metadata_handler
        self.image_paths = list(image_paths)

    def run(self):
        try:
            if not self.handler or not self.image_paths:
                self.finished.emit({})
                return
            tags = self.handler.read_tags_batch(self.image_paths)
            self.finished.emit(tags)
        except Exception as e:
            self.finished.emit({})


class WingetInstallWorker(QThread):
    """Background worker to install ExifTool via winget without freezing UI."""
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, target_location: str = None):
        super().__init__()
        self.target_location = target_location

    def run(self):
        try:
            def cb(msg):
                self.progress.emit(msg)

            path = install_via_winget(target_location=self.target_location, progress_callback=cb)
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))


class ExifToolDownloadWorker(QThread):
    """Background worker to download and install ExifTool without freezing UI."""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def run(self):
        try:
            def cb(cur, tot, msg):
                self.progress.emit(cur, tot, msg)

            path = download_and_install_exiftool(progress_callback=cb)
            self.finished.emit(path)
        except Exception as e:
            self.error.emit(str(e))


class ExifToolSetupDialog(QDialog):
    """Clean dialog allowing the user to install ExifTool via winget, browse for existing, or download."""

    def __init__(self, parent=None, current_path: str = None):
        super().__init__(parent)
        self.setWindowTitle("ExifTool Setup")
        self.setFixedSize(540, 430)
        self.configured_path = None
        self.worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        header = QLabel("<b>📷 ExifTool Setup</b>")
        header.setStyleSheet("color: #58a6ff; font-size: 16px;")
        layout.addWidget(header)

        desc = QLabel(
            "ExifTool is required to write IPTC, XMP, and EXIF keywords directly into your images.<br>"
            "Choose one of the convenient installation options below:"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8b949e; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        # Status row
        curr_text = current_path if current_path else "Not detected"
        self.status_lbl = QLabel(f"<b>Current Path:</b> <span style='color: #f0883e;'>{curr_text}</span>")
        self.status_lbl.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 6px 10px; font-size: 11px;")
        self.status_lbl.setWordWrap(True)
        layout.addWidget(self.status_lbl)

        # SECTION 1: Winget Install (Card)
        winget_card = QFrame()
        winget_card.setStyleSheet("background-color: #161b22; border: 1px solid #238636; border-radius: 8px; padding: 10px;")
        w_layout = QVBoxLayout(winget_card)
        w_layout.setContentsMargins(10, 8, 10, 8)
        w_layout.setSpacing(8)

        w_title = QLabel("<b>⚡ Option 1: Install with winget (Recommended)</b>")
        w_title.setStyleSheet("color: #3fb950; font-size: 13px;")
        w_layout.addWidget(w_title)

        w_desc = QLabel("Installs official Oliver Betz ExifTool package and automatically registers it on your PC.")
        w_desc.setStyleSheet("color: #8b949e; font-size: 11px;")
        w_layout.addWidget(w_desc)

        w_btn_row = QHBoxLayout()
        self.winget_btn = QPushButton("⚡ Install ExifTool via winget")
        self.winget_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #2ea043;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2ea043; }
        """)
        self.winget_btn.clicked.connect(self._on_winget_install)
        w_btn_row.addWidget(self.winget_btn)

        self.copy_cmd_btn = QPushButton("📋 Copy Command")
        self.copy_cmd_btn.setToolTip("Copy command: winget install --id OliverBetz.ExifTool -e")
        self.copy_cmd_btn.clicked.connect(self._copy_winget_cmd)
        w_btn_row.addWidget(self.copy_cmd_btn)
        w_btn_row.addStretch()

        w_layout.addLayout(w_btn_row)
        layout.addWidget(winget_card)

        # SECTION 2: Existing or Portable Download
        other_card = QFrame()
        other_card.setStyleSheet("background-color: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px;")
        o_layout = QVBoxLayout(other_card)
        o_layout.setContentsMargins(10, 8, 10, 8)
        o_layout.setSpacing(8)

        o_title = QLabel("<b>Option 2: Locate Existing or Download Portable ZIP</b>")
        o_title.setStyleSheet("color: #e6edf3; font-size: 12px;")
        o_layout.addWidget(o_title)

        o_btn_row = QHBoxLayout()
        self.browse_btn = QPushButton("📁 Locate Existing exiftool.exe...")
        self.browse_btn.setToolTip("Select an existing exiftool.exe located in another folder on your PC")
        self.browse_btn.clicked.connect(self._on_browse)
        o_btn_row.addWidget(self.browse_btn)

        self.download_btn = QPushButton("⬇ Download Portable ZIP")
        self.download_btn.setToolTip("Download standalone package directly to the app directory")
        self.download_btn.clicked.connect(self._on_download)
        o_btn_row.addWidget(self.download_btn)
        o_btn_row.addStretch()

        o_layout.addLayout(o_btn_row)
        layout.addWidget(other_card)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 4px;
                height: 10px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #238636;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.msg_lbl = QLabel("")
        self.msg_lbl.setStyleSheet("color: #3fb950; font-size: 11px;")
        layout.addWidget(self.msg_lbl)

        # Bottom Buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(self.cancel_btn)
        layout.addLayout(bottom_layout)

    def _copy_winget_cmd(self):
        cmd = "winget install --id OliverBetz.ExifTool -e"
        QApplication.clipboard().setText(cmd)
        self.msg_lbl.setStyleSheet("color: #3fb950; font-size: 11px;")
        self.msg_lbl.setText("Copied to clipboard: winget install --id OliverBetz.ExifTool -e")

    def _set_ui_busy(self, busy: bool):
        self.winget_btn.setEnabled(not busy)
        self.copy_cmd_btn.setEnabled(not busy)
        self.browse_btn.setEnabled(not busy)
        self.download_btn.setEnabled(not busy)
        self.cancel_btn.setEnabled(not busy)
        self.progress_bar.setVisible(busy)

    def _on_winget_install(self):
        self._set_ui_busy(True)
        self.progress_bar.setRange(0, 0)
        self.msg_lbl.setStyleSheet("color: #58a6ff; font-size: 11px;")
        self.msg_lbl.setText("Running winget install --id OliverBetz.ExifTool -e...")

        self.worker = WingetInstallWorker()
        self.worker.progress.connect(lambda msg: self.msg_lbl.setText(msg))
        self.worker.finished.connect(self._on_install_success)
        self.worker.error.connect(self._on_install_error)
        self.worker.start()

    def _on_browse(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Locate exiftool.exe",
            "C:\\",
            "ExifTool Executable (exiftool*.exe);;All Executables (*.exe)"
        )
        if file_path:
            valid, ver_or_err = verify_exiftool(file_path)
            if valid:
                self.configured_path = file_path
                self.msg_lbl.setStyleSheet("color: #3fb950; font-size: 11px;")
                self.msg_lbl.setText(f"ExifTool {ver_or_err} verified!")
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Invalid ExifTool Executable",
                    f"The selected file failed verification test:\n\n{ver_or_err}\n\nPlease select a valid exiftool.exe."
                )

    def _on_download(self):
        self._set_ui_busy(True)
        self.progress_bar.setRange(0, 0)
        self.msg_lbl.setStyleSheet("color: #58a6ff; font-size: 11px;")
        self.msg_lbl.setText("Starting download from official mirrors...")

        self.worker = ExifToolDownloadWorker()
        self.worker.progress.connect(self._on_download_progress)
        self.worker.finished.connect(self._on_install_success)
        self.worker.error.connect(self._on_install_error)
        self.worker.start()

    def _on_download_progress(self, cur, tot, msg):
        self.msg_lbl.setText(msg)
        if tot > 0:
            self.progress_bar.setRange(0, tot)
            self.progress_bar.setValue(cur)
        else:
            self.progress_bar.setRange(0, 0)

    def _on_install_success(self, path):
        self.configured_path = path
        self.msg_lbl.setStyleSheet("color: #3fb950; font-size: 11px;")
        self.msg_lbl.setText("ExifTool successfully configured!")
        self.accept()

    def _on_install_error(self, err):
        self._set_ui_busy(False)
        self.msg_lbl.setStyleSheet("color: #f85149; font-size: 11px;")
        self.msg_lbl.setText("Installation attempt failed.")
        QMessageBox.critical(
            self,
            "ExifTool Installation Error",
            f"{err}\n\n"
            "Tip: You can run this command in your PowerShell / Terminal:\n"
            "winget install --id OliverBetz.ExifTool -e\n\n"
            "Or click 'Locate Existing exiftool.exe' if you already have it installed."
        )


def extract_images_from_paths(paths: list) -> list:
    """Extract and de-duplicate supported images from dropped files and directories."""
    collected = []
    seen = set()
    ignored_dirs = {"venv", ".venv", "env", ".git", "__pycache__", "node_modules", ".gemini", ".idea", ".vscode"}

    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        if path.is_file():
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                s = str(path.resolve())
                if s not in seen:
                    seen.add(s)
                    collected.append(s)
        elif path.is_dir():
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d.lower() not in ignored_dirs and not d.startswith(".")]
                for f in sorted(files):
                    f_path = Path(root) / f
                    if f_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                        s = str(f_path.resolve())
                        if s not in seen:
                            seen.add(s)
                            collected.append(s)
    return collected


class DropListWidget(QListWidget):
    """QListWidget supporting drag-and-drop of files and folders."""
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)


class ImagePreviewWidget(QFrame):
    """
    High-res preview widget with smooth dynamic scaling during resize and divider drags.
    Also accepts dropped images or folders directly.
    """
    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "card")
        self.setMinimumSize(140, 140)
        self.setAcceptDrops(True)
        self.current_pixmap = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        self.label = QLabel("Select an image to preview\nor drag and drop images / folders anywhere")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #6e7681; font-size: 13px; line-height: 1.4;")
        layout.addWidget(self.label)

    def set_image(self, path: str):
        if not path or not Path(path).exists():
            self.current_pixmap = None
            self.label.setPixmap(QPixmap())
            self.label.setText("Select an image to preview\nor drag and drop images / folders anywhere")
            return
        try:
            reader = QImageReader(path)
            reader.setAutoTransform(True)
            qimg = reader.read()
            if not qimg.isNull():
                self.current_pixmap = QPixmap.fromImage(qimg)
            else:
                with Image.open(path) as raw_img:
                    img = ImageOps.exif_transpose(raw_img)
                    if img is None:
                        img = raw_img
                    if img.mode != "RGBA":
                        img = img.convert("RGBA")
                    data = img.tobytes("raw", "RGBA")
                    qimg2 = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                    self.current_pixmap = QPixmap.fromImage(qimg2)

            self._update_scaled_pixmap()
        except Exception:
            self.current_pixmap = None
            self.label.setPixmap(QPixmap())
            self.label.setText("Error loading preview")

    def _update_scaled_pixmap(self):
        if self.current_pixmap and not self.current_pixmap.isNull():
            target_size = self.size() - QSize(16, 16)
            if target_size.width() > 10 and target_size.height() > 10:
                scaled = self.current_pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                self.files_dropped.emit(paths)
            event.acceptProposedAction()


class ThumbnailRunnable(QRunnable):
    """Worker to load and generate image thumbnails asynchronously."""

    class Signals(QObject):
        loaded = pyqtSignal(str, QPixmap)

    def __init__(self, path: str, size: int = 128):
        super().__init__()
        self.path = path
        self.size = max(size, 128)
        self.signals = ThumbnailRunnable.Signals()

    def run(self):
        try:
            with Image.open(self.path) as raw_img:
                img = ImageOps.exif_transpose(raw_img)
                if img is None:
                    img = raw_img
                img.thumbnail((self.size, self.size), Image.Resampling.BILINEAR)
                # Convert PIL to QImage
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg)
                self.signals.loaded.emit(self.path, pixmap)
        except Exception:
            pass


# ── Searchable Alias Target Picker Dialog ────────────────────────────────────

class AliasPickerPopup(QDialog):
    """
    Searchable dialog to select an approved parent tag to alias to,
    or to select an existing tag to link as an alias.
    """
    def __init__(self, parent, source_tag: str, tag_library: TagLibrary, title: str = None, prompt: str = None, exclude_tags: list = None):
        super().__init__(parent)
        self.setWindowTitle(title or f"Alias Tag: {format_tag(source_tag)}")
        self.setFixedSize(460, 520)
        self.source_tag = source_tag
        self.tag_library = tag_library
        self.exclude_tags = set(self.tag_library.normalize(t) for t in (exclude_tags or [source_tag]))
        self.result_parent_tag = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Header info
        header_text = prompt or f"Choose an existing approved tag that <b>{format_tag(source_tag)}</b> should map to:"
        header_lbl = QLabel(header_text)
        header_lbl.setWordWrap(True)
        header_lbl.setStyleSheet("color: #e6edf3; font-size: 13px;")
        layout.addWidget(header_lbl)

        # Search bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter approved tags...")
        self.search_input.textChanged.connect(self._filter_list)
        layout.addWidget(self.search_input)

        # List of tags
        self.tag_list = QListWidget()
        self.tag_list.setStyleSheet("""
            QListWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                background-color: #161b22;
                border: 1px solid #21262d;
                border-radius: 6px;
                padding: 6px 10px;
                margin: 2px 0px;
                color: #e6edf3;
            }
            QListWidget::item:hover {
                background-color: #21262d;
                border-color: #58a6ff;
            }
            QListWidget::item:selected {
                background-color: #1f6feb33;
                border-color: #58a6ff;
                color: #58a6ff;
            }
        """)
        self.tag_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tag_list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.tag_list)

        # Populate tags list: tuples of (tag, category)
        self.all_tags = []
        for cat in sorted(self.tag_library.approved.keys()):
            for tag in sorted(self.tag_library.approved[cat].keys()):
                if self.tag_library.normalize(tag) not in self.exclude_tags:
                    self.all_tags.append((tag, cat))

        self._filter_list(self.search_input.text())

        # Buttons at bottom
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.select_btn = QPushButton("✓ Set as Alias")
        self.select_btn.setEnabled(False)
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: 600;
                padding: 6px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #2ea043; }
            QPushButton:disabled { background-color: #21262d; color: #484f58; }
        """)
        self.select_btn.clicked.connect(self._confirm_selection)
        btn_layout.addWidget(self.select_btn)

        layout.addLayout(btn_layout)

    def _filter_list(self, query: str):
        self.tag_list.clear()
        q = query.strip().lower()
        for tag, cat in self.all_tags:
            if not q or q in tag.lower() or q in cat.lower():
                item = QListWidgetItem(f"{format_tag(tag)}  ({cat})")
                item.setData(Qt.ItemDataRole.UserRole, tag)
                self.tag_list.addItem(item)

    def _on_selection_changed(self):
        items = self.tag_list.selectedItems()
        self.select_btn.setEnabled(len(items) > 0)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._confirm_selection()

    def _confirm_selection(self):
        item = self.tag_list.currentItem()
        if item:
            self.result_parent_tag = item.data(Qt.ItemDataRole.UserRole)
            self.accept()


# ── Inline Category Picker Popup ─────────────────────────────────────────────

class CategoryPickerPopup(QDialog):
    """Clean borderless category picker popup positioned near the tag."""

    def __init__(self, parent, tag: str, categories: list, pos: QPoint, tag_library: TagLibrary = None, title: str = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.result_category = None
        self.result_alias_target = None
        self.tag_library = tag_library
        self.tag = tag
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)

        container = QFrame()
        container.setObjectName("container")
        container.setStyleSheet("""
            #container {
                background-color: #161b22;
                border: 1px solid #58a6ff;
                border-radius: 8px;
            }
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(8, 8, 8, 8)
        c_layout.setSpacing(4)

        header_text = title if title else f"Category for: {format_tag(tag)}"
        header = QLabel(header_text)
        header.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 11px;")
        c_layout.addWidget(header)

        for cat in categories:
            btn = QPushButton(cat)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #e6edf3;
                    border: none;
                    text-align: left;
                    padding: 6px 10px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1f6feb33;
                    color: #58a6ff;
                }
            """)
            btn.clicked.connect(lambda _, c=cat: self._select(c))
            c_layout.addWidget(btn)

        if self.tag_library:
            divider = QFrame()
            divider.setFrameShape(QFrame.Shape.HLine)
            divider.setStyleSheet("color: #30363d; margin: 4px 0;")
            c_layout.addWidget(divider)

            new_cat_btn = QPushButton("+ New Category...")
            new_cat_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #3fb950;
                    border: none;
                    text-align: left;
                    padding: 5px 10px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #23863633;
                    color: #3fb950;
                }
            """)
            new_cat_btn.clicked.connect(self._create_new_category)
            c_layout.addWidget(new_cat_btn)

            alias_btn = QPushButton("↔ Alias to Existing Tag...")
            alias_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1f6feb22;
                    color: #58a6ff;
                    border: 1px solid #1f6feb66;
                    text-align: left;
                    padding: 6px 10px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1f6feb;
                    color: #ffffff;
                }
            """)
            alias_btn.clicked.connect(self._open_alias_picker)
            c_layout.addWidget(alias_btn)

        layout.addWidget(container)
        self.move(pos)

    def _select(self, cat):
        self.result_category = cat
        self.accept()

    def _create_new_category(self):
        name, ok = QInputDialog.getText(
            self,
            "Create Category",
            "Enter new category name:",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if ok and name:
            cat = name.strip()
            if cat:
                if self.tag_library:
                    self.tag_library.add_category(cat)
                self._select(cat)

    def _open_alias_picker(self):
        self.hide()
        dialog = AliasPickerPopup(self.parent(), source_tag=self.tag, tag_library=self.tag_library)
        if dialog.exec() and dialog.result_parent_tag:
            self.result_alias_target = dialog.result_parent_tag
            self.accept()
        else:
            self.reject()


# ── Tag Chip Widget ──────────────────────────────────────────────────────────

class TagChip(QFrame):
    """Interactive tag chip supporting skip toggle (left click), approve, alias, and block."""
    toggled = pyqtSignal(str)
    approved = pyqtSignal(str, QPoint)
    aliased = pyqtSignal(str, QPoint)
    blocked = pyqtSignal(str)
    menu_requested = pyqtSignal(str, str, str, QPoint)  # (source_raw, canonical_tag, category_type, pos)

    CHIP_SIZES = {
        "small": {
            "font_size": 10,
            "margins_normal": (6, 2, 6, 2),
            "margins_pending": (6, 2, 3, 2),
            "btn_w": 18,
            "btn_h": 16,
            "btn_font": 9,
        },
        "default": {
            "font_size": 11,
            "margins_normal": (8, 4, 8, 4),
            "margins_pending": (8, 3, 4, 3),
            "btn_w": 20,
            "btn_h": 18,
            "btn_font": 10,
        },
        "large": {
            "font_size": 13,
            "margins_normal": (10, 5, 10, 5),
            "margins_pending": (10, 4, 5, 4),
            "btn_w": 22,
            "btn_h": 20,
            "btn_font": 11,
        },
        "xlarge": {
            "font_size": 15,
            "margins_normal": (12, 6, 12, 6),
            "margins_pending": (12, 5, 6, 5),
            "btn_w": 26,
            "btn_h": 24,
            "btn_font": 12,
        },
    }
    current_size = "default"

    def __init__(self, tag: str, category_type: str, is_skipped: bool = False, display_text: str = None, source_raw_tag: str = None, is_existing_match: bool = False, is_advanced: bool = False, parent=None):
        super().__init__(parent)
        self.tag = tag
        self.source_raw_tag = source_raw_tag or tag
        self.category_type = category_type  # 'approved', 'pending', 'translated', 'existing', 'blocked'
        self.is_skipped = is_skipped
        self.is_existing_match = is_existing_match
        self.is_advanced = is_advanced
        base_text = display_text or format_tag(tag)
        self.display_text = f"◆ {base_text}" if (is_advanced and not is_skipped) else base_text
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        sz = self.CHIP_SIZES.get(TagChip.current_size, self.CHIP_SIZES["default"])
        self.font_size = sz["font_size"]

        layout = QHBoxLayout(self)
        if category_type == "pending" and not is_skipped:
            m = sz["margins_pending"]
            layout.setContentsMargins(m[0], m[1], m[2], m[3])
            layout.setSpacing(4)
        else:
            m = sz["margins_normal"]
            layout.setContentsMargins(m[0], m[1], m[2], m[3])
            layout.setSpacing(4)

        self.label = QLabel(self.display_text)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.label)

        # Style based on category and skip state
        self._apply_style()

        if category_type == "pending" and not is_skipped:
            # Quick approve button
            self.approve_btn = QPushButton("✓")
            self.approve_btn.setFixedSize(sz["btn_w"], sz["btn_h"])
            self.approve_btn.setToolTip("Approve tag into category")
            self.approve_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #238636;
                    color: #ffffff;
                    border: none;
                    border-radius: 3px;
                    font-size: {sz['btn_font']}px;
                    font-weight: bold;
                    padding: 0;
                }}
                QPushButton:hover {{ background-color: #2ea043; }}
            """)
            self.approve_btn.clicked.connect(self._on_approve_clicked)
            layout.addWidget(self.approve_btn)

            # Quick alias button
            self.alias_btn = QPushButton("↔")
            self.alias_btn.setFixedSize(sz["btn_w"], sz["btn_h"])
            self.alias_btn.setToolTip("Alias this tag to an existing tag (e.g. black belt → belt)")
            self.alias_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1f6feb;
                    color: #ffffff;
                    border: none;
                    border-radius: 3px;
                    font-size: {sz['btn_font']}px;
                    font-weight: bold;
                    padding: 0;
                }}
                QPushButton:hover {{ background-color: #388bfd; }}
            """)
            self.alias_btn.clicked.connect(self._on_alias_clicked)
            layout.addWidget(self.alias_btn)

            # Quick block button
            self.block_btn = QPushButton("✕")
            self.block_btn.setFixedSize(sz["btn_w"], sz["btn_h"])
            self.block_btn.setToolTip("Block / Disable this tag")
            self.block_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #da3633;
                    color: #ffffff;
                    border: none;
                    border-radius: 3px;
                    font-size: {sz['btn_font']}px;
                    font-weight: bold;
                    padding: 0;
                }}
                QPushButton:hover {{ background-color: #f85149; }}
            """)
            self.block_btn.clicked.connect(lambda: self.blocked.emit(self.tag))
            layout.addWidget(self.block_btn)

    def _apply_style(self):
        fsize = getattr(self, "font_size", 11)
        if self.is_skipped:
            self.setToolTip(f"'{format_tag(self.tag)}' is greyed out (will be removed/skipped when saving).\n• Left-click: restore tag\n• Right-click: options (alias, block, change category, advanced)")
            self.setStyleSheet(f"""
                TagChip {{
                    background-color: #21262d;
                    border: 1px dashed #484f58;
                    border-radius: 5px;
                }}
                QLabel {{
                    background: transparent;
                    color: #6e7681;
                    text-decoration: line-through;
                    font-family: Consolas;
                    font-size: {fsize}px;
                }}
            """)
        elif getattr(self, "is_advanced", False):
            match_note = " (already exists on this image)" if getattr(self, "is_existing_match", False) else ""
            self.setToolTip(f"◆ Advanced tag{match_note}: '{format_tag(self.tag)}'.\n• Left-click: grey out / skip\n• Right-click: options (alias, block, change category, unmark advanced)")
            border_color = "#38bdf8" if getattr(self, "is_existing_match", False) else "#f85149"
            self.setStyleSheet(f"""
                TagChip {{
                    background-color: #da363322;
                    border: 1px solid {border_color};
                    border-radius: 5px;
                }}
                TagChip:hover {{
                    border-color: #ff7b72;
                    background-color: #da363333;
                }}
                QLabel {{
                    background: transparent;
                    color: #f85149;
                    font-family: Consolas;
                    font-size: {fsize}px;
                }}
            """)
        elif getattr(self, "is_existing_match", False):
            self.setToolTip(f"Existing match: '{format_tag(self.tag)}' already exists on this image.\n• Left-click: grey out / skip (will remove from file when saved)\n• Right-click: options (alias, block, change category)")
            self.setStyleSheet(f"""
                TagChip {{
                    background-color: #38bdf818;
                    border: 1px solid #38bdf8;
                    border-radius: 5px;
                }}
                TagChip:hover {{
                    border-color: #7dd3fc;
                    background-color: #38bdf830;
                }}
                QLabel {{
                    background: transparent;
                    color: #38bdf8;
                    font-family: Consolas;
                    font-size: {fsize}px;
                    font-weight: 600;
                }}
            """)
        elif self.category_type == "existing":
            self.setToolTip(f"Existing tag on image: '{format_tag(self.tag)}'.\n• Left-click: grey out / remove when saving\n• Right-click: options (alias, block, change category)")
            self.setStyleSheet(f"""
                TagChip {{
                    background-color: #38bdf818;
                    border: 1px solid #38bdf888;
                    border-radius: 5px;
                }}
                TagChip:hover {{
                    border-color: #38bdf8;
                    background-color: #38bdf828;
                }}
                QLabel {{
                    background: transparent;
                    color: #38bdf8;
                    font-family: Consolas;
                    font-size: {fsize}px;
                }}
            """)
        elif self.category_type == "approved":
            self.setToolTip(f"Approved tag: '{format_tag(self.tag)}'.\n• Left-click: grey out / skip\n• Right-click: options (alias, block, change category)")
            self.setStyleSheet(f"""
                TagChip {{
                    background-color: #23863622;
                    border: 1px solid #2ea043;
                    border-radius: 5px;
                }}
                QLabel {{
                    background: transparent;
                    color: #3fb950;
                    font-family: Consolas;
                    font-size: {fsize}px;
                }}
            """)
        elif self.category_type == "pending":
            self.setToolTip(f"Pending tag: '{format_tag(self.tag)}'.\n• Left-click: grey out / skip\n• Right-click: options (alias, block, change category)\n• Quick actions: ✓ approve, ↔ alias, ✕ block")
            self.setStyleSheet(f"""
                TagChip {{
                    background-color: #d2992222;
                    border: 1px solid #d29922;
                    border-radius: 5px;
                }}
                QLabel {{
                    background: transparent;
                    color: #f0883e;
                    font-family: Consolas;
                    font-size: {fsize}px;
                }}
            """)
        elif self.category_type == "translated":
            self.setToolTip(f"Translated tag: '{self.display_text}'.\n• Left-click: grey out / skip\n• Right-click: options (alias, block, change category)")
            self.setStyleSheet(f"""
                TagChip {{
                    background-color: #1f6feb22;
                    border: 1px solid #388bfd;
                    border-radius: 5px;
                }}
                QLabel {{
                    background: transparent;
                    color: #58a6ff;
                    font-family: Consolas;
                    font-size: {fsize}px;
                }}
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggled.emit(self.tag)
        elif event.button() == Qt.MouseButton.RightButton:
            pos = self.mapToGlobal(event.pos())
            target_source = self.source_raw_tag if self.source_raw_tag else self.tag
            self.menu_requested.emit(target_source, self.tag, self.category_type, pos)
        super().mousePressEvent(event)

    def _on_approve_clicked(self):
        pos = self.approve_btn.mapToGlobal(QPoint(0, self.approve_btn.height()))
        self.approved.emit(self.tag, pos)

    def _on_alias_clicked(self):
        pos = self.alias_btn.mapToGlobal(QPoint(0, self.alias_btn.height()))
        target_source = self.source_raw_tag if self.source_raw_tag else self.tag
        self.aliased.emit(target_source, pos)


# ── Flow Layout for Tag Chips ────────────────────────────────────────────────

class FlowLayout(QLayout):
    """
    Standard wrapping flow layout for PyQt6.
    Inherits from QLayout to properly calculate dynamic geometry and height-for-width.
    """

    def __init__(self, parent=None, margin=0, spacing=4):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing
        self.item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self.item_list.append(item)

    def count(self):
        return len(self.item_list)

    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), apply_geom=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, apply_geom=True)

    def sizeHint(self):
        parent = self.parentWidget()
        if parent and parent.width() > 0:
            return QSize(parent.width(), self.heightForWidth(parent.width()))
        return self.minimumSize()

    def minimumSize(self):
        return QSize(0, 0)

    def spacing(self):
        return self._spacing

    def setSpacing(self, spacing):
        self._spacing = spacing

    def _do_layout(self, rect, apply_geom=True):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(+margins.left(), +margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        spacing = self._spacing

        for item in self.item_list:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue

            item_size = item.sizeHint()
            next_x = x + item_size.width() + spacing

            if next_x - spacing > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + spacing
                next_x = x + item_size.width() + spacing
                line_height = 0

            if apply_geom:
                item.setGeometry(QRect(QPoint(x, y), item_size))

            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + margins.bottom()


class FlowContainer(QWidget):
    """
    Wrapping container widget for FlowLayout that properly advertises and reports
    height-for-width to parent layouts (such as QVBoxLayout inside a QScrollArea),
    preventing row overlaps when chips wrap.
    """
    def __init__(self, parent=None, margin=2, spacing=5):
        super().__init__(parent)
        self.flow = FlowLayout(self, margin=margin, spacing=spacing)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.flow.heightForWidth(width)

    def sizeHint(self):
        w = self.width()
        if w > 0:
            return QSize(w, self.flow.heightForWidth(w))
        return self.flow.sizeHint()

    def minimumSizeHint(self):
        return QSize(0, 0)

    def addWidget(self, widget):
        self.flow.addWidget(widget)


# ── Removable Alias Chip ─────────────────────────────────────────────────────

class RemovableAliasChip(QFrame):
    """Small chip showing an alias with a remove button and right-click context menu."""
    removed = pyqtSignal(str)
    make_tag_requested = pyqtSignal(str, QPoint)

    def __init__(self, alias: str, parent=None):
        super().__init__(parent)
        self.alias = alias
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setToolTip(f"Alias: '{format_tag(alias)}'\n• Right-click: Convert back to standalone tag or remove")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 4, 2)
        layout.setSpacing(4)
        self.setStyleSheet("""
            RemovableAliasChip {
                background-color: #1f6feb22;
                border: 1px solid #388bfd;
                border-radius: 4px;
            }
        """)

        lbl = QLabel(format_tag(alias))
        lbl.setStyleSheet("color: #58a6ff; font-family: Consolas; font-size: 11px;")
        layout.addWidget(lbl)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(14, 14)
        del_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        del_btn.setToolTip(f"Remove alias '{format_tag(alias)}'")
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #8b949e;
                border: none;
                font-size: 9px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover {
                color: #f85149;
            }
        """)
        del_btn.clicked.connect(lambda: self.removed.emit(self.alias))
        layout.addWidget(del_btn)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                color: #e6edf3;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        make_tag_act = menu.addAction("🏷️ Make Tag (convert to standalone tag)")
        remove_act = menu.addAction("✕ Remove Alias")
        action = menu.exec(event.globalPos())
        if action == make_tag_act:
            self.make_tag_requested.emit(self.alias, event.globalPos())
        elif action == remove_act:
            self.removed.emit(self.alias)


# ── Add New Tag Dialog ───────────────────────────────────────────────────────

class AddTagDialog(QDialog):
    """Modal dialog to add a new tag to the library with category selection and optional initial aliases."""

    def __init__(self, parent, tag_library: TagLibrary, default_category: str = None, prefill_tag: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Add New Tag to Library")
        self.setFixedSize(460, 360)
        self.tag_library = tag_library
        self.created_tag = None
        self.target_category = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        header = QLabel("<b>Add New Approved Tag</b>")
        header.setStyleSheet("color: #58a6ff; font-size: 15px;")
        layout.addWidget(header)

        # 1. Tag name input
        tag_vbox = QVBoxLayout()
        tag_vbox.setSpacing(4)
        tag_lbl = QLabel("Tag Name:")
        tag_lbl.setStyleSheet("color: #8b949e; font-weight: 600; font-size: 11px;")
        tag_vbox.addWidget(tag_lbl)

        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("e.g. leather jacket, sunglasses, sunset...")
        self.tag_input.setText(prefill_tag)
        self.tag_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 7px 10px;
                color: #e6edf3;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #58a6ff; }
        """)
        tag_vbox.addWidget(self.tag_input)
        layout.addLayout(tag_vbox)

        # 2. Category selection
        cat_vbox = QVBoxLayout()
        cat_vbox.setSpacing(4)
        cat_lbl = QLabel("Category:")
        cat_lbl.setStyleSheet("color: #8b949e; font-weight: 600; font-size: 11px;")
        cat_vbox.addWidget(cat_lbl)

        self.category_combo = QComboBox()
        self.category_combo.setEditable(False)
        self.category_combo.setStyleSheet("""
            QComboBox {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 6px 12px;
                color: #e6edf3;
                font-size: 13px;
            }
            QComboBox:hover { border-color: #58a6ff; }
            QComboBox:focus { border-color: #58a6ff; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #30363d;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
            QComboBox::down-arrow {
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid #8b949e;
                width: 0;
                height: 0;
            }
            QComboBox::down-arrow:hover {
                border-top-color: #58a6ff;
            }
            QComboBox QAbstractItemView {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px;
                color: #e6edf3;
                selection-background-color: #1f6feb;
                selection-color: #ffffff;
            }
        """)
        existing_cats = sorted(self.tag_library.approved.keys()) or ["General"]
        for c in existing_cats:
            self.category_combo.addItem(c)
        self.category_combo.addItem("➕ + Add New Category...")

        if default_category and default_category in existing_cats:
            self.category_combo.setCurrentText(default_category)

        self.category_combo.currentIndexChanged.connect(self._on_category_changed)

        cat_vbox.addWidget(self.category_combo)
        layout.addLayout(cat_vbox)

        # 3. Optional initial aliases
        alias_vbox = QVBoxLayout()
        alias_vbox.setSpacing(4)
        alias_lbl = QLabel("Aliases (optional, comma-separated):")
        alias_lbl.setStyleSheet("color: #8b949e; font-weight: 600; font-size: 11px;")
        alias_vbox.addWidget(alias_lbl)

        self.alias_input = QLineEdit()
        self.alias_input.setPlaceholderText("e.g. biker jacket, motorcycle jacket")
        self.alias_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 7px 10px;
                color: #e6edf3;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #58a6ff; }
        """)
        alias_vbox.addWidget(self.alias_input)
        layout.addLayout(alias_vbox)

        # Feedback / error message
        self.feedback_lbl = QLabel("")
        self.feedback_lbl.setStyleSheet("color: #f85149; font-size: 11px;")
        layout.addWidget(self.feedback_lbl)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.save_btn = QPushButton("✓ Add Tag")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                font-weight: 600;
                padding: 7px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #2ea043; }
        """)
        self.save_btn.clicked.connect(self._on_save)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

        # Keyboard shortcuts
        self.tag_input.returnPressed.connect(self._on_save)
        self.alias_input.returnPressed.connect(self._on_save)

    def _on_category_changed(self, index):
        if self.category_combo.itemText(index) == "➕ + Add New Category...":
            from PyQt6.QtWidgets import QInputDialog
            new_cat, ok = QInputDialog.getText(
                self, "New Category", "Enter new category name:",
                QLineEdit.EchoMode.Normal, ""
            )
            clean_cat = new_cat.strip() if new_cat else ""
            if ok and clean_cat:
                self.tag_library.add_category(clean_cat)
                insert_idx = self.category_combo.count() - 1
                self.category_combo.insertItem(insert_idx, clean_cat)
                self.category_combo.setCurrentIndex(insert_idx)
            else:
                self.category_combo.setCurrentIndex(0)

    def _on_save(self):
        raw_tag = self.tag_input.text().strip()
        if not raw_tag:
            self.feedback_lbl.setText("Please enter a tag name.")
            self.tag_input.setFocus()
            return

        cat = self.category_combo.currentText().strip()
        if not cat or cat == "➕ + Add New Category...":
            cat = "General"

        norm_tag = self.tag_library.normalize(raw_tag)

        # Check if already approved
        for existing_cat, tags in self.tag_library.approved.items():
            if norm_tag in [self.tag_library.normalize(t) for t in tags]:
                self.feedback_lbl.setText(f"Tag already exists in '{existing_cat}'.")
                return

        # Add tag to library
        self.tag_library.approve_tag(norm_tag, cat)
        self.created_tag = norm_tag
        self.target_category = cat

        # Add any initial aliases
        raw_aliases = self.alias_input.text().strip()
        if raw_aliases:
            for part in raw_aliases.split(","):
                alias_clean = part.strip()
                if alias_clean:
                    self.tag_library.add_alias(norm_tag, alias_clean)

        self.accept()


# ── Tag Library Manager (Tabs: Approved + Aliases & Blocked Tags) ────────────

class LibraryManagerWidget(QWidget):
    """
    Two-tab tag library manager:
      Tab 1: 5-Column Approved Categories with live search and dynamic Alias Management
      Tab 2: Blocked / Disabled Tags with unblock and category restore tools
    """
    library_updated = pyqtSignal()

    def __init__(self, tag_library: TagLibrary, parent=None):
        super().__init__(parent)
        self.library = tag_library
        self.selected_tag = None
        self.selected_category = None
        self.show_advanced = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Tab Widget
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # TAB 1: Approved Tags & Aliases
        self.tab_approved = QWidget()
        self._init_approved_tab()
        self.tab_widget.addTab(self.tab_approved, "✓ Approved Tags & Aliases")

        # TAB 2: Blocked / Disabled Tags
        self.tab_blocked = QWidget()
        self._init_blocked_tab()
        self.tab_widget.addTab(self.tab_blocked, "✕ Blocked / Disabled Tags")

        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        # Initial data load
        self.refresh()

    def refresh(self):
        """Refresh all tabs."""
        self._refresh_columns()
        self._refresh_blocked_list()

    def _on_tab_changed(self, index: int):
        if index == 0:
            self._refresh_columns()
        else:
            self._refresh_blocked_list()

    # ── TAB 1: Approved & Aliases Setup ──────────────────────────────────────

    def _init_approved_tab(self):
        tab_layout = QVBoxLayout(self.tab_approved)
        tab_layout.setContentsMargins(8, 8, 8, 8)
        tab_layout.setSpacing(10)

        # Top Bar: Search, Stats, Actions
        top_bar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search approved tags...")
        self.search_input.setMinimumWidth(240)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._refresh_columns)
        top_bar.addWidget(self.search_input)

        self.clear_search_btn = QPushButton("✕ Clear")
        self.clear_search_btn.setToolTip("Clear search query")
        self.clear_search_btn.setFixedHeight(30)
        self.clear_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #e6edf3;
            }
        """)
        self.clear_search_btn.clicked.connect(self._clear_search)
        top_bar.addWidget(self.clear_search_btn)

        self.selected_label = QLabel("No tag selected")
        self.selected_label.setStyleSheet("color: #8b949e; font-style: italic;")
        top_bar.addWidget(self.selected_label)

        top_bar.addStretch()

        self.add_category_btn = QPushButton("📁 + Add Category")
        self.add_category_btn.setToolTip("Create a new category in the approved library")
        self.add_category_btn.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb22;
                color: #58a6ff;
                border: 1px solid #388bfd;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        self.add_category_btn.clicked.connect(self._on_add_category)
        top_bar.addWidget(self.add_category_btn)

        self.add_tag_btn = QPushButton("+ Add New Tag")
        self.add_tag_btn.setToolTip("Add a new tag to the library")
        self.add_tag_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #2ea043;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #2ea043;
            }
        """)
        self.add_tag_btn.clicked.connect(lambda: self._open_add_tag_dialog())
        top_bar.addWidget(self.add_tag_btn)

        self.move_btn = QPushButton("⇄ Move Category")
        self.move_btn.setEnabled(False)
        self.move_btn.clicked.connect(self._on_move_tag)
        top_bar.addWidget(self.move_btn)

        self.adv_btn = QPushButton("◆ Advanced")
        self.adv_btn.setEnabled(False)
        self.adv_btn.setStyleSheet("QPushButton { color: #f85149; border-color: #f8514955; } QPushButton:hover { border-color: #f85149; background-color: #da363322; }")
        self.adv_btn.setToolTip("Mark or unmark the selected tag as an Advanced Tag")
        self.adv_btn.clicked.connect(self._on_toggle_advanced_tag)
        top_bar.addWidget(self.adv_btn)

        self.block_btn = QPushButton("✕ Block Tag")
        self.block_btn.setEnabled(False)
        self.block_btn.clicked.connect(self._on_block_tag)
        top_bar.addWidget(self.block_btn)

        self.remove_btn = QPushButton("🗑 Remove")
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._on_remove_tag)
        top_bar.addWidget(self.remove_btn)

        tab_layout.addLayout(top_bar)

        # 5 Columns Area in ScrollArea
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.columns_container = QWidget()
        self.columns_layout = QHBoxLayout(self.columns_container)
        self.columns_layout.setContentsMargins(0, 0, 0, 0)
        self.columns_layout.setSpacing(10)

        scroll_area.setWidget(self.columns_container)
        tab_layout.addWidget(scroll_area, stretch=1)

        # Bottom Card: Alias Management Panel
        self.alias_panel = QFrame()
        self.alias_panel.setObjectName("aliasPanel")
        self.alias_panel.setStyleSheet("""
            #aliasPanel {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        alias_vlayout = QVBoxLayout(self.alias_panel)
        alias_vlayout.setContentsMargins(12, 10, 12, 10)
        alias_vlayout.setSpacing(8)

        self.alias_header = QLabel("Aliases: Select any tag in the columns above to view and manage its aliases")
        self.alias_header.setStyleSheet("color: #8b949e; font-style: italic; font-size: 12px;")
        alias_vlayout.addWidget(self.alias_header)

        # Container for alias chips
        self.aliases_container = QWidget()
        self.aliases_flow = FlowLayout(self.aliases_container, margin=0, spacing=6)
        alias_vlayout.addWidget(self.aliases_container)

        # Controls row for adding / linking aliases
        alias_ctrl_layout = QHBoxLayout()
        alias_ctrl_layout.setSpacing(8)

        self.new_alias_input = QLineEdit()
        self.new_alias_input.setPlaceholderText("Type new alias string to map to this tag (e.g. waist belt)...")
        self.new_alias_input.setEnabled(False)
        self.new_alias_input.returnPressed.connect(self._on_add_alias)
        self.new_alias_input.textChanged.connect(self._update_add_alias_button_text)
        alias_ctrl_layout.addWidget(self.new_alias_input, 1)

        self.add_alias_btn = QPushButton("+ Add Alias")
        self.add_alias_btn.setEnabled(False)
        self.add_alias_btn.setStyleSheet("""
            QPushButton {
                background-color: #23863622;
                color: #3fb950;
                border: 1px solid #2ea043;
                border-radius: 6px;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #238636;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #21262d;
                border-color: #30363d;
                color: #484f58;
            }
        """)
        self.add_alias_btn.clicked.connect(self._on_add_alias)
        alias_ctrl_layout.addWidget(self.add_alias_btn)

        self.link_existing_btn = QPushButton("Select tag to use as Alias...")
        self.link_existing_btn.setEnabled(False)
        self.link_existing_btn.setStyleSheet("""
            QPushButton {
                background-color: #1f6feb22;
                color: #58a6ff;
                border: 1px solid #388bfd;
                border-radius: 6px;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #1f6feb;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #21262d;
                border-color: #30363d;
                color: #484f58;
            }
        """)
        self.link_existing_btn.clicked.connect(self._on_link_existing_tag)
        alias_ctrl_layout.addWidget(self.link_existing_btn)

        self.use_as_alias_btn = QPushButton("Use tag as alias under existing tag...")
        self.use_as_alias_btn.setEnabled(False)
        self.use_as_alias_btn.setStyleSheet("""
            QPushButton {
                background-color: #8957e522;
                color: #d2a8ff;
                border: 1px solid #8957e5;
                border-radius: 6px;
                font-weight: 600;
                padding: 6px 14px;
            }
            QPushButton:hover {
                background-color: #8957e5;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #21262d;
                border-color: #30363d;
                color: #484f58;
            }
        """)
        self.use_as_alias_btn.clicked.connect(self._on_use_as_alias)
        alias_ctrl_layout.addWidget(self.use_as_alias_btn)

        alias_vlayout.addLayout(alias_ctrl_layout)
        tab_layout.addWidget(self.alias_panel)

    def _refresh_columns(self):
        # Clear existing column widgets
        while self.columns_layout.count():
            item = self.columns_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        categories = sorted(self.library.approved.keys())
        search_query = self.search_input.text().strip().lower()

        for category in categories:
            col_frame = QFrame()
            col_frame.setObjectName("colFrame")
            col_frame.setMinimumWidth(220)
            col_frame.setStyleSheet("""
                #colFrame {
                    background-color: #161b22;
                    border: 1px solid #30363d;
                    border-radius: 8px;
                }
            """)
            col_frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            col_frame.customContextMenuRequested.connect(lambda pos, c=category: self._show_category_menu(c, QCursor.pos()))

            col_layout = QVBoxLayout(col_frame)
            col_layout.setContentsMargins(8, 8, 8, 8)
            col_layout.setSpacing(6)

            # Header
            tags_dict = self.library.approved[category]
            matching_tags = [
                t for t in sorted(tags_dict.keys())
                if (self.show_advanced or not self.library.is_advanced(t))
                and (not search_query or search_query in t.lower())
            ]

            header_layout = QHBoxLayout()
            header_layout.setSpacing(4)

            cat_label = QLabel(f"<b>{category}</b> ({len(matching_tags)})")
            cat_label.setStyleSheet("color: #58a6ff; font-size: 13px; background: transparent;")
            cat_label.setToolTip(f"Category: {category}\nRight-click for options")
            header_layout.addWidget(cat_label)

            header_layout.addStretch()

            add_btn = QPushButton("+")
            add_btn.setFixedSize(24, 24)
            add_btn.setToolTip(f"Add tag to {category}")
            add_btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262d;
                    color: #58a6ff;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 0;
                }
                QPushButton:hover {
                    background-color: #1f6feb33;
                    border-color: #58a6ff;
                }
            """)
            add_btn.clicked.connect(lambda _, c=category: self._add_tag_to_category(c))
            header_layout.addWidget(add_btn)

            del_btn = QPushButton("✕")
            del_btn.setFixedSize(24, 24)
            del_btn.setToolTip(f"Delete category '{category}'")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #21262d;
                    color: #8b949e;
                    border: 1px solid #30363d;
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 0;
                }
                QPushButton:hover {
                    background-color: #da363333;
                    color: #f85149;
                    border-color: #da3633;
                }
            """)
            del_btn.clicked.connect(lambda _, c=category: self._remove_category(c))
            header_layout.addWidget(del_btn)

            col_layout.addLayout(header_layout)

            # Tag list for this category
            tag_list = QListWidget()
            tag_list.setStyleSheet("""
                QListWidget::item {
                    padding: 5px 8px;
                    border-radius: 4px;
                    background-color: #21262d;
                    color: #e6edf3;
                    margin: 1px 0px;
                }
                QListWidget::item:hover {
                    background-color: #30363d;
                }
                QListWidget::item:selected {
                    background-color: #1f6feb;
                    color: #ffffff;
                }
            """)

            for t in matching_tags:
                aliases = tags_dict.get(t, [])
                is_adv = self.library.is_advanced(t)
                prefix = "◆ " if is_adv else ""
                display = f"{prefix}{format_tag(t)}" if not aliases else f"{prefix}{format_tag(t)}  ({len(aliases)} aliases)"
                item = QListWidgetItem(display)
                if is_adv:
                    item.setForeground(QBrush(QColor("#f85149")))
                item.setData(Qt.ItemDataRole.UserRole, (t, category))
                tag_list.addItem(item)
                if self.selected_tag == t and self.selected_category == category:
                    tag_list.setCurrentItem(item)

            tag_list.itemClicked.connect(self._on_tag_item_clicked)
            tag_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            tag_list.customContextMenuRequested.connect(
                lambda pos, tl=tag_list: self._show_library_tag_menu(tl, pos)
            )
            col_layout.addWidget(tag_list)

            self.columns_layout.addWidget(col_frame)

        self._refresh_alias_panel()

    def _show_library_tag_menu(self, tag_list: QListWidget, pos: QPoint):
        """Show context menu when right-clicking a tag in the library columns."""
        item = tag_list.itemAt(pos)
        if not item:
            return
        tag_list.setCurrentItem(item)
        self._on_tag_item_clicked(item)
        if not self.selected_tag:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                color: #e6edf3;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)

        make_alias_act = menu.addAction("🔗 Make Alias of Another Tag")
        add_alias_act = menu.addAction("➕ Add Alias to This Tag")
        move_act = menu.addAction("⇄ Move Category")
        is_adv = self.library.is_advanced(self.selected_tag)
        adv_act = menu.addAction("◇ Unmark Advanced" if is_adv else "◆ Mark as Advanced")
        menu.addSeparator()
        block_act = menu.addAction("🚫 Block Tag")
        remove_act = menu.addAction("🗑 Remove Tag")

        action = menu.exec(tag_list.mapToGlobal(pos))
        if not action:
            return

        if action == make_alias_act:
            self._on_make_alias_tag()
        elif action == add_alias_act:
            self._on_add_alias()
        elif action == move_act:
            self._on_move_tag()
        elif action == adv_act:
            self._on_toggle_advanced_tag()
        elif action == block_act:
            self._on_block_tag()
        elif action == remove_act:
            self._on_remove_tag()

    def _on_make_alias_tag(self):
        """Convert the selected approved tag into an alias of another approved tag."""
        if not self.selected_tag:
            return
        dialog = AliasPickerPopup(
            self,
            source_tag=self.selected_tag,
            tag_library=self.library,
            title=f"Make '{format_tag(self.selected_tag)}' an Alias",
            prompt=f"Choose the parent tag that <b>'{format_tag(self.selected_tag)}'</b> should become an alias of:"
        )
        if dialog.exec() and dialog.result_parent_tag:
            target = dialog.result_parent_tag
            if self.library.normalize(target) == self.library.normalize(self.selected_tag):
                return
            # Preserve any existing aliases on the tag being converted
            existing_aliases = list(self.library.approved.get(self.selected_category, {}).get(self.selected_tag, []))
            old_tag = self.selected_tag
            self.library.remove_approved(old_tag)
            self.library.add_alias(target, old_tag)
            for al in existing_aliases:
                self.library.add_alias(target, al)
            self.selected_tag = None
            self.selected_category = None
            self._refresh_columns()
            self.library_updated.emit()

    def set_advanced_visible(self, enabled: bool):
        self.show_advanced = enabled
        self._refresh_columns()

    def _on_toggle_advanced_tag(self):
        if not self.selected_tag:
            return
        new_state = self.library.toggle_advanced(self.selected_tag)
        self.adv_btn.setText("◇ Unmark Advanced" if new_state else "◆ Mark Advanced")
        self._refresh_columns()
        self.library_updated.emit()

    def _on_tag_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.selected_tag, self.selected_category = data
            is_adv = self.library.is_advanced(self.selected_tag)
            adv_badge = " <span style='color:#f85149;'>[◆ Advanced]</span>" if is_adv else ""
            self.selected_label.setText(f"Selected: <b>{format_tag(self.selected_tag)}</b> ({self.selected_category}){adv_badge}")
            self.move_btn.setEnabled(True)
            self.adv_btn.setEnabled(True)
            self.adv_btn.setText("◇ Unmark Advanced" if is_adv else "◆ Mark Advanced")
            self.block_btn.setEnabled(True)
            self.remove_btn.setEnabled(True)
            self._refresh_alias_panel()

    def _refresh_alias_panel(self):
        """Update the alias list and controls for currently selected tag."""
        # Clear existing chips in flow layout
        while self.aliases_flow.count():
            item = self.aliases_flow.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.selected_tag or self.selected_category not in self.library.approved:
            self.alias_header.setText("Aliases: Select any tag in the columns above to view and manage its aliases")
            self.alias_header.setStyleSheet("color: #8b949e; font-style: italic; font-size: 12px; background: transparent;")
            self.new_alias_input.setEnabled(False)
            self._update_add_alias_button_text()
            self.link_existing_btn.setEnabled(False)
            self.link_existing_btn.setText("Select tag to use as Alias...")
            self.link_existing_btn.setToolTip("")
            self.use_as_alias_btn.setEnabled(False)
            self.use_as_alias_btn.setText("Use tag as alias under existing tag...")
            self.use_as_alias_btn.setToolTip("")
            return

        formatted = format_tag(self.selected_tag)
        self.alias_header.setText(f"Aliases for: <b>{formatted}</b> ({self.selected_category})")
        self.alias_header.setStyleSheet("color: #58a6ff; font-weight: bold; font-size: 12px; background: transparent;")
        self.new_alias_input.setEnabled(True)
        self._update_add_alias_button_text()
        self.link_existing_btn.setEnabled(True)
        self.link_existing_btn.setText(f'Select tag to use as Alias under "{formatted}"')
        self.link_existing_btn.setToolTip(f'Convert an existing tag into an alias under "{formatted}"')
        self.use_as_alias_btn.setEnabled(True)
        self.use_as_alias_btn.setText(f'Use "{formatted}" as alias under existing tag')
        self.use_as_alias_btn.setToolTip(f'Convert "{formatted}" into an alias under another approved tag')

        aliases = self.library.get_aliases(self.selected_tag)
        if not aliases:
            empty_lbl = QLabel("(No aliases defined for this tag. Add or link one below)")
            empty_lbl.setStyleSheet("color: #6e7681; font-style: italic; font-size: 11px; background: transparent;")
            self.aliases_flow.addWidget(empty_lbl)
        else:
            for alias in aliases:
                chip = RemovableAliasChip(alias)
                chip.removed.connect(self._on_remove_alias)
                chip.make_tag_requested.connect(self._on_convert_alias_to_tag)
                self.aliases_flow.addWidget(chip)

    def _on_convert_alias_to_tag(self, alias: str, global_pos: QPoint):
        """Convert an alias back into a standalone approved tag in a chosen category."""
        if not self.selected_tag:
            return
        cats = sorted(self.library.approved.keys()) or ["General"]
        # Put current parent tag's category first for convenience
        if self.selected_category in cats:
            cats = [self.selected_category] + [c for c in cats if c != self.selected_category]

        popup = CategoryPickerPopup(
            self,
            alias,
            cats,
            global_pos,
            tag_library=self.library,
            title=f"Convert Alias '{format_tag(alias)}' to Tag"
        )
        if popup.exec() and popup.result_category:
            chosen_cat = popup.result_category
            self.library.remove_alias(self.selected_tag, alias)
            self.library.approve_tag(alias, chosen_cat)
            self._refresh_columns()
            self.library_updated.emit()

    def _update_add_alias_button_text(self):
        """Dynamically update add alias button label based on selected tag and input text."""
        if not self.selected_tag or self.selected_category not in self.library.approved:
            self.add_alias_btn.setEnabled(False)
            self.add_alias_btn.setText("+ Add Alias")
            self.add_alias_btn.setToolTip("")
            return

        self.add_alias_btn.setEnabled(True)
        tag_disp = format_tag(self.selected_tag)
        typed = self.new_alias_input.text().strip()
        if typed:
            self.add_alias_btn.setText(f'Add "{typed}" as an alias under "{tag_disp}"')
            self.add_alias_btn.setToolTip(f'Register "{typed}" as an alias of "{tag_disp}"')
        else:
            self.add_alias_btn.setText(f'+ Add Alias under "{tag_disp}"')
            self.add_alias_btn.setToolTip(f'Type an alias name and click to add under "{tag_disp}"')

    def _on_add_alias(self):
        if not self.selected_tag:
            return
        text = self.new_alias_input.text().strip()
        if not text:
            return
        self.library.add_alias(self.selected_tag, text)
        self.new_alias_input.clear()
        self._refresh_alias_panel()
        self._refresh_columns()
        self.library_updated.emit()

    def _on_remove_alias(self, alias: str):
        if not self.selected_tag:
            return
        self.library.remove_alias(self.selected_tag, alias)
        self._refresh_alias_panel()
        self._refresh_columns()
        self.library_updated.emit()

    def _on_link_existing_tag(self):
        if not self.selected_tag:
            return
        current_tag = self.selected_tag
        formatted = format_tag(current_tag)
        prompt_text = (
            f"Select an existing approved tag to convert into an alias under <b>{formatted}</b>:<br>"
            f"<span style='color: #8b949e; font-size: 11px;'>The selected tag will be converted to an alias and removed from its current category.</span>"
        )
        dialog = AliasPickerPopup(
            self,
            source_tag=current_tag,
            tag_library=self.library,
            title=f"Select tag to use as Alias under '{formatted}'",
            prompt=prompt_text,
            exclude_tags=[current_tag]
        )
        if dialog.exec() and dialog.result_parent_tag:
            chosen_tag = dialog.result_parent_tag
            self.library.add_alias(current_tag, chosen_tag)
            self._refresh_alias_panel()
            self._refresh_columns()
            self.library_updated.emit()
            QMessageBox.information(
                self,
                "Alias Linked",
                f"'{format_tag(chosen_tag)}' is now registered as an alias under '{formatted}'!"
            )

    def _on_use_as_alias(self):
        if not self.selected_tag:
            return
        current_tag = self.selected_tag
        current_cat = self.selected_category
        formatted = format_tag(current_tag)
        prompt_text = (
            f"Select an existing approved tag that <b>{formatted}</b> will become an alias under:<br>"
            f"<span style='color: #8b949e; font-size: 11px;'>'{formatted}' will be removed from '{current_cat}' and become an alias under the chosen tag.</span>"
        )
        dialog = AliasPickerPopup(
            self,
            source_tag=current_tag,
            tag_library=self.library,
            title=f"Use '{formatted}' as Alias under Existing Tag",
            prompt=prompt_text,
            exclude_tags=[current_tag]
        )
        if dialog.exec() and dialog.result_parent_tag:
            parent_tag = dialog.result_parent_tag
            self.library.add_alias(parent_tag, current_tag)

            target_cat = "General"
            for cat, tags in self.library.approved.items():
                if parent_tag in tags:
                    target_cat = cat
                    break

            self.selected_tag = parent_tag
            self.selected_category = target_cat
            self.selected_label.setText(f"Selected: <b>{format_tag(self.selected_tag)}</b> ({self.selected_category})")
            self._refresh_columns()
            self._refresh_alias_panel()
            self.library_updated.emit()
            QMessageBox.information(
                self,
                "Alias Linked",
                f"'{formatted}' is now registered as an alias under '{format_tag(parent_tag)}'!"
            )

    def _clear_search(self):
        """Clear the approved tags search box and return focus."""
        self.search_input.clear()
        self.search_input.setFocus()

    def _clear_blocked_search(self):
        """Clear the blocked tags search box and return focus."""
        self.blocked_search_input.clear()
        self.blocked_search_input.setFocus()

    def _open_add_tag_dialog(self, default_category: str = None):
        """Open the Add New Tag dialog, optionally pre-filled with a category."""
        prefill = ""
        current_search = self.search_input.text().strip()
        if current_search:
            prefill = current_search

        dialog = AddTagDialog(self, self.library, default_category=default_category, prefill_tag=prefill)
        if dialog.exec() and dialog.created_tag:
            self.search_input.clear()
            self.selected_tag = dialog.created_tag
            self.selected_category = dialog.target_category
            self.selected_label.setText(f"Selected: <b>{format_tag(self.selected_tag)}</b> ({self.selected_category})")
            self.move_btn.setEnabled(True)
            self.block_btn.setEnabled(True)
            self.remove_btn.setEnabled(True)
            self._refresh_columns()
            self._refresh_alias_panel()
            self.library_updated.emit()

    def _add_tag_to_category(self, category):
        """Called when clicking the '+' button on a category column header."""
        self._open_add_tag_dialog(default_category=category)

    def _on_move_tag(self):
        if not self.selected_tag:
            return
        tag = self.selected_tag
        old_cat = self.selected_category
        categories = [c for c in sorted(self.library.approved.keys()) if c != old_cat]
        popup = CategoryPickerPopup(self, tag, categories, QCursor.pos())
        if popup.exec() and popup.result_category:
            new_cat = popup.result_category
            self.library.move_tag(tag, new_cat)
            self.selected_category = new_cat
            self.selected_label.setText(f"Selected: <b>{format_tag(self.selected_tag)}</b> ({self.selected_category})")
            self._refresh_columns()
            self._refresh_alias_panel()
            self.library_updated.emit()

    def _on_block_tag(self):
        if not self.selected_tag:
            return
        self.library.block_tag(self.selected_tag)
        self.selected_tag = None
        self.selected_label.setText("No tag selected")
        self.move_btn.setEnabled(False)
        self.block_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self._refresh_columns()
        self._refresh_blocked_list()
        self.library_updated.emit()

    def _on_remove_tag(self):
        if not self.selected_tag:
            return
        self.library.remove_approved(self.selected_tag)
        self.selected_tag = None
        self.selected_label.setText("No tag selected")
        self.move_btn.setEnabled(False)
        self.block_btn.setEnabled(False)
        self.remove_btn.setEnabled(False)
        self._refresh_columns()
        self.library_updated.emit()

    def _on_add_category(self):
        """Prompt to create a new category in the approved library."""
        name, ok = QInputDialog.getText(
            self,
            "Add Category",
            "Enter new category name (e.g. Objects, Lighting, Atmosphere):",
            QLineEdit.EchoMode.Normal,
            ""
        )
        if ok and name:
            cat_name = name.strip()
            if not cat_name:
                return
            existing_lower = [c.lower() for c in self.library.approved.keys()]
            if cat_name.lower() in existing_lower:
                QMessageBox.warning(self, "Category Exists", f"A category named '{cat_name}' already exists.")
                return
            self.library.add_category(cat_name)
            self._refresh_columns()
            self.library_updated.emit()

    def _remove_category(self, category: str):
        """Prompt to confirm and delete a category."""
        tags_count = len(self.library.approved.get(category, {}))
        if tags_count > 0:
            reply = QMessageBox.question(
                self,
                f"Delete Category '{category}'",
                f"Are you sure you want to delete the category <b>'{category}'</b>?<br><br>"
                f"⚠️ This will permanently remove all <b>{tags_count}</b> approved tags "
                f"and their aliases in this category.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
        else:
            reply = QMessageBox.question(
                self,
                f"Delete Category '{category}'",
                f"Are you sure you want to delete the empty category <b>'{category}'</b>?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

        if reply == QMessageBox.StandardButton.Yes:
            if self.selected_category == category:
                self.selected_tag = None
                self.selected_category = None
                self.selected_label.setText("No tag selected")
                self.move_btn.setEnabled(False)
                self.block_btn.setEnabled(False)
                self.remove_btn.setEnabled(False)

            self.library.remove_category(category)
            self._refresh_columns()
            self._refresh_alias_panel()
            self.library_updated.emit()

    def _rename_category(self, category: str):
        """Prompt to rename an existing category."""
        new_name, ok = QInputDialog.getText(
            self,
            f"Rename Category '{category}'",
            "Enter new category name:",
            QLineEdit.EchoMode.Normal,
            category
        )
        if ok and new_name:
            clean_name = new_name.strip()
            if not clean_name or clean_name == category:
                return
            existing_lower = [c.lower() for c in self.library.approved.keys() if c != category]
            if clean_name.lower() in existing_lower:
                QMessageBox.warning(self, "Category Exists", f"A category named '{clean_name}' already exists.")
                return
            if self.library.rename_category(category, clean_name):
                if self.selected_category == category:
                    self.selected_category = clean_name
                    self.selected_label.setText(f"Selected: <b>{format_tag(self.selected_tag)}</b> ({self.selected_category})")
                self._refresh_columns()
                self._refresh_alias_panel()
                self.library_updated.emit()

    def _show_category_menu(self, category: str, global_pos: QPoint):
        """Show context menu for a category column."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                color: #e6edf3;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        add_act = menu.addAction(f"+ Add Tag to '{category}'")
        rename_act = menu.addAction(f"✏️ Rename Category '{category}'...")
        menu.addSeparator()
        del_act = menu.addAction(f"🗑 Delete Category '{category}'")

        action = menu.exec(global_pos)
        if action == add_act:
            self._add_tag_to_category(category)
        elif action == rename_act:
            self._rename_category(category)
        elif action == del_act:
            self._remove_category(category)

    # ── TAB 2: Blocked / Disabled Tags Setup ──────────────────────────────────

    def _init_blocked_tab(self):
        tab_layout = QVBoxLayout(self.tab_blocked)
        tab_layout.setContentsMargins(12, 12, 12, 12)
        tab_layout.setSpacing(10)

        # Top Bar: Search, Stats, Actions
        top_bar = QHBoxLayout()

        self.blocked_search_input = QLineEdit()
        self.blocked_search_input.setPlaceholderText("🔍 Filter blocked / disabled tags...")
        self.blocked_search_input.setMinimumWidth(240)
        self.blocked_search_input.setClearButtonEnabled(True)
        self.blocked_search_input.textChanged.connect(self._refresh_blocked_list)
        top_bar.addWidget(self.blocked_search_input)

        self.clear_blocked_search_btn = QPushButton("✕ Clear")
        self.clear_blocked_search_btn.setToolTip("Clear filter query")
        self.clear_blocked_search_btn.setFixedHeight(30)
        self.clear_blocked_search_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #e6edf3;
            }
        """)
        self.clear_blocked_search_btn.clicked.connect(self._clear_blocked_search)
        top_bar.addWidget(self.clear_blocked_search_btn)

        self.blocked_count_label = QLabel("0 blocked tags")
        self.blocked_count_label.setStyleSheet("color: #da3633; font-weight: 600;")
        top_bar.addWidget(self.blocked_count_label)

        top_bar.addStretch()

        self.new_block_input = QLineEdit()
        self.new_block_input.setPlaceholderText("Tag to block...")
        self.new_block_input.setFixedWidth(180)
        self.new_block_input.returnPressed.connect(self._on_add_blocked_tag)
        top_bar.addWidget(self.new_block_input)

        add_block_btn = QPushButton("+ Block Tag")
        add_block_btn.setStyleSheet("""
            QPushButton {
                background-color: #da363322;
                color: #f85149;
                border: 1px solid #da3633;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #da3633;
                color: #ffffff;
            }
        """)
        add_block_btn.clicked.connect(self._on_add_blocked_tag)
        top_bar.addWidget(add_block_btn)

        self.unblock_btn = QPushButton("✓ Unblock / Enable Tag")
        self.unblock_btn.setEnabled(False)
        self.unblock_btn.setStyleSheet("""
            QPushButton {
                background-color: #23863622;
                color: #3fb950;
                border: 1px solid #2ea043;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #238636;
                color: #ffffff;
            }
            QPushButton:disabled {
                background-color: #21262d;
                border-color: #30363d;
                color: #484f58;
            }
        """)
        self.unblock_btn.clicked.connect(self._on_unblock_selected_tag)
        top_bar.addWidget(self.unblock_btn)

        self.move_to_approved_btn = QPushButton("📁 Move to Category...")
        self.move_to_approved_btn.setEnabled(False)
        self.move_to_approved_btn.clicked.connect(self._on_move_blocked_to_category)
        top_bar.addWidget(self.move_to_approved_btn)

        tab_layout.addLayout(top_bar)

        # Blocked Tags List
        self.blocked_list = QListWidget()
        self.blocked_list.setStyleSheet("""
            QListWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 6px;
            }
            QListWidget::item {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 8px 12px;
                margin: 2px 4px;
                color: #f85149;
                font-family: Consolas;
                font-size: 12px;
            }
            QListWidget::item:hover {
                background-color: #30363d;
                border-color: #da3633;
            }
            QListWidget::item:selected {
                background-color: #da363333;
                border-color: #f85149;
                color: #ffffff;
            }
        """)
        self.blocked_list.itemClicked.connect(self._on_blocked_item_clicked)
        self.blocked_list.itemDoubleClicked.connect(lambda item: self._on_unblock_selected_tag())
        tab_layout.addWidget(self.blocked_list)

        hint_label = QLabel("Tip: Double-click any tag above to quickly unblock it. Blocked tags are automatically suppressed during AI analysis.")
        hint_label.setStyleSheet("color: #8b949e; font-size: 11px; font-style: italic;")
        tab_layout.addWidget(hint_label)

    def _refresh_blocked_list(self):
        """Populate blocked tags list according to search filter."""
        self.blocked_list.clear()
        query = self.blocked_search_input.text().strip().lower()

        all_blocked = sorted(list(self.library.blocked))
        matching = [t for t in all_blocked if not query or query in t.lower()]

        for tag in matching:
            item = QListWidgetItem(f"✕  {format_tag(tag)}")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            self.blocked_list.addItem(item)

        total = len(self.library.blocked)
        if query:
            self.blocked_count_label.setText(f"{len(matching)} of {total} blocked tags")
        else:
            self.blocked_count_label.setText(f"{total} blocked tags")

        self.unblock_btn.setEnabled(False)
        self.move_to_approved_btn.setEnabled(False)

    def _on_blocked_item_clicked(self, item: QListWidgetItem):
        self.unblock_btn.setEnabled(True)
        self.move_to_approved_btn.setEnabled(True)

    def _on_add_blocked_tag(self):
        text = self.new_block_input.text().strip()
        if not text:
            return
        self.library.block_tag(text)
        self.new_block_input.clear()
        self._refresh_blocked_list()
        self._refresh_columns()
        self.library_updated.emit()

    def _on_unblock_selected_tag(self):
        item = self.blocked_list.currentItem()
        if not item:
            return
        tag = item.data(Qt.ItemDataRole.UserRole)
        self.library.unblock_tag(tag)
        self._refresh_blocked_list()
        self._refresh_columns()
        self.library_updated.emit()

    def _on_move_blocked_to_category(self):
        item = self.blocked_list.currentItem()
        if not item:
            return
        tag = item.data(Qt.ItemDataRole.UserRole)
        categories = sorted(self.library.approved.keys()) or ["General"]
        popup = CategoryPickerPopup(self, tag, categories, QCursor.pos())
        if popup.exec() and popup.result_category:
            self.library.approve_tag(tag, popup.result_category)
            self._refresh_blocked_list()
            self._refresh_columns()
            self.library_updated.emit()


# ── Main Application Window ──────────────────────────────────────────────────

class AutoPhotoTaggerApp(QMainWindow):
    """Main PyQt6 Application Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Auto Photo Tagger {APP_BUILD_STRING}")
        if APP_ICON_PNG.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PNG)))
        self.resize(1440, 880)

        # State
        self.config = self._load_config()
        self.image_paths = []
        self.results = {}
        self.processed_tags = {}
        self.edited_tags = {}
        self.skipped_tags = {}
        self.existing_tags = {}
        self.thumbnail_cache = {}
        self.selected_path = None
        self.is_processing = False
        self.show_translated_in_categories = self.config.get("show_translated_in_categories", True)
        self.advanced_tags_enabled = self.config.get("advanced_tags_enabled", True)
        self.always_replace_on_drop = self.config.get("always_replace_on_drop", False)
        self.analyze_on_load = self.config.get("analyze_on_load", False)
        self.setAcceptDrops(True)

        # Thread Pool for thumbnail loading
        self.thread_pool = QThreadPool.globalInstance()
        self.thread_pool.setMaxThreadCount(8)

        # Core Engines
        model_choice = self.config.get("model", DEFAULT_MODEL)
        threshold_val = self.config.get("threshold", 0.35)
        self.engine = TaggerEngine(
            model_key=model_choice,
            general_threshold=threshold_val,
            batch_size=16,
            use_gpu=True,
        )
        self.tag_library = TagLibrary()

        exif_path = self.config.get("exiftool_path")
        try:
            self.metadata_handler = MetadataHandler(exiftool_path=exif_path)
            if self.metadata_handler.exiftool_path and not exif_path:
                self.config["exiftool_path"] = self.metadata_handler.exiftool_path
                self._save_config()
        except Exception:
            self.metadata_handler = None

        # Build UI
        self._init_ui()

        # Load engine in background
        self._init_engine_background()

    def _load_config(self) -> dict:
        defaults = {
            "threshold": 0.35,
            "model": DEFAULT_MODEL,
            "exiftool_path": "",
            "thumbnail_size": 60,
            "show_thumbnails": True,
            "preview_orientation": "vertical",
            "show_translated_in_categories": True,
            "advanced_tags_enabled": True,
            "always_replace_on_drop": False,
            "analyze_on_load": False,
        }
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
            except Exception:
                pass
        return defaults

    def _save_config(self):
        try:
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # ── 1. Top Controls Bar ──────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        # Title / Logo & Build Badge
        logo_container = QWidget()
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 4, 0)
        logo_layout.setSpacing(6)

        if APP_ICON_PNG.exists():
            icon_lbl = QLabel()
            icon_pix = QPixmap(str(APP_ICON_PNG)).scaled(
                22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            icon_lbl.setPixmap(icon_pix)
            logo_layout.addWidget(icon_lbl)
            logo_label = QLabel("<b>Auto Photo Tagger</b>")
        else:
            logo_label = QLabel("⚡ <b>Auto Photo Tagger</b>")

        logo_label.setStyleSheet("font-size: 15px; color: #58a6ff;")
        logo_layout.addWidget(logo_label)

        build_badge = QLabel(APP_BUILD_STRING)
        build_badge.setStyleSheet("""
            QLabel {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 7px;
                font-family: Consolas, monospace;
                font-size: 11px;
                font-weight: 600;
            }
        """)
        build_badge.setToolTip(f"Auto Photo Tagger {APP_BUILD_STRING}")
        logo_layout.addWidget(build_badge)

        top_bar.addWidget(logo_container)

        # Model Selector Dropdown
        top_bar.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        for k, v in AVAILABLE_MODELS.items():
            self.model_combo.addItem(v["name"], k)
        current_idx = self.model_combo.findData(self.engine.model_key)
        if current_idx >= 0:
            self.model_combo.setCurrentIndex(current_idx)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)
        top_bar.addWidget(self.model_combo)

        # Threshold Slider
        top_bar.addWidget(QLabel("Confidence:"))
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(10, 80)
        self.threshold_slider.setValue(int(self.engine.general_threshold * 100))
        self.threshold_slider.setFixedWidth(110)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        top_bar.addWidget(self.threshold_slider)

        self.threshold_label = QLabel(f"{self.engine.general_threshold:.2f}")
        self.threshold_label.setStyleSheet("""
            QLabel {
                background-color: #21262d;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 6px;
                font-family: Consolas, monospace;
                font-weight: bold;
                font-size: 11px;
            }
        """)
        self.threshold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threshold_label.setFixedWidth(42)
        top_bar.addWidget(self.threshold_label)

        # Action Buttons
        self.folder_btn = QPushButton("📁 Select Folder")
        self.folder_btn.clicked.connect(self._select_folder)
        top_bar.addWidget(self.folder_btn)

        self.analyze_btn = QPushButton("⚡ Analyze Batch")
        self.analyze_btn.setProperty("class", "primary")
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.clicked.connect(self._start_batch_analysis)
        top_bar.addWidget(self.analyze_btn)

        top_bar.addStretch()

        # Advanced Tags Global Toggle
        self.advanced_toggle_btn = QPushButton("◆ Advanced: ON" if self.advanced_tags_enabled else "◇ Advanced: OFF")
        self.advanced_toggle_btn.setCheckable(True)
        self.advanced_toggle_btn.setChecked(self.advanced_tags_enabled)
        self.advanced_toggle_btn.setToolTip(
            "Enable or disable Advanced Tags:\n"
            "• ON: Highlighted in violet, shown in Detected Tags & Library, and included when writing\n"
            "• OFF: Hidden from Detected Tags & Library and excluded from writing to images"
        )
        self.advanced_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 5px 11px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: #f85149;
                color: #f85149;
            }
            QPushButton:checked {
                background-color: #da363322;
                color: #f85149;
                border: 1px solid #f85149;
            }
        """)
        self.advanced_toggle_btn.toggled.connect(self._on_advanced_tags_toggled)
        top_bar.addWidget(self.advanced_toggle_btn)

        # View Switcher (Workspace vs Library)
        self.view_btn = QPushButton("📚 Tag Libraries")
        self.view_btn.clicked.connect(self._toggle_view)
        top_bar.addWidget(self.view_btn)

        # Write Tags Button (positioned at far right of top bar)
        self.write_btn = QPushButton("💾 Write Tags to Images")
        self.write_btn.setProperty("class", "accent")
        self.write_btn.setEnabled(False)
        self.write_btn.clicked.connect(self._start_batch_write)
        top_bar.addWidget(self.write_btn)

        main_layout.addLayout(top_bar)

        # ── 2. Central Content Stack (Tagger View vs Library Manager) ─────
        self.content_stack = QStackedWidget()

        # PAGE 0: Tagger Workspace
        self.workspace_widget = QWidget()
        ws_layout = QHBoxLayout(self.workspace_widget)
        ws_layout.setContentsMargins(0, 0, 0, 0)
        ws_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Image List & View Settings
        left_panel = QFrame()
        left_panel.setProperty("class", "panel")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)

        # Row 1: Header (count, select all, clear)
        left_header = QHBoxLayout()
        self.image_count_label = QLabel("No images loaded")
        self.image_count_label.setStyleSheet("font-weight: bold; color: #e6edf3;")
        left_header.addWidget(self.image_count_label)
        left_header.addStretch()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setFixedHeight(26)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #30363d;
                border-color: #58a6ff;
            }
        """)
        self.select_all_btn.clicked.connect(self._toggle_select_all)
        left_header.addWidget(self.select_all_btn)

        self.filter_pending_btn = QPushButton("⚠️ Pending")
        self.filter_pending_btn.setCheckable(True)
        self.filter_pending_btn.setFixedHeight(26)
        self.filter_pending_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #d2992222;
                color: #f0883e;
                border-color: #d29922;
            }
            QPushButton:checked {
                background-color: #d2992233;
                color: #f0883e;
                border: 1px solid #d29922;
                font-weight: bold;
            }
        """)
        self.filter_pending_btn.setToolTip("Filter list to view only images with unapproved pending tags")
        self.filter_pending_btn.toggled.connect(self._toggle_pending_filter)
        left_header.addWidget(self.filter_pending_btn)

        self.filter_advanced_btn = QPushButton("◆ Adv")
        self.filter_advanced_btn.setCheckable(True)
        self.filter_advanced_btn.setFixedHeight(26)
        self.filter_advanced_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #da363322;
                color: #f85149;
                border-color: #f85149;
            }
            QPushButton:checked {
                background-color: #da363333;
                color: #f85149;
                border: 1px solid #f85149;
                font-weight: bold;
            }
        """)
        self.filter_advanced_btn.setToolTip("Filter list to view only images with detected advanced tags")
        self.filter_advanced_btn.toggled.connect(self._toggle_advanced_filter)
        self.filter_advanced_btn.setVisible(self.advanced_tags_enabled)
        left_header.addWidget(self.filter_advanced_btn)

        self.clear_btn = QPushButton("✕ Clear")
        self.clear_btn.setFixedHeight(26)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #8b949e;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #da363322;
                color: #f85149;
                border-color: #da3633;
            }
        """)
        self.clear_btn.clicked.connect(self._clear_images)
        left_header.addWidget(self.clear_btn)

        left_layout.addLayout(left_header)

        # Row 2: View Settings (Thumbnails on/off, Thumbnail Size)
        view_settings_layout = QHBoxLayout()
        view_settings_layout.setContentsMargins(0, 0, 0, 0)
        view_settings_layout.setSpacing(8)

        self.thumb_toggle = QCheckBox("Thumbnails")
        self.thumb_toggle.setChecked(self.config.get("show_thumbnails", True))
        self.thumb_toggle.toggled.connect(self._apply_thumbnail_settings)
        view_settings_layout.addWidget(self.thumb_toggle)

        view_settings_layout.addSpacing(6)
        size_lbl = QLabel("Size:")
        size_lbl.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
        view_settings_layout.addWidget(size_lbl)

        self.thumb_size_combo = QComboBox()
        self.thumb_size_combo.setFixedHeight(26)
        self.thumb_size_combo.setStyleSheet("QComboBox { padding: 2px 8px; font-size: 11px; min-height: 22px; }")
        self.thumb_size_combo.addItem("36px (Compact)", 36)
        self.thumb_size_combo.addItem("48px (Small)", 48)
        self.thumb_size_combo.addItem("60px (Default)", 60)
        self.thumb_size_combo.addItem("80px (Medium)", 80)
        self.thumb_size_combo.addItem("100px (Large)", 100)
        self.thumb_size_combo.addItem("128px (Extra Large)", 128)

        saved_size = self.config.get("thumbnail_size", 60)
        idx = self.thumb_size_combo.findData(saved_size)
        if idx >= 0:
            self.thumb_size_combo.setCurrentIndex(idx)
        else:
            self.thumb_size_combo.setCurrentIndex(2)

        self.thumb_size_combo.currentIndexChanged.connect(self._apply_thumbnail_settings)
        view_settings_layout.addWidget(self.thumb_size_combo)
        view_settings_layout.addStretch()

        left_layout.addLayout(view_settings_layout)

        # Row 3: Streamlined Load / Drop Toggles (Always Replace, Analyze on Load)
        drop_options_layout = QHBoxLayout()
        drop_options_layout.setContentsMargins(0, 0, 0, 0)
        drop_options_layout.setSpacing(12)

        self.always_replace_chk = QCheckBox("Always Replace")
        self.always_replace_chk.setChecked(self.always_replace_on_drop)
        self.always_replace_chk.setToolTip(
            "When dropping images onto an existing list, automatically replace\n"
            "the list without asking whether to replace or append."
        )
        self.always_replace_chk.toggled.connect(self._on_always_replace_toggled)
        drop_options_layout.addWidget(self.always_replace_chk)

        self.analyze_on_load_chk = QCheckBox("Analyze on Load")
        self.analyze_on_load_chk.setChecked(self.analyze_on_load)
        self.analyze_on_load_chk.setToolTip(
            "Automatically run AI tag analysis immediately after images\n"
            "are dropped or loaded from a folder."
        )
        self.analyze_on_load_chk.toggled.connect(self._on_analyze_on_load_toggled)
        drop_options_layout.addWidget(self.analyze_on_load_chk)

        drop_options_layout.addStretch()
        left_layout.addLayout(drop_options_layout)

        self.image_list = DropListWidget()
        self.image_list.setIconSize(QSize(saved_size, saved_size) if self.thumb_toggle.isChecked() else QSize(0, 0))
        self.image_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.image_list.itemClicked.connect(self._on_image_selected)
        self.image_list.currentItemChanged.connect(self._on_current_item_changed)
        self.image_list.files_dropped.connect(self._handle_dropped_paths)
        left_layout.addWidget(self.image_list)

        splitter.addWidget(left_panel)

        # Right Panel: Image Preview & Tag Editor with resizable drag divider
        right_panel = QFrame()
        right_panel.setProperty("class", "panel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(6)

        saved_orient_str = self.config.get("preview_orientation", "vertical")
        initial_orient = Qt.Orientation.Horizontal if saved_orient_str == "horizontal" else Qt.Orientation.Vertical
        self.editor_splitter = QSplitter(initial_orient)
        self.editor_splitter.setChildrenCollapsible(False)
        self.editor_splitter.splitterMoved.connect(lambda: self.preview_widget._update_scaled_pixmap())

        # ── 1. Preview Container ─────────────────────────────────────
        self.preview_container = QWidget()
        prev_container_layout = QVBoxLayout(self.preview_container)
        prev_container_layout.setContentsMargins(0, 0, 0, 0)
        prev_container_layout.setSpacing(6)

        prev_header = QHBoxLayout()
        prev_header.setContentsMargins(0, 0, 10, 4)
        prev_title = QLabel("<b>Image Preview</b>")
        prev_title.setStyleSheet("color: #e6edf3; font-size: 13px; background: transparent;")
        prev_header.addWidget(prev_title)

        prev_header.addStretch()
        self.quick_analyze_btn = QPushButton("⚡ Analyze Current Image")
        self.quick_analyze_btn.setFixedHeight(26)
        self.quick_analyze_btn.setToolTip("Analyze tags for only the currently viewed image")
        self.quick_analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #ffffff;
                border: 1px solid #2ea043;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2ea043; }
            QPushButton:disabled { background-color: #21262d; color: #484f58; border-color: #30363d; }
        """)
        self.quick_analyze_btn.setEnabled(False)
        self.quick_analyze_btn.clicked.connect(self._start_single_analysis)
        prev_header.addWidget(self.quick_analyze_btn)

        prev_header.addSpacing(6)

        self.layout_toggle_btn = QPushButton(
            "⬍ Top/Bottom View" if initial_orient == Qt.Orientation.Horizontal else "⬄ Side-by-Side View"
        )
        self.layout_toggle_btn.setFixedHeight(26)
        self.layout_toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #e6edf3;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                border-color: #58a6ff;
                background-color: #30363d;
            }
        """)
        self.layout_toggle_btn.clicked.connect(self._toggle_editor_layout)
        prev_header.addWidget(self.layout_toggle_btn)
        prev_container_layout.addLayout(prev_header)

        self.preview_widget = ImagePreviewWidget()
        self.preview_widget.files_dropped.connect(self._handle_dropped_paths)
        prev_container_layout.addWidget(self.preview_widget)

        self.editor_splitter.addWidget(self.preview_container)

        # ── 2. Tag Editor Container ──────────────────────────────────
        self.tag_editor_container = QWidget()
        tag_edit_layout = QVBoxLayout(self.tag_editor_container)
        tag_edit_layout.setContentsMargins(12, 0, 8, 0)
        tag_edit_layout.setSpacing(6)

        # Tag Section Header (Row 1: Title and Toggle - aligned with Image Preview header)
        header_top_row = QHBoxLayout()
        header_top_row.setContentsMargins(0, 0, 0, 4)
        tag_title = QLabel("<b>Detected Tags</b>")
        tag_title.setStyleSheet("font-size: 13px; color: #e6edf3; background: transparent;")
        header_top_row.addWidget(tag_title)

        header_top_row.addSpacing(14)

        self.trans_in_cat_toggle = QCheckBox("Show Translated in Categories")
        self.trans_in_cat_toggle.setFixedHeight(26)
        self.trans_in_cat_toggle.setToolTip(
            "Toggle display of translated/alias tags:\n"
            "• Checked: Show translated tags (orig → final) inline inside their categories\n"
            "• Unchecked: Show final tags inside categories, and list translations (orig → final) separately below"
        )
        self.trans_in_cat_toggle.setChecked(self.show_translated_in_categories)
        self.trans_in_cat_toggle.toggled.connect(self._on_translated_view_toggled)
        header_top_row.addWidget(self.trans_in_cat_toggle)

        header_top_row.addStretch()

        size_lbl = QLabel("Tag Size:")
        size_lbl.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
        header_top_row.addWidget(size_lbl)

        self.tag_size_combo = QComboBox()
        self.tag_size_combo.setFixedHeight(26)
        self.tag_size_combo.setStyleSheet("QComboBox { padding: 2px 8px; font-size: 11px; min-height: 22px; }")
        self.tag_size_combo.addItem("Small (10px)", "small")
        self.tag_size_combo.addItem("Default (11px)", "default")
        self.tag_size_combo.addItem("Large (13px)", "large")
        self.tag_size_combo.addItem("Extra Large (15px)", "xlarge")

        saved_tag_size = self.config.get("tag_chip_size", "default")
        idx = self.tag_size_combo.findData(saved_tag_size)
        if idx >= 0:
            self.tag_size_combo.setCurrentIndex(idx)
        else:
            self.tag_size_combo.setCurrentIndex(1)

        TagChip.current_size = saved_tag_size
        self.tag_size_combo.currentIndexChanged.connect(self._on_tag_size_changed)
        header_top_row.addWidget(self.tag_size_combo)

        tag_edit_layout.addLayout(header_top_row)

        # Row 2: Legend Bar (Clean pill bar, proper spacing, no overlapping)
        legend_frame = QFrame()
        legend_frame.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #21262d;
                border-radius: 6px;
                padding: 3px 8px;
            }
        """)
        legend_layout = QHBoxLayout(legend_frame)
        legend_layout.setContentsMargins(6, 2, 6, 2)
        legend_layout.setSpacing(12)

        legend_label = QLabel(
            "<span style='color:#38bdf8;'>● Existing / Match</span> &nbsp;&nbsp; "
            "<span style='color:#3fb950;'>● Approved (New)</span> &nbsp;&nbsp; "
            "<span style='color:#58a6ff;'>● Translated</span> &nbsp;&nbsp; "
            "<span style='color:#f85149;'>◆ Advanced</span> &nbsp;&nbsp; "
            "<span style='color:#f0883e;'>● Pending</span> &nbsp;&nbsp; "
            "<span style='color:#8b949e; text-decoration:line-through;'>● Skipped</span>"
        )
        legend_label.setStyleSheet("font-size: 11px; background: transparent;")
        legend_layout.addWidget(legend_label)
        legend_layout.addStretch()

        tag_edit_layout.addWidget(legend_frame)

        # Row 3: Rating / Caption Banner Card (Clean card with padding, only visible when ratings/caption exist)
        self.rating_card = QFrame()
        self.rating_card.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 1px solid #21262d;
                border-radius: 6px;
            }
        """)
        rating_card_layout = QHBoxLayout(self.rating_card)
        rating_card_layout.setContentsMargins(10, 5, 10, 5)
        rating_card_layout.setSpacing(6)

        self.rating_label = QLabel("")
        self.rating_label.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
        self.rating_label.setWordWrap(True)
        rating_card_layout.addWidget(self.rating_label)

        self.rating_card.setVisible(False)
        tag_edit_layout.addWidget(self.rating_card)

        # Row 4: Tags Container (Scrollable)
        tags_scroll = QScrollArea()
        tags_scroll.setWidgetResizable(True)
        tags_scroll.setFrameShape(QFrame.Shape.NoFrame)
        tags_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.tags_container = QWidget()
        self.tags_vlayout = QVBoxLayout(self.tags_container)
        self.tags_vlayout.setContentsMargins(4, 4, 4, 4)
        self.tags_vlayout.setSpacing(8)

        tags_scroll.setWidget(self.tags_container)

        # ── Existing Tags Card (Interactive Chips - Resizable) ─────────
        self.existing_tags_card = QFrame()
        self.existing_tags_card.setObjectName("existingTagsCard")
        self.existing_tags_card.setMinimumHeight(65)
        self.existing_tags_card.setStyleSheet("""
            #existingTagsCard {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
        """)
        ex_vlayout = QVBoxLayout(self.existing_tags_card)
        ex_vlayout.setContentsMargins(10, 8, 10, 8)
        ex_vlayout.setSpacing(6)

        # Header with title, count, and action buttons
        ex_header = QHBoxLayout()
        ex_header.setSpacing(8)

        ex_title = QLabel("<b>📁 Existing Image Tags</b>")
        ex_title.setStyleSheet("color: #38bdf8; font-size: 12px; background: transparent;")
        ex_header.addWidget(ex_title)

        self.existing_count_lbl = QLabel("")
        self.existing_count_lbl.setStyleSheet("color: #8b949e; font-size: 11px; background: transparent;")
        ex_header.addWidget(self.existing_count_lbl)

        ex_header.addStretch()

        self.clear_existing_btn = QPushButton("✕ Clear All")
        self.clear_existing_btn.setToolTip("Grey out all existing tags (will be removed when writing to image)")
        self.clear_existing_btn.setFixedHeight(24)
        self.clear_existing_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #f85149;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #da363322;
                border-color: #f85149;
            }
            QPushButton:disabled {
                color: #484f58;
                border-color: #21262d;
                background-color: transparent;
            }
        """)
        self.clear_existing_btn.clicked.connect(self._clear_all_existing_tags)
        ex_header.addWidget(self.clear_existing_btn)

        self.restore_existing_btn = QPushButton("↺ Restore All")
        self.restore_existing_btn.setToolTip("Restore all greyed-out existing tags")
        self.restore_existing_btn.setFixedHeight(24)
        self.restore_existing_btn.setStyleSheet("""
            QPushButton {
                background-color: #21262d;
                color: #58a6ff;
                border: 1px solid #30363d;
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1f6feb22;
                border-color: #58a6ff;
            }
            QPushButton:disabled {
                color: #484f58;
                border-color: #21262d;
                background-color: transparent;
            }
        """)
        self.restore_existing_btn.clicked.connect(self._restore_all_existing_tags)
        ex_header.addWidget(self.restore_existing_btn)

        ex_vlayout.addLayout(ex_header)

        # Scrollable flow area for existing tag chips
        self.existing_scroll = QScrollArea()
        self.existing_scroll.setWidgetResizable(True)
        self.existing_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.existing_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.existing_scroll.setMinimumHeight(32)
        self.existing_scroll.setStyleSheet("background: transparent; border: none;")

        self.existing_chips_container = FlowContainer(margin=2, spacing=4)
        self.existing_chips_container.setStyleSheet("background: transparent;")
        self.existing_flow = self.existing_chips_container.flow

        self.existing_scroll.setWidget(self.existing_chips_container)
        ex_vlayout.addWidget(self.existing_scroll)

        # Vertical Splitter between Detected Tags scroll area and Existing Tags card
        self.tags_existing_splitter = QSplitter(Qt.Orientation.Vertical)
        self.tags_existing_splitter.setChildrenCollapsible(False)
        self.tags_existing_splitter.addWidget(tags_scroll)
        self.tags_existing_splitter.addWidget(self.existing_tags_card)
        self.tags_existing_splitter.setStretchFactor(0, 4)
        self.tags_existing_splitter.setStretchFactor(1, 1)
        self.tags_existing_splitter.setSizes([450, 110])

        tag_edit_layout.addWidget(self.tags_existing_splitter, stretch=1)

        self.editor_splitter.addWidget(self.tag_editor_container)

        if initial_orient == Qt.Orientation.Horizontal:
            self.editor_splitter.setSizes([450, 550])
        else:
            self.editor_splitter.setSizes([280, 420])

        right_layout.addWidget(self.editor_splitter)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)

        ws_layout.addWidget(splitter)
        self.content_stack.addWidget(self.workspace_widget)

        # PAGE 1: Library Manager (5-Column)
        self.library_manager = LibraryManagerWidget(self.tag_library)
        self.library_manager.set_advanced_visible(self.advanced_tags_enabled)
        self.library_manager.library_updated.connect(self._on_library_modified)
        self.content_stack.addWidget(self.library_manager)

        main_layout.addWidget(self.content_stack)

        # ── 3. Footer Progress & Status ──────────────────────────────────
        footer = QHBoxLayout()
        footer.setContentsMargins(12, 6, 12, 6)
        footer.setSpacing(8)
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #8b949e; font-size: 12px; background: transparent; padding: 2px 4px;")
        footer.addWidget(self.status_label)

        footer.addStretch()

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setVisible(False)
        footer.addWidget(self.progress_bar)

        footer.addSpacing(6)

        # ExifTool Status Button / Badge (bottom right)
        self.exif_btn = QPushButton("ExifTool...")
        self.exif_btn.setFixedHeight(24)
        self.exif_btn.clicked.connect(lambda: self._setup_exiftool(then_write=False))
        footer.addWidget(self.exif_btn)

        footer.addSpacing(4)

        # Device Badge (bottom right)
        self.device_badge = QLabel("Detecting...")
        self.device_badge.setFixedHeight(24)
        self.device_badge.setStyleSheet("""
            background-color: #21262d;
            color: #8b949e;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 3px 10px;
            font-weight: 600;
            font-size: 11px;
        """)
        footer.addWidget(self.device_badge)
        self._update_exif_badge()

        main_layout.addLayout(footer)

    # ── Background Initialization ────────────────────────────────────────────

    def _init_engine_background(self):
        """Load engine without blocking UI."""
        class InitWorker(QThread):
            loaded = pyqtSignal(str)
            failed = pyqtSignal(str)

            def __init__(self, engine):
                super().__init__()
                self.engine = engine

            def run(self):
                try:
                    self.engine.load_model()
                    self.loaded.emit(self.engine.provider_info)
                except Exception as e:
                    self.failed.emit(str(e))

        self.init_thread = InitWorker(self.engine)
        self.init_thread.loaded.connect(self._on_engine_loaded)
        self.init_thread.failed.connect(lambda err: self.device_badge.setText(f"Error: {err}"))
        self.init_thread.start()

    def _on_engine_loaded(self, provider):
        is_gpu = "cpu" not in provider.lower()
        if is_gpu:
            icon = "⚡"
            self.device_badge.setStyleSheet("""
                background-color: #23863622;
                color: #3fb950;
                border: 1px solid #2ea043;
                border-radius: 6px;
                padding: 3px 10px;
                font-weight: 600;
                font-size: 11px;
            """)
        else:
            icon = "💻"
            self.device_badge.setStyleSheet("""
                background-color: #388bfd1a;
                color: #58a6ff;
                border: 1px solid #388bfd;
                border-radius: 6px;
                padding: 3px 10px;
                font-weight: 600;
                font-size: 11px;
            """)
        self.device_badge.setText(f"{icon} {provider}")
        self.device_badge.setToolTip(f"Active Inference Provider: {provider}")
        exif_status = "ExifTool ✓" if self.metadata_handler else "ExifTool ✕"
        self.status_label.setText(f"Ready — {provider} | {exif_status}")
        self.setWindowTitle(f"Auto Photo Tagger {APP_BUILD_STRING} — {provider}")
        self._update_exif_badge()

    def _update_exif_badge(self):
        """Update ExifTool status badge in footer status bar."""
        if self.metadata_handler:
            self.exif_btn.setText("ExifTool ✓")
            self.exif_btn.setStyleSheet("""
                QPushButton {
                    background-color: #23863622;
                    color: #3fb950;
                    border: 1px solid #2ea043;
                    border-radius: 6px;
                    padding: 3px 10px;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #23863644; }
            """)
            self.exif_btn.setToolTip(f"ExifTool active: {self.metadata_handler.exiftool_path}\nClick to change location or update.")
        else:
            self.exif_btn.setText("ExifTool ✕")
            self.exif_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d2992222;
                    color: #f0883e;
                    border: 1px solid #d29922;
                    border-radius: 6px;
                    padding: 3px 10px;
                    font-weight: 600;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: #d2992244; }
            """)
            self.exif_btn.setToolTip("ExifTool not detected. Click to locate existing or download.")

    def _setup_exiftool(self, then_write: bool = False) -> bool:
        """Prompt to locate or download ExifTool."""
        dialog = ExifToolSetupDialog(self, current_path=self.config.get("exiftool_path"))
        if dialog.exec() and dialog.configured_path:
            path = dialog.configured_path
            self.config["exiftool_path"] = path
            self._save_config()
            try:
                if self.metadata_handler:
                    self.metadata_handler.close()
                self.metadata_handler = MetadataHandler(exiftool_path=path)
                self._update_exif_badge()
                self.status_label.setText(f"ExifTool configured: {path} ✓")

                # If images loaded and haven't read existing tags yet, read them now
                if self.image_paths and not self.existing_tags:
                    def on_meta(meta):
                        self.existing_tags = meta
                        self._update_existing_tags_display()

                    self.meta_reader = MetaReadWorker(self.metadata_handler, self.image_paths)
                    self.meta_reader.finished.connect(on_meta)
                    self.meta_reader.start()

                if then_write:
                    self._start_batch_write()
                return True
            except Exception as e:
                QMessageBox.critical(self, "ExifTool Error", f"Failed to initialize ExifTool:\n\n{e}")
                self._update_exif_badge()
                return False
        return False

    # ── View & Model Controls ────────────────────────────────────────────────

    def _toggle_view(self):
        if self.content_stack.currentIndex() == 0:
            self.content_stack.setCurrentIndex(1)
            self.view_btn.setText("🏷️ Tagger Workspace")
            self.library_manager.refresh()
        else:
            self.content_stack.setCurrentIndex(0)
            self.view_btn.setText("📚 Tag Libraries")

    def _on_model_changed(self):
        new_key = self.model_combo.currentData()
        if not new_key or new_key == self.engine.model_key:
            return

        cfg = AVAILABLE_MODELS.get(new_key)
        if not cfg:
            return

        # Check if the model is installed on disk
        if not self.engine.is_model_installed(new_key):
            file_size_str = "~380 MB"
            reply = QMessageBox.question(
                self,
                "Model Not Installed",
                f"The model '{cfg['name']}' is not currently downloaded.\n\n"
                f"Would you like to download and install this model now?\n"
                f"(File size: {file_size_str} from HuggingFace)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )

            if reply != QMessageBox.StandardButton.Yes:
                # User cancelled -> revert combo box selection back to active model
                self.model_combo.blockSignals(True)
                prev_idx = self.model_combo.findData(self.engine.model_key)
                if prev_idx >= 0:
                    self.model_combo.setCurrentIndex(prev_idx)
                self.model_combo.blockSignals(False)
                self.status_label.setText(f"Model switch cancelled. Keeping {AVAILABLE_MODELS[self.engine.model_key]['name']}.")
                return

        # User confirmed or model already exists -> proceed with switch
        prev_key = self.engine.model_key
        self.model_combo.setEnabled(False)
        self.analyze_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # indeterminate busy mode
        self.status_label.setText(f"Loading {cfg['name']}...")

        class SwitchWorker(QThread):
            progress = pyqtSignal(str)
            done = pyqtSignal()
            failed = pyqtSignal(str)

            def __init__(self, engine, key):
                super().__init__()
                self.engine = engine
                self.key = key

            def run(self):
                try:
                    def cb(msg):
                        self.progress.emit(msg)
                    self.engine.switch_model(self.key, progress_callback=cb)
                    self.done.emit()
                except Exception as e:
                    self.failed.emit(str(e))

        self.switch_worker = SwitchWorker(self.engine, new_key)
        self.switch_worker.progress.connect(lambda msg: self.status_label.setText(msg))

        def on_done():
            self.model_combo.setEnabled(True)
            self.analyze_btn.setEnabled(len(self.image_paths) > 0)
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"Active model: {AVAILABLE_MODELS[new_key]['name']} ✓")
            self.config["model"] = new_key
            self._save_config()

        def on_failed(err):
            self.model_combo.setEnabled(True)
            self.analyze_btn.setEnabled(len(self.image_paths) > 0)
            self.progress_bar.setVisible(False)
            # Revert combo box to previous working model
            self.model_combo.blockSignals(True)
            prev_idx = self.model_combo.findData(prev_key)
            if prev_idx >= 0:
                self.model_combo.setCurrentIndex(prev_idx)
            self.model_combo.blockSignals(False)
            self.status_label.setText(f"Failed to switch model: {err}")
            QMessageBox.critical(self, "Model Installation Error", f"Failed to download or load model '{cfg['name']}':\n\n{err}")

        self.switch_worker.done.connect(on_done)
        self.switch_worker.failed.connect(on_failed)
        self.switch_worker.start()

    def _on_threshold_changed(self, val):
        flt = val / 100.0
        self.engine.general_threshold = flt
        self.threshold_label.setText(f"{flt:.2f}")
        self.config["threshold"] = flt
        self._save_config()

    def _on_tag_size_changed(self):
        new_size = self.tag_size_combo.currentData() or "default"
        TagChip.current_size = new_size
        self.config["tag_chip_size"] = new_size
        self._save_config()
        if self.selected_path:
            self._refresh_tag_display(self.selected_path)
            self._update_existing_tags_display()

    # ── Drag & Drop Event Handlers ───────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                self._handle_dropped_paths(paths)
            event.acceptProposedAction()

    def _on_always_replace_toggled(self, checked: bool):
        self.always_replace_on_drop = checked
        self.config["always_replace_on_drop"] = checked
        self._save_config()

    def _on_analyze_on_load_toggled(self, checked: bool):
        self.analyze_on_load = checked
        self.config["analyze_on_load"] = checked
        self._save_config()

    def _handle_dropped_paths(self, paths: list):
        """Process dropped image files or folders."""
        extracted = extract_images_from_paths(paths)
        if not extracted:
            QMessageBox.information(
                self, "No Images Found",
                "No supported images (.jpg, .png, .webp, .bmp, .tif, .gif) found in the dropped items."
            )
            return

        if not self.image_paths or getattr(self, "always_replace_on_drop", False):
            self._load_image_paths(extracted, source_label=f"{len(extracted)} dropped images")
        else:
            # Prompt user to replace or append
            msg = QMessageBox(self)
            msg.setWindowTitle("Load Dropped Images")
            msg.setText(f"You dropped {len(extracted)} image(s).\nHow would you like to load them?")
            replace_btn = msg.addButton("Replace Current List", QMessageBox.ButtonRole.AcceptRole)
            append_btn = msg.addButton("Add to Existing List", QMessageBox.ButtonRole.ActionRole)
            cancel_btn = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            msg.setDefaultButton(replace_btn)
            msg.exec()

            if msg.clickedButton() == replace_btn:
                self._load_image_paths(extracted, source_label=f"{len(extracted)} dropped images")
            elif msg.clickedButton() == append_btn:
                self._append_image_paths(extracted)

    # ── Folder & Image Loading ───────────────────────────────────────────────

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            images = find_images_in_folder(folder)
            if not images:
                QMessageBox.information(self, "No Images", "No supported image files found in folder.")
                return
            self._load_image_paths(images, source_label=Path(folder).name)

    def _load_folder(self, folder_path: str):
        images = find_images_in_folder(folder_path)
        if not images:
            QMessageBox.information(self, "No Images", "No supported image files found in folder.")
            return
        self._load_image_paths(images, source_label=Path(folder_path).name)

    def _load_image_paths(self, image_paths: list, source_label: str = "Folder"):
        self.image_paths = list(image_paths)
        self.image_list.clear()
        self.results.clear()
        self.processed_tags.clear()
        self.edited_tags.clear()
        self.skipped_tags.clear()
        self.existing_tags.clear()
        self.thumbnail_cache.clear()
        self.selected_path = None

        count = len(self.image_paths)
        self.image_count_label.setText(f"{count} images")
        self.status_label.setText(f"Loaded {count} images from {source_label}. Ready to Analyze.")
        self.analyze_btn.setEnabled(True)
        self.write_btn.setEnabled(False)

        # Batch-read existing metadata tags in background
        if self.metadata_handler:
            def on_meta(meta):
                self.existing_tags = meta
                self._update_existing_tags_display()
                if self.selected_path:
                    self._refresh_tag_display(self.selected_path)
                self._check_write_button_state()

            self.meta_reader = MetaReadWorker(self.metadata_handler, self.image_paths)
            self.meta_reader.finished.connect(on_meta)
            self.meta_reader.start()

        # Add items to virtualized list and launch async thumbnail rendering
        show_thumbs = self.thumb_toggle.isChecked()
        size = self.thumb_size_combo.currentData() or 60
        self.image_list.setIconSize(QSize(size, size) if show_thumbs else QSize(0, 0))

        for p in self.image_paths:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setCheckState(Qt.CheckState.Checked)
            self._update_image_list_item(item, p)
            self.image_list.addItem(item)

            thumb_task = ThumbnailRunnable(p, size=128)
            thumb_task.signals.loaded.connect(self._on_thumbnail_ready)
            self.thread_pool.start(thumb_task)

        if hasattr(self, "filter_pending_btn"):
            self.filter_pending_btn.setChecked(False)
            self.filter_pending_btn.setText("⚠️ Pending")
            self.filter_pending_btn.setEnabled(True)

        if self.image_paths:
            self.image_list.setCurrentRow(0)
            self._select_image(self.image_paths[0])
            if getattr(self, "analyze_on_load", False) and not self.is_processing:
                self._run_analysis_on_paths(list(self.image_paths))

    def _append_image_paths(self, new_paths: list):
        """Append new image paths to the existing list."""
        existing_set = set(self.image_paths)
        to_add = [p for p in new_paths if p not in existing_set]
        if not to_add:
            QMessageBox.information(self, "No New Images", "All dropped images are already in the list.")
            return

        self.image_paths.extend(to_add)
        count = len(self.image_paths)
        self.image_count_label.setText(f"{count} images")
        self.status_label.setText(f"Added {len(to_add)} images (total {count}).")
        self.analyze_btn.setEnabled(True)

        for p in to_add:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, p)
            item.setCheckState(Qt.CheckState.Checked)
            self._update_image_list_item(item, p)
            self.image_list.addItem(item)

            thumb_task = ThumbnailRunnable(p, size=128)
            thumb_task.signals.loaded.connect(self._on_thumbnail_ready)
            self.thread_pool.start(thumb_task)

        if hasattr(self, "filter_pending_btn"):
            self.filter_pending_btn.setEnabled(True)

        if self.metadata_handler:
            def on_meta_add(meta):
                self.existing_tags.update(meta)
                self._update_existing_tags_display()
                if self.selected_path:
                    self._refresh_tag_display(self.selected_path)
                self._check_write_button_state()

            self.meta_add_reader = MetaReadWorker(self.metadata_handler, to_add)
            self.meta_add_reader.finished.connect(on_meta_add)
            self.meta_add_reader.start()

        if self.selected_path is None and self.image_paths:
            self.image_list.setCurrentRow(0)
            self._select_image(self.image_paths[0])

        if getattr(self, "analyze_on_load", False) and not self.is_processing and to_add:
            self._run_analysis_on_paths(list(to_add))

    def _clear_images(self):
        """Clear all loaded images and reset tag views."""
        self.image_paths.clear()
        self.image_list.clear()
        self.results.clear()
        self.processed_tags.clear()
        self.edited_tags.clear()
        self.skipped_tags.clear()
        self.existing_tags.clear()
        self.thumbnail_cache.clear()
        self.selected_path = None
        self.preview_widget.set_image(None)
        self.image_count_label.setText("No images loaded")
        self.status_label.setText("Ready")
        self.analyze_btn.setEnabled(False)
        self.quick_analyze_btn.setEnabled(False)
        self.write_btn.setEnabled(False)
        self.rating_label.setText("")
        self.rating_card.setVisible(False)
        self._update_existing_tags_display()

        if hasattr(self, "filter_pending_btn"):
            self.filter_pending_btn.setChecked(False)
            self.filter_pending_btn.setText("⚠️ Pending")
            self.filter_pending_btn.setEnabled(False)

        while self.tags_vlayout.count():
            item = self.tags_vlayout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    # ── View Settings & Orientation ──────────────────────────────────────────

    def _apply_thumbnail_settings(self):
        """Toggle thumbnails on/off or change thumbnail icon size."""
        show = self.thumb_toggle.isChecked()
        size = self.thumb_size_combo.currentData() or 60
        self.thumb_size_combo.setEnabled(show)
        self.image_list.setIconSize(QSize(size, size) if show else QSize(0, 0))

        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            p = item.data(Qt.ItemDataRole.UserRole)
            if show and p in self.thumbnail_cache:
                scaled = self.thumbnail_cache[p].scaled(
                    QSize(size, size),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                item.setIcon(QIcon(scaled))
            else:
                item.setIcon(QIcon())

        self.config["show_thumbnails"] = show
        self.config["thumbnail_size"] = size
        self._save_config()

    def _toggle_editor_layout(self):
        """Toggle preview layout between Top/Bottom and Side-by-Side."""
        if self.editor_splitter.orientation() == Qt.Orientation.Vertical:
            self.editor_splitter.setOrientation(Qt.Orientation.Horizontal)
            self.layout_toggle_btn.setText("⬍ Top/Bottom View")
            self.config["preview_orientation"] = "horizontal"
            w = max(self.editor_splitter.width(), 600)
            self.editor_splitter.setSizes([int(w * 0.45), int(w * 0.55)])
        else:
            self.editor_splitter.setOrientation(Qt.Orientation.Vertical)
            self.layout_toggle_btn.setText("⬄ Side-by-Side View")
            self.config["preview_orientation"] = "vertical"
            h = max(self.editor_splitter.height(), 500)
            self.editor_splitter.setSizes([int(h * 0.38), int(h * 0.62)])
        self._save_config()
        self.preview_widget._update_scaled_pixmap()

    def _on_thumbnail_ready(self, path: str, pixmap: QPixmap):
        self.thumbnail_cache[path] = pixmap
        if not self.thumb_toggle.isChecked():
            return
        size = self.thumb_size_combo.currentData() or 60
        scaled = pixmap.scaled(
            QSize(size, size),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                item.setIcon(QIcon(scaled))
                break

    def _update_image_list_item(self, item: QListWidgetItem, path: str):
        """Update a list item's text, prefix badge, color, and background based on tag status."""
        fname = Path(path).name
        proc = self.processed_tags.get(path)

        font = item.font()
        if proc:
            adv_enabled = getattr(self, "advanced_tags_enabled", True)
            raw_approved = proc.get("approved", [])
            raw_pending = proc.get("pending", [])
            raw_adv = proc.get("advanced", [])

            if adv_enabled:
                app_n = len(raw_approved)
                pend_n = len(raw_pending)
                adv_n = len(raw_adv)
            else:
                app_n = sum(1 for t, _ in raw_approved if not self.tag_library.is_advanced(t))
                pend_n = sum(1 for t in raw_pending if not self.tag_library.is_advanced(t))
                adv_n = 0

            if pend_n > 0:
                adv_prefix = f"◆ [{adv_n} ADV]  " if adv_n > 0 else ""
                item.setText(f"⚠️ [?{pend_n} PENDING]  {adv_prefix}{fname}  (✓{app_n})")
                item.setForeground(QBrush(QColor("#f0883e")))
                item.setBackground(QBrush(QColor(210, 153, 34, 40)))
                font.setBold(True)
                item.setFont(font)
                adv_tip = f"\n• ◆ {adv_n} advanced tag(s) detected" if adv_n > 0 else ""
                item.setToolTip(f"{fname}\n• ⚠️ {pend_n} tag(s) pending approval (not written until approved){adv_tip}\n• ✓ {app_n} approved tag(s)")
            elif adv_n > 0:
                item.setText(f"◆ [{adv_n} ADV]  {fname}  (✓{app_n})")
                item.setForeground(QBrush(QColor("#f85149")))
                item.setBackground(QBrush(QColor(218, 54, 51, 35)))
                font.setBold(True)
                item.setFont(font)
                item.setToolTip(f"{fname}\n• ◆ {adv_n} advanced tag(s) detected\n• ✓ {app_n} approved tag(s)")
            elif app_n > 0:
                # All detected tags approved / ready
                item.setText(f"✓ {fname}  [{app_n}]")
                item.setForeground(QBrush(QColor("#3fb950")))
                item.setBackground(QBrush(QColor(0, 0, 0, 0)))
                font.setBold(False)
                item.setFont(font)
                item.setToolTip(f"{fname}\n• ✓ All {app_n} detected tag(s) approved and ready")
            else:
                # Analyzed but 0 tags
                item.setText(f"○ {fname}  [0 tags]")
                item.setForeground(QBrush(QColor("#8b949e")))
                item.setBackground(QBrush(QColor(0, 0, 0, 0)))
                font.setBold(False)
                item.setFont(font)
                item.setToolTip(f"{fname}\n• 0 tags detected above confidence threshold")
        else:
            # Unanalyzed
            item.setText(fname)
            item.setForeground(QBrush(QColor("#c9d1d9")))
            item.setBackground(QBrush(QColor(0, 0, 0, 0)))
            font.setBold(False)
            item.setFont(font)
            item.setToolTip(fname)

    def _apply_list_filters(self):
        """Apply active Pending / Advanced filters to the image list."""
        want_pending = hasattr(self, "filter_pending_btn") and self.filter_pending_btn.isChecked()
        want_adv = (
            getattr(self, "advanced_tags_enabled", True)
            and hasattr(self, "filter_advanced_btn")
            and self.filter_advanced_btn.isChecked()
        )
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            p = item.data(Qt.ItemDataRole.UserRole)
            proc = self.processed_tags.get(p, {})
            hide = False
            if want_pending:
                raw_pend = proc.get("pending", [])
                if not getattr(self, "advanced_tags_enabled", True):
                    raw_pend = [t for t in raw_pend if not self.tag_library.is_advanced(t)]
                if len(raw_pend) == 0:
                    hide = True
            if want_adv and not hide:
                if len(proc.get("advanced", [])) == 0:
                    hide = True
            item.setHidden(hide)

    def _toggle_pending_filter(self, checked: bool):
        """Filter the image list to only show files with pending tags."""
        self._apply_list_filters()

    def _toggle_advanced_filter(self, checked: bool):
        """Filter the image list to only show files with advanced tags."""
        self._apply_list_filters()

    def _on_advanced_tags_toggled(self, checked: bool):
        """Toggle global Advanced Tags visibility and writing."""
        self.advanced_tags_enabled = checked
        self.config["advanced_tags_enabled"] = checked
        self._save_config()

        if hasattr(self, "advanced_toggle_btn"):
            self.advanced_toggle_btn.setText("◆ Advanced: ON" if checked else "◇ Advanced: OFF")
        if hasattr(self, "filter_advanced_btn"):
            if not checked and self.filter_advanced_btn.isChecked():
                self.filter_advanced_btn.setChecked(False)
            self.filter_advanced_btn.setVisible(checked)
        if hasattr(self, "library_manager"):
            self.library_manager.set_advanced_visible(checked)

        self._on_library_modified()
        self._update_existing_tags_display()
        state_str = "enabled" if checked else "disabled (hidden & excluded from writes)"
        self.status_label.setText(f"Advanced Tags {state_str}")

    def _toggle_select_all(self):
        visible_items = [
            self.image_list.item(i)
            for i in range(self.image_list.count())
            if not self.image_list.item(i).isHidden()
        ]
        if not visible_items:
            return
        all_checked = all(it.checkState() == Qt.CheckState.Checked for it in visible_items)
        new_state = Qt.CheckState.Unchecked if all_checked else Qt.CheckState.Checked
        for it in visible_items:
            it.setCheckState(new_state)
        self.select_all_btn.setText("Select All" if all_checked else "Deselect All")

    # ── Image Selection & Preview ────────────────────────────────────────────

    def _on_image_selected(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._select_image(path)

    def _on_current_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        if current:
            path = current.data(Qt.ItemDataRole.UserRole)
            if path and path != self.selected_path:
                self._select_image(path)

    def _get_existing_tags(self, path: str) -> list:
        """Retrieve existing tags for a given image path with case and slash normalization."""
        if not path or not self.existing_tags:
            return []
        if path in self.existing_tags:
            return self.existing_tags[path]
        try:
            norm_target = os.path.normcase(os.path.normpath(str(Path(path).resolve())))
            for k, v in self.existing_tags.items():
                if os.path.normcase(os.path.normpath(str(Path(k).resolve()))) == norm_target:
                    return v
        except Exception:
            pass
        return []

    def _update_existing_tags_display(self):
        """Update existing metadata tags chip display for the currently selected image."""
        if not hasattr(self, "existing_flow"):
            return

        while self.existing_flow.count():
            item = self.existing_flow.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not self.selected_path:
            self.existing_count_lbl.setText("")
            self.clear_existing_btn.setEnabled(False)
            self.restore_existing_btn.setEnabled(False)
            lbl = QLabel("(No image selected — select an image to inspect or edit existing metadata tags)")
            lbl.setStyleSheet("color: #6e7681; font-style: italic; font-size: 11px; background: transparent; padding: 2px 4px;")
            self.existing_flow.addWidget(lbl)
            return

        existing = self._get_existing_tags(self.selected_path)
        is_reading = (
            (hasattr(self, "meta_reader") and self.meta_reader and self.meta_reader.isRunning())
            or (hasattr(self, "meta_add_reader") and self.meta_add_reader and self.meta_add_reader.isRunning())
        )

        if not existing:
            if is_reading:
                self.existing_count_lbl.setText("(Reading...)")
                lbl = QLabel("Reading existing metadata tags from file...")
                lbl.setStyleSheet("color: #58a6ff; font-style: italic; font-size: 11px; background: transparent; padding: 2px 4px;")
            else:
                self.existing_count_lbl.setText("(0)")
                lbl = QLabel("(No existing metadata tags on this image)")
                lbl.setStyleSheet("color: #6e7681; font-style: italic; font-size: 11px; background: transparent; padding: 2px 4px;")
            self.clear_existing_btn.setEnabled(False)
            self.restore_existing_btn.setEnabled(False)
            self.existing_flow.addWidget(lbl)
            return

        skipped = self.skipped_tags.get(self.selected_path, set())
        n_skipped = sum(1 for t in existing if normalize_tag(t) in skipped)
        n_active = len(existing) - n_skipped

        if n_skipped == 0:
            self.existing_count_lbl.setText(f"({len(existing)} tags)")
        else:
            self.existing_count_lbl.setText(f"({n_active} kept / {len(existing)} total)")

        self.clear_existing_btn.setEnabled(n_active > 0)
        self.restore_existing_btn.setEnabled(n_skipped > 0)

        adv_enabled = getattr(self, "advanced_tags_enabled", True)
        for t in existing:
            norm = normalize_tag(t)
            is_skp = norm in skipped
            is_adv = adv_enabled and self.tag_library.is_advanced(t)
            chip = TagChip(t, "existing", is_skipped=is_skp, source_raw_tag=t, is_advanced=is_adv)
            chip.toggled.connect(lambda _, t_name=t: self._toggle_tag_skip(t_name, self.selected_path))
            chip.aliased.connect(lambda t_name, pos: self._alias_tag(t_name, pos, self.selected_path))
            chip.menu_requested.connect(lambda raw, canon, cat_type, pos: self._show_tag_context_menu(raw, canon, cat_type, pos, self.selected_path))
            self.existing_flow.addWidget(chip)

    def _clear_all_existing_tags(self):
        """Grey out (skip) all existing tags for the currently selected image."""
        if not self.selected_path:
            return
        existing = self._get_existing_tags(self.selected_path)
        if not existing:
            return
        if self.selected_path not in self.skipped_tags:
            self.skipped_tags[self.selected_path] = set()

        for t in existing:
            self.skipped_tags[self.selected_path].add(normalize_tag(t))

        self._update_existing_tags_display()
        self._refresh_tag_display(self.selected_path)
        self._check_write_button_state()

    def _restore_all_existing_tags(self):
        """Restore all greyed-out existing tags for the currently selected image."""
        if not self.selected_path:
            return
        existing = self._get_existing_tags(self.selected_path)
        if not existing or self.selected_path not in self.skipped_tags:
            return

        for t in existing:
            self.skipped_tags[self.selected_path].discard(normalize_tag(t))

        self._update_existing_tags_display()
        self._refresh_tag_display(self.selected_path)
        self._check_write_button_state()

    def _check_write_button_state(self):
        """Enable Write button if images are loaded, ExifTool is ready, and there are tags or edits."""
        if self.is_processing or not self.image_paths or not self.metadata_handler:
            self.write_btn.setEnabled(False)
            return

        has_content = bool(self.processed_tags or self.skipped_tags or self.existing_tags)
        self.write_btn.setEnabled(has_content)

    def _select_image(self, path: str):
        self.selected_path = path
        if not self.is_processing:
            self.quick_analyze_btn.setEnabled(True)

        # Show high-res preview via preview_widget
        self.preview_widget.set_image(path)

        # Update existing metadata tags
        self._update_existing_tags_display()

        # Refresh tag chips
        self._refresh_tag_display(path)

    def _on_translated_view_toggled(self, in_categories: bool):
        """Toggle whether translated tags appear in categories or in a separate section below."""
        self.show_translated_in_categories = in_categories
        self.config["show_translated_in_categories"] = in_categories
        self._save_config()
        if self.selected_path:
            self._refresh_tag_display(self.selected_path)

    def _refresh_tag_display(self, path: str):
        # Clear existing tag chips
        while self.tags_vlayout.count():
            item = self.tags_vlayout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        result = self.results.get(path)
        if not result:
            no_tags = QLabel("Click '⚡ Analyze Batch' to detect tags for this image")
            no_tags.setStyleSheet("color: #6e7681; font-style: italic; padding: 10px 0;")
            self.tags_vlayout.addWidget(no_tags)
            self.rating_label.setText("")
            self.rating_card.setVisible(False)
            return

        if "error" in result:
            err_lbl = QLabel(f"Inference error: {result['error']}")
            err_lbl.setStyleSheet("color: #f85149; font-weight: bold; padding: 10px 0;")
            self.tags_vlayout.addWidget(err_lbl)
            self.rating_label.setText("")
            self.rating_card.setVisible(False)
            return

        # Rating / Caption banner card
        caption = result.get("caption", "").strip()
        ratings = result.get("rating", {})
        if caption:
            self.rating_label.setText(
                f"<span style='color: #58a6ff;'><b>💬 Caption:</b></span> &nbsp;<span style='color: #e6edf3; font-style: italic;'>\"{caption}\"</span>"
            )
            self.rating_card.setVisible(True)
        elif ratings:
            parts = [
                f"<span style='color: #8b949e;'>{k.title()}:</span> "
                f"<b style='color: {'#3fb950' if k == 'general' and v > 0.5 else '#f0883e' if v > 0.2 else '#e6edf3'}; font-family: Consolas;'>{v*100:.1f}%</b>"
                for k, v in ratings.items()
            ]
            self.rating_label.setText(
                "<span style='color: #58a6ff;'><b>🛡️ Safety Ratings:</b></span> &nbsp;&nbsp;" + " &nbsp;•&nbsp; ".join(parts)
            )
            self.rating_card.setVisible(True)
        else:
            self.rating_label.setText("")
            self.rating_card.setVisible(False)

        # Ensure processed tags are present
        if path not in self.processed_tags and "all_tags" in result:
            self.processed_tags[path] = self.tag_library.process_tags(result["all_tags"])

        processed = self.processed_tags.get(path, {})
        skipped = self.skipped_tags.get(path, set())

        adv_enabled = getattr(self, "advanced_tags_enabled", True)
        approved = processed.get("approved", [])
        translated = processed.get("translated", [])
        pending = processed.get("pending", [])
        blocked = processed.get("blocked", [])

        if not adv_enabled:
            approved = [(t, c) for t, c in approved if not self.tag_library.is_advanced(t)]
            translated = [(orig, final) for orig, final in translated if not self.tag_library.is_advanced(final)]
            pending = [t for t in pending if not self.tag_library.is_advanced(t)]

        # Translation alias mapping: {normalized(final_tag): original_raw_tag}
        trans_map = {}
        for orig, final in translated:
            trans_map[normalize_tag(final)] = orig

        # Existing metadata tags on this image (for matching detection)
        existing_raw = self._get_existing_tags(path)
        existing_set = {normalize_tag(t) for t in existing_raw}

        in_categories = getattr(self, "show_translated_in_categories", True)

        # 1. Approved & Translated Tags Grouped by Category
        if approved:
            by_cat = {}
            for tag, cat in approved:
                by_cat.setdefault(cat, []).append(tag)

            for cat in sorted(by_cat.keys()):
                cat_tags = by_cat[cat]
                if not cat_tags:
                    continue

                cat_section = QWidget()
                cat_layout = QVBoxLayout(cat_section)
                cat_layout.setContentsMargins(0, 2, 0, 6)
                cat_layout.setSpacing(4)

                header = QLabel(
                    f"<span style='color: #e6edf3; font-size: 12px;'><b>📁 {cat}</b></span> "
                    f"<span style='color: #8b949e; font-size: 11px;'>({len(cat_tags)})</span>"
                )
                header.setStyleSheet("background: transparent; padding: 2px 0;")
                cat_layout.addWidget(header)

                chip_container = FlowContainer(margin=2, spacing=5)
                for t in cat_tags:
                    norm = normalize_tag(t)
                    is_skp = norm in skipped
                    is_adv = adv_enabled and self.tag_library.is_advanced(t)
                    if in_categories and norm in trans_map:
                        orig = trans_map[norm]
                        is_match = (norm in existing_set) or (normalize_tag(orig) in existing_set)
                        chip = TagChip(
                            tag=t,
                            category_type="translated",
                            is_skipped=is_skp,
                            display_text=f"{format_tag(orig)} → {format_tag(t)}",
                            source_raw_tag=orig,
                            is_existing_match=is_match,
                            is_advanced=is_adv,
                        )
                    else:
                        is_match = norm in existing_set
                        chip = TagChip(
                            tag=t,
                            category_type="approved",
                            is_skipped=is_skp,
                            source_raw_tag=t,
                            is_existing_match=is_match,
                            is_advanced=is_adv,
                        )

                    chip.toggled.connect(lambda _, t_name=t: self._toggle_tag_skip(t_name, path))
                    chip.aliased.connect(lambda t_name, pos: self._alias_tag(t_name, pos, path))
                    chip.menu_requested.connect(lambda raw, canon, cat_type, pos: self._show_tag_context_menu(raw, canon, cat_type, pos, path))
                    chip_container.addWidget(chip)

                cat_layout.addWidget(chip_container)
                self.tags_vlayout.addWidget(cat_section)

        # 2. Dedicated Translated Tags Section (when "In Categories" is unchecked)
        if not in_categories and translated:
            n_trans_active = sum(1 for orig, final in translated if normalize_tag(final) not in skipped)
            trans_section = QWidget()
            trans_layout = QVBoxLayout(trans_section)
            trans_layout.setContentsMargins(0, 4, 0, 6)
            trans_layout.setSpacing(4)

            header = QLabel(
                f"<span style='color: #58a6ff; font-size: 12px;'><b>⇄ Translated Tags</b></span> "
                f"<span style='color: #8b949e; font-size: 11px;'>({n_trans_active}/{len(translated)}) — mapped via aliases</span>"
            )
            header.setStyleSheet("background: transparent; padding: 2px 0;")
            trans_layout.addWidget(header)

            chip_container = FlowContainer(margin=2, spacing=5)
            for orig, final in translated:
                norm = normalize_tag(final)
                is_skp = norm in skipped
                is_match = (norm in existing_set) or (normalize_tag(orig) in existing_set)
                is_adv = adv_enabled and self.tag_library.is_advanced(final)
                chip = TagChip(
                    tag=final,
                    category_type="translated",
                    is_skipped=is_skp,
                    display_text=f"{format_tag(orig)} → {format_tag(final)}",
                    source_raw_tag=orig,
                    is_existing_match=is_match,
                    is_advanced=is_adv,
                )
                chip.toggled.connect(lambda _, t_name=final: self._toggle_tag_skip(t_name, path))
                chip.aliased.connect(lambda t_name, pos: self._alias_tag(t_name, pos, path))
                chip.menu_requested.connect(lambda raw, canon, cat_type, pos: self._show_tag_context_menu(raw, canon, cat_type, pos, path))
                chip_container.addWidget(chip)

            trans_layout.addWidget(chip_container)
            self.tags_vlayout.addWidget(trans_section)

        # 3. Pending Tags
        if pending:
            n_active = sum(1 for t in pending if normalize_tag(t) not in skipped)
            pending_section = QWidget()
            pending_layout = QVBoxLayout(pending_section)
            pending_layout.setContentsMargins(0, 4, 0, 6)
            pending_layout.setSpacing(4)

            header = QLabel(
                f"<span style='color: #f0883e; font-size: 12px;'><b>? Pending Approval</b></span> "
                f"<span style='color: #8b949e; font-size: 11px;'>({len(pending)} unapproved — excluded from write until approved; ✓: approve, 🔗: alias, ✕: block)</span>"
            )
            header.setStyleSheet("background: transparent; padding: 2px 0;")
            pending_layout.addWidget(header)

            chip_container = FlowContainer(margin=2, spacing=5)
            for t in pending:
                is_skp = normalize_tag(t) in skipped
                is_match = normalize_tag(t) in existing_set
                is_adv = adv_enabled and self.tag_library.is_advanced(t)
                chip = TagChip(
                    tag=t,
                    category_type="pending",
                    is_skipped=is_skp,
                    source_raw_tag=t,
                    is_existing_match=is_match,
                    is_advanced=is_adv,
                )
                chip.toggled.connect(lambda _, t_name=t: self._toggle_tag_skip(t_name, path))
                chip.approved.connect(lambda t_name, pos: self._approve_pending_tag(t_name, pos, path))
                chip.aliased.connect(lambda t_name, pos: self._alias_tag(t_name, pos, path))
                chip.blocked.connect(lambda t_name: self._block_pending_tag(t_name, path))
                chip.menu_requested.connect(lambda raw, canon, cat_type, pos: self._show_tag_context_menu(raw, canon, cat_type, pos, path))
                chip_container.addWidget(chip)

            pending_layout.addWidget(chip_container)
            self.tags_vlayout.addWidget(pending_section)

        # 4. If no tags detected
        if not approved and not translated and not pending:
            empty_lbl = QLabel("No tags met the confidence threshold. Try lowering the threshold slider.")
            empty_lbl.setStyleSheet("color: #8b949e; font-style: italic; padding: 10px 0;")
            self.tags_vlayout.addWidget(empty_lbl)

        # 5. Blocked Tags Summary (if any)
        if blocked:
            n_blocked = len(blocked)
            preview = ", ".join(format_tag(t) for t in blocked[:8])
            if n_blocked > 8:
                preview += f" ... +{n_blocked - 8} more"
            b_lbl = QLabel(f"<span style='color: #da3633;'>✗ Blocked ({n_blocked}):</span> <span style='color: #6e7681;'>{preview}</span>")
            b_lbl.setStyleSheet("font-size: 11px; margin-top: 10px;")
            self.tags_vlayout.addWidget(b_lbl)

        self.tags_vlayout.addStretch()

    def _toggle_tag_skip(self, tag: str, path: str):
        norm = normalize_tag(tag)
        if path not in self.skipped_tags:
            self.skipped_tags[path] = set()

        if norm in self.skipped_tags[path]:
            self.skipped_tags[path].remove(norm)
        else:
            self.skipped_tags[path].add(norm)

        self._refresh_tag_display(path)
        self._update_existing_tags_display()
        self._check_write_button_state()

    def _approve_pending_tag(self, tag: str, global_pos: QPoint, path: str):
        cats = self.tag_library.get_categories() or ["General"]
        popup = CategoryPickerPopup(self, tag, cats, global_pos, tag_library=self.tag_library)
        if popup.exec():
            if popup.result_category:
                self.tag_library.approve_tag(tag, popup.result_category)
                self._on_library_modified()
                self.status_label.setText(f"Approved '{format_tag(tag)}' into {popup.result_category} ✓")
            elif getattr(popup, "result_alias_target", None):
                target = popup.result_alias_target
                self.tag_library.add_alias(target, tag)
                self._on_library_modified()
                self.status_label.setText(f"Aliased '{format_tag(tag)}' → '{format_tag(target)}' ✓")

    def _alias_tag(self, tag: str, global_pos: QPoint = None, path: str = None):
        """Open alias picker dialog to set tag as an alias of an existing approved tag."""
        dialog = AliasPickerPopup(
            self,
            source_tag=tag,
            tag_library=self.tag_library,
            title=f"Set Alias for '{format_tag(tag)}'",
            prompt=f"Choose an existing approved tag that <b>'{format_tag(tag)}'</b> should map to:"
        )
        if dialog.exec() and dialog.result_parent_tag:
            target = dialog.result_parent_tag
            self.tag_library.add_alias(target, tag)
            self._on_library_modified()
            self.status_label.setText(f"Aliased '{format_tag(tag)}' → '{format_tag(target)}' ✓")

    def _alias_pending_tag(self, tag: str, global_pos: QPoint, path: str):
        self._alias_tag(tag, global_pos, path)

    def _block_pending_tag(self, tag: str, path: str):
        self.tag_library.block_tag(tag)
        self._on_library_modified()

    def _show_tag_context_menu(self, raw_tag: str, canonical_tag: str, category_type: str, global_pos: QPoint, path: str = None):
        """Show small context menu on tag chip: Set as alias, Block Tag, Change Category."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #161b22;
                border: 1px solid #30363d;
                color: #e6edf3;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 11px;
            }
            QMenu::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)

        alias_act = menu.addAction("🔗 Set as alias")
        make_tag_act = None
        if category_type == "translated" and normalize_tag(raw_tag) != normalize_tag(canonical_tag):
            make_tag_act = menu.addAction(f"🏷️ Make Tag ('{format_tag(raw_tag)}')")
        block_act = menu.addAction("🚫 Block Tag")
        change_cat_act = menu.addAction("📁 Change Category")
        is_adv = self.tag_library.is_advanced(canonical_tag)
        adv_act = menu.addAction("◇ Remove Advanced" if is_adv else "◆ Mark as Advanced")

        action = menu.exec(global_pos)
        if not action:
            return

        if action == alias_act:
            self._alias_tag(raw_tag, global_pos, path)
        elif make_tag_act and action == make_tag_act:
            cats = sorted(self.tag_library.approved.keys()) or ["General"]
            popup = CategoryPickerPopup(
                self,
                raw_tag,
                cats,
                global_pos,
                tag_library=self.tag_library,
                title=f"Convert Alias '{format_tag(raw_tag)}' to Tag"
            )
            if popup.exec() and popup.result_category:
                self.tag_library.remove_alias(canonical_tag, raw_tag)
                self.tag_library.approve_tag(raw_tag, popup.result_category)
                self._on_library_modified()
                self.status_label.setText(f"Converted alias '{format_tag(raw_tag)}' to tag in '{popup.result_category}' ✓")
        elif action == block_act:
            self.tag_library.block_tag(raw_tag)
            self._on_library_modified()
            self.status_label.setText(f"Blocked tag '{format_tag(raw_tag)}' ✓")
        elif action == change_cat_act:
            self._change_tag_category(canonical_tag, global_pos, path)
        elif action == adv_act:
            new_state = self.tag_library.toggle_advanced(canonical_tag)
            self._on_library_modified()
            self._update_existing_tags_display()
            state_msg = "marked as Advanced" if new_state else "removed from Advanced"
            self.status_label.setText(f"'{format_tag(canonical_tag)}' {state_msg} ✓")

    def _change_tag_category(self, tag: str, global_pos: QPoint = None, path: str = None):
        """Open category picker to move or assign tag to a category."""
        norm = self.tag_library.normalize(tag)
        current_cat = None
        for cat, tags in self.tag_library.approved.items():
            if norm in (self.tag_library.normalize(t) for t in tags):
                current_cat = cat
                break

        categories = sorted(self.tag_library.approved.keys())
        available_cats = [c for c in categories if c != current_cat] if current_cat else categories
        if not available_cats:
            available_cats = categories or ["General"]

        title = f"Move '{format_tag(tag)}' to Category" if current_cat else f"Assign Category for '{format_tag(tag)}'"
        popup = CategoryPickerPopup(self, tag, available_cats, global_pos or QCursor.pos(), tag_library=self.tag_library, title=title)
        if popup.exec():
            if popup.result_category:
                new_cat = popup.result_category
                if current_cat:
                    self.tag_library.move_tag(tag, new_cat)
                    self.status_label.setText(f"Moved '{format_tag(tag)}' to '{new_cat}' ✓")
                else:
                    self.tag_library.approve_tag(tag, new_cat)
                    self.status_label.setText(f"Approved '{format_tag(tag)}' into '{new_cat}' ✓")
                self._on_library_modified()
            elif getattr(popup, "result_alias_target", None):
                target = popup.result_alias_target
                self.tag_library.add_alias(target, tag)
                self._on_library_modified()
                self.status_label.setText(f"Aliased '{format_tag(tag)}' → '{format_tag(target)}' ✓")

    def _on_library_modified(self):
        """Reprocess all image tags through updated libraries and refresh."""
        for p, res in self.results.items():
            if "error" not in res and "all_tags" in res:
                self.processed_tags[p] = self.tag_library.process_tags(res["all_tags"])

        if self.selected_path:
            self._refresh_tag_display(self.selected_path)

        # Update badges on image list
        adv_enabled = getattr(self, "advanced_tags_enabled", True)
        pending_img_count = 0
        adv_img_count = 0
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            p = item.data(Qt.ItemDataRole.UserRole)
            self._update_image_list_item(item, p)
            proc = self.processed_tags.get(p, {})
            pend_list = proc.get("pending", [])
            if not adv_enabled:
                pend_list = [t for t in pend_list if not self.tag_library.is_advanced(t)]
            if len(pend_list) > 0:
                pending_img_count += 1
            if adv_enabled and len(proc.get("advanced", [])) > 0:
                adv_img_count += 1

        total = len(self.image_paths)
        if total > 0:
            badges = []
            if pending_img_count > 0:
                badges.append(f"<span style='color: #f0883e; font-weight: bold;'>[⚠️ {pending_img_count} pending]</span>")
            if adv_enabled and adv_img_count > 0:
                badges.append(f"<span style='color: #f85149; font-weight: bold;'>[◆ {adv_img_count} adv]</span>")

            if badges:
                self.image_count_label.setText(f"{total} images &nbsp;" + " ".join(badges))
            else:
                self.image_count_label.setText(f"{total} images")

            if hasattr(self, "filter_pending_btn"):
                self.filter_pending_btn.setText(f"⚠️ Pending ({pending_img_count})")
            if hasattr(self, "filter_advanced_btn"):
                self.filter_advanced_btn.setText(f"◆ Adv ({adv_img_count})")

        self._apply_list_filters()

    # ── Single & Batch Analysis (GPU Accelerated) ────────────────────────────

    def _start_single_analysis(self):
        """Run AI inference on only the currently selected/viewed image."""
        if not self.selected_path or self.is_processing:
            return

        path = self.selected_path
        self.is_processing = True
        self.analyze_btn.setEnabled(False)
        self.quick_analyze_btn.setEnabled(False)
        self.folder_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Analyzing {Path(path).name} on GPU...")

        self.worker = BatchAnalyzeWorker(self.engine, [path], batch_size=1)
        self.worker.progress.connect(self._on_analysis_progress)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _start_batch_analysis(self):
        if not self.image_paths or self.is_processing:
            return

        # Gather checked items
        selected_paths = []
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected_paths.append(item.data(Qt.ItemDataRole.UserRole))

        if not selected_paths:
            if self.selected_path:
                selected_paths = [self.selected_path]
            else:
                QMessageBox.information(self, "No Images", "Please check or select at least one image to analyze.")
                return

        self._run_analysis_on_paths(selected_paths)

    def _run_analysis_on_paths(self, paths_to_analyze: list):
        """Run batch AI inference on a list of image paths."""
        if not paths_to_analyze or self.is_processing:
            return

        self.is_processing = True
        self.analyze_btn.setEnabled(False)
        self.quick_analyze_btn.setEnabled(False)
        self.folder_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Starting analysis on {len(paths_to_analyze)} image(s)...")

        self.worker = BatchAnalyzeWorker(self.engine, paths_to_analyze, batch_size=16)
        self.worker.progress.connect(self._on_analysis_progress)
        self.worker.finished.connect(self._on_analysis_finished)
        self.worker.error.connect(self._on_analysis_error)
        self.worker.start()

    def _on_analysis_progress(self, current, total, path, status):
        pct = int((current / total) * 100) if total else 0
        self.progress_bar.setValue(pct)
        self.status_label.setText(f"Analyzing {current}/{total} on GPU — {Path(path).name}")

    def _on_analysis_finished(self, results):
        self.results.update(results)
        self.is_processing = False
        self.analyze_btn.setEnabled(len(self.image_paths) > 0)
        self.quick_analyze_btn.setEnabled(self.selected_path is not None)
        self.folder_btn.setEnabled(True)
        self.write_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        self._on_library_modified()
        if self.selected_path:
            self._select_image(self.selected_path)
        elif self.image_paths:
            self._select_image(self.image_paths[0])

        count = len(results)
        if count == 1:
            name = Path(list(results.keys())[0]).name
            self.status_label.setText(f"Analysis complete for {name}! ✓")
        else:
            self.status_label.setText(f"Analysis complete! Processed {count} images on GPU ✓")

    def _on_analysis_error(self, err):
        self.is_processing = False
        self.analyze_btn.setEnabled(len(self.image_paths) > 0)
        self.quick_analyze_btn.setEnabled(self.selected_path is not None)
        self.folder_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Analysis Error: {err}")
        QMessageBox.critical(self, "Error", f"AI inference failed:\n\n{err}")

    # ── Batch Exif Metadata Write (High Speed) ───────────────────────────────

    def _start_batch_write(self):
        if not self.metadata_handler:
            self._setup_exiftool(then_write=True)
            return

        tag_map = {}
        for i in range(self.image_list.count()):
            item = self.image_list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                p = item.data(Qt.ItemDataRole.UserRole)
                existing = self._get_existing_tags(p)
                proc = self.processed_tags.get(p, {})
                # Only approved and translated tags are written; pending (unapproved) tags are strictly excluded
                ai_tags = proc.get("final_tags", [])
                skipped = self.skipped_tags.get(p, set())

                # Active existing tags (not greyed out / skipped)
                active_existing = [t for t in existing if normalize_tag(t) not in skipped]

                # Active AI detected tags (only approved/translated, not skipped; exclude advanced if disabled)
                adv_enabled = getattr(self, "advanced_tags_enabled", True)
                active_ai = [
                    t for t in ai_tags
                    if normalize_tag(t) not in skipped
                    and (adv_enabled or not self.tag_library.is_advanced(t))
                ]

                # Target tags to write: merged, deduplicated, sorted alphabetically
                desired = self.metadata_handler._deduplicate_and_sort(active_existing + active_ai)

                # Check if desired tags differ from what is currently on disk
                norm_existing = [self.metadata_handler._normalize(t) for t in existing]
                norm_desired = [self.metadata_handler._normalize(t) for t in desired]

                if norm_existing != norm_desired:
                    tag_map[p] = desired

        if not tag_map:
            QMessageBox.information(
                self,
                "Tags Up to Date",
                "No metadata changes to write for the selected images.\nAll active tags already match the files."
            )
            return

        # Confirm before writing tags to disk
        count = len(tag_map)
        plural = "s" if count != 1 else ""
        confirm_msg = (
            f"Are you sure you want to write tags to {count} image file{plural}?\n\n"
            f"• Original modified/access dates will be preserved.\n"
            f"• Active tags will be written and greyed-out tags will be removed.\n"
            f"• Unapproved pending tags are excluded."
        )
        reply = QMessageBox.question(
            self,
            "Confirm Write Tags",
            confirm_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.status_label.setText("Tag write cancelled.")
            return

        self.is_processing = True
        self.write_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Writing metadata to {len(tag_map)} files...")

        self.write_worker = BatchWriteWorker(self.metadata_handler, tag_map)
        self.write_worker.progress.connect(lambda cur, tot, p, msg: self.status_label.setText(msg))
        self.write_worker.finished.connect(self._on_write_finished)
        self.write_worker.error.connect(lambda err: QMessageBox.critical(self, "Write Error", err))
        self.write_worker.start()

    def _on_write_finished(self, results):
        self.is_processing = False
        self.write_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        success_count = sum(1 for v in results.values() if v)
        self.status_label.setText(f"Metadata write complete! Updated {success_count}/{len(results)} files.")

        # Update in-memory existing tags with the newly merged and sorted tags
        if self.metadata_handler and hasattr(self.metadata_handler, "last_merged_tags"):
            for path, written_tags in self.metadata_handler.last_merged_tags.items():
                self.existing_tags[path] = written_tags
                if path in self.skipped_tags:
                    self.skipped_tags[path].clear()

            self._update_existing_tags_display()

        QMessageBox.information(self, "Write Complete", f"Successfully written tags to {success_count} images!")


# ── Application Entry Point ──────────────────────────────────────────────────

def main():
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("autophototagger.desktop.app.v1")
    except Exception:
        pass

    app = QApplication(sys.argv)
    if APP_ICON_PNG.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PNG)))
    app.setStyleSheet(DARK_STYLE)
    window = AutoPhotoTaggerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
