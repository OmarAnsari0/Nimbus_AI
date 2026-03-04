"""
github_client.py — Fetches useful files from a GitHub repository.

WHY THIS FILE EXISTS
--------------------
A repo can have hundreds of files.  We cannot send them all to the LLM
because:
  - LLMs have a limited "context window" (how much text they can read at once)
  - Sending everything is expensive and slow
  - Most files (lock files, compiled assets, etc.) add noise, not signal

STRATEGY
--------
We use a tiered approach:
  1. Always include: README, package manifests (package.json, requirements.txt, etc.)
  2. Then include: top-level source files (main.py, index.js, app.py, etc.)
  3. Then include: a representative sample of source files from subdirectories
  4. Stop when we hit a token budget (~12,000 words is safe for most LLMs)

We use the GitHub REST API (no authentication needed for public repos,
but you can add a token via GITHUB_TOKEN env var to raise rate limits).
"""

import os
import re
import requests
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Optional but recommended

# Files we always want, ordered by priority
PRIORITY_FILENAMES = [
    "README.md", "README.rst", "README.txt", "readme.md",
    "package.json", "pyproject.toml", "requirements.txt",
    "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".env.example", "Makefile",
]

# File extensions we consider "source code" (worth reading)
SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
    ".java", ".rb", ".php", ".cs", ".cpp", ".c", ".h",
    ".swift", ".kt", ".scala", ".r", ".lua", ".ex", ".exs",
    ".yaml", ".yml", ".toml", ".json",  # config files
    ".md", ".txt",  # docs
    ".html", ".css",  # web
    ".sh", ".bash",  # scripts
}

# Paths we should always skip
SKIP_PATHS = {
    "node_modules", ".git", "__pycache__", ".pytest_cache",
    "dist", "build", "target", ".next", "venv", ".venv",
    "env", ".env", "vendor", "coverage", ".coverage",
    "*.lock", "package-lock.json", "yarn.lock", "poetry.lock",
    "Pipfile.lock", "Gemfile.lock", "*.min.js", "*.min.css",
    "*.map", "*.pyc", "*.class", "*.o", "*.so", "*.dll",
    ".DS_Store", "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico",
    "*.svg", "*.pdf", "*.zip", "*.tar", "*.gz",
}

# Word budget — roughly how much text we'll send to the LLM
MAX_WORDS = 12_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    """Build request headers, adding auth token if available.
    
    GitHub REQUIRES a User-Agent header — without it the connection is reset.
    See: https://docs.github.com/en/rest/overview/resources-in-the-rest-api#user-agent-required
    """
    h = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "github-summarizer-app/1.0",  # GitHub requires this
    }
    if GITHUB_TOKEN:
        h["Authorization"] = f"token {GITHUB_TOKEN}"
    return h


def _parse_github_url(url: str) -> tuple[str, str]:
    """
    Extract owner and repo name from a GitHub URL.

    Handles formats like:
      https://github.com/owner/repo
      https://github.com/owner/repo.git
      https://github.com/owner/repo/tree/main
    """
    # Remove trailing slashes and .git
    url = url.rstrip("/").removesuffix(".git")

    # Match github.com/owner/repo (with optional extra path)
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if not match:
        raise ValueError(f"Cannot parse GitHub owner/repo from URL: {url}")

    owner, repo = match.group(1), match.group(2)
    return owner, repo


def _should_skip(path: str) -> bool:
    """Return True if this file/directory should be ignored."""
    parts = path.split("/")
    for part in parts:
        if part in SKIP_PATHS:
            return True
        # Skip hidden directories (like .github, .vscode)
        if part.startswith(".") and part not in {".env.example", ".gitignore"}:
            return True
    # Check extension-based skips
    _, ext = os.path.splitext(path)
    if ext in {".lock", ".pyc", ".class", ".o", ".so", ".dll",
               ".png", ".jpg", ".jpeg", ".gif", ".ico",
               ".pdf", ".zip", ".tar", ".gz", ".map",
               ".min.js", ".min.css"}:
        return True
    return False


def _is_source_file(path: str) -> bool:
    """Return True if this looks like readable source code."""
    _, ext = os.path.splitext(path)
    return ext.lower() in SOURCE_EXTENSIONS


def _fetch_file_content(owner: str, repo: str, path: str) -> Optional[str]:
    """Fetch the decoded text content of a single file via GitHub API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=_headers(), timeout=10)
    if resp.status_code != 200:
        return None

    data = resp.json()
    if data.get("encoding") != "base64":
        return None  # Not a plain text file we can decode easily

    import base64
    try:
        content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return content
    except Exception:
        return None


def _flatten_tree(owner: str, repo: str) -> list[dict]:
    """
    Use the Git Trees API to get a flat list of every file in the repo.
    This is much faster than recursively calling the contents API.
    """
    # First get the default branch
    repo_info = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers=_headers(), timeout=10
    )
    repo_info.raise_for_status()
    default_branch = repo_info.json().get("default_branch", "main")

    # Now get the full tree
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    resp = requests.get(tree_url, headers=_headers(), timeout=15)
    resp.raise_for_status()

    tree_data = resp.json()
    files = [item for item in tree_data.get("tree", []) if item["type"] == "blob"]
    return files


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def fetch_repo_contents(github_url: str) -> str:
    """
    Given a GitHub URL, return a string containing:
      - The repo name and URL
      - A directory tree
      - The content of the most important files (up to MAX_WORDS total)

    This string is what we'll feed to the LLM.
    """
    owner, repo = _parse_github_url(github_url)

    # --- Get full file list ---
    all_files = _flatten_tree(owner, repo)

    # Build a quick directory tree string (for context)
    tree_lines = []
    for f in all_files:
        if not _should_skip(f["path"]):
            tree_lines.append(f["path"])

    directory_tree = "\n".join(sorted(tree_lines)[:200])  # cap at 200 lines

    # --- Decide which files to actually read ---
    # Phase 1: priority files (README, manifests, etc.)
    priority_paths = []
    other_paths = []

    for f in all_files:
        path = f["path"]
        if _should_skip(path):
            continue
        filename = os.path.basename(path)
        if filename in PRIORITY_FILENAMES or path in PRIORITY_FILENAMES:
            priority_paths.append(path)
        elif _is_source_file(path):
            other_paths.append(path)

    # Sort other_paths: prefer top-level files and shorter paths
    other_paths.sort(key=lambda p: (p.count("/"), len(p)))

    files_to_read = priority_paths + other_paths

    # --- Fetch file contents within word budget ---
    collected_files = []
    total_words = 0

    for path in files_to_read:
        if total_words >= MAX_WORDS:
            break
        content = _fetch_file_content(owner, repo, path)
        if content is None:
            continue
        words = len(content.split())
        # Truncate very large files so one file doesn't eat all the budget
        if words > 3000:
            content = " ".join(content.split()[:3000]) + "\n... [truncated]"
            words = 3000
        total_words += words
        collected_files.append((path, content))

    # --- Assemble the context string ---
    parts = [
        f"# Repository: {owner}/{repo}",
        f"URL: {github_url}",
        "",
        "## Directory Structure",
        "```",
        directory_tree,
        "```",
        "",
        "## Key File Contents",
    ]

    for path, content in collected_files:
        parts.append(f"\n### {path}\n```\n{content}\n```")

    return "\n".join(parts)