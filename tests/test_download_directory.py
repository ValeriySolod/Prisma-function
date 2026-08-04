from pathlib import Path
from types import SimpleNamespace

import pytest

import download_directory as download_directory_module
from download_directory import (
    DownloadDirectoryError,
    DownloadDirectorySelection,
    default_download_directory,
    default_downloads_directory,
    default_managed_download_directory,
    ensure_directory_exists,
    validate_download_directory,
)
from runtime_paths import runtime_paths


class RegistryKey:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _fake_registry(value: str | None, *, raises: bool = False):
    def open_key(*args):
        if raises:
            raise OSError("registry key unavailable")
        return RegistryKey()

    return SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=open_key,
        QueryValueEx=lambda key, name: (value, None),
    )


def test_default_resolves_via_shell_folders_registry_entry(tmp_path):
    documents = tmp_path / "Redirected" / "Documents"
    registry = _fake_registry(str(documents))

    result = default_download_directory(platform="nt", registry=registry)

    assert result == documents


def test_default_expands_environment_variables_from_registry_value(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    registry = _fake_registry("%USERPROFILE%\\Documents")

    result = default_download_directory(platform="nt", registry=registry)

    assert result == tmp_path / "Documents"


def test_default_falls_back_to_userprofile_when_registry_unavailable(tmp_path):
    registry = _fake_registry(None, raises=True)

    result = default_download_directory(
        platform="nt", registry=registry, environ={"USERPROFILE": str(tmp_path)}
    )

    assert result == tmp_path / "Documents"


def test_default_falls_back_to_home_when_userprofile_unset(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = default_download_directory(platform="nt", registry=_fake_registry(None, raises=True), environ={})

    assert result == tmp_path / "Documents"


def test_default_skips_registry_off_windows(tmp_path):
    registry = _fake_registry(str(tmp_path / "should-not-be-used"))

    result = default_download_directory(
        platform="posix", registry=registry, environ={"USERPROFILE": str(tmp_path)}
    )

    assert result == tmp_path / "Documents"


def test_default_is_not_an_internal_application_data_path(tmp_path, monkeypatch):
    local_app_data = tmp_path / "Local App Data"
    monkeypatch.setenv("LOCALAPPDATA", str(local_app_data))
    registry = _fake_registry(None, raises=True)

    default_dir = default_download_directory(
        platform="nt", registry=registry, environ={"USERPROFILE": str(tmp_path / "profile")}
    )
    application_root = runtime_paths().root

    assert default_dir != application_root
    assert application_root not in default_dir.parents
    assert local_app_data not in default_dir.parents
    assert default_dir.name == "Documents"


def test_validate_accepts_existing_directory(tmp_path):
    target = tmp_path / "downloads"
    target.mkdir()

    assert validate_download_directory(target) == target.resolve()


def test_validate_rejects_missing_path(tmp_path):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(DownloadDirectoryError):
        validate_download_directory(missing)


def test_validate_rejects_file_path(tmp_path):
    file_path = tmp_path / "export.csv"
    file_path.write_text("data", encoding="utf-8")

    with pytest.raises(DownloadDirectoryError):
        validate_download_directory(file_path)


def test_validate_rejects_inaccessible_directory(tmp_path, monkeypatch):
    target = tmp_path / "locked"
    target.mkdir()
    monkeypatch.setattr(download_directory_module.os, "access", lambda *args, **kwargs: False)

    with pytest.raises(DownloadDirectoryError):
        validate_download_directory(target)


def test_selection_starts_at_initial_directory(tmp_path):
    selection = DownloadDirectorySelection(tmp_path)

    assert selection.current == tmp_path


def test_selection_normalizes_initial_directory(tmp_path):
    initial = tmp_path / "downloads"
    initial.mkdir()

    selection = DownloadDirectorySelection(initial)

    assert selection.current == initial.resolve()


def test_selection_rejects_missing_initial_directory(tmp_path):
    missing = tmp_path / "does-not-exist"

    with pytest.raises(DownloadDirectoryError):
        DownloadDirectorySelection(missing)


def test_selection_rejects_file_initial_path(tmp_path):
    file_path = tmp_path / "export.csv"
    file_path.write_text("data", encoding="utf-8")

    with pytest.raises(DownloadDirectoryError):
        DownloadDirectorySelection(file_path)


def test_selection_rejects_inaccessible_initial_directory(tmp_path, monkeypatch):
    target = tmp_path / "locked"
    target.mkdir()
    monkeypatch.setattr(download_directory_module.os, "access", lambda *args, **kwargs: False)

    with pytest.raises(DownloadDirectoryError):
        DownloadDirectorySelection(target)


def test_selection_updates_current_on_valid_selection(tmp_path):
    target = tmp_path / "chosen"
    target.mkdir()
    selection = DownloadDirectorySelection(tmp_path)

    result = selection.select(target)

    assert result == target.resolve()
    assert selection.current == target.resolve()


def test_selection_rejects_invalid_candidate_without_changing_current(tmp_path):
    initial = tmp_path / "initial"
    initial.mkdir()
    selection = DownloadDirectorySelection(initial)

    with pytest.raises(DownloadDirectoryError):
        selection.select(tmp_path / "missing")

    assert selection.current == initial


def test_selection_rejects_file_candidate_without_changing_current(tmp_path):
    initial = tmp_path / "initial"
    initial.mkdir()
    file_path = tmp_path / "export.csv"
    file_path.write_text("data", encoding="utf-8")
    selection = DownloadDirectorySelection(initial)

    with pytest.raises(DownloadDirectoryError):
        selection.select(file_path)

    assert selection.current == initial


# --- P.36.14: application-managed default download directory -------------


def test_downloads_default_resolves_via_shell_folders_registry_entry(tmp_path):
    downloads = tmp_path / "Redirected" / "Downloads"
    registry = _fake_registry(str(downloads))

    result = default_downloads_directory(platform="nt", registry=registry)

    assert result == downloads


def test_downloads_default_expands_environment_variables_from_registry_value(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    registry = _fake_registry("%USERPROFILE%\\Downloads")

    result = default_downloads_directory(platform="nt", registry=registry)

    assert result == tmp_path / "Downloads"


def test_downloads_default_falls_back_to_userprofile_when_registry_unavailable(tmp_path):
    registry = _fake_registry(None, raises=True)

    result = default_downloads_directory(
        platform="nt", registry=registry, environ={"USERPROFILE": str(tmp_path)}
    )

    assert result == tmp_path / "Downloads"


def test_downloads_default_skips_registry_off_windows(tmp_path):
    registry = _fake_registry(str(tmp_path / "should-not-be-used"))

    result = default_downloads_directory(
        platform="posix", registry=registry, environ={"USERPROFILE": str(tmp_path)}
    )

    assert result == tmp_path / "Downloads"


def test_managed_default_is_the_prismafunction_subdirectory_of_downloads(tmp_path):
    registry = _fake_registry(None, raises=True)

    result = default_managed_download_directory(
        platform="nt", registry=registry, environ={"USERPROFILE": str(tmp_path)}
    )

    assert result == tmp_path / "Downloads" / "PrismaFunction"


def test_ensure_directory_exists_creates_missing_directory_and_parents(tmp_path):
    target = tmp_path / "Downloads" / "PrismaFunction"

    result = ensure_directory_exists(target)

    assert result == target.resolve()
    assert target.is_dir()


def test_ensure_directory_exists_is_idempotent_for_an_existing_directory(tmp_path):
    target = tmp_path / "Downloads" / "PrismaFunction"
    target.mkdir(parents=True)
    marker = target / "already-here.csv"
    marker.write_text("data", encoding="utf-8")

    result = ensure_directory_exists(target)

    assert result == target.resolve()
    assert marker.exists()


def test_ensure_directory_exists_rejects_a_file_at_the_target_path(tmp_path):
    target = tmp_path / "PrismaFunction"
    target.write_text("not a directory", encoding="utf-8")

    with pytest.raises(DownloadDirectoryError):
        ensure_directory_exists(target)


def test_ensure_directory_exists_wraps_creation_failure(tmp_path, monkeypatch):
    target = tmp_path / "Downloads" / "PrismaFunction"

    def fail_mkdir(self, *args, **kwargs):
        raise OSError("access denied")

    monkeypatch.setattr(download_directory_module.Path, "mkdir", fail_mkdir)

    with pytest.raises(DownloadDirectoryError):
        ensure_directory_exists(target)
