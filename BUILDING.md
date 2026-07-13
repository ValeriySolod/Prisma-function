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

The Playwright Python modules needed by the application are included, but
Playwright browser binaries are not bundled in this increment. Clean-machine
executable validation belongs to Workflow P stage P.22 and is outside this
increment. The packaged executable must be tested on Windows; a successful
build alone does not verify launch or runtime behavior on a clean machine.

## Reproduce Windows CI locally

From an activated environment with `requirements.txt` installed, run these
checks from the repository root:

```bat
set QT_QPA_PLATFORM=offscreen
set PYTHONUTF8=1
python -m pytest -q
python -m compileall -q app.py auction_csv.py browser.py monitoring.py processor.py runtime_logging.py scheduler.py storage.py tests
python -m PyInstaller --clean --noconfirm PrismaFunction.spec
```

The packaging command validates the checked-in PyInstaller configuration and
writes an unarchived build to `dist\PrismaFunction\`; CI does not publish or
upload it. Playwright browser binaries are not required by these checks.
