"""Qt-independent boundary for the directory PrismaFunction publishes into.

Per the revised specification, PrismaFunction never opens, controls, or
downloads anything from the PRISMA website: the user downloads the official
CSV independently and hands it to the application through manual selection
(`manual_csv_selection.py`). This module now only resolves and validates the
default publication directory (the current Windows user's Documents folder),
the same P.36.3 default that existed before any managed-download feature was
ever added.
"""
from __future__ import annotations

import os
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - exercised only off Windows
    winreg = None

__all__ = [
    "DownloadDirectoryError",
    "default_download_directory",
    "validate_download_directory",
]

_USER_SHELL_FOLDERS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"


class DownloadDirectoryError(Exception):
    """A download directory could not be resolved, selected, or validated."""


def _registry_documents_path(*, registry=None) -> str | None:
    reg = registry if registry is not None else winreg
    if reg is None:
        return None
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, _USER_SHELL_FOLDERS_KEY) as key:
            value, _ = reg.QueryValueEx(key, "Personal")
    except OSError:
        return None
    return value or None


def default_download_directory(*, environ=None, registry=None, platform: str | None = None) -> Path:
    """Resolve the current user's Documents folder.

    Tries the Shell Folders registry entry first (this reflects redirection,
    e.g. by OneDrive or a domain policy), then falls back to
    ``%USERPROFILE%\\Documents``, then to the interpreter's own home-directory
    resolution. No username or machine-specific path is hardcoded: every tier
    resolves dynamically for the current user and current environment.
    """
    env = os.environ if environ is None else environ
    selected_platform = os.name if platform is None else platform
    if selected_platform == "nt":
        raw = _registry_documents_path(registry=registry)
        if raw:
            expanded = os.path.expandvars(raw)
            path = Path(expanded)
            if path.is_absolute():
                return path
    profile = env.get("USERPROFILE", "").strip()
    if profile and Path(profile).expanduser().is_absolute():
        return Path(profile).expanduser() / "Documents"
    home = Path.home()
    if home.is_absolute():
        return home / "Documents"
    raise DownloadDirectoryError("The current user's Documents directory is unavailable.")


def validate_download_directory(candidate: str | Path) -> Path:
    """Accept only an existing, readable directory; never fall back silently."""
    path = Path(candidate)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise DownloadDirectoryError(f"Path does not exist or is not accessible: {candidate}") from exc
    if not resolved.is_dir():
        raise DownloadDirectoryError(f"Path is not a directory: {candidate}")
    if not os.access(resolved, os.R_OK):
        raise DownloadDirectoryError(f"Directory is not accessible: {candidate}")
    return resolved
