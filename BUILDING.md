# Windows application build

## Prerequisites

- Windows;
- Python with the `py` launcher;
- the project virtual environment and pinned dependencies.

Create the environment and install dependencies using the project's existing
setup command:

```bat
setup.bat
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
increment.
