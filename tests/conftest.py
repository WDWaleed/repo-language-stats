"""Shared pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_ascii_text() -> str:
    return "print('hello world')\n"


@pytest.fixture
def sample_utf8_text() -> str:
    return "# Café précis naïve résumé\nx = 'ümlaut'\n"

