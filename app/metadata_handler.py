"""
Auto Photo Tagger - Metadata Handler
High-performance batch reading and writing of IPTC/XMP/EXIF keyword tags to images using ExifTool.
Utilizes ExifTool batch argument files (-@) for ultra-fast, safe, non-destructive metadata operations.
"""

import os
import subprocess
import json
import shutil
import tempfile
from pathlib import Path

from exiftool_installer import find_exiftool, verify_exiftool


class MetadataHandler:
    """
    Handles reading and writing metadata tags to image files using ExifTool.
    Optimized for high-speed batch operations.
    """

    def __init__(self, exiftool_path: str = None):
        """
        Initialize the metadata handler.

        Args:
            exiftool_path: Path to exiftool executable. If None, searches PATH
                           and the application directory.
        """
        self._helper = None
        self.last_merged_tags = {}
        self.exiftool_path = exiftool_path or self._find_exiftool()
        if not self.exiftool_path:
            raise FileNotFoundError(
                "ExifTool not found. Please install it from https://exiftool.org/ "
                "and add it to your PATH or place exiftool.exe in the application folder."
            )

    def close(self):
        """Close any persistent resources if needed."""
        self._helper = None

    def __del__(self):
        self.close()

    def _find_exiftool(self) -> str:
        """Locate the exiftool executable across custom paths, app dir, PATH, and standard folders."""
        return find_exiftool()

    def _run_exiftool_raw(self, args: list) -> str:
        """Run a raw ExifTool command and return stdout."""
        cmd = [self.exiftool_path] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return result.stdout
        except subprocess.TimeoutExpired:
            raise RuntimeError("ExifTool timed out")
        except Exception as e:
            raise RuntimeError(f"ExifTool error: {e}")

    def read_tags(self, image_path: str) -> list:
        """
        Read existing keyword tags from a single image file.
        Returns a deduplicated, alphabetically sorted list of existing tags.
        """
        res = self.read_tags_batch([image_path])
        return res.get(image_path, [])

    def read_tags_batch(self, image_paths: list) -> dict:
        """
        Read existing keyword tags from multiple images in a single batch operation.
        Returns dict of {image_path: [existing_tags]}.
        Reads from IPTC:Keywords, XMP:Subject, XPKeywords, and HierarchicalSubject.
        """
        results = {p: [] for p in image_paths}
        if not image_paths or not self.exiftool_path:
            return results

        # Create temporary argfile for ExifTool batch reading
        arg_lines = [
            "-j",
            "-fast2",
            "-charset", "filename=utf8",
            "-Keywords",
            "-IPTC:Keywords",
            "-Subject",
            "-XMP:Subject",
            "-XPKeywords",
            "-HierarchicalSubject",
            "-CatalogSets",
        ]
        for p in image_paths:
            arg_lines.append(str(Path(p).resolve()))

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as tf:
            tf.write("\n".join(arg_lines) + "\n")
            argfile_path = tf.name

        try:
            output = self._run_exiftool_raw(["-@", argfile_path])
            if output and output.strip():
                raw_str = output.strip()
                s_idx = raw_str.find("[")
                e_idx = raw_str.rfind("]")
                if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                    json_str = raw_str[s_idx : e_idx + 1]
                    data = json.loads(json_str)

                    # Build map by normalized source file
                    record_by_src = {}
                    for record in data:
                        src = record.get("SourceFile", "")
                        if src:
                            norm_src = os.path.normcase(os.path.normpath(src))
                            record_by_src[norm_src] = record

                    for path in image_paths:
                        norm_p = os.path.normcase(os.path.normpath(str(Path(path).resolve())))
                        record = record_by_src.get(norm_p)
                        if not record:
                            norm_raw = os.path.normcase(os.path.normpath(path))
                            record = record_by_src.get(norm_raw, {})

                        all_tags = set()
                        for field_name, val in record.items():
                            if field_name.lower() in ("sourcefile", "exiftoolversion", "error"):
                                continue
                            if isinstance(val, list):
                                for item in val:
                                    if isinstance(item, str):
                                        s = item.strip()
                                        if s:
                                            all_tags.add(s)
                            elif isinstance(val, str) and val.strip():
                                for part in val.replace(";", ",").split(","):
                                    s = part.strip()
                                    if s:
                                        all_tags.add(s)

                        results[path] = self._deduplicate_and_sort(all_tags)
        except Exception:
            pass
        finally:
            try:
                os.remove(argfile_path)
            except Exception:
                pass

        return results

    def write_tags(self, image_path: str, new_tags: list, existing_tags: list = None) -> bool:
        """Write tags to a single image file."""
        res = self.write_tags_batch({image_path: new_tags})
        return res.get(image_path, False)

    def write_tags_batch(self, tag_map: dict, progress_callback=None, merge_with_existing: bool = False) -> dict:
        """
        High-performance batch writing of tags using an ExifTool argument file (-@).
        Processes all images in a single process invocation.
        
        Guarantees:
        1. Writes exact target tags (or merges with existing if merge_with_existing=True).
        2. Any greyed-out/omitted existing tags are removed from IPTC, XMP, and XPKeywords.
        3. Sorts all tags alphabetically across IPTC:Keywords, XMP:Subject, and XPKeywords.
        4. Strictly preserves original file modification and access timestamps.
        """
        results = {p: False for p in tag_map}
        self.last_merged_tags = {}
        total = len(tag_map)
        if total == 0:
            return results

        # 1. Read existing tags in a single batch first
        if progress_callback:
            progress_callback(0, total, "", "Checking existing tags...")
        existing_map = self.read_tags_batch(list(tag_map.keys()))

        # 2. Determine target tags and find files that need changes
        commands_to_run = []
        file_timestamps = {}

        for path, tags in tag_map.items():
            curr_existing = existing_map.get(path, [])
            if merge_with_existing:
                desired = self._merge_and_sort_tags(curr_existing, tags)
            else:
                desired = self._deduplicate_and_sort(tags)

            self.last_merged_tags[path] = desired

            # Compare normalized tags to see if write is actually needed
            norm_existing = [self._normalize(t) for t in curr_existing]
            norm_desired = [self._normalize(t) for t in desired]

            if norm_existing == norm_desired:
                # File already has these exact tags, no write needed
                results[path] = True
                continue

            # Store original timestamps before modification
            try:
                st = os.stat(path)
                file_timestamps[path] = (st.st_atime_ns, st.st_mtime_ns)
            except Exception:
                try:
                    st = os.stat(path)
                    file_timestamps[path] = (int(st.st_atime * 1e9), int(st.st_mtime * 1e9))
                except Exception:
                    pass

            file_args = [
                "-overwrite_original",
                "-P",
                "-charset", "filename=utf8",
                "-IPTC:CodedCharacterSet=UTF8",
                "-IPTC:Keywords=",
                "-XMP:Subject=",
                "-XPKeywords="
            ]
            for t in desired:
                file_args.append(f"-IPTC:Keywords={t}")
                file_args.append(f"-XMP:Subject={t}")
            if desired:
                file_args.append(f"-XPKeywords={'; '.join(desired)}")
            file_args.append(str(Path(path).resolve()))
            file_args.append("-execute")
            commands_to_run.append((path, file_args))

        if not commands_to_run:
            if progress_callback:
                progress_callback(total, total, "", "All tags already up to date ✓")
            return results

        # 3. Write args to temporary argfile for batch execution
        argfile_lines = []
        for _, f_args in commands_to_run:
            argfile_lines.extend(f_args)

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, suffix=".txt") as tf:
            tf.write("\n".join(argfile_lines) + "\n")
            argfile_path = tf.name

        try:
            if progress_callback:
                progress_callback(1, total, "", f"Writing metadata to {len(commands_to_run)} files...")

            output = self._run_exiftool_raw(["-@", argfile_path])

            # Mark updated files
            for path, _ in commands_to_run:
                results[path] = True

            if progress_callback:
                progress_callback(total, total, "", "Metadata write complete ✓")

        except Exception as e:
            if progress_callback:
                progress_callback(total, total, "", f"Metadata write error: {e}")
        finally:
            try:
                os.remove(argfile_path)
            except Exception:
                pass

            # 4. Strictly restore original file modified and accessed timestamps
            for path, (atime_ns, mtime_ns) in file_timestamps.items():
                try:
                    os.utime(path, ns=(atime_ns, mtime_ns))
                except Exception:
                    try:
                        os.utime(path, (atime_ns / 1e9, mtime_ns / 1e9))
                    except Exception:
                        pass

        return results

    @staticmethod
    def _normalize(tag: str) -> str:
        """Normalize tag for deduplication."""
        return tag.strip().lower().replace("_", " ")

    @classmethod
    def _deduplicate_and_sort(cls, tags) -> list:
        """Deduplicate tags case-insensitively and return sorted alphabetically."""
        seen = set()
        result = []
        for t in tags:
            s = str(t).strip().replace("_", " ")
            if not s:
                continue
            k = s.lower()
            if k not in seen:
                seen.add(k)
                result.append(s)
        result.sort(key=lambda x: x.lower())
        return result

    @classmethod
    def _merge_and_sort_tags(cls, existing: list, new_tags: list) -> list:
        """Merge existing and new tags, deduplicate case-insensitively, and sort alphabetically."""
        return cls._deduplicate_and_sort((existing or []) + (new_tags or []))

    @staticmethod
    def is_available(exiftool_path: str = None) -> bool:
        """Check if ExifTool is available."""
        try:
            MetadataHandler(exiftool_path)
            return True
        except FileNotFoundError:
            return False
