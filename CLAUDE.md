# CLAUDE.md — Prisma-function 

Auto-loaded every session. Keep short — re-read on every turn.

## Project identity

PrismaFunction is a single-user Windows desktop application built with PySide6.
It monitors live PRISMA auction status and separately processes official PRISMA
Export CSV files into cumulative local data and user-facing output.

A separate successor, Prisma Function Mini (`Prisma-function-mini`), has its own
M-series roadmap and a different output contract. Never mix the two projects or
roadmaps.

## Source of truth — read before any change

- Read every applicable `AGENTS.md`.
- Read `ROADMAP.md` and `workflow_p.md` completely.
- Read the architecture and technical documentation referenced by those files.
- Inspect relevant production code, tests, configuration, and packaging files.
- Run `git status --short --branch` before starting.
- Treat repository evidence as authoritative when it is newer than this file.

`Prisma Function.odt` is the sole authoritative business specification for the
P.36 manual-workflow line. Never infer missing requirements.

## Current roadmap state

Completed work includes P.1–P.9, P.17–P.19, P.20.1, P.23–P.27, P.29–P.35.1,
subject to the remaining manual validation explicitly recorded in
`ROADMAP.md`.

P.10, P.11, P.20.2, P.22, and P.28 remain incomplete or partially complete.
Never claim P.22 or P.28 passed.

P.35.2–P.35.5 were cancelled on 2026-07-28. Do not restore their automated
CSV/PDF pairing, staging, fingerprinting, or browser-driven source-acquisition
design.

P.36 is the authoritative forward roadmap for the manual PRISMA workflow:

- P.36.1–P.36.5 (documentation/contracts, Open/Close Prisma lifecycle, download
  directory, manual CSV selection, and PDF-scope/output-contract resolution)
  are complete. P.36.5 resolved the remaining specification questions: PDF
  input/processing is excluded from the current version, and the approved
  output contract has 14 columns.
- No unresolved specification question remains. P.36.6 is unblocked and is the
  next recommended implementation increment.
- Later P.36 increments must follow the dependency and status recorded in
  `ROADMAP.md`.

## Separate CSV contracts — never conflate

Monitoring CSV is UTF-8 and comma-delimited, with columns `auction_id`,
`auction_url`, `lot_number`, `item_name`, `expected_status`,
`last_known_status`, `check_interval_seconds`, and `enabled`. It is loaded
through "Load Monitoring CSV".

The legacy PRISMA Export CSV contract is cp1252, semicolon-delimited, and has 34
fixed columns. Detection is header-based, never filename-based.

The P.36 target output is a separate UTF-8, semicolon-delimited 14-field CSV
contract defined by the authoritative specification, P.36.1, and P.36.5 (which
resolved the two combined Market-or-Storage fields into four separate columns:
Exit Market, Exit Storage, Entry Market, Entry Storage). Do not reuse the
Prisma Function Mini contract by assumption.

## Non-negotiable rules

- Only auctions with booked capacity at or above the authoritative threshold
  after unit normalization are relevant. For P.36, follow the approved 1 MWh
  contract exactly.
- Market/Storage mapping may come only from exact Auction-ID-linked official
  PRISMA evidence. Never use fuzzy, geographic, TSO, EIC, substring, or
  name-based inference.
- Entry and Exit evidence are side-specific. Never assume a mapping is valid on
  the opposite side.
- Every catalog expansion is an independently reviewed batch with regression
  tests for exact-side resolution and no cross-side leakage, plus recorded
  SHA-256 evidence digests.
- Runtime data belongs only under `%LOCALAPPDATA%\PrismaFunction\`. Never write
  runtime data to the installation directory, current working directory, or a
  hidden staging path.
- Code, identifiers, comments, UI text, CSV headers and values, technical
  documentation, branch names, and commit messages must be English.
- Never bypass PRISMA authentication, anti-bot protection, or terms.
- Preserve validation, auditing, error context, atomicity, recovery, security,
  and backward compatibility.

## Working style

- One increment equals one bounded branch and one independently tested task.
- Do not include unrelated refactoring, cleanup, formatting, or dependency
  updates.
- Prefer tests over production changes when existing behavior only needs proof.
- Run focused tests, the complete test suite, Python compilation, relevant
  packaging validation, and `git diff --check`.
- Update documentation and `ROADMAP.md` when behavior, configuration,
  contracts, conditions, or status change.
- Implementation executor may be Claude Code or Codex, but both use the same
  roadmap, branch boundaries, requirements, and Definition of Done.
- Review may use GitHub Copilot without allowing it to edit files.
- Never commit, push, merge, rebase, force-push, release, or delete a branch
  without explicit user authorization. The user creates and merges pull
  requests.

## Definition of Done

The increment contains only the agreed scope; English UI and CSV contracts are
preserved; errors, retry, and cleanup are handled; focused and full tests pass;
authoritative requirements remain intact; no critical review finding remains;
documentation is current; the change is merged to `main`; and the feature
branch is deleted.

## Claude Code efficiency

Use `/clear` between unrelated increments. Reference repository files with
`@filename` instead of pasting them. Default to `/model sonnet`; reserve Opus
for genuine architecture decisions.
