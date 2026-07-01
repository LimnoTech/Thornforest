"""Per-notebook session setup: repo-root discovery, `.env`/API-key loading, HTTP-cache
configuration, and plot defaults, bundled into a `Session` object."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def find_repo_root(marker: str = "pyproject.toml", start: Path | None = None) -> Path:
    """Walk up from `start` (default: the working directory) to the repo root, i.e. the first
    parent directory that contains `marker`. Lets notebooks build absolute paths to repo-level
    folders (data/, cache/, .env) regardless of where the kernel's working directory is."""
    start = Path(start) if start is not None else Path.cwd()
    for folder in [start, *start.parents]:
        if (folder / marker).exists():
            return folder
    print(f"WARNING: {marker} not found walking up from {start}; using it as repo root.")
    return start


# --- Session setup (shared by every notebook) ---------------------------------

@dataclass(frozen=True)
class Session:
    """Resolved per-notebook configuration returned by init_session()."""
    repo_root: Path
    data_dir: Path
    cache_file: str
    cache_expire_seconds: int
    api_key: str | None
    api_headers: dict


def init_session(cache_expire_seconds: int = 7 * 24 * 3600) -> Session:
    """Load the optional USGS API key from .env, point HyRiver's request cache at the
    git-ignored cache/ folder, and return the resolved paths/headers as a Session.
    Safe to call without a .env (falls back to anonymous rate limits)."""
    from .viz import set_plot_defaults

    repo_root = find_repo_root()
    load_dotenv(repo_root / ".env")
    api_key = os.getenv("API_USGS_PAT")
    api_headers = {"X-Api-Key": api_key} if api_key else {}
    cache_file = str(repo_root / "cache" / "aiohttp_cache.sqlite")
    os.environ.setdefault("HYRIVER_CACHE_NAME", cache_file)
    os.environ.setdefault("HYRIVER_CACHE_EXPIRE", str(cache_expire_seconds))
    print(
        "USGS API key loaded."
        if api_key
        else "No API key — using anonymous (lower) rate limits."
    )
    set_plot_defaults()
    return Session(
        repo_root=repo_root,
        data_dir=repo_root / "data",
        cache_file=cache_file,
        cache_expire_seconds=cache_expire_seconds,
        api_key=api_key,
        api_headers=api_headers,
    )
