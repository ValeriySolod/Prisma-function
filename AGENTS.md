# AGENTS.md — Prisma-function

Repository-wide engineering rules for anyone or anything implementing changes
in this repository — Claude Code, Codex, GitHub Copilot review, or a human
contributor. The implementation executor may be Claude Code or Codex, but
both follow the same roadmap, branch boundaries, requirements, and
Definition of Done below.

For project identity, current roadmap state, CSV contracts, and other
product-specific context, see `CLAUDE.md` and `ROADMAP.md`. This file does
not duplicate that content; it defines how work is done, not what the
product is.

## Source of truth and precedence

Before making any change:

- Read this file completely.
- Read `ROADMAP.md` completely, plus the architecture, build, packaging,
  testing, and release documents it references.
- Read `Prisma Function.odt` (the authoritative business specification) when
  a change touches product requirements.
- Inspect relevant production code, tests, configuration, and packaging
  files — do not rely on documentation alone.
- Run `git status --short --branch` before starting.

Priority when sources conflict: the newest explicitly approved customer
decision, then the newest authoritative specification (`Prisma
Function.odt`), then the corrected `ROADMAP.md`, then implementation
evidence in the repository, then `CLAUDE.md`/this file. Never infer missing
requirements.

## Language

Code, identifiers, comments, UI text, CSV headers and values, technical
documentation, branch names, and commit messages must be English.

## Scope: one bounded increment per branch

- One increment equals one bounded scope, implemented on its own feature
  branch, and independently tested.
- Do not include unrelated refactoring, cleanup, formatting, or dependency
  updates.
- Implement the entire agreed scope and run only the necessary checks
  without repeated permission requests within an already-agreed task; stop
  and ask for clarification only before a significant change in behavior,
  architecture, data, security, or scope.
- Do not start the next increment until the current one is finished and
  merged to `main`.
- Prefer tests over production changes when existing behavior only needs to
  be proven, not corrected.

## Validation, error-handling, and safety requirements

- Preserve validation, auditing, error context, atomicity, recovery,
  security, and backward compatibility.
- Handle every error without hanging the application and without blocking a
  retry.
- Never weaken, reinterpret, or silently contradict authoritative
  requirements. Any deviation requires explicit customer approval, recorded
  in `ROADMAP.md`, before implementation.

## Testing, compilation, and packaging requirements

- Run focused tests for the changed behavior, then the complete automated
  test suite.
- Run the project's documented Python compilation check (see
  `BUILDING.md`).
- Run relevant packaging validation when packaging-affecting files change
  (see `BUILDING.md`, `INSTALLER.md`, `RELEASE_CHECKLIST.md`).
- Run `git diff --check`.
- Do not repeat an expensive check if the code it covers has not changed
  since the check last passed.
- Real-environment (Windows/PRISMA) validation is required before a
  real-environment-dependent increment can be marked fully complete. Never
  claim such validation passed unless it was actually run and the exact
  result is recorded.

## Documentation requirements

- Update `ROADMAP.md`, `CLAUDE.md`, and any other current documentation
  whenever behavior, configuration, contracts, conditions, or status change.
- Record the exact validation commands and their exact results, not a
  paraphrase or an assumption.
- Do not copy obsolete historical implementation reports between documents;
  Git history is the record of superseded documentation.

## Review and correction workflow

- Review may use GitHub Copilot (or an equivalent automated review pass)
  without allowing it to edit files.
- Fix critical and important review findings, then rerun the full test
  suite.
- Produce one final report containing: the exact implemented scope; the
  list of changed files; the result of every check actually run; any
  outstanding manual/real-environment checks; risks and blockers; and
  confirmation that no commit or push happened without authorization.
- When manual or real-environment validation is required, complete it
  before producing the final review diff; if it surfaces actionable
  findings, apply one narrow correction at a time and repeat the
  report-and-review cycle.
- When a review diff is requested, produce it with
  `git status --short --branch`, `git diff --check`, `git diff --stat`, and
  `git diff --binary --no-ext-diff > <increment>-final-review.diff`. These
  `*-final-review.diff` files are working artifacts for human review and are
  never committed.

## Git safety rules

- Never commit, push, merge, rebase, force-push, release, or delete a
  branch without explicit user authorization. The user creates and merges
  pull requests.
- Never skip hooks or bypass signing unless explicitly instructed.

## Definition of Done

An increment is done when:

- it contains only the agreed scope;
- English UI and CSV contracts are preserved;
- errors, retry, and cleanup are handled;
- focused and full automated tests pass;
- authoritative requirements remain intact;
- no critical review finding remains unresolved;
- documentation is current;
- the change is merged to `main`;
- the feature branch is deleted.
