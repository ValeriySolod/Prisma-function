# PrismaFunction v1.0.0 release-readiness checklist

## Source validation

- [ ] Confirm the release commit is on main and the working tree is clean.
- [ ] Run the full pytest suite successfully.
- [ ] Run the documented Python compilation check successfully.
- [ ] Run git diff --check successfully.
- [ ] Build and validate the PyInstaller package.

## Windows application acceptance

- [ ] Launch the packaged PrismaFunction.exe without a console window.
- [ ] Confirm Prisma Function never opens or controls the PRISMA website.
- [ ] Select a valid Windows-1252 official PRISMA Export CSV.
- [ ] Confirm the complete file is processed to EOF without a 5,000-row application limit.
- [ ] Validate a representative CSV containing more than 5,000 rows.
- [ ] Select two distinct CSV files for the same date and confirm both are accepted.
- [ ] Re-import an identical CSV and confirm no duplicate Mapping rows are created.
- [ ] Import a partially overlapping CSV and confirm only new distinct rows are added.
- [ ] Confirm only rows meeting the normalized 1 MWh threshold are retained.
- [ ] Confirm Mapping contains exactly the authoritative 12 columns.
- [ ] Confirm all cumulative accepted rows remain visible after restart.
- [ ] Confirm vertical and horizontal Mapping scrolling works with a large dataset.
- [ ] Confirm Tariff Price and Premium Price are EUR/MWh/h.
- [ ] Validate a non-EUR row, mixed-currency bundle, ECB cache reuse, and prior-reference-date fallback.
- [ ] Validate CET/CEST output, including DST boundary behavior.
- [ ] Confirm published output is UTF-8, semicolon-delimited, and contains exactly the same ordered 12 columns.
- [ ] Confirm runtime data is written only under %LOCALAPPDATA%\PrismaFunction\.
- [ ] Confirm user-facing output is written only to the approved Documents directory.
- [ ] Confirm retry and application shutdown do not hang or leave a worker active.

## Archive and clean-PC validation

- [ ] Run release.bat and inspect the ZIP contents.
- [ ] Confirm PrismaFunction is the only top-level archive directory.
- [ ] Confirm the archive contains PrismaFunction.exe.
- [ ] Confirm no caches, temporary files, logs, CSV data, virtual environments, local databases, or generated output are present.
- [ ] Verify the ZIP against its SHA-256 checksum using BUILDING.md.
- [ ] Repeat launch, CSV processing, persistence, Mapping, output, and logging checks on a second 64-bit Windows PC.

## Publication

- [ ] Create the intended version tag from the approved main commit.
- [ ] Push the tag.
- [ ] Create the GitHub Release and attach the verified ZIP and checksum.
- [ ] Download the published artifacts and verify the checksum again.
