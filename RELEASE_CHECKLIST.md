# PrismaFunction v1.0.0 release-readiness checklist

Repository-side metadata, scripts, tests, and documentation are complete.
Complete and record the following manual checks before tagging or publishing.

## Source and automated validation

- [ ] Confirm the working tree is clean before the release build.
- [ ] Run the full pytest suite successfully.
- [ ] Run the documented Python compile checks successfully.
- [ ] Run `git diff --check` successfully before merge.

## Windows package validation

- [ ] Run `build.bat` and confirm the PyInstaller build succeeds.
- [ ] Launch `dist\PrismaFunction\PrismaFunction.exe` without a console window.
- [ ] Confirm the title displays `PRISMA Monitor v1.0.0`.
- [ ] Select a start and end date and confirm date-range validation behaves as documented.
- [ ] Open Prisma, confirm the application-managed PRISMA CSV download completes into the
      configured Documents-based or user-selected directory, and confirm Close Prisma ends
      the session cleanly.
- [ ] As a fallback path, manually select a previously downloaded CSV and confirm it is
      validated against the official PRISMA export contract.
- [ ] Confirm the accepted CSV is transformed and published as the exact 12-column output
      contract, and that the mapping presentation shows only the approved columns.
- [ ] Confirm unrelated Chrome or Edge windows remain open when the application-managed
      browser session ends.
- [ ] Confirm a runtime log is created in the documented runtime log location.

## Archive and clean-PC validation

- [ ] Run `release.bat` and inspect the ZIP contents.
- [ ] Confirm `PrismaFunction\` is the only top-level archive directory.
- [ ] Confirm the archive contains `PrismaFunction\PrismaFunction.exe`.
- [ ] Confirm no caches, temporary files, logs, CSV data, virtual environments,
      development-only files, or generated local output are present.
- [ ] Verify the ZIP against its SHA-256 checksum using `BUILDING.md`.
- [ ] Copy the verified package to a second 64-bit Windows PC and repeat launch,
      CSV, browser, monitoring, stop, result, and logging checks.

## Manual post-merge publication

- [ ] Merge the approved P.30 change to `main`.
- [ ] Create the `v1.0.0` Git tag from the intended `main` commit and push it.
- [ ] Create the GitHub Release, attach the ZIP and checksum, and use
      `RELEASE_NOTES_v1.0.0.md` as the release notes.
- [ ] Download the published artifacts and verify the checksum once more.
