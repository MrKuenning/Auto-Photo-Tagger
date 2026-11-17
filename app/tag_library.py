"""
Auto Photo Tagger - Tag Library System
Manages approved and blocked tag libraries.
Translations are embedded as aliases within approved tags.

Libraries are stored as JSON files in the 'config/' directory.

Approved format:
  { "Category": { "tag": ["alias1", "alias2"], "tag2": [] }, ... }

Each approved tag can have zero or more aliases. When the AI produces
an alias, it is automatically translated to the parent tag.
"""

import json
import os
import sys
from pathlib import Path
from collections import OrderedDict


def _resolve_library_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "config").exists():
            return exe_dir / "config"
        if (exe_dir / "tag_libraries").exists():
            return exe_dir / "tag_libraries"
        if hasattr(sys, "_MEIPASS") and (Path(sys._MEIPASS) / "config").exists():
            return Path(sys._MEIPASS) / "config"
        if (exe_dir / "_internal" / "config").exists():
            return exe_dir / "_internal" / "config"
        return exe_dir / "config"
    return Path(__file__).resolve().parent.parent / "config"


LIBRARY_DIR = _resolve_library_dir()

# File paths
APPROVED_FILE = LIBRARY_DIR / "approved_tags.json"
BLOCKED_FILE = LIBRARY_DIR / "blocked_tags.json"
ADVANCED_FILE = LIBRARY_DIR / "advanced_tags.json"
TRANSLATIONS_FILE = LIBRARY_DIR / "translations.json"  # Legacy, for migration

# Tag status constants
TAG_APPROVED = "approved"
TAG_BLOCKED = "blocked"
TAG_TRANSLATED = "translated"
TAG_PENDING = "pending"


