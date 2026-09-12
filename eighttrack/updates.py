"""Update checking for 8T DAW via GitHub releases and tags."""

from dataclasses import dataclass
import json
import re
import urllib.error
import urllib.request
from typing import Optional, Tuple

DEFAULT_REPO = "Butter-tart/8TrackStudio"
DEFAULT_REPO_URL = f"https://github.com/{DEFAULT_REPO}"
DEFAULT_CLONE_URL = f"https://github.com/{DEFAULT_REPO}.git"


def parse_version(version_str: str) -> Tuple[int, ...]:
    """Extract integer version components from strings like 'v0.1.0', '0.2.0', 'v1.0.0-rc1'."""
    if not version_str:
        return (0,)
    cleaned = version_str.strip().lstrip("vV")
    numbers = re.findall(r"\d+", cleaned)
    if not numbers:
        return (0,)
    return tuple(int(n) for n in numbers)


def is_newer_version(latest_str: str, current_str: str) -> bool:
    """Return True if latest_str is strictly newer than current_str."""
    latest_tuple = parse_version(latest_str)
    current_tuple = parse_version(current_str)
    # Pad tuples to same length
    max_len = max(len(latest_tuple), len(current_tuple))
    lat = latest_tuple + (0,) * (max_len - len(latest_tuple))
    cur = current_tuple + (0,) * (max_len - len(current_tuple))
    return lat > cur


@dataclass
class UpdateInfo:
    current_version: str
    latest_version: str
    has_update: bool
    release_name: str = ""
    release_notes: str = ""
    published_at: str = ""
    html_url: str = DEFAULT_REPO_URL
    download_url: Optional[str] = None
    error: Optional[str] = None


def check_for_updates(
    current_version: str = "0.1.0",
    repo: str = DEFAULT_REPO,
    timeout: float = 6.0,
) -> UpdateInfo:
    """Check GitHub repository releases/tags for new updates.
    
    Returns UpdateInfo with comparison results and release details.
    """
    clean_repo = repo.replace("https://github.com/", "").replace(".git", "").strip("/")
    headers = {
        "User-Agent": f"8TrackStudio-DAW/{current_version}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Try /releases/latest first
    latest_url = f"https://api.github.com/repos/{clean_repo}/releases/latest"
    try:
        req = urllib.request.Request(latest_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                tag_name = data.get("tag_name", "")
                latest_ver = tag_name.lstrip("vV") if tag_name else current_version
                has_update = is_newer_version(latest_ver, current_version)
                html_url = data.get("html_url", f"https://github.com/{clean_repo}")
                assets = data.get("assets", [])
                download_url = assets[0].get("browser_download_url") if assets else None
                return UpdateInfo(
                    current_version=current_version,
                    latest_version=latest_ver,
                    has_update=has_update,
                    release_name=data.get("name") or tag_name or "Latest Release",
                    release_notes=data.get("body") or "",
                    published_at=data.get("published_at", "")[:10],
                    html_url=html_url,
                    download_url=download_url,
                )
    except urllib.error.HTTPError as err:
        if err.code != 404:
            return UpdateInfo(
                current_version=current_version,
                latest_version=current_version,
                has_update=False,
                error=f"GitHub API returned HTTP {err.code}: {err.reason}",
            )
    except Exception as err:
        return UpdateInfo(
            current_version=current_version,
            latest_version=current_version,
            has_update=False,
            error=f"Network error checking for updates: {err}",
        )

    # 2. Fallback: try /releases list
    releases_url = f"https://api.github.com/repos/{clean_repo}/releases"
    try:
        req = urllib.request.Request(releases_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                releases = json.loads(response.read().decode("utf-8"))
                if releases and isinstance(releases, list):
                    latest_rel = releases[0]
                    tag_name = latest_rel.get("tag_name", "")
                    latest_ver = tag_name.lstrip("vV") if tag_name else current_version
                    has_update = is_newer_version(latest_ver, current_version)
                    return UpdateInfo(
                        current_version=current_version,
                        latest_version=latest_ver,
                        has_update=has_update,
                        release_name=latest_rel.get("name") or tag_name,
                        release_notes=latest_rel.get("body") or "",
                        published_at=latest_rel.get("published_at", "")[:10],
                        html_url=latest_rel.get("html_url", f"https://github.com/{clean_repo}"),
                    )
    except Exception:
        pass

    # 3. Fallback: try /tags
    tags_url = f"https://api.github.com/repos/{clean_repo}/tags"
    try:
        req = urllib.request.Request(tags_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status == 200:
                tags = json.loads(response.read().decode("utf-8"))
                if tags and isinstance(tags, list):
                    tag_name = tags[0].get("name", "")
                    latest_ver = tag_name.lstrip("vV") if tag_name else current_version
                    has_update = is_newer_version(latest_ver, current_version)
                    return UpdateInfo(
                        current_version=current_version,
                        latest_version=latest_ver,
                        has_update=has_update,
                        release_name=tag_name,
                        html_url=f"https://github.com/{clean_repo}/releases/tag/{tag_name}",
                    )
    except Exception as err:
        return UpdateInfo(
            current_version=current_version,
            latest_version=current_version,
            has_update=False,
            error=f"Error checking tags: {err}",
        )

    # No releases or tags found; up to date
    return UpdateInfo(
        current_version=current_version,
        latest_version=current_version,
        has_update=False,
        release_name="Up to date",
        html_url=f"https://github.com/{clean_repo}",
    )
