from types import SimpleNamespace
from pathlib import Path

import pytest

from browser import DefaultBrowserDetector
import browser as browser_module

ORIGINAL_DETECT_EXECUTABLE = DefaultBrowserDetector.detect_executable


class RegistryKey:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_detector_resolves_registered_supported_executable(monkeypatch):
    monkeypatch.setattr(
        DefaultBrowserDetector, "detect_executable", ORIGINAL_DETECT_EXECUTABLE
    )
    values = iter(("ChromeHTML", '"C:\\Apps\\Chrome\\chrome.exe" -- "%1"'))
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=object(), HKEY_CLASSES_ROOT=object(),
        OpenKey=lambda *args: RegistryKey(next(values)),
        QueryValueEx=lambda key, name: (key.value, None),
    )
    monkeypatch.setattr(browser_module, "winreg", registry)
    monkeypatch.setattr(Path, "is_file", lambda self: True)

    assert DefaultBrowserDetector().detect_executable() == Path(
        "C:/Apps/Chrome/chrome.exe"
    )


def test_detector_rejects_unsupported_default_browser(monkeypatch):
    monkeypatch.setattr(
        DefaultBrowserDetector, "detect_executable", ORIGINAL_DETECT_EXECUTABLE
    )
    values = iter(("FirefoxURL", '"C:\\Apps\\Firefox\\firefox.exe" -osint'))
    registry = SimpleNamespace(
        HKEY_CURRENT_USER=object(), HKEY_CLASSES_ROOT=object(),
        OpenKey=lambda *args: RegistryKey(next(values)),
        QueryValueEx=lambda key, name: (key.value, None),
    )
    monkeypatch.setattr(browser_module, "winreg", registry)

    with pytest.raises(RuntimeError, match="not supported"):
        DefaultBrowserDetector().detect_executable()