class TagLibrary:
    """
    Manages tag libraries:
      - Approved: Tags organized by category, with optional aliases
      - Blocked: Tags automatically removed from results

    Tags not found in any library are marked as 'pending'.
    Aliases on approved tags serve as translations (raw AI tag → parent tag).
    """

    def __init__(self):
        self.approved = {}      # {category: {tag: [aliases], ...}}
        self.blocked = set()    # {tag, tag, ...}
        self.advanced = set()   # {normalized_tag, ...}
        self._load()

    # ── File I/O ──────────────────────────────────────────────────────────

    def _load(self):
        """Load all libraries from disk. Migrate old format if needed."""
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

        if APPROVED_FILE.exists():
            try:
                with open(APPROVED_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                # Detect format: old = {cat: [tags]}, new = {cat: {tag: [aliases]}}
                self.approved = self._parse_approved(raw)
            except (json.JSONDecodeError, IOError):
                self.approved = {}

        if BLOCKED_FILE.exists():
            try:
                with open(BLOCKED_FILE, "r", encoding="utf-8") as f:
                    self.blocked = set(json.load(f))
            except (json.JSONDecodeError, IOError):
                self.blocked = set()

        if ADVANCED_FILE.exists():
            try:
                with open(ADVANCED_FILE, "r", encoding="utf-8") as f:
                    self.advanced = {self.normalize(t) for t in json.load(f) if isinstance(t, str) and t.strip()}
            except (json.JSONDecodeError, IOError):
                self.advanced = set()

        # Migrate legacy translations.json into approved aliases
        if TRANSLATIONS_FILE.exists():
            self._migrate_translations()

        # Create defaults if nothing exists
        if not self.approved and not APPROVED_FILE.exists():
            self.approved = self._default_approved()
            self._save_approved()

        if not self.blocked and not BLOCKED_FILE.exists():
            self.blocked = self._default_blocked()
            self._save_blocked()

        if not ADVANCED_FILE.exists():
            self.advanced = self._default_advanced()
            self._save_advanced()

        # Auto-migrate "Category +" categories into base category + advanced_tags.json
        self._migrate_plus_categories()

        # Clean up any tags that exist as both an alias and a standalone tag
        if self.approved:
            self._cleanup_duplicates()

    def _migrate_plus_categories(self):
        """Migrate any 'Category +' categories into their base category and mark their tags as advanced."""
        plus_cats = [cat for cat in list(self.approved.keys()) if cat.rstrip().endswith("+")]
        if not plus_cats:
            return
        changed = False
        for cat in plus_cats:
            base_cat = cat.rstrip()[:-1].strip()
            if not base_cat:
                continue
            tags_dict = self.approved.pop(cat, {})
            if base_cat not in self.approved:
                self.approved[base_cat] = {}
            for tag, aliases in tags_dict.items():
                self.advanced.add(self.normalize(tag))
                if tag in self.approved[base_cat]:
                    existing = set(self.approved[base_cat][tag])
                    existing.update(aliases)
                    self.approved[base_cat][tag] = sorted(existing)
                else:
                    self.approved[base_cat][tag] = list(aliases)
            changed = True
        if changed:
            self._save_approved()
            self._save_advanced()

    def _cleanup_duplicates(self):
        """Ensure aliases do not exist as independent tags anywhere in the library."""
        aliases = set()
        for cat, tags in self.approved.items():
            for tag, als in tags.items():
                for a in als:
                    aliases.add(self.normalize(a))

        cleaned = False
        for alias in aliases:
            # Remove from approved primary tags
            for cat in list(self.approved.keys()):
                if alias in self.approved[cat]:
                    del self.approved[cat][alias]
                    cleaned = True
            
            # Remove from blocked
            if alias in self.blocked:
                self.blocked.discard(alias)
                cleaned = True

        if cleaned:
            self._save_approved()
            self._save_blocked()

    def _parse_approved(self, raw: dict) -> dict:
        """Parse approved tags, handling both old and new formats."""
        result = {}
        for cat, value in raw.items():
            if isinstance(value, list):
                # Old format: [tag, tag, ...]  → convert to {tag: [], ...}
                result[cat] = {tag: [] for tag in value}
            elif isinstance(value, dict):
                # New format: {tag: [aliases], ...}
                # Ensure all values are lists
                result[cat] = {}
                for tag, aliases in value.items():
                    if isinstance(aliases, list):
                        result[cat][tag] = aliases
                    else:
                        result[cat][tag] = []
            else:
                result[cat] = {}
        return result

    def _migrate_translations(self):
        """Migrate translations.json entries into approved tag aliases."""
        try:
            with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
                translations = json.load(f)
        except (json.JSONDecodeError, IOError):
            return

        if not translations:
            # Empty file, just remove it
            TRANSLATIONS_FILE.rename(TRANSLATIONS_FILE.with_suffix(".json.bak"))
            return

        migrated = 0
        for from_tag, to_tag in translations.items():
            from_norm = self.normalize(from_tag)
            to_norm = self.normalize(to_tag)

            # Find the target tag in approved
            found = False
            for cat, tags in self.approved.items():
                for tag in tags:
                    if self.normalize(tag) == to_norm:
                        # Add alias if not already present
                        existing_aliases = [self.normalize(a) for a in tags[tag]]
                        if from_norm not in existing_aliases:
                            tags[tag].append(from_norm)
                        found = True
                        migrated += 1
                        break
                if found:
                    break

            if not found:
                # Target tag not in approved — skip (it might be a dangling reference)
                pass

        # Save the updated approved library
        self._save_approved()

        # Rename old translations file as backup
        backup = TRANSLATIONS_FILE.with_suffix(".json.bak")
        if backup.exists():
            backup.unlink()
        TRANSLATIONS_FILE.rename(backup)
        print(f"Migrated {migrated} translations into approved tag aliases.")

    def _save_approved(self):
        """Save approved tags to disk."""
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        sorted_lib = OrderedDict()
        for cat in sorted(self.approved.keys()):
            sorted_tags = OrderedDict()
            for tag in sorted(self.approved[cat].keys()):
                sorted_tags[tag] = sorted(self.approved[cat][tag])
            sorted_lib[cat] = sorted_tags
        with open(APPROVED_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted_lib, f, indent=2, ensure_ascii=False)

    def _save_blocked(self):
        """Save blocked tags to disk."""
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        with open(BLOCKED_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(self.blocked), f, indent=2, ensure_ascii=False)

    def _save_advanced(self):
        """Save advanced tag names to disk."""
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        with open(ADVANCED_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(self.advanced), f, indent=2, ensure_ascii=False)

    def save_all(self):
        """Save all libraries."""
        self._save_approved()
        self._save_blocked()
        self._save_advanced()

    def is_advanced(self, tag: str) -> bool:
        """Check if a tag (or its canonical alias parent) is marked as an advanced tag."""
        norm = self.normalize(tag)
        if norm in self.advanced:
            return True
        alias_index = self._build_alias_index()
        if norm in alias_index:
            parent_tag, _ = alias_index[norm]
            return self.normalize(parent_tag) in self.advanced
        return False

    def set_advanced(self, tag: str, enabled: bool = True):
        """Mark or unmark a tag as an advanced tag and persist to disk."""
        norm = self.normalize(tag)
        alias_index = self._build_alias_index()
        if norm in alias_index:
            norm = self.normalize(alias_index[norm][0])
        if enabled:
            self.advanced.add(norm)
        else:
            self.advanced.discard(norm)
        self._save_advanced()

    def toggle_advanced(self, tag: str) -> bool:
        """Toggle the advanced status of a tag and return the new state."""
        new_state = not self.is_advanced(tag)
        self.set_advanced(tag, new_state)
        return new_state

    # ── Alias Lookup Index ────────────────────────────────────────────────

    def _build_alias_index(self) -> dict:
        """Build a reverse lookup: {alias_norm: (parent_tag, category)}."""
        index = {}
        for cat, tags in self.approved.items():
            for tag, aliases in tags.items():
                for alias in aliases:
                    index[self.normalize(alias)] = (tag, cat)
        return index

    # ── Tag Lookup ────────────────────────────────────────────────────────

    def normalize(self, tag: str) -> str:
        """Normalize a tag for consistent lookup."""
        return tag.strip().lower().replace(" ", "_")

    def get_status(self, raw_tag: str) -> tuple:
        """
        Check a raw AI tag against all libraries.

        Returns:
            (status, final_tag, category_or_none)
            status: TAG_APPROVED, TAG_BLOCKED, TAG_TRANSLATED, or TAG_PENDING
            final_tag: the tag to use (may be translated via alias)
            category: which approved category it belongs to (or None)
        """
        normalized = self.normalize(raw_tag)

        # 1. Check blocked first
        if normalized in self.blocked:
            return TAG_BLOCKED, raw_tag, None

        # 2. Check if it's a direct approved tag
        for cat, tags in self.approved.items():
            if normalized in [self.normalize(t) for t in tags]:
                return TAG_APPROVED, raw_tag, cat

        # 3. Check if it's an alias of an approved tag
        alias_index = self._build_alias_index()
        if normalized in alias_index:
            parent_tag, cat = alias_index[normalized]
            return TAG_APPROVED, parent_tag, cat

        # 4. Not found anywhere → pending
        return TAG_PENDING, raw_tag, None

    def process_tags(self, raw_tags: list) -> dict:
        """
        Process a list of raw AI tags through all libraries.

        Returns:
            {
                'approved': [(tag, category), ...],
                'blocked': [tag, ...],
                'translated': [(original, translated), ...],
                'pending': [tag, ...],
                'final_tags': [tag, ...],  # approved + translated, ready to write
            }
        """
        approved = []
        blocked = []
        translated = []
        pending = []
        final_tags = []
        advanced = []
        seen = set()

        alias_index = self._build_alias_index()

        for raw_tag in raw_tags:
            normalized = self.normalize(raw_tag)

            if normalized in self.blocked:
                blocked.append(raw_tag)
                continue

            # Direct approved tag
            found_direct = False
            for cat, tags in self.approved.items():
                if normalized in [self.normalize(t) for t in tags]:
                    if normalized not in seen:
                        approved.append((raw_tag, cat))
                        final_tags.append(raw_tag)
                        if normalized in self.advanced:
                            advanced.append(raw_tag)
                        seen.add(normalized)
                    found_direct = True
                    break

            if found_direct:
                continue

            # Alias match (translation)
            if normalized in alias_index:
                parent_tag, cat = alias_index[normalized]
                parent_norm = self.normalize(parent_tag)
                if parent_norm not in seen:
                    translated.append((raw_tag, parent_tag))
                    approved.append((parent_tag, cat))
                    final_tags.append(parent_tag)
                    if parent_norm in self.advanced:
                        advanced.append(parent_tag)
                    seen.add(parent_norm)
                continue

            # Pending
            if normalized not in seen:
                pending.append(raw_tag)
                if normalized in self.advanced:
                    advanced.append(raw_tag)
                seen.add(normalized)

        return {
            "approved": approved,
            "blocked": blocked,
            "translated": translated,
            "pending": pending,
            "final_tags": final_tags,
            "advanced": advanced,
        }

    # ── Library Modification ──────────────────────────────────────────────

    def approve_tag(self, tag: str, category: str):
        """Add a tag to an approved category."""
        normalized = self.normalize(tag)
        if category not in self.approved:
            self.approved[category] = {}
        # Add if not already present
        existing = [self.normalize(t) for t in self.approved[category]]
        if normalized not in existing:
            self.approved[category][normalized] = []
        # Remove from blocked if present
        self.blocked.discard(normalized)
        self._save_approved()
        self._save_blocked()

    def move_tag(self, tag: str, new_category: str) -> bool:
        """Move an approved tag to a new category while preserving all of its aliases."""
        normalized = self.normalize(tag)
        if new_category not in self.approved:
            self.approved[new_category] = {}

        found_tag_key = None
        aliases = []
        for cat in list(self.approved.keys()):
            for t in list(self.approved[cat].keys()):
                if self.normalize(t) == normalized:
                    found_tag_key = t
                    aliases = list(self.approved[cat][t])
                    del self.approved[cat][t]
                    break
            if found_tag_key is not None:
                break

        if found_tag_key is None:
            found_tag_key = normalized
            aliases = []

        self.approved[new_category][found_tag_key] = aliases
        self._save_approved()
        return True

    def block_tag(self, tag: str):
        """Add a tag to the blocked list."""
        normalized = self.normalize(tag)
        self.blocked.add(normalized)
        # Remove from approved categories
        for cat in self.approved:
            to_remove = [t for t in self.approved[cat] if self.normalize(t) == normalized]
            for t in to_remove:
                del self.approved[cat][t]
        self._save_approved()
        self._save_blocked()

    def add_alias(self, parent_tag: str, alias: str):
        """
        Add an alias to an existing approved tag.
        If the alias was itself an approved tag with its own aliases, all of its
        existing aliases are carried over and merged under the new parent tag.
        """
        alias_norm = self.normalize(alias)
        parent_norm = self.normalize(parent_tag)
        if alias_norm == parent_norm:
            return False

        # 1. Collect any existing aliases that this alias tag had before removing it
        sub_aliases = list(self.get_aliases(alias_norm))

        # 2. Remove alias from approved and blocked lists so it doesn't exist twice
        self.remove_approved(alias_norm)
        self.unblock_tag(alias_norm)

        # 3. Add alias and carry over all of its sub-aliases under parent_tag
        for cat, tags in self.approved.items():
            for tag in tags:
                if self.normalize(tag) == parent_norm:
                    existing_set = set(self.normalize(a) for a in tags[tag])
                    if alias_norm not in existing_set:
                        tags[tag].append(alias_norm)
                        existing_set.add(alias_norm)

                    # Carry over any sub-aliases
                    for sub in sub_aliases:
                        sub_norm = self.normalize(sub)
                        if sub_norm != parent_norm and sub_norm not in existing_set:
                            tags[tag].append(sub_norm)
                            existing_set.add(sub_norm)
                            self.remove_approved(sub_norm)
                            self.unblock_tag(sub_norm)

                    tags[tag].sort()
                    self._save_approved()
                    return True
        return False

    def remove_alias(self, parent_tag: str, alias: str):
        """Remove an alias from an approved tag."""
        alias_norm = self.normalize(alias)
        parent_norm = self.normalize(parent_tag)
        for cat, tags in self.approved.items():
            for tag in tags:
                if self.normalize(tag) == parent_norm:
                    tags[tag] = [a for a in tags[tag] if self.normalize(a) != alias_norm]
                    self._save_approved()
                    return True
        return False

    def get_aliases(self, tag: str) -> list:
        """Get aliases for a given approved tag."""
        normalized = self.normalize(tag)
        for cat, tags in self.approved.items():
            for t, aliases in tags.items():
                if self.normalize(t) == normalized:
                    return aliases
        return []

    def remove_approved(self, tag: str):
        """Remove a tag from approved lists."""
        normalized = self.normalize(tag)
        for cat in self.approved:
            to_remove = [t for t in self.approved[cat] if self.normalize(t) == normalized]
            for t in to_remove:
                del self.approved[cat][t]
        self._save_approved()

    def unblock_tag(self, tag: str):
        """Remove a tag from the blocked list."""
        normalized = self.normalize(tag)
        self.blocked.discard(normalized)
        self._save_blocked()

    def add_category(self, category: str):
        """Add a new approved category."""
        category = category.strip()
        if not category:
            return
        if category not in self.approved:
            self.approved[category] = {}
            self._save_approved()

    def remove_category(self, category: str):
        """Remove an approved category (and all its tags)."""
        category = category.strip()
        self.approved.pop(category, None)
        self._save_approved()

    def rename_category(self, old_name: str, new_name: str) -> bool:
        """Rename an approved category, preserving its tags and position."""
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or not new_name or old_name not in self.approved:
            return False
        if new_name in self.approved and new_name != old_name:
            return False

        new_approved = {}
        for cat, tags in self.approved.items():
            if cat == old_name:
                new_approved[new_name] = tags
            else:
                new_approved[cat] = tags
        self.approved = new_approved
        self._save_approved()
        return True

    def get_all_approved_tags(self) -> set:
        """Get a flat set of all approved tags (normalized)."""
        tags = set()
        for cat_tags in self.approved.values():
            for t in cat_tags:
                tags.add(self.normalize(t))
        return tags

    def get_categories(self) -> list:
        """Get list of approved categories."""
        return sorted(self.approved.keys())

    # ── Statistics ────────────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return library statistics."""
        total_approved = sum(len(tags) for tags in self.approved.values())
        total_aliases = sum(
            len(aliases)
            for tags in self.approved.values()
            for aliases in tags.values()
        )
        return {
            "categories": len(self.approved),
            "approved": total_approved,
            "blocked": len(self.blocked),
            "aliases": total_aliases,
        }

    # ── Default Libraries ─────────────────────────────────────────────────

    @staticmethod
    @staticmethod
    @staticmethod
    def _default_approved() -> dict:
        """Pre-populated approved tags organized by category."""
        return {
            "Body": {
                "abs": [],
                "armpits": [],
                "arms": [],
                "baby": [],
                "back": [],
                "bangs": [],
                "barefoot": [],
                "beard": [],
                "belly": [],
                "black_hair": [],
                "blonde_hair": [],
                "blue_eyes": [],
                "bob_cut": [],
                "braid": ["twin_braids"],
                "brown_eyes": [],
                "brown_hair": [],
                "chest_hair": [],
                "child": [],
                "collarbone": [],
                "curly_hair": [],
                "eyelashes": [],
                "eyes": [],
                "face": [],
                "facial_hair": ["mustache"],
                "feet": [],
                "fingernails": [],
                "fingers": [],
                "floating_hair": [],
                "glowing_eyes": [],
                "green_eyes": [],
                "grey_eyes": [],
                "grey_hair": [],
                "hair": [],
                "hair_bun": ["single_hair_bun"],
                "hairy": ["arm_hair", "body_hair"],
                "hands": [],
                "hips": [],
                "leg_hair": [],
                "legs": [],
                "lipstick": ["black_lips", "red_lips"],
                "long_hair": [],
                "makeup": [],
                "medium_hair": [],
                "midriff": [],
                "mouth": [],
                "muscular": [],
                "nail_polish": ["black_nails", "pink_nails", "red_nails", "toenail_polish"],
                "navel": [],
                "neck": [],
                "nose": [],
                "pale_skin": [],
                "petite": [],
                "pointy_ears": [],
                "ponytail": [],
                "pregnant": [],
                "red_hair": [],
                "short_hair": ["very_short_hair"],
                "shoulders": [],
                "sideburns": [],
                "skin": [],
                "slim": [],
                "spine": [],
                "stomach": [],
                "straight_hair": [],
                "stubble": [],
                "tall": [],
                "tan": [],
                "tattoo": ["arm_tattoo"],
                "teeth": ["sharp_teeth"],
                "toes": [],
                "tongue": [],
                "twintails": [],
                "wavy_hair": [],
                "wet_hair": [],
                "whiskers": [],
                "white_hair": [],
                "wings": [],
            },
            "Clothing": {
                "animal_print": [],
                "apron": ["black_apron", "blue_apron", "brown_apron", "gray_apron", "green_apron", "grey_apron", "navy_apron", "orange_apron", "pink_apron", "purple_apron", "red_apron", "silver_apron", "tan_apron", "white_apron", "yellow_apron"],
                "aqua_dress": [],
                "aqua_shirt": [],
                "armor": [],
                "assisted_exposure": [],
                "bare_legs": [],
                "bare_shoulders": [],
                "beige_pants": [],
                "beige_shirt": [],
                "beige_sweater": [],
                "belt": ["black_belt"],
                "beret": [],
                "bikini": ["black_bikini", "blue_bikini", "brown_bikini", "gold_bikini", "gray_bikini", "green_bikini", "grey_bikini", "navy_bikini", "orange_bikini", "pink_bikini", "print_bikini", "purple_bikini", "red_bikini", "silver_bikini", "tan_bikini", "white_bikini", "yellow_bikini"],
                "black_pants": [],
                "black_shirt": [],
                "black_sweater": [],
                "blouse": ["beige_blouse", "black_blouse", "blue_blouse", "brown_blouse", "gold_blouse", "gray_blouse", "green_blouse", "grey_blouse", "navy_blouse", "orange_blouse", "pink_blouse", "purple_blouse", "red_blouse", "silver_blouse", "tan_blouse", "white_blouse", "yellow_blouse"],
                "blue_pants": [],
                "blue_shirt": [],
                "blue_sweater": [],
                "bodysuit": ["beige_bodysuit", "black_bodysuit", "blue_bodysuit", "brown_bodysuit", "gold_bodysuit", "gray_bodysuit", "green_bodysuit", "grey_bodysuit", "navy_bodysuit", "orange_bodysuit", "pink_bodysuit", "purple_bodysuit", "red_bodysuit", "silver_bodysuit", "tan_bodysuit", "white_bodysuit", "yellow_bodysuit"],
                "bonnet": [],
                "boots": ["beige_boots", "black_boots", "blue_boots", "brown_boots", "gold_boots", "gray_boots", "green_boots", "grey_boots", "high_heel_boots", "navy_boots", "orange_boots", "pink_boots", "purple_boots", "red_boots", "silver_boots", "tan_boots", "thigh_boots", "white_boots", "yellow_boots"],
                "bow": ["hair_bow", "pink_bow"],
                "bowtie": ["beige_bowtie", "black_bowtie", "blue_bowtie", "brown_bowtie", "gold_bowtie", "gray_bowtie", "green_bowtie", "grey_bowtie", "navy_bowtie", "orange_bowtie", "pink_bowtie", "purple_bowtie", "red_bowtie", "silver_bowtie", "tan_bowtie", "white_bowtie", "yellow_bowtie"],
                "bride": [],
                "brown_pants": [],
                "brown_shirt": [],
                "brown_sweater": [],
                "camisole": ["black_camisole", "white_camisole"],
                "camouflage": [],
                "cape": ["beige_cape", "black_cape", "blue_cape", "brown_cape", "gold_cape", "gray_cape", "green_cape", "grey_cape", "navy_cape", "orange_cape", "pink_cape", "purple_cape", "red_cape", "silver_cape", "tan_cape", "white_cape", "yellow_cape"],
                "capri_pants": [],
                "cardigan": ["beige_cardigan", "black_cardigan", "blue_cardigan", "brown_cardigan", "gold_cardigan", "gray_cardigan", "green_cardigan", "grey_cardigan", "navy_cardigan", "orange_cardigan", "pink_cardigan", "purple_cardigan", "red_cardigan", "silver_cardigan", "tan_cardigan", "white_cardigan", "yellow_cardigan"],
                "choker": [],
                "coat": ["beige_coat", "black_coat", "blazer", "blue_coat", "brown_coat", "gold_coat", "gray_coat", "green_coat", "grey_coat", "navy_coat", "orange_coat", "pink_coat", "purple_coat", "red_coat", "silver_coat", "tan_coat", "white_coat", "yellow_coat"],
                "costume": ["cosplay"],
                "crop_top": ["beige_crop_top", "black_crop_top", "blue_crop_top", "brown_crop_top", "gold_crop_top", "gray_crop_top", "green_crop_top", "grey_crop_top", "navy_crop_top", "orange_crop_top", "pink_crop_top", "purple_crop_top", "red_crop_top", "silver_crop_top", "tan_crop_top", "white_crop_top", "yellow_crop_top"],
                "crown": [],
                "denim_shorts": [],
                "dress": ["beige_dress", "black_dress", "blue_dress", "brown_dress", "gold_dress", "gray_dress", "green_dress", "grey_dress", "navy_dress", "orange_dress", "pinafore_dress", "pink_dress", "print_dress", "purple_dress", "red_dress", "silver_dress", "tan_dress", "white_dress", "yellow_dress"],
                "dress_shirt": ["beige_collared_shirt", "black_collared_shirt", "blue_collared_shirt", "brown_collared_shirt", "collared_shirt", "gold_collared_shirt", "gray_collared_shirt", "green_collared_shirt", "grey_collared_shirt", "navy_collared_shirt", "orange_collared_shirt", "pink_collared_shirt", "purple_collared_shirt", "red_collared_shirt", "silver_collared_shirt", "tan_collared_shirt", "white_collared_shirt", "yellow_collared_shirt"],
                "egyptian": ["egyptian_clothes"],
                "elbow_gloves": [],
                "fishnets": [],
                "floral_print": [],
                "frilled_shirt": [],
                "frills": [],
                "glasses": ["adjusting_eyewear", "black-framed_eyewear", "eyewear_hang", "eyewear_on_head", "hand_on_eyewear", "holding_removed_eyewear", "over-rim_eyewear", "red-framed_eyewear", "round_eyewear", "unworn_eyewear", "white-framed_eyewear"],
                "gloves": ["beige_gloves", "black_gloves", "blue_gloves", "brown_gloves", "gold_gloves", "gray_gloves", "green_gloves", "grey_gloves", "latex_gloves", "navy_gloves", "orange_gloves", "pink_gloves", "purple_gloves", "red_gloves", "silver_gloves", "tan_gloves", "white_gloves", "yellow_gloves"],
                "gold_pants": [],
                "gold_shirt": [],
                "gold_sweater": [],
                "gray_pants": [],
                "gray_shirt": [],
                "gray_sweater": [],
                "greco-roman_clothes": [],
                "green_pants": [],
                "green_shirt": [],
                "green_sweater": [],
                "grey_pants": [],
                "grey_shirt": [],
                "grey_sweater": [],
                "hair_flower": ["head_wreath"],
                "hair_ribbon": [],
                "hairband": ["red_hairband"],
                "hairclip": ["hair_ornament"],
                "halter_top": ["beige_halter_top", "black_halter_top", "blue_halter_top", "brown_halter_top", "gold_halter_top", "gray_halter_top", "green_halter_top", "grey_halter_top", "navy_halter_top", "orange_halter_top", "pink_halter_top", "purple_halter_top", "red_halter_top", "silver_halter_top", "tan_halter_top", "white_halter_top", "yellow_halter_top"],
                "hat": ["baseball_cap", "beanie", "beige_hat", "black_hat", "black_headwear", "blue_hat", "brown_hat", "cap", "gold_hat", "gray_hat", "green_hat", "grey_hat", "navy_hat", "orange_hat", "pink_hat", "purple_hat", "red_hat", "silver_hat", "tan_hat", "white_hat", "white_headwear", "yellow_hat"],
                "headband": [],
                "heart_cutout": [],
                "helmet": [],
                "high_heels": ["beige_high_heels", "black_high_heels", "blue_high_heels", "brown_high_heels", "gold_high_heels", "gray_high_heels", "green_high_heels", "grey_high_heels", "navy_high_heels", "orange_high_heels", "pink_high_heels", "purple_high_heels", "red_high_heels", "silver_high_heels", "tan_high_heels", "white_high_heels", "yellow_high_heels"],
                "hoodie": ["beige_hoodie", "black_hoodie", "blue_hoodie", "brown_hoodie", "gold_hoodie", "gray_hoodie", "green_hoodie", "grey_hoodie", "navy_hoodie", "orange_hoodie", "pink_hoodie", "purple_hoodie", "red_hoodie", "silver_hoodie", "tan_hoodie", "white_hoodie", "yellow_hoodie"],
                "jacket": ["beige_jacket", "black_jacket", "blue_jacket", "brown_jacket", "gold_jacket", "gray_jacket", "green_jacket", "grey_jacket", "navy_jacket", "open_jacket", "orange_jacket", "pink_jacket", "purple_jacket", "red_jacket", "silver_jacket", "tan_jacket", "white_jacket", "yellow_jacket"],
                "jeans": ["beige_jeans", "black_jeans", "blue_jeans", "brown_jeans", "denim", "gold_jeans", "gray_jeans", "green_jeans", "grey_jeans", "navy_jeans", "orange_jeans", "pink_jeans", "purple_jeans", "red_jeans", "silver_jeans", "tan_jeans", "white_jeans", "yellow_jeans"],
                "jewelry": ["armlet", "bracelet", "gold_jewelry", "silver_jewelry"],
                "kneehighs": ["beige_kneehighs", "black_kneehighs", "blue_kneehighs", "brown_kneehighs", "gold_kneehighs", "gray_kneehighs", "green_kneehighs", "grey_kneehighs", "navy_kneehighs", "orange_kneehighs", "pink_kneehighs", "purple_kneehighs", "red_kneehighs", "silver_kneehighs", "tan_kneehighs", "white_kneehighs", "yellow_kneehighs"],
                "lace": [],
                "lace_trim": ["lace-trimmed_legwear"],
                "latex": [],
                "leggings": ["beige_leggings", "black_leggings", "blue_leggings", "brown_leggings", "gold_leggings", "gray_leggings", "green_leggings", "grey_leggings", "navy_leggings", "orange_leggings", "pink_leggings", "purple_leggings", "red_leggings", "silver_leggings", "tan_leggings", "white_leggings", "yellow_leggings", "yoga_pants"],
                "leotard": ["beige_leotard", "black_leotard", "blue_leotard", "brown_leotard", "gold_leotard", "gray_leotard", "green_leotard", "grey_leotard", "navy_leotard", "orange_leotard", "pink_leotard", "purple_leotard", "red_leotard", "silver_leotard", "tan_leotard", "white_leotard", "yellow_leotard"],
                "long_skirt": [],
                "mask": [],
                "miniskirt": ["beige_miniskirt", "black_miniskirt", "blue_miniskirt", "brown_miniskirt", "gold_miniskirt", "gray_miniskirt", "green_miniskirt", "grey_miniskirt", "navy_miniskirt", "orange_miniskirt", "pink_miniskirt", "purple_miniskirt", "red_miniskirt", "silver_miniskirt", "tan_miniskirt", "white_miniskirt", "yellow_miniskirt"],
                "navy_pants": [],
                "navy_shirt": [],
                "navy_sweater": [],
                "necklace": ["gold_necklace", "pearl_necklace"],
                "necktie": ["beige_necktie", "black_necktie", "blue_necktie", "brown_necktie", "gold_necktie", "gray_necktie", "green_necktie", "grey_necktie", "navy_necktie", "orange_necktie", "pink_necktie", "purple_necktie", "red_necktie", "silver_necktie", "striped_necktie", "tan_necktie", "white_necktie", "yellow_necktie"],
                "nightgown": ["beige_nightgown", "black_nightgown", "blue_nightgown", "brown_nightgown", "gold_nightgown", "gray_nightgown", "green_nightgown", "grey_nightgown", "navy_nightgown", "orange_nightgown", "pink_nightgown", "purple_nightgown", "red_nightgown", "silver_nightgown", "tan_nightgown", "white_nightgown", "yellow_nightgown"],
                "one-piece_swimsuit": ["black_one-piece_swimsuit", "casual_one-piece_swimsuit"],
                "orange_pants": [],
                "orange_shirt": [],
                "orange_sweater": [],
                "overalls": ["blue_overalls"],
                "pajamas": ["beige_pajamas", "black_pajamas", "blue_pajamas", "brown_pajamas", "gold_pajamas", "gray_pajamas", "green_pajamas", "grey_pajamas", "navy_pajamas", "orange_pajamas", "pink_pajamas", "purple_pajamas", "red_pajamas", "silver_pajamas", "tan_pajamas", "white_pajamas", "yellow_pajamas"],
                "panties_under_pantyhose": [],
                "pants": [],
                "partially_nude": [],
                "pencil_skirt": [],
                "piercing": ["navel_piercing"],
                "pink_pants": [],
                "pink_shirt": [],
                "pink_sweater": [],
                "plaid": ["plaid_shirt", "plaid_skirt"],
                "pleated_skirt": [],
                "polka_dot": ["polka_dot_dress", "polka_dot_shirt"],
                "puffy_sleeves": ["puffy_short_sleeves"],
                "purple_pants": [],
                "purple_shirt": [],
                "purple_sweater": [],
                "red_pants": [],
                "red_shirt": [],
                "red_sweater": [],
                "ribbon": [],
                "robe": ["beige_robe", "black_robe", "blue_robe", "brown_robe", "gold_robe", "gray_robe", "green_robe", "grey_robe", "navy_robe", "orange_robe", "pink_robe", "purple_robe", "red_robe", "silver_robe", "tan_robe", "white_robe", "yellow_robe"],
                "sailor_collar": [],
                "sandals": ["brown_sandals"],
                "sash": ["red_sash"],
                "scarf": ["beige_scarf", "black_scarf", "blue_scarf", "brown_scarf", "gold_scarf", "gray_scarf", "green_scarf", "grey_scarf", "navy_scarf", "orange_scarf", "pink_scarf", "purple_scarf", "red_scarf", "silver_scarf", "tan_scarf", "white_scarf", "yellow_scarf"],
                "school_uniform": [],
                "shirt": ["print_shirt", "striped_shirt"],
                "shoes": ["black_shoes"],
                "short_shorts": [],
                "shorts": ["beige_shorts", "black_shorts", "blue_shorts", "brown_shorts", "gold_shorts", "gray_shorts", "green_shorts", "grey_shorts", "navy_shorts", "orange_shorts", "pink_shorts", "purple_shorts", "red_shorts", "silver_shorts", "tan_shorts", "white_shorts", "yellow_shorts"],
                "silver_pants": [],
                "silver_shirt": [],
                "silver_sweater": [],
                "skirt": ["beige_skirt", "black_skirt", "blue_skirt", "brown_skirt", "gold_skirt", "gray_skirt", "green_skirt", "grey_skirt", "navy_skirt", "orange_skirt", "pink_skirt", "purple_skirt", "red_skirt", "silver_skirt", "tan_skirt", "white_skirt", "yellow_skirt"],
                "sleeveless": ["sleeveless_dress", "sleeveless_shirt"],
                "sneakers": ["white_sneakers"],
                "socks": ["beige_socks", "black_socks", "blue_socks", "brown_socks", "gold_socks", "gray_socks", "green_socks", "grey_socks", "navy_socks", "orange_socks", "pink_socks", "purple_socks", "red_socks", "silver_socks", "tan_socks", "white_socks", "yellow_socks"],
                "spaghetti_strap": [],
                "stockings": ["black_stockings", "white_stockings"],
                "string_bikini": ["side-tie_bikini_bottom"],
                "suit": ["black_suit", "white_suit"],
                "sunglasses": ["aviator_sunglasses"],
                "superhero": [],
                "suspenders": [],
                "sweater": ["ribbed_sweater"],
                "swimsuit": ["beige_swimsuit", "black_swimsuit", "blue_swimsuit", "brown_swimsuit", "gold_swimsuit", "gray_swimsuit", "green_swimsuit", "grey_swimsuit", "navy_swimsuit", "orange_swimsuit", "pink_swimsuit", "purple_swimsuit", "red_swimsuit", "silver_swimsuit", "tan_swimsuit", "white_swimsuit", "yellow_swimsuit"],
                "t-shirt": ["beige_t-shirt", "black_t-shirt", "blue_t-shirt", "brown_t-shirt", "gold_t-shirt", "gray_t-shirt", "green_t-shirt", "grey_t-shirt", "navy_t-shirt", "orange_t-shirt", "pink_t-shirt", "purple_t-shirt", "red_t-shirt", "silver_t-shirt", "tan_t-shirt", "white_t-shirt", "yellow_t-shirt"],
                "tan_pants": [],
                "tan_shirt": [],
                "tan_sweater": [],
                "tank_top": ["beige_tank_top", "black_tank_top", "blue_tank_top", "brown_tank_top", "gold_tank_top", "gray_tank_top", "green_tank_top", "grey_tank_top", "navy_tank_top", "orange_tank_top", "pink_tank_top", "purple_tank_top", "red_tank_top", "silver_tank_top", "tan_tank_top", "white_tank_top", "yellow_tank_top"],
                "tiara": [],
                "tie": ["beige_tie", "black_tie", "blue_tie", "brown_tie", "gold_tie", "gray_tie", "green_tie", "grey_tie", "navy_tie", "orange_tie", "pink_tie", "purple_tie", "red_tie", "silver_tie", "tan_tie", "white_tie", "yellow_tie"],
                "towel": [],
                "towel_on_head": [],
                "tube_top": ["beige_tube_top", "black_tube_top", "blue_tube_top", "brown_tube_top", "gold_tube_top", "gray_tube_top", "green_tube_top", "grey_tube_top", "navy_tube_top", "orange_tube_top", "pink_tube_top", "purple_tube_top", "red_tube_top", "silver_tube_top", "tan_tube_top", "white_tube_top", "yellow_tube_top"],
                "turtleneck": ["beige_turtleneck", "black_turtleneck", "blue_turtleneck", "brown_turtleneck", "gold_turtleneck", "gray_turtleneck", "green_turtleneck", "grey_turtleneck", "navy_turtleneck", "orange_turtleneck", "pink_turtleneck", "purple_turtleneck", "red_turtleneck", "silver_turtleneck", "tan_turtleneck", "turtleneck_sweater", "white_turtleneck", "yellow_turtleneck"],
                "tuxedo": [],
                "uniform": [],
                "veil": ["bridal_veil"],
                "vest": ["beige_vest", "black_vest", "blue_vest", "brown_vest", "gold_vest", "gray_vest", "green_vest", "grey_vest", "navy_vest", "orange_vest", "pink_vest", "purple_vest", "red_vest", "silver_vest", "tan_vest", "white_vest", "yellow_vest"],
                "wedding_dress": [],
                "wet_clothes": ["wet_shirt"],
                "white_pants": [],
                "white_shirt": [],
                "white_sweater": [],
                "yellow_pants": [],
                "yellow_shirt": [],
                "yellow_sweater": [],
            },
            "Objects / Props": {
                "american_flag": [],
                "animal": [],
                "aurora": [],
                "axe": ["holding_axe"],
                "backpack": [],
                "bag": ["black_bag", "handbag"],
                "basket": [],
                "bicycle": [],
                "bird": [],
                "blanket": [],
                "book": ["holding_book", "magazine_(object)", "newspaper"],
                "bottle": [],
                "bouquet": ["holding_bouquet"],
                "bubbles": ["air_bubble", "bubble"],
                "cable": [],
                "cake": ["birthday_cake"],
                "camera": [],
                "candle": [],
                "candy": [],
                "candy_cane": [],
                "car": [],
                "cat": [],
                "caustics": [],
                "christmas_tree": [],
                "clock": ["wall_clock"],
                "computer": ["keyboard_(computer)", "monitor"],
                "cosmetics": ["makeup_brush", "perfume_bottle"],
                "cup": [],
                "curtain": [],
                "dildo": [],
                "dog": [],
                "dragon": ["eastern_dragon"],
                "drink": ["coffee_cup", "drink_can", "soda_can"],
                "earrings": ["hoop_earrings"],
                "fan": [],
                "fire": ["burning", "embers"],
                "fish": [],
                "flag": ["flag_background", "flag_print", "french_flag"],
                "flower": ["flower_field", "red_flower"],
                "food": ["holding_food"],
                "frog": [],
                "game_console": ["handheld_game_console"],
                "glass": ["drinking_glass"],
                "grass": [],
                "gun": [],
                "harp": [],
                "headphones": [],
                "holly": [],
                "house": [],
                "ice_cream": ["ice_cream_cone"],
                "instrument": ["holding_instrument", "playing_instrument"],
                "lamp": [],
                "laptop": [],
                "laundry": ["laundry_basket"],
                "locker": ["locker_room"],
                "magazine": [],
                "milking_machine": [],
                "motor_vehicle": [],
                "motorcycle": [],
                "multiple_girls": [],
                "object_insertion": ["vvaginal_object_insertion"],
                "painting_(object)": ["canvas_(object)", "easel"],
                "paper": [],
                "pen": [],
                "phone": ["cellphone", "holding_phone", "smartphone"],
                "pillow": [],
                "pine_tree": [],
                "pink_flower": [],
                "plant": [],
                "plate": [],
                "purple_flower": [],
                "purse": [],
                "reindeer": [],
                "ring": ["ornate_ring"],
                "rock": [],
                "rose": [],
                "sex_toy": [],
                "shark": [],
                "sign": [],
                "silverware": ["fork", "holding_spoon", "knife", "spoon"],
                "spear": ["holding_polearm", "polearm"],
                "star_(symbol)": [],
                "sword": ["energy_sword", "holding_sword"],
                "table": ["tablecloth", "wooden_table"],
                "teacup": [],
                "teapot": [],
                "television": [],
                "throne": [],
                "toilet_paper": [],
                "toothbrush": [],
                "toy": [],
                "tree": [],
                "truck": [],
                "tulip": [],
                "umbrella": [],
                "vase": [],
                "vibrator": [],
                "watch": ["wristwatch"],
                "water": [],
                "weapon": ["glowing_weapon", "holding_weapon"],
                "white_flower": ["white_rose"],
                "wine": [],
                "wine_glass": [],
                "yellow_flower": [],
            },
            "Pose / Expression": {
                "adjusting_hair": [],
                "all_fours": [],
                "angry": [],
                "arm_behind_back": [],
                "arms_at_sides": [],
                "arms_behind_back": [],
                "arms_up": ["arm_behind_head", "arm_up", "arms_behind_head", "hands_up", "holding_hair", "washing_hair"],
                "bent_over": [],
                "blush": [],
                "brushing_teeth": [],
                "carrying": ["princess_carry"],
                "cheek-to-cheek": ["heads_together"],
                "close-up": [],
                "closed_eyes": [],
                "clothes_in_mouth": ["mouth_hold"],
                "cowboy_shot": [],
                "crossed_arms": [],
                "crossed_legs": [],
                "crying": [],
                "driving": [],
                "eating": [],
                "embarrassed": [],
                "facing_away": [],
                "falling": [],
                "flexible": [],
                "food_focus": [],
                "foot_focus": [],
                "from_above": [],
                "from_behind": [],
                "from_below": [],
                "from_side": [],
                "frown": [],
                "full_body": [],
                "grabbing": [],
                "grin": [],
                "hand_on_hip": ["hand_on_own_hip", "hands_on_own_hips"],
                "happy": [],
                "head_out_of_frame": [],
                "holding_hands": [],
                "hug": ["arm_around_neck", "arm_around_shoulder", "arm_around_waist"],
                "hug_from_behind": [],
                "jumping": [],
                "kiss": [],
                "kissing_cheek": ["licking_another's_face"],
                "kneeling": [],
                "laughing": [],
                "leaning": [],
                "leaning_back": [],
                "leaning_forward": [],
                "looking_at_mirror": [],
                "looking_at_phone": [],
                "looking_at_viewer": [],
                "looking_away": [],
                "looking_back": [],
                "looking_down": [],
                "looking_to_the_side": [],
                "looking_up": [],
                "lower_body": [],
                "lying": [],
                "on_back": [],
                "on_floor": [],
                "on_side": [],
                "on_stomach": [],
                "open_mouth": ["parted_lips"],
                "outstretched_arm": [],
                "partially_submerged": [],
                "portrait": [],
                "profile": [],
                "reading": [],
                "reclining": [],
                "running": [],
                "serious": [],
                "shy": [],
                "sitting": [],
                "sleeping": [],
                "smile": [],
                "splits": ["split"],
                "squatting": [],
                "standing": [],
                "surprised": [],
                "swimming": [],
                "tiptoes": [],
                "upper_body": [],
                "upside-down": [],
                "walking": [],
                "wink": [],
            },
            "Setting / Background": {
                "alley": [],
                "arch": [],
                "autumn": [],
                "autumn_leaves": [],
                "backlighting": [],
                "balcony": [],
                "bathroom": ["shower_(place)", "shower_head"],
                "bathtub": ["bath"],
                "beach": [],
                "bed_sheet": [],
                "bedroom": ["bed", "on_bed"],
                "black_and_white": ["greyscale"],
                "black_background": [],
                "blurry": [],
                "blurry_background": [],
                "bokeh": [],
                "bookshelf": [],
                "border": ["white_border"],
                "building": [],
                "candid": [],
                "car_interior": [],
                "cave": [],
                "chair": ["on_chair", "wooden_chair"],
                "christmas": [],
                "city": ["cityscape", "skyscraper"],
                "classroom": [],
                "closet": [],
                "clouds": ["cloud", "cloudy", "cloudy_sky", "dark_clouds"],
                "couch": ["on_couch"],
                "curtains": [],
                "dark": [],
                "day": [],
                "depth_of_field": [],
                "desert": [],
                "detailed": [],
                "door": [],
                "family": [],
                "fantasy": [],
                "fence": [],
                "field": [],
                "film_grain": [],
                "floor": [],
                "fog": [],
                "footprints": [],
                "foreshortening": [],
                "forest": [],
                "garden": [],
                "glowing": [],
                "gradient_background": [],
                "gym": [],
                "high_resolution": [],
                "horizon": [],
                "ice": [],
                "indoors": [],
                "kitchen": [],
                "lake": [],
                "landscape": [],
                "lava": [],
                "leaf": [],
                "lens_flare": [],
                "lightning": [],
                "livestream": [],
                "living_room": [],
                "meme": [],
                "mirror": [],
                "monochrome": [],
                "moon": ["full_moon", "red_moon"],
                "motion_blur": [],
                "mountain": ["mountainous_horizon"],
                "music": [],
                "natural_lighting": [],
                "nature": [],
                "night": [],
                "night_sky": ["milky_way", "star_(sky)", "starry_sky"],
                "no_humans": [],
                "nsfw": ["uncensored"],
                "ocean": ["waves"],
                "office": [],
                "outdoors": [],
                "park": [],
                "photo": [],
                "pool": [],
                "pov": [],
                "rain": [],
                "reflection": [],
                "reflective_water": [],
                "restaurant": [],
                "river": [],
                "road": [],
                "rooftop": [],
                "sand": [],
                "selfie": [],
                "sepia": [],
                "silhouette": [],
                "simple_background": ["blue_background", "green_background", "grey_background", "pink_background", "yellow_background"],
                "sink": [],
                "sky": ["gradient_sky"],
                "snow": [],
                "snowflakes": [],
                "soap_bubbles": [],
                "stairs": [],
                "still_life": [],
                "storm": [],
                "street": [],
                "studio_lighting": [],
                "sunny": [],
                "sunrise": [],
                "sunset": ["dusk", "evening", "orange_sky", "red_sky", "twilight"],
                "tile_floor": [],
                "toilet": [],
                "underwater": [],
                "vintage": [],
                "wall": [],
                "washing_machine": [],
                "waterfall": [],
                "wedding": [],
                "white_background": [],
                "window": [],
                "winter": [],
                "wooden_floor": [],
            },
            "Subject / Character": {
                "creature": [],
                "fairy": ["fairy_wings"],
                "man": ["1boy", "fat_man", "mature_male", "old_man", "ugly_man"],
                "men": ["2boys", "3boys", "4boys", "5boys", "6+boys"],
                "princess": [],
                "woman": ["1girl", "mature_female", "old_woman"],
                "women": ["2girls", "3girls", "4girls"],
            },
        }

    @staticmethod
    def _default_blocked() -> set:
        """Tags that are blocked/suppressed by default."""
        return {
            "1other",
            "4koma",
            "^_^",
            "absurdres",
            "afro",
            "age_difference",
            "aged_down",
            "ahoge",
            "air_conditioner",
            "animal_ears",
            "animal_focus",
            "anime",
            "animification",
            "anklet",
            "annotated",
            "arm_support",
            "armband",
            "armpit_hair",
            "artist_name",
            "ashtray",
            "asian",
            "bad_id",
            "bad_link",
            "bad_source",
            "badge",
            "bald",
            "bandaid",
            "bandaid_on_face",
            "bandaid_on_nose",
            "bara",
            "bare_pectorals",
            "beer_can",
            "bib",
            "bikini_tan",
            "black_buruma",
            "black_eyes",
            "black_footwear",
            "blue",
            "blue_buruma",
            "blue_hair",
            "blue_sky",
            "blue_theme",
            "body_freckles",
            "bracer",
            "bread",
            "breast_pocket",
            "brother_and_sister",
            "brown_footwear",
            "bulge",
            "buruma",
            "buttons",
            "buzz_cut",
            "can",
            "carpet",
            "cel_shading",
            "censored",
            "check_translation",
            "checkered_shirt",
            "chibi",
            "child_on_child",
            "chopsticks",
            "chris_redfield",
            "cigarette",
            "cigarette_pack",
            "clenched_hand",
            "closed_mouth",
            "clothes",
            "clothes_hanger",
            "colored_skin",
            "column",
            "comic",
            "commentary",
            "commentary_request",
            "commentary_typo",
            "condom",
            "condom_wrapper",
            "controller",
            "copyright_name",
            "couple",
            "covered_eyes",
            "covering_privates",
            "crossdressing",
            "dark-skinned_female",
            "dark-skinned_male",
            "dark_background",
            "dark_skin",
            "dated",
            "denim_jacket",
            "detached_sleeves",
            "diaper",
            "dirty",
            "dirty_feet",
            "domino_mask",
            "doorway",
            "double_bun",
            "doujinshi",
            "drawer",
            "drawing_(object)",
            "elderly",
            "english_text",
            "faceless",
            "father_and_daughter",
            "father_and_son",
            "faucet",
            "faux_traditional_media",
            "feet_out_of_frame",
            "female",
            "female_pov",
            "figure",
            "fine_art_parody",
            "fine_fabric_emphasis",
            "fingerless_gloves",
            "flat_color",
            "forehead",
            "formal",
            "freckles",
            "front-tie_top",
            "fruit",
            "fur_trim",
            "genderswap",
            "genderswap_(mtf)",
            "glitch",
            "good_end",
            "green_hair",
            "green_theme",
            "grey_sky",
            "grey_theme",
            "group",
            "habit",
            "hair_over_eyes",
            "halo",
            "hand_fan",
            "hand_focus",
            "hand_in_pocket",
            "hand_on_another's_head",
            "hand_on_another's_shoulder",
            "hand_up",
            "hands_in_pockets",
            "hands_on_ground",
            "hands_on_own_face",
            "hanging",
            "head_tilt",
            "hetero",
            "highres",
            "holding",
            "holding_can",
            "holding_flower",
            "holding_stylus",
            "hood",
            "horror_(theme)",
            "husband_and_wife",
            "if_they_mated",
            "imminent_kiss",
            "incredibly_absurdres",
            "japanese_clothes",
            "key_visual",
            "kimono",
            "kneepits",
            "large_pectorals",
            "layered_sleeves",
            "left",
            "legs_together",
            "licking",
            "lineart",
            "lips",
            "loli",
            "long_sleeves",
            "looking_at_another",
            "lowres",
            "male",
            "male_focus",
            "manga",
            "manly",
            "mary_janes",
            "mature",
            "middle_finger",
            "milk_carton",
            "mixed-sex_bathing",
            "model_kit",
            "mole",
            "mole_on_arm",
            "mole_on_ass",
            "mole_on_body",
            "mole_on_breast",
            "mole_on_stomach",
            "mole_on_thigh",
            "mosaic_censoring",
            "mother_and_daughter",
            "mouth_mask",
            "multicolored_clothes",
            "multicolored_dress",
            "multicolored_hair",
            "multiple_boys",
            "multiple_girls",
            "multiple_rings",
            "muscular_male",
            "name_tag",
            "napkin",
            "navel_hair",
            "no_shoes",
            "nun",
            "o-ring",
            "office_lady",
            "official_art",
            "old",
            "one_eye_closed",
            "onee-loli",
            "onii-shota",
            "open_door",
            "open_fly",
            "out-of-frame_censoring",
            "out_of_frame",
            "own_hands_together",
            "painting_(medium)",
            "panel",
            "parody",
            "partially_translated",
            "pasta",
            "path",
            "pectoral_grab",
            "pectorals",
            "photo_(object)",
            "photo_background",
            "photo_inset",
            "photorealistic",
            "picture_frame",
            "pillar",
            "pink_hair",
            "pixiv_id",
            "pocket",
            "pointing",
            "portrait_(object)",
            "poster_(object)",
            "potted_plant",
            "pov_across_table",
            "power_lines",
            "promotional_art",
            "pulled_by_self",
            "pussy_juice",
            "randoseru",
            "real_life_insert",
            "realistic",
            "red_skin",
            "red_theme",
            "reference_inset",
            "rice_paddy",
            "right",
            "right_side",
            "rough",
            "rug",
            "sample",
            "scan",
            "scenery",
            "seductive",
            "shadow",
            "shampoo_bottle",
            "shiny_skin",
            "short_over_long_sleeves",
            "short_sleeves",
            "shota",
            "siblings",
            "side",
            "signature",
            "sitting_on_lap",
            "sitting_on_person",
            "size_difference",
            "sketch",
            "sleeves_past_wrists",
            "soap",
            "soles",
            "solo",
            "solo_focus",
            "speech_bubble",
            "steering_wheel",
            "strawberry_print",
            "striped_clothes",
            "stud_earrings",
            "stuffed_toy",
            "stylus",
            "sun",
            "sunlight",
            "super_deformed",
            "swept_bangs",
            "tanlines",
            "tape_measure",
            "their",
            "they",
            "thought_bubble",
            "tile_wall",
            "tiles",
            "tissue",
            "tissue_box",
            "toenails",
            "tongue_out",
            "traditional_media",
            "translated",
            "translation_request",
            "trash_bag",
            "trash_can",
            "tray",
            "twitter_username",
            "two-tone_hair",
            "under_covers",
            "unknown_tag_xyz",
            "unworn_clothes",
            "unworn_shirt",
            "unworn_shoes",
            "v",
            "vehicle_focus",
            "veins",
            "virtual_youtuber",
            "wariza",
            "watermark",
            "wearing",
            "web_address",
            "wedding_ring",
            "weight_conscious",
            "what",
            "white",
            "white_footwear",
            "window_blinds",
            "wrinkled_skin",
            "yaoi",
            "year",
            "yellow_eyes",
            "young",
            "yuri",
            "zipper",
        }

    @staticmethod
    def _default_advanced() -> set:
        """Tags flagged as Advanced by default (empty for clean installs)."""
        return set()
