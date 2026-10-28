"""repo-language-stats — GitHub Language Statistics CLI."""

__version__ = "0.1.0"

from repo_language_stats.counting import (
    AggregateStats,
    LanguageStats,
    RepoStats,
    StatsAccumulator,
    aggregate_stats,
    calculate_percentage,
    count_bytes,
    count_lines,
)
from repo_language_stats.discovery import (
    FileDiscoveryFilter,
    TreeEntry,
    TreeFilterConfig,
    filter_tree,
    is_eligible,
)
from repo_language_stats.github_api import (
    GitHubAPIClient,
    RepoInfo,
)
from repo_language_stats.language import (
    LanguageClassifier,
    classify,
    get_language_color,
    get_language_type,
    is_binary,
    is_notebook,
)
from repo_language_stats.notebook import (
    NotebookParseResult,
    determine_notebook_language,
    parse_notebook,
)

__all__ = [
    "__version__",
    "count_bytes",
    "count_lines",
    "calculate_percentage",
    "aggregate_stats",
    "LanguageStats",
    "RepoStats",
    "AggregateStats",
    "StatsAccumulator",
    "LanguageClassifier",
    "classify",
    "is_binary",
    "is_notebook",
    "get_language_type",
    "get_language_color",
    "NotebookParseResult",
    "parse_notebook",
    "determine_notebook_language",
    "TreeEntry",
    "TreeFilterConfig",
    "FileDiscoveryFilter",
    "filter_tree",
    "is_eligible",
    "RepoInfo",
    "GitHubAPIClient",
]
