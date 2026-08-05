# Windows installer and uninstaller

## Scope

The installer packages the already validated PyInstaller `onedir` distribution from
`dist\PrismaFunction`. It does not replace or modify the existing PyInstaller build.

The default installation is per-user and does not require administrator rights:

```text
%LOCALAPPDATA%\Programs\PrismaFunction
```

Application runtime data remains separate under:

```text
%LOCALAPPDATA%\PrismaFunction
```

Uninstalling or upgrading the application must not remove that runtime-data directory.

## Prerequisites

- Windows x64;
- the project environment and dependencies described in `BUILDING.md`;
- a successful validated `dist\PrismaFunction` build;
- Inno Setup 6 with `ISCC.exe` available in its default location, or
  `INNO_SETUP_COMPILER` set to the full compiler path.

## Build

From an activated project environment at the repository root:

```bat
build.bat
python validate_package.py
build-installer.bat
```

The installer is written to:

```text
installer\PrismaFunction-Setup-1.0.0-windows-x64.exe
```

The version is read from the packaged executable metadata, whose source of truth is
`version.py` through the existing PyInstaller version resource.

## Signing readiness

The checked-in definition enables signed uninstallers (`SignedUninstaller=yes`,
unconditional — not gated by `#ifdef SignToolName`). Configure a named Inno Setup
SignTool command in the Inno Setup IDE, then pass that name while building:

```bat
set INNO_SIGNTOOL_NAME=prismasign
build-installer.bat
```

`INNO_SIGNTOOL_NAME` cannot be omitted from a non-interactive `ISCC.exe`/
`build-installer.bat` run: because `SignedUninstaller=yes` is unconditional, the
compiler hard-aborts ("please attach your digital signature ... and compile again")
whenever no `SignTool` is configured, even for a local, unsigned validation build. A
local validation build without a real signing certificate must still configure some
`SignTool` command (for example, an ephemeral, non-committed self-signed test
certificate used only for that local build) for the compiler to complete. Certificate
selection, secret storage, timestamp service configuration, and release signing remain
external to the repository and must not be committed.

## Installation behavior

- installs only files from the validated `dist\PrismaFunction` directory;
- creates a Start Menu shortcut;
- offers an unchecked optional desktop shortcut;
- supports paths containing spaces;
- launches without elevation for a standard Windows user;
- does not modify `PATH`, file associations, browser configuration, or system settings.

## Uninstall and upgrade behavior

The generated uninstaller removes installed application binaries and shortcuts. It
must preserve `%LOCALAPPDATA%\PrismaFunction`, including databases, logs, generated
workbooks, import state, and other user-owned runtime data.

The stable Inno Setup `AppId` and default directory provide an in-place upgrade path.
Before publishing an upgrade, install the previous version, create representative
runtime data, install the new version over it, and verify that both application launch
and runtime-data preservation succeed.

## Manual validation

Perform these checks on a standard non-administrator Windows account:

1. Build and validate the PyInstaller package.
2. Build the installer from a repository path containing spaces.
3. Confirm the installer version and publisher identity.
4. Install to the default per-user directory without elevation.
5. Confirm the Start Menu shortcut and optional desktop shortcut behavior.
6. Launch the application and exercise Open Prisma/Close Prisma, CSV selection or
   download, PRISMA Export import, generated output, shutdown, and relaunch.
7. Confirm writable data appears only below `%LOCALAPPDATA%\PrismaFunction`.
8. Install the same or a newer build over the existing installation and confirm user
   data remains intact.
9. Uninstall from Windows Settings and confirm binaries and shortcuts are removed.
10. Confirm `%LOCALAPPDATA%\PrismaFunction` remains intact after uninstall.
11. Reinstall and confirm the preserved database and baseline can be reused.
12. For a release candidate, verify Authenticode signatures on both setup and
    uninstaller and complete `RELEASE_CHECKLIST.md`.
