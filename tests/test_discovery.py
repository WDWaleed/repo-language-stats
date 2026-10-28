"""Tests for file tree discovery, filtering, and exclusion rules."""

from pathlib import Path
import pytest
from repo_language_stats.discovery import (
    FileDiscoveryFilter,
    TreeEntry,
    TreeFilterConfig,
    filter_tree,
    is_eligible,
)


def test_exclude_vendored_default():
    assert is_eligible("vendor/lib.js") is False
    assert is_eligible("node_modules/express/index.js") is False
    assert is_eligible("third_party/protobuf/compiler.cc") is False


def test_include_vendored_flag():
    cfg = TreeFilterConfig(include_vendored=True)
    assert is_eligible("vendor/lib.js", config=cfg) is True
    assert is_eligible("node_modules/express/index.js", config=cfg) is True


def test_exclude_generated():
    assert is_eligible("app.min.js") is False
    assert is_eligible("dist/bundle.js") is False
    assert is_eligible("service.pb.go") is False
    assert is_eligible("model_generated.py") is False

    # When include_generated is True
    cfg = TreeFilterConfig(include_generated=True)
    assert is_eligible("service.pb.go", config=cfg) is True
    assert is_eligible("model_generated.py", config=cfg) is True

    # min.js matches both vendor.yml and generated_patterns.txt in Linguist
    cfg_both = TreeFilterConfig(include_generated=True, include_vendored=True)
    assert is_eligible("app.min.js", config=cfg_both) is True


def test_custom_glob_exclusion():
    cfg = TreeFilterConfig(exclude_patterns=["*.lock", "test_*"])
    assert is_eligible("poetry.lock", config=cfg) is False
    assert is_eligible("Cargo.lock", config=cfg) is False
    assert is_eligible("tests/test_api.py", config=cfg) is False
    # Normal file should still be eligible
    assert is_eligible("src/main.py", config=cfg) is True


def test_binary_excluded():
    assert is_eligible("image.png") is False
    assert is_eligible("photo.jpg") is False
    assert is_eligible("binary.exe") is False
    assert is_eligible("archive.zip") is False
    # Even if flags are all True, binary is never eligible
    cfg = TreeFilterConfig(include_vendored=True, include_generated=True, include_docs=True)
    assert is_eligible("image.png", config=cfg) is False


def test_nested_paths():
    assert is_eligible("src/vendor/deep/file.py") is False
    cfg = TreeFilterConfig(include_vendored=True)
    assert is_eligible("src/vendor/deep/file.py", config=cfg) is True


def test_documentation_excluded_and_included():
    # Markdown/prose excluded by default
    assert is_eligible("README.md") is False
    assert is_eligible("docs/guide.rst") is False

    # Included when include_docs is True
    cfg = TreeFilterConfig(include_docs=True)
    assert is_eligible("README.md", config=cfg) is True
    assert is_eligible("docs/guide.rst", config=cfg) is True


def test_non_blob_entries_excluded():
    assert is_eligible("src", entry_type="tree") is False
    assert is_eligible("submodule", entry_type="commit") is False


def test_filter_tree_with_objects_and_dicts():
    entries = [
        {"path": "src/main.py", "type": "blob", "sha": "111"},
        {"path": "vendor/lib.js", "type": "blob", "sha": "222"},
        {"path": "assets/logo.png", "type": "blob", "sha": "333"},
        {"path": "src/components", "type": "tree", "sha": "444"},
        TreeEntry(path="src/utils.py", type="blob", sha="555"),
    ]

    filtered = filter_tree(entries)
    paths = [e.path for e in filtered]

    assert "src/main.py" in paths
    assert "src/utils.py" in paths
    assert "vendor/lib.js" not in paths
    assert "assets/logo.png" not in paths
    assert "src/components" not in paths


def test_notebook_always_eligible_unless_excluded():
    assert is_eligible("analysis.ipynb") is True
    cfg = TreeFilterConfig(exclude_patterns=["*.ipynb"])
    assert is_eligible("analysis.ipynb", config=cfg) is False


def test_custom_filter_missing_files(tmp_path: Path):
    custom = FileDiscoveryFilter(
        vendor_file=tmp_path / "no_vendor.yml",
        generated_file=tmp_path / "no_gen.txt",
    )
    # Should not crash, just operate without vendor/generated rules
    assert custom.is_eligible("src/main.py") is True


def test_discovery_get_data_path_and_regex_errors(tmp_path: Path):
    from repo_language_stats.discovery import _get_data_path

    # Existing file
    assert _get_data_path("vendor.yml").exists()
    # Non-existing file fallback branch
    fb = _get_data_path("non_existent.txt")
    assert isinstance(fb, Path)

    # Invalid regex in vendor / generated file
    bad_vendor = tmp_path / "bad_vendor.yml"
    bad_vendor.write_text("- '[invalid regex('\n", encoding="utf-8")
    bad_gen = tmp_path / "bad_gen.txt"
    bad_gen.write_text("[invalid regex(\n", encoding="utf-8")

    f = FileDiscoveryFilter(vendor_file=bad_vendor, generated_file=bad_gen)
    assert f.is_eligible("src/main.py") is True
