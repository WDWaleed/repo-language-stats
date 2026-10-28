"""Tests for language classification and binary detection."""

from pathlib import Path
import pytest
from repo_language_stats.language import (
    LanguageClassifier,
    classify,
    get_language_color,
    get_language_type,
    is_binary,
    is_notebook,
)


def test_extension_python():
    assert classify("script.py") == "Python"
    assert classify("path/to/script.py") == "Python"
    assert classify("script.pyi") == "Python"


def test_extension_ambiguous():
    # .h can be C, C++, Objective-C — should pick Linguist preferred language C
    assert classify("header.h") == "C"
    assert classify("include/header.h") == "C"


def test_filename_makefile():
    assert classify("Makefile") == "Make"
    assert classify("makefile") == "Make"
    assert classify("path/to/Makefile") == "Make"
    assert classify("GNUmakefile") == "Make"


def test_filename_dockerfile():
    assert classify("Dockerfile") == "Dockerfile"
    assert classify("dockerfile") == "Dockerfile"
    assert classify("deploy/Dockerfile") == "Dockerfile"
    assert classify("Containerfile") == "Dockerfile"


def test_unknown_extension():
    assert classify("file.xyz123") is None
    assert classify("file_without_extension") is None


def test_binary_detected():
    assert is_binary("image.png") is True
    assert is_binary("photo.jpg") is True
    assert is_binary("binary.exe") is True
    assert is_binary("library.dll") is True
    assert is_binary("font.woff2") is True
    assert is_binary("archive.zip") is True

    # classify() returns None for binary files
    assert classify("image.png") is None
    assert classify("binary.exe") is None

    # Binary detection with content (null byte heuristic)
    assert is_binary("file.txt", content=b"hello \x00 world") is True
    assert is_binary("file.txt", content=b"clean ascii text") is False


def test_ipynb_routed_to_notebook():
    assert is_notebook("data_analysis.ipynb") is True
    assert is_notebook("notebooks/model.ipynb") is True
    assert is_notebook("script.py") is False

    # Classified as Jupyter Notebook, not as JSON
    lang = classify("data_analysis.ipynb")
    assert lang == "Jupyter Notebook"
    assert lang != "JSON"


def test_top_20_extensions():
    expected_mappings = {
        "file.py": "Python",
        "file.js": "JavaScript",
        "file.ts": "TypeScript",
        "file.jsx": "JavaScript",
        "file.tsx": "TSX",
        "file.c": "C",
        "file.cpp": "C++",
        "file.h": "C",
        "file.hpp": "C++",
        "file.java": "Java",
        "file.rb": "Ruby",
        "file.go": "Go",
        "file.rs": "Rust",
        "file.php": "PHP",
        "file.cs": "C#",
        "file.sh": "Shell",
        "file.html": "HTML",
        "file.css": "CSS",
        "file.sql": "SQL",
        "file.swift": "Swift",
        "file.kt": "Kotlin",
    }
    for filename, expected_lang in expected_mappings.items():
        assert classify(filename) == expected_lang, f"Failed for {filename}: expected {expected_lang}, got {classify(filename)}"


def test_language_types():
    assert get_language_type("Python") == "programming"
    assert get_language_type("Rust") == "programming"
    assert get_language_type("Make") == "programming"
    assert get_language_type("HTML") == "markup"
    assert get_language_type("Markdown") == "prose"
    assert get_language_type("JSON") == "data"
    assert get_language_type("NonExistentLanguage") is None


def test_language_colors():
    python_color = get_language_color("Python")
    assert python_color is not None
    assert python_color.startswith("#")

    make_color = get_language_color("Make")
    assert make_color is not None

    assert get_language_color("NonExistentLanguage") is None


def test_custom_classifier_missing_file(tmp_path: Path):
    missing_file = tmp_path / "does_not_exist.yml"
    classifier = LanguageClassifier(data_file=missing_file)
    assert classifier.classify("test.py") is None


def test_get_data_path_fallback():
    from repo_language_stats.language import _get_data_path
    # Existing file
    assert _get_data_path("languages.yml").exists()
    # Non-existing file fallback branch
    fallback_path = _get_data_path("non_existent_file.xyz")
    assert isinstance(fallback_path, Path)
