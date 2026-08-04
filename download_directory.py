"""Qt-independent boundary for the user's expected PRISMA CSV download directory.

Per `Prisma Function.odt`, PrismaFunction does not scan, stage, or monitor
arbitrary filesystem locations. Through P.36.13, the user manually downloaded
the official CSV from PRISMA and later handed it to the program separately
(P.36.4); `default_download_directory()` (the current Windows user's Documents
folder) resolved the expected location for that manual handoff.

As of P.36.14, PrismaFunction can also perform a user-initiated, application-
managed download directly into an application-owned default directory
(`default_managed_download_directory()`, `<Downloads>\\PrismaFunction`,
auto-created idempotently by `ensure_directory_exists()`), while manual
selection (P.36.4) remains an available fallback in the same tracked
directory. This module tracks which single, existing, accessible directory
the user currently expects downloads to land in, however they arrive there.
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
    "DownloadDirectorySelection",
    "default_download_directory",
    "default_downloads_directory",
    "default_managed_download_directory",
    "ensure_directory_exists",
    "validate_download_directory",
]

_USER_SHELL_FOLDERS_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
# Known Folder GUID for the per-user Downloads folder. Unlike "Personal"
# (Documents), Windows does not expose Downloads through a plain named Shell
# Folders value; the literal GUID string is the documented registry lookup key.
_DOWNLOADS_FOLDER_GUID = "{374DE290-123F-4565-9164-39C4925E467B}"
_MANAGED_DOWNLOAD_SUBDIRECTORY = "PrismaFunction"


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


def _registry_downloads_path(*, registry=None) -> str | None:
    reg = registry if registry is not None else winreg
    if reg is None:
        return None
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, _USER_SHELL_FOLDERS_KEY) as key:
            value, _ = reg.QueryValueEx(key, _DOWNLOADS_FOLDER_GUID)
    except OSError:
        return None
    return value or None


def default_downloads_directory(*, environ=None, registry=None, platform: str | None = None) -> Path:
    """Resolve the current user's Downloads folder.

    Mirrors `default_download_directory()`'s tiered resolution (Shell Folders
    registry entry, then `%USERPROFILE%`, then the interpreter's own home
    resolution), substituting the Downloads Known Folder GUID for the
    Documents "Personal" value. No username or machine-specific path is
    hardcoded.
    """
    env = os.environ if environ is None else environ
    selected_platform = os.name if platform is None else platform
    if selected_platform == "nt":
        raw = _registry_downloads_path(registry=registry)
        if raw:
            expanded = os.path.expandvars(raw)
            path = Path(expanded)
            if path.is_absolute():
                return path
    profile = env.get("USERPROFILE", "").strip()
    if profile and Path(profile).expanduser().is_absolute():
        return Path(profile).expanduser() / "Downloads"
    home = Path.home()
    if home.is_absolute():
        return home / "Downloads"
    raise DownloadDirectoryError("The current user's Downloads directory is unavailable.")


def default_managed_download_directory(*, environ=None, registry=None, platform: str | None = None) -> Path:
    """Resolve the P.36.14 application-managed default download directory.

    Per the approved P.36.14 decision gate, this is `<Downloads>\\PrismaFunction`.
    It is only a location resolver: the caller is responsible for creating it
    (`ensure_directory_exists()`) before use.
    """
    return default_downloads_directory(
        environ=environ, registry=registry, platform=platform
    ) / _MANAGED_DOWNLOAD_SUBDIRECTORY


def ensure_directory_exists(path: str | Path) -> Path:
    """Idempotently create ``path`` (and missing parents), then validate it.

    Per the approved P.36.14 decision gate, only this application-managed
    default directory is ever auto-created; a user-selected directory
    (`DownloadDirectorySelection.select()`) is never created automatically.
    """
    target = Path(path)
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise DownloadDirectoryError(
            f"The default download directory could not be created: {target}"
        ) from exc
    return validate_download_directory(target)


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


class DownloadDirectorySelection:
    """Tracks the single active expected download directory for the session.

    Session-scoped only, by explicit P.36.3 decision: PrismaFunction has no
    generic UI-preference persistence mechanism today. The existing SQLite
    operations ledger and `prisma_import_state.json` are narrowly typed to the
    PRISMA source-import lifecycle (accepted sources), not arbitrary UI
    selections, and inventing a second settings store for this one value is
    out of scope for this increment (see ROADMAP.md / workflow_p.md P.36.3).
    """

    def __init__(self, initial: Path) -> None:
        self._current = validate_download_directory(initial)

    @property
    def current(self) -> Path:
        return self._current

    def select(self, candidate: str | Path) -> Path:
        """Validate and activate ``candidate``; on failure, ``current`` is unchanged."""
        validated = validate_download_directory(candidate)
        self._current = validated
        return validated
