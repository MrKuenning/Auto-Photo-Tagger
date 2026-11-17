"""
Auto Photo Tagger - ExifTool Installer & Locator Module
Automates locating existing ExifTool installations on the system
and provides in-app downloading and extraction of ExifTool from official sources.
"""

import os
import sys
import shutil
import zipfile
import subprocess
import http.cookiejar
import urllib.request
from pathlib import Path


DEFAULT_FALLBACK_VERSION = "13.63"


def _resolve_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = _resolve_app_dir()


def find_exiftool(custom_path: str = None) -> str | None:
    """
    Search for a working exiftool.exe across custom path, app directory, system PATH,
    and common Windows installation directories. Verifies that the executable can run.
    """
    candidates = []

    if custom_path:
        try:
            p = Path(custom_path)
            if p.exists() and p.is_file():
                candidates.append(p)
            elif p.exists() and p.is_dir():
                for name in ["exiftool.exe", "exiftool(-k).exe"]:
                    if (p / name).exists():
                        candidates.append(p / name)
        except (OSError, PermissionError):
            pass

    # App directory
    for name in ["exiftool.exe", "exiftool(-k).exe"]:
        try:
            cand = APP_DIR / name
            if cand.exists():
                candidates.append(cand)
        except (OSError, PermissionError):
            pass

    # System PATH
    which_path = shutil.which("exiftool")
    if which_path:
        candidates.append(Path(which_path))

    # Common Windows folders
    common_locations = [
        Path(r"C:\Program Files\ExifTool\exiftool.exe"),
        Path(r"C:\Program Files (x86)\ExifTool\exiftool.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\ExifTool\exiftool.exe")),
        Path(os.path.expandvars(r"%ProgramW6432%\ExifTool\exiftool.exe")),
        Path(r"C:\Exiftool\exiftool.exe"),
        Path(r"C:\ExifTool\exiftool.exe"),
        Path(r"C:\exiftool\exiftool.exe"),
        Path(r"C:\Program Files\exiftool\exiftool.exe"),
        Path(r"C:\Program Files (x86)\exiftool\exiftool.exe"),
        Path.home() / "exiftool" / "exiftool.exe",
    ]
    for loc in common_locations:
        try:
            if loc.exists() and loc not in candidates:
                candidates.append(loc)
        except (OSError, PermissionError):
            continue

    # Return first verified working candidate
    for c in candidates:
        try:
            valid, _ = verify_exiftool(str(c))
            if valid:
                return str(c.resolve())
        except (OSError, PermissionError):
            continue

    return None


def verify_exiftool(executable_path: str) -> tuple[bool, str]:
    """
    Test running the given ExifTool executable with '-ver'.
    Returns (is_valid, version_or_error_string).
    """
    if not executable_path or not os.path.exists(executable_path):
        return False, "File does not exist"

    try:
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        res = subprocess.run(
            [executable_path, "-ver"],
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=flags
        )
        if res.returncode == 0 and res.stdout.strip():
            return True, res.stdout.strip()
        else:
            err = res.stderr.strip() or f"Process exited with code {res.returncode}"
            return False, err
    except Exception as e:
        return False, str(e)


def install_via_winget(target_location: str = None, progress_callback = None) -> str:
    """
    Install ExifTool using Windows Package Manager (winget).
    Package ID: OliverBetz.ExifTool
    """
    winget_path = shutil.which("winget") or os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe")
    if not os.path.exists(winget_path):
        raise RuntimeError("winget.exe was not found on this system.")

    cmd = [
        winget_path, "install",
        "--id", "OliverBetz.ExifTool",
        "-e",
        "--accept-source-agreements",
        "--accept-package-agreements",
        "--silent"
    ]
    if target_location:
        cmd.extend(["--location", target_location])

    if progress_callback:
        progress_callback("Running winget install --id OliverBetz.ExifTool -e...")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    )

    out_lines = []
    for line in iter(proc.stdout.readline, ""):
        line_str = line.strip()
        if line_str:
            out_lines.append(line_str)
            if progress_callback:
                progress_callback(line_str)

    proc.stdout.close()
    ret = proc.wait()

    # Find the installed executable
    installed = find_exiftool(target_location)
    if installed:
        return installed

    # Check Oliver Betz standard locations
    std_locations = [
        Path(r"C:\Program Files\ExifTool\exiftool.exe"),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Programs\ExifTool\exiftool.exe")),
        Path(r"C:\Program Files (x86)\ExifTool\exiftool.exe"),
    ]
    for loc in std_locations:
        if loc.exists():
            valid, _ = verify_exiftool(str(loc))
            if valid:
                return str(loc.resolve())

    raise RuntimeError(
        f"winget installation finished with code {ret}, but exiftool.exe was not detected.\n"
        f"Output:\n" + "\n".join(out_lines[-4:])
    )


def get_latest_version() -> str:
    """Fetch latest ExifTool version string from exiftool.org, or return fallback."""
    urls = [
        "http://www.exiftool.org/ver.txt",
        "https://www.exiftool.org/ver.txt",
        "https://exiftool.org/ver.txt",
        "http://exiftool.org/ver.txt",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.exiftool.org/",
        "Accept": "text/plain, */*",
    }

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPRedirectHandler()
    )

    for u in urls:
        try:
            req = urllib.request.Request(u, headers=headers)
            with opener.open(req, timeout=6) as response:
                ver_text = response.read().decode("utf-8", errors="ignore").strip()
                if ver_text:
                    # Clean out any non-version characters
                    cleaned = "".join(c for c in ver_text if c.isdigit() or c == ".").strip()
                    if cleaned:
                        return cleaned
        except Exception:
            continue

    return DEFAULT_FALLBACK_VERSION


