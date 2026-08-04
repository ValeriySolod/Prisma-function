from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - exercised only on non-Windows hosts
    winreg = None

PRISMA_AUCTIONS_URL = (
    "https://app.prisma-capacity.eu/reporting/auctions/"
    "short-and-long-term-auctions"
)

_NULL_STREAMS = []


def _ensure_subprocess_output_streams() -> None:
    """Give child processes valid output handles in windowed executables."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            stream = open(os.devnull, "w", encoding="utf-8")
            _NULL_STREAMS.append(stream)
            setattr(sys, name, stream)


class DefaultBrowserDetector:
    """Resolves the supported browser registered for HTTP URLs on Windows."""

    USER_CHOICE = (
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations"
        r"\http\UserChoice"
    )

    def detect_executable(self) -> Path:
        if winreg is None:
            raise RuntimeError("Default browser detection is only supported on Windows.")
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.USER_CHOICE) as key:
                prog_id = winreg.QueryValueEx(key, "ProgId")[0]
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"{prog_id}\shell\open\command"
            ) as key:
                command = winreg.QueryValueEx(key, None)[0]
        except OSError as exc:
            raise RuntimeError(
                "The Windows default browser association could not be read."
            ) from exc

        match = re.match(r'^\s*"([^"]+)"|^\s*([^\s]+)', command or "")
        if not match:
            raise RuntimeError("The Windows default browser association is invalid.")
        executable = Path(match.group(1) or match.group(2))
        name = executable.name.lower()
        if name not in {"chrome.exe", "msedge.exe"}:
            raise RuntimeError(
                "The default browser is not supported. Use Google Chrome or Microsoft Edge."
            )
        if not executable.is_file():
            raise RuntimeError(f"The default browser executable was not found: {executable}")
        return executable
