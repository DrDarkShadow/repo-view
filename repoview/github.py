"""
github.py — GitHub URL detection, branch listing, and zip download.

Supported input formats:
    https://github.com/owner/repo
    https://github.com/owner/repo/tree/branch
    github.com/owner/repo
    owner/repo            ← shorthand
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List, Optional


# ── Data ─────────────────────────────────────────────────────────────────────

@dataclass
class GitHubRepo:
    owner:  str
    repo:   str
    branch: str = "main"

    @property
    def display(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def zip_url(self) -> str:
        return (
            f"https://github.com/{self.owner}/{self.repo}"
            f"/archive/refs/heads/{self.branch}.zip"
        )


class GitHubError(Exception):
    pass


# ── URL parsing ───────────────────────────────────────────────────────────────

_GH_FULL = re.compile(
    r"(?:https?://)?github\.com/([^/\s]+)/([^/\s]+?)"
    r"(?:\.git)?(?:/tree/([^/\s]+))?/?$",
    re.IGNORECASE,
)
_GH_SHORT = re.compile(
    r"^([a-zA-Z0-9_.\-]+)/([a-zA-Z0-9_.\-]+)$"
)


def parse_github_url(text: str) -> Optional[GitHubRepo]:
    """Return GitHubRepo if text looks like a GitHub reference, else None."""
    text = text.strip().rstrip("/")

    m = _GH_FULL.match(text)
    if m:
        return GitHubRepo(
            owner=m.group(1),
            repo=m.group(2),
            branch=m.group(3) or "main",
        )

    # Don't parse shorthand if it looks like a local path
    if "/" in text and not text.startswith("http") and not text.startswith("github"):
        if text.startswith(".") or text.startswith("/") or text.startswith("~"):
            return None
        m = _GH_SHORT.match(text)
        if m:
            return GitHubRepo(owner=m.group(1), repo=m.group(2))

    return None


# ── Branch listing ────────────────────────────────────────────────────────────

def fetch_branches(gh: GitHubRepo, max_branches: int = 30) -> List[str]:
    """
    Fetch branch names from GitHub API.
    No auth needed for public repos.
    Returns list of branch names, or raises GitHubError.
    """
    url = (
        f"https://api.github.com/repos/{gh.owner}/{gh.repo}"
        f"/branches?per_page={max_branches}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":  "repoview/1.0",
            "Accept":      "application/vnd.github.v3+json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if not isinstance(data, list):
                raise GitHubError("Unexpected API response")
            return [b["name"] for b in data if "name" in b]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise GitHubError(
                f"Repository not found: github.com/{gh.owner}/{gh.repo}\n"
                "  Check the name is correct and the repo is public."
            )
        raise GitHubError(f"GitHub API error: HTTP {e.code}")
    except urllib.error.URLError as e:
        raise GitHubError(f"Network error: {e.reason}")
    except Exception as e:
        raise GitHubError(f"Could not fetch branches: {e}")


# ── Download ──────────────────────────────────────────────────────────────────

def download_zip(
    gh: GitHubRepo,
    dest_path: str,
    progress_cb=None,
) -> None:
    """
    Download repo zip for gh.branch to dest_path.
    Raises GitHubError on failure.
    progress_cb(bytes_done, total_bytes) called during download.
    """
    url = gh.zip_url
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "repoview/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done  = 0
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
    except urllib.error.HTTPError as e:
        raise GitHubError(
            f"Could not download {gh.owner}/{gh.repo} "
            f"(branch: {gh.branch}) — HTTP {e.code}"
        )
    except urllib.error.URLError as e:
        raise GitHubError(f"Network error: {e.reason}")