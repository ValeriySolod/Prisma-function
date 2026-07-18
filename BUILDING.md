# Windows application build

## Prerequisites

- Windows;
- Python with the `py` launcher;
- an active Python environment with the pinned project dependencies.

Create the environment and install dependencies using the project's existing
setup command:

```bat
setup.bat
```

Then activate that environment before building:

```bat
.venv\Scripts\activate.bat
```

## Build

Run the Windows build script from the repository root:

```bat
build.bat
```

The windowed application and its supporting files are written to
`dist\PrismaFunction\`. The executable is expected at
`dist\PrismaFunction\PrismaFunction.exe`.

The Playwright Python modules needed by the application are included. The
application uses an installed system-default Chrome or Edge browser; browser
binaries are not bundled. A successful build does not replace the manual
release-readiness checks in `RELEASE_CHECKLIST.md`.

## Prepare and create the release archive

Version `1.0.0` is defined in `version.py`. Before preparing a release, start
from a clean working tree, activate the project environment, and run the full
validation commands below. Then build and archive from the repository root:

```bat
build.bat
release.bat
```

`release.bat` requires the successful onedir build at
`dist\PrismaFunction\PrismaFunction.exe`. It uses Windows PowerShell and .NET;
no external archive program is required. It creates these ignored outputs:

```text
release\PrismaFunction-v1.0.0-windows-x64.zip
release\PrismaFunction-v1.0.0-windows-x64.zip.sha256
```

The ZIP has `PrismaFunction\` as its top-level directory. Its entries are
sorted and use a fixed timestamp for reproducible archive input. Runtime CSV,
log, cache, temporary, output, and virtual-environment files are excluded.

Verify the checksum in PowerShell from the repository root:

```powershell
$expected = (Get-Content .\release\PrismaFunction-v1.0.0-windows-x64.zip.sha256).Split()[0]
$actual = (Get-FileHash .\release\PrismaFunction-v1.0.0-windows-x64.zip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 checksum mismatch." }
Write-Host "SHA-256 verified: $actual"
```

Inspect the archive before publication and complete every manual item in
`RELEASE_CHECKLIST.md`. The Git tag and GitHub Release are post-merge actions.

## Reproduce Windows CI locally

From an activated environment with `requirements.txt` installed, run these
checks from the repository root:

```bat
set QT_QPA_PLATFORM=offscreen
set PYTHONUTF8=1
python -m pytest -q
python -m compileall -q app.py auction_csv.py browser.py monitoring.py processor.py runtime_logging.py runtime_paths.py scheduler.py storage.py version.py tests
python -m PyInstaller --clean --noconfirm PrismaFunction.spec
```

The packaging command validates the checked-in PyInstaller configuration and
writes an unarchived build to `dist\PrismaFunction\`; CI does not publish or
upload it. Playwright browser binaries are not required by these checks.

Source and packaged runs write application-owned data only below
`%LOCALAPPDATA%\PrismaFunction`; they do not require the repository or install
directory to be writable. On first launch, confirmed legacy database, result,
state, and temporary-fallback log paths are copied and verified there. Close all
other PrismaFunction processes before manually testing migration.