def download_and_install_exiftool(dest_dir: Path = None, progress_callback=None) -> str:
    """
    Download ExifTool Windows zip archive, extract exiftool.exe and its dependencies into dest_dir,
    and verify the installation.

    Args:
        dest_dir: Directory where exiftool.exe should be placed (defaults to app dir).
        progress_callback: Optional callable(downloaded_bytes, total_bytes, message).

    Returns:
        Absolute path to installed exiftool.exe.
    """
    if dest_dir is None:
        dest_dir = APP_DIR

    dest_dir.mkdir(parents=True, exist_ok=True)
    target_exe = dest_dir / "exiftool.exe"

    if progress_callback:
        progress_callback(0, 100, "Checking latest ExifTool version...")

    ver = get_latest_version()

    # Mirror list in order of reliability for direct binary zip download
    zip_urls = [
        f"https://download.sourceforge.net/project/exiftool/exiftool-{ver}_64.zip",
        f"https://downloads.sourceforge.net/project/exiftool/exiftool-{ver}_64.zip",
        f"http://www.exiftool.org/exiftool-{ver}_64.zip",
        f"https://www.exiftool.org/exiftool-{ver}_64.zip",
        f"https://exiftool.org/exiftool-{ver}_64.zip",
        f"https://download.sourceforge.net/project/exiftool/exiftool-{ver}.zip",
        f"http://www.exiftool.org/exiftool-{ver}.zip",
        f"https://www.exiftool.org/exiftool-{ver}.zip",
    ]

    zip_path = dest_dir / f"exiftool_download_{ver}.zip"
    extract_dir = dest_dir / f"exiftool_extract_{ver}"

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(cookie_jar),
        urllib.request.HTTPRedirectHandler()
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.exiftool.org/",
        "Accept": "application/zip, application/octet-stream, */*",
    }

    download_success = False
    last_err = None

    for url in zip_urls:
        try:
            if progress_callback:
                progress_callback(0, 0, f"Connecting to {url}...")

            # Clean previous partial attempt
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass

            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 64 * 1024

                with open(zip_path, "wb") as out_f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size, f"Downloading ExifTool ({downloaded // 1024} KB)...")

            # Validate that the downloaded file is a genuine ZIP archive
            if zip_path.exists() and zip_path.stat().st_size > 100_000:
                with open(zip_path, "rb") as check_f:
                    magic = check_f.read(4)
                if magic.startswith(b"PK") and zipfile.is_zipfile(zip_path):
                    download_success = True
                    break
                else:
                    # Received HTML error page instead of zip
                    try:
                        zip_path.unlink()
                    except Exception:
                        pass
                    last_err = "Server response was an HTML page rather than a ZIP archive"
            else:
                if zip_path.exists():
                    try:
                        zip_path.unlink()
                    except Exception:
                        pass
        except Exception as e:
            last_err = e
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass
            continue

    if not download_success:
        raise RuntimeError(
            f"Failed to download ExifTool archive from mirrors: {last_err}\n"
            f"You can manually download exiftool-{ver}_64.zip from https://exiftool.org/ "
            f"and use 'Locate Existing exiftool.exe'."
        )

    # Extract Archive
    if progress_callback:
        progress_callback(0, 0, "Extracting ExifTool archive and dependencies...")

    try:
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # Find the executable and exiftool_files directory inside extracted files
        source_exe = None
        source_files_dir = None

        for root, dirs, files in os.walk(extract_dir):
            for d in dirs:
                if d.lower() == "exiftool_files":
                    source_files_dir = Path(root) / d
            for f in files:
                if f.lower() in ["exiftool(-k).exe", "exiftool.exe"]:
                    source_exe = Path(root) / f
                    break
            if source_exe:
                break

        if not source_exe or not source_exe.exists():
            raise FileNotFoundError("Could not find exiftool(-k).exe inside downloaded archive")

        # Copy exiftool_files directory if present (critical for 64-bit Perl/C dependencies)
        if source_files_dir and source_files_dir.exists():
            target_files = dest_dir / "exiftool_files"
            if target_files.exists():
                try:
                    shutil.rmtree(target_files, ignore_errors=True)
                except Exception:
                    pass
            try:
                shutil.copytree(str(source_files_dir), str(target_files))
            except Exception:
                pass

        # Copy executable to exiftool.exe
        if target_exe.exists():
            try:
                target_exe.unlink()
            except Exception:
                pass

        shutil.copy2(str(source_exe), str(target_exe))

    finally:
        # Cleanup temp archive and extracted directory
        try:
            if zip_path.exists():
                zip_path.unlink()
            if extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)
        except Exception:
            pass

    # Verify installation
    valid, ver_info = verify_exiftool(str(target_exe))
    if not valid:
        raise RuntimeError(f"Installed ExifTool failed verification test: {ver_info}")

    if progress_callback:
        progress_callback(100, 100, f"ExifTool {ver_info} successfully installed!")

    return str(target_exe.resolve())
