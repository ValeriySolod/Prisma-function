from pathlib import Path
from types import SimpleNamespace

import pytest

import download_directory as download_directory_module
from download_directory import (
    DownloadDirectoryError,
    DownloadDirectorySelection,
    default_download_directory,
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
