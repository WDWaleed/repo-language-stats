"""Tests for Jupyter notebook (.ipynb) parsing and cell source extraction."""

from pathlib import Path
import pytest
from repo_language_stats.notebook import (
    NotebookParseResult,
    determine_notebook_language,
    normalize_language_name,
    parse_notebook,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_parse_valid_python_notebook():
    fixture_path = FIXTURES_DIR / "sample.ipynb"
    result = parse_notebook(fixture_path)

    assert result is not None
    assert isinstance(result, NotebookParseResult)
    assert result.language == "Python"
    # Contains code cells
    assert "def hello():" in result.code_text
    assert "x = 42" in result.code_text
    # Markdown text must NOT be in code_text
    assert "# Sample Title" not in result.code_text
    assert "This is markdown documentation." not in result.code_text
    assert result.total_bytes > 0
    assert result.total_lines > 0


def test_parse_r_notebook():
    fixture_path = FIXTURES_DIR / "r_kernel.ipynb"
    result = parse_notebook(fixture_path)

    assert result is not None
    assert result.language == "R"
    assert "library(ggplot2)" in result.code_text


def test_skip_markdown_cells():
    fixture_path = FIXTURES_DIR / "sample.ipynb"
    result = parse_notebook(fixture_path)

    assert result is not None
    assert "This is markdown documentation." not in result.code_text


def test_skip_outputs_and_metadata():
    fixture_path = FIXTURES_DIR / "sample.ipynb"
    result = parse_notebook(fixture_path)

    assert result is not None
    # Outputs like "Hello, world!\n" stream output should not be included in code text
    # (unless part of the code definition `print('Hello, world!')`)
    assert "execution_count" not in result.code_text
    assert "output_type" not in result.code_text


def test_missing_kernelspec(caplog):
    fixture_path = FIXTURES_DIR / "no_kernel.ipynb"
    with caplog.at_level("WARNING"):
        result = parse_notebook(fixture_path)

    assert result is not None
    assert result.language == "Unknown (notebook)"
    assert "val a = 10" in result.code_text
    assert "recording as 'Unknown (notebook)'" in caplog.text


def test_malformed_notebook(caplog):
    fixture_path = FIXTURES_DIR / "malformed.ipynb"
    with caplog.at_level("WARNING"):
        result = parse_notebook(fixture_path)

    assert result is None
    assert "Failed to parse notebook" in caplog.text


def test_empty_notebook():
    fixture_path = FIXTURES_DIR / "empty_cells.ipynb"
    result = parse_notebook(fixture_path)

    assert result is not None
    assert result.language == "Python"
    assert result.code_text == ""
    assert result.total_bytes == 0
    assert result.total_lines == 0


def test_kernel_name_fallback():
    metadata = {
        "kernelspec": {
            "name": "ir",
            "language": "",  # missing or empty
        }
    }
    assert determine_notebook_language(metadata) == "R"

    # Test other patterns
    assert determine_notebook_language({"kernelspec": {"name": "python3.11"}}) == "Python"
    assert determine_notebook_language({"kernelspec": {"name": "julia-1.8"}}) == "Julia"
    assert determine_notebook_language({"kernelspec": {"name": "xeus-cling-cpp17"}}) == "C++"
    assert determine_notebook_language({"kernelspec": {"name": "bash"}}) == "Shell"
    assert determine_notebook_language({"kernelspec": {"name": "tslab"}}) == "TypeScript"
    assert determine_notebook_language({"kernelspec": {"name": "rust"}}) == "Rust"


def test_language_info_fallback():
    metadata = {
        "kernelspec": {},
        "language_info": {
            "name": "julia"
        }
    }
    assert determine_notebook_language(metadata) == "Julia"


def test_ipynb_language_override():
    fixture_path = FIXTURES_DIR / "no_kernel.ipynb"
    result = parse_notebook(fixture_path, fallback_language="Scala")

    assert result is not None
    assert result.language == "Scala"


def test_parse_notebook_from_string_and_bytes():
    fixture_path = FIXTURES_DIR / "sample.ipynb"
    content_str = fixture_path.read_text(encoding="utf-8")
    content_bytes = fixture_path.read_bytes()

    res_str = parse_notebook(content_str)
    assert res_str is not None
    assert res_str.language == "Python"

    res_bytes = parse_notebook(content_bytes)
    assert res_bytes is not None
    assert res_bytes.language == "Python"


def test_normalize_language_name():
    assert normalize_language_name("python") == "Python"
    assert normalize_language_name("c++") == "C++"
    assert normalize_language_name("cpp") == "C++"
    assert normalize_language_name("js") == "JavaScript"
    assert normalize_language_name("ts") == "TypeScript"
    assert normalize_language_name("custom_lang") == "Custom_lang"


def test_edge_cases_metadata_structure():
    # kernelspec is not a dict
    assert determine_notebook_language({"kernelspec": "invalid"}) == "Unknown (notebook)"
    # kernelspec name doesn't match known patterns
    assert determine_notebook_language({"kernelspec": {"name": "completely_unknown_kernel"}}) == "Unknown (notebook)"
    # language_info is not a dict
    assert determine_notebook_language({"kernelspec": {}, "language_info": "invalid"}) == "Unknown (notebook)"


def test_code_cells_with_source_as_list():
    import json
    nb_dict = {
        "cells": [
            {
                "cell_type": "code",
                "id": "list-cell-1",
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": ["def test_func():\n", "    return 123\n"]
            }
        ],
        "metadata": {
            "kernelspec": {"language": "python", "name": "python3"}
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }
    # Pass as JSON string
    result = parse_notebook(json.dumps(nb_dict))
    assert result is not None
    assert "def test_func():" in result.code_text
    assert result.total_lines == 2
