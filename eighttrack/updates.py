"""Update checking for 8T DAW via GitHub releases and tags."""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import urllib.error
import urllib.parse
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
    checksum_url: Optional[str] = None
    error: Optional[str] = None


@dataclass
class UpdateInstallResult:
    path: Path
    launched: bool
    checksum_verified: bool = False


class UpdateInstallError(RuntimeError):
    pass


def _request_headers(current_version: str) -> dict[str, str]:
    return {
        "User-Agent": f"8TrackStudio-DAW/{current_version}",
        "Accept": "application/vnd.github.v3+json",
    }


def _asset_score(name: str) -> int:
    lower = name.lower()
    if lower.endswith((".sha256", ".sig", ".asc", ".json", ".txt")):
        return -1

    system = platform.system().lower()
    machine = platform.machine().lower()
    score = 1
    if system == "windows" and lower.endswith((".exe", ".msi")):
        score += 20
    elif system == "darwin" and lower.endswith((".dmg", ".pkg", ".zip")):
        score += 20
    elif system == "linux" and lower.endswith((".tar.gz", ".appimage", ".zip")):
        score += 20

    platform_tokens = [system]
    if system == "windows":
        platform_tokens.append("win")
    if any(token in lower for token in platform_tokens):
        score += 5
    if machine in lower or (machine in {"x86_64", "amd64"} and any(token in lower for token in ("x64", "amd64", "x86_64"))):
        score += 3
    if machine in {"arm64", "aarch64"} and any(token in lower for token in ("arm64", "aarch64")):
        score += 3
    return score


def select_release_asset(assets: list[dict]) -> tuple[Optional[str], Optional[str]]:
    """Choose the best release asset for this platform and its optional SHA-256 sidecar."""
    candidates = []
    checksums = []
    for asset in assets:
        name = str(asset.get("name") or "")
        url = asset.get("browser_download_url")
        if not url:
            continue
        if name.lower().endswith(".sha256"):
            checksums.append((name, url))
            continue
        score = _asset_score(name or url)
        if score >= 0:
            candidates.append((score, name, url))
    if not candidates:
        return None, None

    score, name, download_url = max(candidates, key=lambda item: item[0])
    checksum_url = None
    if name:
        for checksum_name, url in checksums:
            if checksum_name.startswith(name) or checksum_name == f"{name}.sha256":
                checksum_url = url
                break
    return download_url, checksum_url


def _filename_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    filename = urllib.parse.unquote(Path(path).name)
    return filename or "8t-update"


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem = "".join(Path(filename).suffixes)
    base = filename[: -len(stem)] if stem else filename
    for index in range(1, 100):
        numbered = directory / f"{base}-{index}{stem}"
        if not numbered.exists():
            return numbered
    raise UpdateInstallError(f"Could not choose a download path for {filename}")


def _read_url(url: str, current_version: str, timeout: float) -> bytes:
    req = urllib.request.Request(url, headers=_request_headers(current_version))
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _expected_sha256(text: str) -> Optional[str]:
    match = re.search(r"\b[a-fA-F0-9]{64}\b", text)
    return match.group(0).lower() if match else None


def download_update(info: UpdateInfo, destination_dir: Optional[Path] = None, timeout: float = 60.0) -> UpdateInstallResult:
    """Download the GitHub release asset for an available update."""
    if not info.has_update:
        raise UpdateInstallError("No update is available.")
    if not info.download_url:
        raise UpdateInstallError("This GitHub release does not include a downloadable desktop build.")

    target_dir = Path(destination_dir) if destination_dir is not None else Path.home() / "Downloads"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename_from_url(info.download_url)
    target_path = _unique_path(target_dir, filename)
    temp_path = target_path.with_name(f".{target_path.name}.download")

    req = urllib.request.Request(info.download_url, headers=_request_headers(info.current_version))
    with urllib.request.urlopen(req, timeout=timeout) as response, temp_path.open("wb") as output:
        shutil.copyfileobj(response, output)

    checksum_verified = False
    if info.checksum_url:
        checksum_text = _read_url(info.checksum_url, info.current_version, timeout).decode("utf-8", errors="replace")
        expected = _expected_sha256(checksum_text)
        actual = hashlib.sha256(temp_path.read_bytes()).hexdigest()
        if expected is None:
            temp_path.unlink(missing_ok=True)
            raise UpdateInstallError("The update checksum file did not contain a SHA-256 hash.")
        if actual != expected:
            temp_path.unlink(missing_ok=True)
            raise UpdateInstallError("The downloaded update did not match its SHA-256 checksum.")
        checksum_verified = True

    temp_path.replace(target_path)
    return UpdateInstallResult(path=target_path, launched=False, checksum_verified=checksum_verified)


def launch_update(path: Path) -> None:
    """Open the downloaded update with the platform installer/archive handler."""
    path = Path(path)
    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
        return

    lower_name = path.name.lower()
    if lower_name.endswith(".appimage") or path.suffix == "":
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        subprocess.Popen([str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def install_update_from_github(
    info: UpdateInfo,
    destination_dir: Optional[Path] = None,
    timeout: float = 60.0,
    launch: bool = True,
) -> UpdateInstallResult:
    """Download the GitHub release asset and optionally launch the installer/archive."""
    result = download_update(info, destination_dir=destination_dir, timeout=timeout)
    if launch:
        launch_update(result.path)
        result.launched = True
    return result


def check_for_updates(
    current_version: str = "0.1.0",
    repo: str = DEFAULT_REPO,
    timeout: float = 6.0,
) -> UpdateInfo:
    """Check GitHub repository releases/tags for new updates.
    
    Returns UpdateInfo with comparison results and release details.
    """
    clean_repo = repo.replace("https://github.com/", "").replace(".git", "").strip("/")
    headers = _request_headers(current_version)

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
                download_url, checksum_url = select_release_asset(data.get("assets", []))
                return UpdateInfo(
                    current_version=current_version,
                    latest_version=latest_ver,
                    has_update=has_update,
                    release_name=data.get("name") or tag_name or "Latest Release",
                    release_notes=data.get("body") or "",
                    published_at=data.get("published_at", "")[:10],
                    html_url=html_url,
                    download_url=download_url,
                    checksum_url=checksum_url,
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
                    download_url, checksum_url = select_release_asset(latest_rel.get("assets", []))
                    return UpdateInfo(
                        current_version=current_version,
                        latest_version=latest_ver,
                        has_update=has_update,
                        release_name=latest_rel.get("name") or tag_name,
                        release_notes=latest_rel.get("body") or "",
                        published_at=latest_rel.get("published_at", "")[:10],
                        html_url=latest_rel.get("html_url", f"https://github.com/{clean_repo}"),
                        download_url=download_url,
                        checksum_url=checksum_url,
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
