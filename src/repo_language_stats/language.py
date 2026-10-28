"""Language classification and binary detection based on GitHub Linguist data."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml


# Common binary file extensions that should never be counted as source code
BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Images
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".ico",
        ".webp",
        ".bmp",
        ".tiff",
        ".tif",
        ".svgz",
        ".psd",
        ".ai",
        # Audio & Video
        ".mp3",
        ".wav",
        ".ogg",
        ".flac",
        ".aac",
        ".m4a",
        ".wma",
        ".mp4",
        ".mkv",
        ".avi",
        ".mov",
        ".wmv",
        ".flv",
        ".webm",
        # Archives & Compressed
        ".zip",
        ".tar",
        ".gz",
        ".tgz",
        ".bz2",
        ".tbz2",
        ".xz",
        ".txz",
        ".7z",
        ".rar",
        ".zst",
        # Binaries & Libraries
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".iso",
        ".dmg",
        ".app",
        # Compiled Bytecode / Objects
        ".class",
        ".o",
        ".obj",
        ".pyc",
        ".pyo",
        ".pyd",
        ".wasm",
        # Fonts
        ".ttf",
        ".otf",
        ".woff",
        ".woff2",
        ".eot",
        # Documents & Media
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        # Databases & Keystores
        ".db",
        ".sqlite",
        ".sqlite3",
        ".p12",
        ".pfx",
        ".keystore",
        ".jks",
    }
)

# Overrides for common ambiguous extensions to ensure the primary programming language is selected
PRIMARY_EXTENSION_OVERRIDES: dict[str, str] = {
    ".rs": "Rust",
    ".php": "PHP",
    ".cs": "C#",
    ".sql": "SQL",
    ".ts": "TypeScript",
    ".tsx": "TSX",
    ".h": "C",
    ".hpp": "C++",
    ".r": "R",
    ".m": "Objective-C",
    ".pl": "Perl",
    ".html": "HTML",
    ".htm": "HTML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".json": "JSON",
}

# Language naming adjustments for common CLI display expectations
LANGUAGE_NAME_OVERRIDES: dict[str, str] = {
    "Makefile": "Make",
}


def _get_data_path(filename: str) -> Path:
    """Resolve the path to a vendored data file."""
    path = Path(__file__).resolve().parent / "data" / filename
    if path.exists():
        return path
    try:
        from importlib.resources import files

        return Path(str(files("repo_language_stats.data").joinpath(filename)))
    except Exception:
        return path


class LanguageClassifier:
    """Classifies files into programming languages using Linguist data."""

    def __init__(self, data_file: Path | str | None = None) -> None:
        if data_file is None:
            self._data_file = _get_data_path("languages.yml")
        else:
            self._data_file = Path(data_file)

        self._languages_data: dict[str, dict[str, Any]] = {}
        self._extension_map: dict[str, str] = {}
        self._filename_map: dict[str, str] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load and index the languages.yml Linguist dataset."""
        if not self._data_file.exists():
            return

        with open(self._data_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._languages_data = data

        # Track programming languages vs others for disambiguation
        ext_to_langs: dict[str, list[tuple[str, str]]] = {}

        for raw_lang_name, info in data.items():
            lang_type = info.get("type", "programming")
            display_name = LANGUAGE_NAME_OVERRIDES.get(raw_lang_name, raw_lang_name)

            # Map exact filenames
            for fname in info.get("filenames", []):
                self._filename_map[fname] = display_name

            # Collect extensions
            for ext in info.get("extensions", []):
                lower_ext = ext.lower()
                if lower_ext not in ext_to_langs:
                    ext_to_langs[lower_ext] = []
                ext_to_langs[lower_ext].append((display_name, lang_type))

        # Build extension map
        for ext, candidates in ext_to_langs.items():
            # Check explicit override first
            if ext in PRIMARY_EXTENSION_OVERRIDES:
                self._extension_map[ext] = PRIMARY_EXTENSION_OVERRIDES[ext]
                continue

            # Prioritize 'programming' languages over markup/data/prose
            prog_candidates = [name for name, t in candidates if t == "programming"]
            if prog_candidates:
                self._extension_map[ext] = prog_candidates[0]
            else:
                self._extension_map[ext] = candidates[0][0]

    def is_binary(self, path: str | Path, content: bytes | None = None) -> bool:
        """Check if a file is binary by extension or null-byte content."""
        p = Path(path)
        ext = p.suffix.lower()

        # Check common binary extensions
        if ext in BINARY_EXTENSIONS:
            return True

        # Check content if provided
        if content is not None:
            # Check the first 8000 bytes for null bytes (standard git/Linguist heuristic)
            if b"\x00" in content[:8000]:
                return True

        return False

    def is_notebook(self, path: str | Path) -> bool:
        """Check if a file is a Jupyter notebook."""
        return Path(path).suffix.lower() == ".ipynb"

    def get_language_type(self, language: str) -> str | None:
        """Get the Linguist type for a language (programming, data, markup, prose)."""
        # Reverse override if any
        lookup_name = language
        for raw_name, override_name in LANGUAGE_NAME_OVERRIDES.items():
            if override_name == language:
                lookup_name = raw_name
                break

        info = self._languages_data.get(lookup_name)
        if info:
            return info.get("type")
        return None

    def get_language_color(self, language: str) -> str | None:
        """Get the hex color code for a language if defined."""
        lookup_name = language
        for raw_name, override_name in LANGUAGE_NAME_OVERRIDES.items():
            if override_name == language:
                lookup_name = raw_name
                break

        info = self._languages_data.get(lookup_name)
        if info:
            return info.get("color")
        return None

    def classify(self, path: str | Path) -> str | None:
        """Classify a file path to its programming language name.

        Returns None if the file is binary or unrecognized.
        Returns 'Jupyter Notebook' for .ipynb files.
        """
        if self.is_binary(path):
            return None

        p = Path(path)
        filename = p.name

        # Notebook files are routed separately
        if self.is_notebook(p):
            return "Jupyter Notebook"

        # Check exact filename first (e.g. Makefile, Dockerfile)
        if filename in self._filename_map:
            return self._filename_map[filename]

        # Check lowercase filename
        for k, v in self._filename_map.items():
            if k.lower() == filename.lower():
                return v

        # Check extension
        ext = p.suffix.lower()
        if not ext:
            return None

        return self._extension_map.get(ext)


# Global default classifier instance
_DEFAULT_CLASSIFIER: LanguageClassifier | None = None


def get_default_classifier() -> LanguageClassifier:
    """Get or create the global default LanguageClassifier."""
    global _DEFAULT_CLASSIFIER
    if _DEFAULT_CLASSIFIER is None:
        _DEFAULT_CLASSIFIER = LanguageClassifier()
    return _DEFAULT_CLASSIFIER


def classify(path: str | Path) -> str | None:
    """Classify a file path using the default classifier."""
    return get_default_classifier().classify(path)


def is_binary(path: str | Path, content: bytes | None = None) -> bool:
    """Check if a file is binary using the default classifier."""
    return get_default_classifier().is_binary(path, content=content)


def is_notebook(path: str | Path) -> bool:
    """Check if a file is a notebook using the default classifier."""
    return get_default_classifier().is_notebook(path)


def get_language_type(language: str) -> str | None:
    """Get the type for a language using the default classifier."""
    return get_default_classifier().get_language_type(language)


def get_language_color(language: str) -> str | None:
    """Get the hex color for a language using the default classifier."""
    return get_default_classifier().get_language_color(language)

