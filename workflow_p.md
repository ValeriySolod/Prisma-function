# Workflow P — Prisma-function

## 1. Призначення

Workflow P визначає послідовність створення, перевірки та розвитку програми **Prisma-function**.

Програма повинна бути невеликою, зрозумілою для користувача та працювати з браузерами **Google Chrome** і **Microsoft Edge**.

## 1.1. Authoritative customer requirements

This section is the permanent product acceptance baseline for the entire **Prisma-function** project. Every future increment, review, and roadmap decision must be checked against these requirements.

1. PRISMA is the source platform for European gas-capacity auction data.
2. The application processes official PRISMA auction exports.
3. The user selects a start date and an end date inside Prisma Function; there is no first-day-of-month restriction on the start date, and the date range must otherwise follow the validation rules defined for `P.36.13`.
4. Only auctions with booked capacity of at least 1000 kWh/h after supported unit normalization are relevant. This threshold corresponds to the established PRISMA import and live-filter contract.
5. The transformed output is a fixed, ordered **12-field** contract (see `ROADMAP.md`'s "Resolved
   specification questions" 2026-08-02 correction entry and "P.36 roadmap correction (2026-08-02)"
   for the full authoritative record; this corrects a 2026-08-01 `P.36.5` decision that had briefly
   revised this to a 14-field, four-column structure — see the `P.36.5` completion note below, under
   "4. Порядок створення програми", which records that history and its 2026-08-02 correction). In
   order, the transformed output must expose:
   - Auction Date;
   - `Exit Market`: the exit-side market **or** exit-side storage name — whichever official PRISMA
     evidence resolves the exit-side network point to, under `P.33.3`'s `ReferenceClassification`
     (`market` or `storage`). There is no separate `Exit Storage` output column.
   - `Entry Market`: the entry-side market **or** entry-side storage name — whichever official
     PRISMA evidence resolves the entry-side network point to. There is no separate `Entry Storage`
     output column.
   - Capacity Type: entry, exit, or bundle;
   - Network Point Name, for example `VGS Storage Hub`;
   - Product Type: `WD`, `Day Ahead`, `Month`, `Quarter`, or `Year`;
   - Flow Start (date and time);
   - Flow End (date and time);
   - Booked Capacity in kWh/h;
   - Flow Duration Hours;
   - Tariff Price in EUR/MWh/h;
   - Premium Price in EUR/MWh/h.

   `Exit Market`/`Entry Market` are resolved only from their own side's evidence: `Exit Market` only
   from exit-side evidence, `Entry Market` only from entry-side evidence, per items 6-11 below. No
   value is ever inferred for the opposite side.

   The existing authoritative Market/Storage enrichment rule (`P.33.3`) governs the genuinely
   unresolved case: if a required side is missing, or a required side's network point cannot be
   resolved to either an approved Market alias or an approved Storage alias, the entire row is
   rejected, with a typed enrichment reason code plus the affected field, side, and unchanged
   source-value context. The `P.36.15` transformation increment (see `ROADMAP.md`'s "P.36 roadmap
   correction (2026-08-02)") must apply this existing reject rule; it is not a new choice for that
   increment, and no placeholder or silent skip is introduced for a genuinely unresolved side. This
   is distinct from the separate `P.33.6`/`P.33.7` historical-backfill skip-and-audit behavior,
   which governs only already-persisted rows in an explicit, opt-in maintenance operation that
   `P.33.7` confirms "is never called by ... CSV import ... export"; it does not apply to new-row
   enrichment and must not be conflated with the P.36 output contract.
6. Market and storage enrichment must use only official PRISMA evidence.
7. A Market mapping may be added only when an exact Auction ID links:
   - the exact side-specific network-point name and identifier from the CSV export;
   - the corresponding Market Area shown in an official PRISMA PDF or equivalent official reference export.
8. Evidence files that do not contain the same Auction ID must not be cross-matched.
9. Ambiguous, visually overlapped, incomplete, or conflicting source rows must be excluded from authoritative mapping batches.
10. Do not infer mappings from geography, TSO names, EIC similarity, display-text similarity, naming conventions, or previously observed mappings.
11. Do not assume that an Exit alias is valid for Entry, or that an Entry alias is valid for Exit.
12. Every catalog expansion must be a separate reviewed batch with focused regression tests proving:
    - exact resolution on the evidenced side;
    - no resolution on an unevidenced side;
    - no fuzzy, substring, geographic, or automatic matching;
    - preservation of existing mappings and import behavior.
13. No future task may silently weaken, reinterpret, or contradict these requirements. Any requested deviation must be documented and explicitly approved by the customer before implementation.
14. Every authoritative mapping batch must identify the exact evidence files used and record their SHA-256 digests. The accepted mappings must remain reproducible from those unchanged source files.

## 2. Мовні правила

- Мова інтерфейсу програми: **English**.
- Назви кнопок, полів, повідомлень, статусів, діалогових вікон і помилок: **English**.
- Назви колонок CSV: **English**.
- Значення статусів у CSV: **English**.
- Назви файлів, класів, функцій і змінних у коді: **English**.
- Документація для розробника може бути українською.
- Не змішувати українську та англійську мови в інтерфейсі або CSV.

## 3. Основні правила роботи

1. Один етап — одна завершена задача.
2. Кожний новий етап виконувати в окремій Git-гілці.
3. Кожний новий завершений блок починати в новому чаті.
4. Перед змінами перевіряти актуальний стан гілки `main`.
5. Виконавцем реалізації може бути Claude Code або Codex; для Workflow P за
   замовчуванням готується один повний prompt для Claude Code.
6. Виконавець самостійно реалізує весь погоджений scope інкременту та виконує
   тільки необхідні перевірки без постійних запитів на дозвіл у межах уже
   погодженого завдання. Значні зміни поведінки, архітектури, даних, безпеки або
   scope залишаються стоп-умовою для уточнення.
7. Після кожного етапу запускати тести.
8. Не переходити до наступного етапу, доки поточний не завершено та не об’єднано з `main`.
9. Не змінювати production-код, якщо необхідну поведінку можна підтвердити або покрити тестами.
10. Усі помилки повинні оброблятися без зависання програми та без блокування повторного запуску.

## 4. Порядок створення програми

### P.1. Базова структура

Створити мінімальну структуру проєкту:

- application entry point;
- UI module;
- browser controller;
- CSV reader and validator;
- monitoring logic;
- configuration;
- tests;
- setup and run scripts;
- project documentation.

Результат етапу:

- програма запускається;
- відкривається головне вікно;
- тести стартової структури проходять.

### P.2. Головне вікно

Створити компактне головне вікно.

Мінімальні елементи:

- `Open Browser`;
- `Load Monitoring CSV`;
- `Start Monitoring`;
- `Stop Monitoring`;
- `Status`;
- поле або журнал результатів.

Правила:

- усі написи англійською;
- недоступні дії повинні бути disabled;
- після помилки кнопки повинні повертатися у правильний стан;
- користувач повинен мати можливість повторити операцію.

### P.3. Automatic default browser detection

Програма повинна автоматично визначати браузер, налаштований як Windows default browser.

Підтримувані браузери для першої версії:

- `Google Chrome`;
- `Microsoft Edge`.

Вимоги:

- прибрати ручний вибір Chrome або Edge з GUI;
- прибрати browser selector і весь пов’язаний з ним UI state;
- відокремити browser detection від UI layer і browser controller;
- перевіряти існування executable визначеного браузера;
- обробляти unsupported default browser, missing or corrupted browser association, registry read failure і missing executable з чіткими англомовними повідомленнями про помилки;
- monitoring flow повинен і надалі використовувати Playwright, а не `webbrowser.open()`;
- коректно завершувати browser session;
- не залишати фонові процеси після зупинки.

Обов’язкові тести:

- Chrome as default browser;
- Edge as default browser;
- unsupported default browser;
- missing or corrupted browser association;
- missing executable;
- Windows registry read failure;
- successful retry after an error;
- complete removal of the browser selector from the UI.

### P.4. Відкриття Prisma

Реалізувати відкриття цільового сайту Prisma.

Перевірити сценарії:

- успішний запуск;
- помилка запуску Playwright;
- помилка створення browser instance;
- помилка створення page;
- закриття браузера користувачем;
- повторний запуск після помилки;
- зупинка під час запуску;
- захист від застарілого результату попереднього запуску.

### P.5. CSV contract

CSV повинен мати англійські назви колонок.

Базовий контракт:

```csv
auction_id,auction_url,lot_number,item_name,expected_status,last_known_status,check_interval_seconds,enabled
```

Опис колонок:

| Column | Purpose |
|---|---|
| `auction_id` | Unique auction identifier |
| `auction_url` | Direct URL to the auction page |
| `lot_number` | Lot number |
| `item_name` | Item or auction name |
| `expected_status` | Status that should trigger attention |
| `last_known_status` | Last status saved by the program |
| `check_interval_seconds` | Monitoring interval |
| `enabled` | Enables or disables monitoring for the row |

Допустимі boolean values:

- `true`;
- `false`.

Приклади status values:

- `Scheduled`;
- `Open`;
- `In Progress`;
- `Completed`;
- `Cancelled`;
- `Unknown`;
- `Error`.

CSV validation повинна перевіряти:

- наявність усіх обов’язкових колонок;
- унікальність `auction_id`;
- коректність URL;
- допустимий interval;
- допустиме boolean value;
- порожні обов’язкові поля;
- дублікати;
- неправильне кодування або пошкоджений файл.

Усі validation messages повинні бути англійською.

### P.6. Завантаження CSV

Після вибору CSV програма повинна:

1. відкрити файл;
2. перевірити заголовки;
3. перевірити кожний рядок;
4. показати кількість завантажених записів;
5. показати помилки з номером рядка;
6. не запускати monitoring при критичних помилках;
7. дозволити повторно вибрати виправлений файл.

Приклади повідомлень:

- `CSV file loaded successfully.`;
- `Missing required column: auction_url.`;
- `Invalid URL in row 4.`;
- `Duplicate auction_id in row 7.`;
- `No active auctions found.`;

### P.7. Monitoring engine

Для кожного активного запису програма повинна:

- відкривати відповідну сторінку;
- зчитувати поточний статус;
- порівнювати його з попереднім;
- фіксувати час перевірки;
- обробляти network timeout;
- обробляти зміну структури сторінки;
- продовжувати роботу з іншими записами після локальної помилки;
- підтримувати безпечну зупинку користувачем.

Monitoring не повинен блокувати UI thread.

### P.8. Результати моніторингу

Результати повинні використовувати англійські назви полів.

Рекомендований output CSV:

```csv
checked_at,auction_id,lot_number,item_name,current_status,previous_status,status_changed,result,error_message
```

Приклади `result`:

- `Success`;
- `Changed`;
- `Skipped`;
- `Error`.

Поле `error_message` повинно бути порожнім при успішній перевірці.

### P.9. UI state management

Визначити стани програми:

- `Idle`;
- `Loading CSV`;
- `Opening Browser`;
- `Ready`;
- `Monitoring`;
- `Stopping`;
- `Error`.

Для кожного стану визначити:

- активні кнопки;
- неактивні кнопки;
- текст status label;
- дозволені переходи;
- обробку помилок;
- можливість повторного запуску.

### P.10. Error handling

Обов’язково обробити:

- browser launch failure;
- page creation failure;
- invalid CSV;
- missing columns;
- unavailable website;
- timeout;
- authentication failure;
- unexpected page format;
- browser closed manually;
- monitoring stop request;
- unexpected exception.

Після будь-якої помилки:

- UI не повинен зависати;
- кнопки повинні повернутися у коректний стан;
- internal references повинні очищатися;
- browser resources повинні закриватися;
- повторний запуск повинен залишатися доступним.

### P.11. Testing

Мінімальні групи тестів:

1. UI state tests.
2. Browser controller tests.
3. CSV validation tests.
4. Monitoring tests.
5. Error handling tests.
6. Stop and retry tests.
7. Generation or stale-result protection tests.
8. Resource cleanup tests.

Перед завершенням кожного етапу:

- запустити focused tests;
- запустити full test suite;
- перевірити, що production behavior не регресував;
- перевірити GitHub Copilot review findings;
- виправити critical і important findings;
- повторно запустити full test suite.

### P.12. Packaging and launch

Підготувати:

- `setup.bat`;
- `run.bat`;
- dependency file;
- README;
- sample CSV;
- logs directory;
- output directory.

Для Git Bash запуск Windows scripts виконувати так:

```bash
./setup.bat
./run.bat
```

Для Command Prompt:

```bat
setup.bat
run.bat
```

### P.13. Final readiness check

Перед першою стабільною версією перевірити:

- automatic default browser detection;
- Chrome as default browser;
- Edge as default browser;
- unsupported default browser;
- PySide6 GUI readiness;
- valid CSV;
- invalid CSV;
- empty CSV;
- interrupted launch;
- browser close;
- monitoring start;
- monitoring stop;
- repeated start and stop;
- network failure;
- page structure mismatch;
- output CSV;
- cleanup after exit;
- all UI text is English;
- all CSV headers and status values are English;
- all tests pass.

### P.14. GUI framework migration to PySide6

Для GUI використовувати `PySide6` і виконати migration from Tkinter to PySide6.

Вимоги:

- business logic повинна залишатися незалежною від GUI framework;
- GUI повинен залишатися presentation layer;
- long-running work не повинен виконуватися в main GUI thread;
- worker-thread communication з GUI повинна використовувати Qt signals;
- використовувати `QMainWindow`;
- використовувати `QFileDialog` для вибору CSV;
- використовувати `QMessageBox` для повідомлень;
- використовувати `QTableView` або `QTableWidget` для tabular data;
- інтегрувати monitoring і browser lifecycle через Qt-safe mechanisms;
- весь UI text повинен залишатися англійською.

#### P.14.1. PySide6 application skeleton

Створити PySide6 application entry point, `QApplication` lifecycle і базовий `QMainWindow`, зберігши business logic поза GUI framework.

#### P.14.2. Main window and CSV table

Перенести main window controls, CSV selection через `QFileDialog`, messages через `QMessageBox` і tabular data до `QTableView` або `QTableWidget`.

#### P.14.3. Browser and monitoring integration

Інтегрувати browser lifecycle і monitoring workers через Qt-safe mechanisms та Qt signals без прямого оновлення widgets з background threads.

#### P.14.4. Tkinter removal

Видалити Tkinter UI, dependencies і пов’язаний GUI state після підтвердження parity та проходження PySide6 tests.

Обов’язкові тести:

- main window creation;
- correct initial UI state;
- CSV loading;
- monitoring start and stop;
- browser launch failure;
- worker exception handling;
- retry after failure;
- closing the application during monitoring;
- no direct widget updates from background threads.

### P.15. Windows executable packaging

Primary packaging tool: `PyInstaller`.

Fallback packaging tool: `cx_Freeze`.

Packaging починати лише після завершення:

- automatic default browser detection;
- PySide6 migration;
- monitoring integration;
- resource cleanup;
- stable application paths;
- passing the full test suite.

Підготувати:

- PyInstaller `.spec` file;
- application icon;
- version metadata;
- executable name;
- application data paths;
- writable user-data directory;
- logs and output directories;
- bundled configuration;
- bundled Qt plugins;
- Playwright and browser dependency strategy;
- clean-build script;
- release-build script.

Перший packaging mode:

- `onedir`;
- `windowed`;
- without a console window.

`onefile` залишити як later-stage option після стабілізації `onedir`.

Runtime data не повинні записуватися до temporary directory PyInstaller. Рекомендована writable location:

`%LOCALAPPDATA%\PrismaFunction\`

Packaging checks:

- launch on Windows without Python installed;
- launch from a path containing spaces;
- launch without administrator rights;
- Qt platform plugin loading;
- default browser detection;
- Chrome and Edge launch through Playwright;
- CSV selection;
- monitoring start and stop;
- writable database, result, and log directories;
- successful retry;
- safe removal without changing system settings.

### P.16. Windows release readiness

Final release checks:

- clean build;
- application icon and version metadata;
- Windows Defender scan;
- clean Windows machine or VM;
- no Python installed;
- Chrome as default browser;
- Edge as default browser;
- unsupported default browser;
- valid and invalid CSV;
- monitoring start and stop;
- browser cleanup;
- application shutdown;
- log generation;
- result generation;
- upgrade from a previous build;
- installation and usage documentation.

Результат етапу:

- release archive;
- versioned executable;
- checksum;
- release notes;
- installation instructions.

### P.17. Remove the manual browser selector from the UI

Status: **Completed**.

Remove the manual Chrome/Edge selector and all UI state that exists only to support manual browser selection.

Completion note: The manual Chrome/Edge selector and its UI-only state were removed.

### P.18. Use the operating system default browser automatically

Status: **Completed**.

Automatically detect and use the browser configured as the operating system default, while preserving clear error handling for unsupported or invalid browser associations.

Completion note: The application now detects and uses the operating system default browser, with handling for unsupported or invalid browser associations.

### P.19. Evaluate and select the Qt GUI framework

Status: **Completed**.

Evaluate the following Qt-based GUI frameworks:

- `PySide6`;
- `PyQt6`.

Select the framework based on licensing, packaging, maintenance, documentation, and project compatibility before starting the GUI migration.

Completion note: PySide6 was selected as the Qt framework.

### P.20. Migrate the Tkinter interface to the selected Qt framework

Status: **Completed**.

Migrate the current Tkinter interface to the Qt-based framework selected in P.19 while preserving existing application behavior, UI states, error handling, and background-work safety.

Completion note: The Tkinter GUI was migrated to PySide6 while preserving application behavior, background-work safety, error handling, and tests. The full test suite passed with `125 passed`.

### P.21. Package the application as a Windows executable

Status: **Completed**.

Package the application as a Windows `.exe` after the Qt migration is complete.

Packaging tools to evaluate:

- evaluate `PyInstaller` first;
- retain `cx_Freeze` as an alternative.

Completion note: Added a pinned PyInstaller build dependency, a version-controlled
windowed `onedir` specification for `PrismaFunction.exe`, a clean Windows build
script using the active Python environment, packaging documentation, Git ignores,
and focused configuration tests. Clean-environment executable validation remains
in P.22.

### P.22. Validate the packaged executable on a clean Windows environment

Status: **In progress — physical-PC validation exposed an intermittent browser runtime crash; clean-Windows validation has not passed**.

Validate the packaged executable on a clean physical Windows computer without a project development environment or Python installation, including launch, default-browser use, CSV loading, monitoring, shutdown, and writable data paths.

Progress note: the documented windowed onedir build succeeded and package
contents, direct non-admin process launch, launch from a path containing spaces,
and writes beside the package were checked on the Windows development host.
This host is not a clean machine, its sandbox user has no configured HTTP default
browser, and its packaged GUI was not interactively accessible. A VirtualBox
validation attempt was discontinued because the VM setup was unreliable and
repeatedly returned to Windows installation. Virtual machines are no longer part
of the planned validation approach. Use `P22_CLEAN_WINDOWS_CHECKLIST.md` when a
separate physical Windows computer is available. The clean-machine GUI, CSV,
monitoring, browser, graceful-shutdown, cleanup, retry, and protected
install-location checks remain. See `P22_VALIDATION.md`.

#### P.22.1. Add persistent packaged-browser runtime diagnostics

Status: **Completed (diagnostic increment only); P.22 remains In progress**.

Validation on a second physical Windows PC confirmed package launch, matching
executable SHA-256, and default Chrome/Edge launch through Playwright, but exposed
an intermittent browser closure after several minutes or sometimes on window
maximize. The root cause is not yet determined. Persistent, generation-scoped
runtime and browser lifecycle diagnostics were added to collect evidence without
changing launch flags, browser selection, retry/relaunch behavior, lifecycle
synchronization, generation protection, cleanup, or UI result semantics. This
does not mark clean-Windows validation complete.

### P.23. Live PRISMA auction monitoring

Status: **Completed — P.23.1, P.23.2, and P.23.3 are Completed**.

Use the Playwright page owned by the existing browser lifecycle as the live
monitoring source. Authentication/session support and complete recovery for
timeouts, unavailable pages, DOM changes, and manual browser closure are separate
follow-up increments.

#### P.23.1. Implement live PRISMA page adapter

Status: **Completed**.

Completion note: validated the source application against the real public PRISMA
short-and-long-term auctions page in system-default Chrome. The live page loaded
with its research-consent banner untouched, the existing Start of Auction date
filter remained active, and the current filter panel accepted `Marketed >= 1000`.
The adapter inspected the rendered table, matched auction `62255317` by the live
`Auction ID` column, read live status `Finished`, and normalized it to `Completed`
on repeated scheduled checks. Live-site differences were corrected by supporting
the collapsed current-design filter panel (`Marketed` plus `Filter`) and selecting
the rendered header row instead of PRISMA's empty sorting-header row. Missing rows
remained typed failures, delayed loading completed safely, stopping monitoring
restored the UI, and stopping the application-managed browser closed only its
PRISMA page while unrelated Chrome remained open. Runtime logs recorded lifecycle,
filter, public auction ID, result, and cleanup diagnostics without cookies,
credentials, or account data. Focused regression tests were added for both live
DOM corrections. Authentication and broader recovery remain scoped to P.23.2 and
P.23.3; clean-Windows validation is not claimed by this increment.

#### P.23.2. Add authentication/session handling if required

Status: **Completed**.

Completion note: P.23.1 live-site evidence established that the current daily
auctions workflow is public and works without authentication, including with the
research-consent banner left untouched. P.23.2 therefore adds focused validation
of the existing lifecycle-owned page before filtering and every live table read.
It accepts the expected PRISMA origin/path only when a meaningful auctions-page
landmark is visible, tolerates delayed rendering, recognizes authentication by a
sanitized redirect path or visible login structure, and reports typed
authentication-required or invalid-session failures. Diagnostics contain only
generation, safe classification, and origin/path without query strings, fragments,
userinfo, page content, cookies, storage, or session identifiers. No credentials,
cookie/profile persistence, login automation, retry loop, second browser, context,
or page were added. P.23 remains in progress because P.23.3 recovery work is not
complete.

#### P.23.3. Harden live-page failure and recovery behavior

Status: **Completed**.

Handle live-page timeouts, unavailable pages, DOM changes, and manually closed
browsers with complete recovery and user-visible lifecycle behavior.

Completion note: every live lookup now has a bounded controller wait and reports
a typed timeout instead of blocking a monitoring cycle indefinitely. A timeout
stops only its owning browser generation, abandons the stale request, and returns
the UI to a retryable non-monitoring state without automatic relaunch or an
unbounded retry loop. Closed or unusable pages, contexts, and browser disconnects
are converted to stable application-level failures; generation-aware lifecycle
callbacks stop active monitoring, perform idempotent managed-resource cleanup,
and cannot overwrite a newer generation. Normal `Stop Browser` cleanup remains
classified as user-requested and does not produce an unexpected-failure result.

Missing tables or required headers, malformed rows, unreadable statuses, and
ambiguous auction matches are typed page-structure failures. A genuinely absent
auction ID remains a separate typed result from a valid table, and live monitoring
never falls back to CSV data or fabricates a status. English UI messages distinguish
timeout, unavailable/closed page, unreadable page structure, and a missing auction.
Diagnostics record generation, lifecycle classification, termination type, and
retryable recovery without cookies, credentials, storage state, or page HTML.

Verification used deterministic fake pages and browsers only. The complete suite
passed with 185 tests. Project source and tests compiled successfully, and the
final diff passed whitespace validation. Manual validation with a real public
PRISMA session is still recommended for browser-close, disconnect, and live DOM
timing behavior; no new real-site validation is claimed by this increment.

### P.29. Add project-wide Windows CI

Status: **Completed**.

Run project-wide validation on GitHub Actions using `windows-latest` and pinned
project dependencies. The workflow runs for pushes to `main`, pull requests
targeting `main`, and manual dispatches. It executes the complete pytest suite
with headless Qt settings, compiles the project Python sources and tests, and
builds the existing PyInstaller specification as a packaging validation without
publishing a release or uploading build artifacts. Concurrent runs for the same
branch or pull request are cancelled when superseded.

Completion note: The Windows CI workflow and local reproduction instructions
were added and all relevant local validation passed. CI does not install
Playwright browser binaries and does not require secrets or interactive desktop
access.

### P.30. Final release readiness and versioned release archive

Status: **Completed (repository-side)**.

Version 1.0.0 is now authoritative in `version.py` and is exposed through Qt,
the compact window title, and PyInstaller Windows executable metadata. The
deterministic PowerShell release workflow validates the onedir executable,
creates `PrismaFunction-v1.0.0-windows-x64.zip` with `PrismaFunction` as its
top-level directory, filters runtime and development artifacts, and writes a
SHA-256 checksum. Automated metadata and script contracts, exact build and
verification instructions, v1.0.0 release notes, and the final release
checklist are included.

Completion note: Repository-side deliverables and automated validation for
this increment are complete. Actual package launch and functional validation,
archive inspection, checksum verification, and validation on a second Windows
PC remain checklist items unless explicitly recorded after running them. The
`v1.0.0` Git tag and GitHub Release publication are manual post-merge actions;
neither is claimed by this increment.

## 5. Git workflow для кожного етапу

1. На початку нового інкременту визначити рівно один bounded scope за актуальним
   `ROADMAP.md` і одразу надати користувачу один блок Git Bash команд для:
   - переходу на `main`;
   - отримання актуальних змін;
   - створення окремої англомовної feature branch для цього інкременту;
   - перевірки `git status --short --branch`.
   Команди на цьому кроці надаються користувачу, але не виконуються асистентом
   без окремого явного доручення.
2. У тому самому повідомленні одразу надати один самодостатній англомовний
   prompt для Claude Code. Prompt повинен доручати Claude Code:
   - прочитати `CLAUDE.md`, усі застосовні `AGENTS.md`, `ROADMAP.md` і
     `workflow_p.md`, а також пов'язані архітектурні документи, production code,
     tests, configuration, packaging files і поточний Git status;
   - реалізувати весь погоджений інкремент як одну завершену задачу без
     розширення scope;
   - працювати автономно в межах погодженого scope без постійних звернень за
     дозволом; зупинитися й запитати уточнення тільки перед значною зміною
     поведінки, архітектури, даних, безпеки або scope;
   - виконати найменшу достатню кількість перевірок: focused tests для зміненої
     поведінки, один final full test suite, потрібну compilation/packaging
     validation і `git diff --check`; не повторювати однакові дорогі перевірки,
     якщо код після них не змінювався;
   - оновити `ROADMAP.md` і `workflow_p.md`, якщо змінилися behavior,
     configuration, conditions або status;
   - не виконувати commit, push, merge, rebase, створення Pull Request або
     видалення гілки.
3. Після завершення Claude Code повинен надати один фінальний звіт із:
   - точним implemented scope;
   - списком змінених файлів;
   - результатами кожної фактично виконаної перевірки;
   - невиконаними manual/real-environment checks;
   - ризиками, blockers і підтвердженням відсутності commit та push.
4. Після отримання цього звіту асистент одразу надає один із двох наступних
   блоків команд залежно від характеру інкременту:
   - команди для створення review diff (`git status --short --branch`,
     `git diff --check`, `git diff --stat`, `git diff --binary --no-ext-diff >
     <increment>-final-review.diff`); або
   - точні команди для реальної перевірки програми з її запуском, якщо
     acceptance criteria потребують manual/Windows/PRISMA validation.
   Якщо потрібні обидві перевірки, спочатку виконується реальна перевірка, а
   після виправлень створюється фінальний diff.
5. Асистент перевіряє наданий diff або результат реального запуску. Якщо є
   actionable findings, він надає один вузький correction prompt для Claude
   Code; після виправлення застосовується той самий цикл звіту та перевірки.
6. Після явного схвалення всіх змін користувачем асистент в одному повідомленні
   одразу надає:
   - Git Bash команди для додавання тільки файлів інкременту, commit з
     англомовним повідомленням і push feature branch;
   - команди для створення Pull Request або чітку вказівку створити його в
     GitHub з base branch `main`;
   - окремий post-merge блок команд для переходу на `main`, `git pull
     --ff-only`, перевірки статусу та виходу з feature branch;
   - команди видалення локальної й remote feature branch тільки якщо вона вже
     merged, більше не потрібна і користувач погодив її видалення.
7. Після підтвердження користувача, що merge і post-merge cleanup завершені,
   асистент одразу визначає наступний дозволений інкремент за актуальним
   `ROADMAP.md` і надає короткий текст для початку нового чату. Реалізація
   наступного інкременту в поточному чаті не починається.

### P.31. Modern PySide6 monitoring dashboard

Status: **Completed**.

The desktop interface now uses a responsive monitoring-dashboard layout with a
graphite workflow sidebar and a light main workspace. It provides explicit
browser and monitoring state badges, context-aware controls, truthful summary
counters, and a model-backed auction table with search, status filtering, and
incremental live-result updates. Recent user-relevant activity is visible
without replacing rotating diagnostic logs, and the log directory can be
opened through Qt. Presentation code, filtering, table state, status delegates,
and the centralized theme are separated from browser and monitoring logic.

Completion note: Focused offscreen Qt coverage verifies initial state, CSV and
browser transitions, stale generations, monitoring prerequisites and lifecycle,
incremental counters and rows, search/filter behavior, activity handling,
stable error wording, and managed-resource shutdown. Manual visual checks at
Windows display scaling levels from 125% through 200% remain recommended.

### P.32. Windows installer and uninstaller using Inno Setup

Status: **Completed**.

The version-controlled `PrismaFunction.iss` definition builds a per-user Inno
Setup installer from the existing PyInstaller onedir distribution at
`dist\PrismaFunction`. Installation does not require administrator privileges
and defaults to `%LOCALAPPDATA%\Programs\PrismaFunction`.

The installer uses the authoritative application identity and executable version
metadata, creates a Start Menu shortcut, offers an optional desktop shortcut,
supports paths containing spaces, and includes a functional uninstaller. A
stable application identifier supports in-place upgrades of later versions.

Only the validated packaged runtime is installed. Python source, tests,
development files, caches, runtime databases, logs, generated workbooks, and
other writable user data are excluded. Uninstall removes installed application
files and shortcuts but intentionally preserves application-owned runtime data
below `%LOCALAPPDATA%\PrismaFunction`.

`build-installer.bat` validates the existing PyInstaller distribution and invokes
Inno Setup 6. Optional signing is supported through the documented Inno Setup
sign-tool configuration. Deterministic tests verify the installer contract,
per-user behavior, shortcut definitions, upgrade identity, uninstall behavior,
and packaging exclusions. Build, signing, installation, upgrade, uninstall, and
manual validation procedures are documented in `INSTALLER.md`.

### P.33. Unified PRISMA CSV import foundation

Status: **Completed — P.33.1-P.33.7 are Completed**.

P.33 separates two independent inputs that must never be converted into or
silently substituted for one another.

#### CSV contracts

The **Monitoring CSV** configures live auction monitoring. It is UTF-8,
comma-delimited, and has exactly these columns in this order:
`auction_id`, `auction_url`, `lot_number`, `item_name`, `expected_status`,
`last_known_status`, `check_interval_seconds`, `enabled`. Existing row
validation in `load_auction_csv()` remains authoritative and backward
compatible. A UTF-8 BOM is not accepted by the established contract.

The **PRISMA Export CSV** is a raw export downloaded from PRISMA. It is cp1252,
semicolon-delimited, and has exactly these columns in this order:
`Auction ID`, `Start of Auction`, `Network Point Name Exit`,
`Network Point EIC Exit`, `Network Point Type Exit`, `Network Point ID Exit`,
`Network Point Name Entry`, `Network Point EIC Entry`,
`Network Point Type Entry`, `Network Point ID Entry`,
`Network Point Name Exit/Entry`, `Network Point EIC Exit/Entry`,
`Network Point ID Exit/Entry`, `Published capacity`,
`Published capacity unit`, `Marketable Capacity`,
`Unit Marketable Capacity`, `Marketed Capacity`, `Unit Marketed Capacity`,
`Regulated Tariff Exit TSO`, `Unit Regulated Exit Capacity Tariff`,
`Regulated Tariff Entry TSO`, `Unit Regulated Entry Capacity Tariff`,
`Surcharge`, `Unit Surcharge`, `Product Runtime Start`, `Product Runtime End`,
`Capacity Category`, `TSO Exit`, `TSO EIC Exit`, `TSO Entry`, `TSO EIC Entry`,
`Direction`, `Type of Gas`, `State`. A BOM is not part of the confirmed export
contract.

#### P.33.1. Separate and detect both CSV contracts

Status: **Completed**.

P.33.1 adds a single source of truth for both exact headers and a public typed
detection/routing API. Detection reads only the header, uses structure rather
than the filename, returns `monitoring`, `prisma_export`, `unsupported`, or
`ambiguous`, and rejects incomplete headers, duplicates, wrong delimiters,
empty files, and unknown formats with specific English errors. Ambiguity is an
explicit outcome for API stability, although it is structurally impossible for
the current exact, disjoint headers. `process_csv()` explicitly requires a
PRISMA export; `load_auction_csv()` keeps its existing monitoring validation.

Definition of Done for P.33.1: the real repository export confirms the complete
PRISMA header; both exact contracts and reading rules have one source of truth;
no partial or fallback detection occurs; existing capacity, tariff, surcharge,
product-type, direction, database, Excel, browser, monitoring, and UI behavior
is unchanged; focused and complete tests pass; project Python files compile;
and the final diff passes whitespace validation.

#### P.33.2. Complete original PRISMA export import — Completed

The detailed importer classifies every physical source row as imported,
filtered, or rejected and reports human-readable CSV row numbers, stable reason
codes, English messages, and invariant counts. Issues intentionally do not copy
complete source rows. The compatibility `process_csv(path)` entry point still
requires the exact PRISMA Export contract and returns only imported normalized
row dictionaries.

Marketed capacity supports `kWh/h`, `MWh/h` (×1000), and `kWh/d` (÷24). Valid
values below 1000 kWh/h are filtered; empty, malformed, negative, non-finite,
and unsupported-unit values are rejected. Entry, Exit, and Exit/Entry map to
`entry`, `exit`, and `bundle`, using their corresponding network-point fields.
Dates use strict `DD.MM.YYYY HH:MM` parsing and runtime must be positive. Product
types are `WD` for runtimes through 24 hours beginning on the auction calendar
date, `Day Ahead` for other runtimes through 24 hours, then `Month` through 31
days, `Quarter` through 93 days, and `Year` above 93 days.

Regulated tariff components and surcharge support only
`cent/kWh/h/Runtime` (×10) and `cent/kWh/d/Runtime` (×10 ÷24), producing
EUR/MWh/h values. An empty value/unit pair is zero. Unsupported currencies,
including pence and halér, are explicitly rejected rather than converted or
mislabelled as EUR.

#### P.33.3. Market and storage reference enrichment — Completed

P.33.3 adds `prisma_references.py`, a UI-independent immutable catalog of stable
canonical references, explicit classifications (`market` or `storage`), and
side-specific aliases. Lookup strips surrounding whitespace and compares case
insensitively. It performs no fuzzy, substring, or inferred matching. Catalog
construction rejects blank, surrounding-whitespace, duplicate, or conflicting
canonical names and duplicate/conflicting side/alias pairs, both within one
entry and across entries.

Semantic P.33.2 imports are enriched only after parsing and validation succeed.
The normalized source `Direction` remains authoritative: `entry` requires the
entry-side value, `exit` requires the exit-side value, and `bundle` requires
both. A populated side irrelevant to that direction is preserved in `raw_row`
but ignored; it cannot alter direction, network point, or enrichment. A missing
required side or unknown required alias rejects the row with a typed enrichment
reason code plus field, side, and unchanged source-value context.

Successful detailed records retain the unchanged 18-field normalized row, an
immutable copy of the complete raw row, the starting physical source line, and
optional side-specific `exit_reference` / `entry_reference` values. Each
resolved reference contains its canonical name, `market` or `storage`
classification, and side. `process_csv()` and normalized row dictionary keys
remain backward compatible; legacy `exit_market` and `entry_market` names are
preserved for P.33.2 compatibility even when the classified reference is a
storage facility.

The deliberately small seed catalog contains the exact five market mappings
from `mapping.csv` (BG/HTP, BG/RS, CEGH/MGP, CEGH/PSV, and CEGH/SK) and the VGS
Storage Hub alias evidenced by `Auction_overview.csv`. It is not represented as
a complete PRISMA catalog. Extend it only by adding confirmed `PrismaReference`
entries and explicit side aliases to `DEFAULT_PRISMA_REFERENCES`; constructor
validation prevents ambiguous additions.

Validation evidence covers direction authority, side mismatches, classified
market/storage references, bundles, exact normalized aliases, unknown/missing
required sides, intra-entry and cross-entry alias conflicts, raw/source-line
preservation, compatibility, and deterministic ordering.
`python -m compileall .` and `git diff --check` also pass.

#### P.33.4. Controlled daily source updates

Status: **Completed**.

`prisma_source_updates.py` provides a deterministic, UI-independent lifecycle
boundary for caller-supplied local PRISMA Export CSV files. The caller supplies
an exact `datetime.date`, a timezone-aware evaluation time, and the previous
immutable accepted state. The policy computes SHA-256 from the exact file bytes
and exposes only the basename in audit metadata. It never infers dates or reads
the clock.

The stable lifecycle statuses are `APPLIED`, `UNCHANGED`, and `REJECTED`, with
typed reasons for applied, identical, stale, conflicting, future-dated, and
invalid sources. A first or newer valid source is applied. An already accepted
date and digest is unchanged without rerunning the importer; different content
for an accepted date, stale dates, and future dates are rejected before import.
`import_prisma_export()` remains the authoritative validation boundary. Fatal
validation never advances state or exposes a partial import, while header-only
exports and row-level filtered/rejected outcomes remain valid auditable imports.
Only an applied result returns advanced accepted state.

The pure daily due policy compares a caller-supplied aware local evaluation time
with an explicit wall-clock scheduled time. It does not sleep, start threads, or
read the system clock; acceptance for the source date suppresses another due
update. Tests cover local times before and after the schedule and non-UTC
offsets.

P.33.4 does not change `MonitoringScheduler`, `AuctionStorage`, SQLite schemas,
the UI, or source files. It adds no threads, browser automation, downloads, or
persistence. End-to-end persistence/UI integration and user-facing issue
reporting are completed in P.33.5. Automatic downloading remains outside the
confirmed local-file import scope.

Validation evidence: focused lifecycle policy tests, affected processor/storage/
scheduler contract tests, the complete pytest suite, Python source compilation,
and `git diff --check` pass for this increment.

#### P.33.5. Integrate the completed import workflow — Completed

SQLite is the authoritative source-operation ledger. Each operation is identified
by source date, exact-byte SHA-256 digest, and a generated operation ID. A pending
record is durable before auction mutation; auction changes, persisted summary
metadata, and the `data_committed` transition are one transaction. The cumulative
workbook is generated under a unique name in its destination directory, closed,
validated, and atomically replaced before the operation becomes `accepted`.
Failures retain a recoverable ledger state and never overwrite a prior workbook;
a conflicting same-date digest is blocked until recovery. Exact retries report
the stored accepted summary and regenerate a missing or invalid workbook from
SQLite without changing auction rows. Legacy accepted-state JSON remains readable
when no ledger exists, but SQLite owns all new lifecycle decisions.

Automatic browser downloading and authentication automation remain outside P.33.5;
the workflow accepts only an explicitly selected local PRISMA Export CSV.

P.33.5 adds an explicit `Import PRISMA Export` action and source-date control to
the PySide6 UI. It is independent from `Load Monitoring CSV`, which remains the
Monitoring CSV entry point. The central contract detector rejects Monitoring,
unsupported, and ambiguous inputs with specific English messages before detailed import.

`prisma_import_workflow.py` is the UI-independent orchestration boundary. It
uses the existing audited importer, reference enrichment, controlled daily
source policy, SQLite operation transaction, and atomic Excel export. Parsing,
enrichment, and update rules are not duplicated in the UI.

Long-running work executes outside the Qt GUI thread. Qt signals restore the
controls on success or failure, while status and activity report processed,
inserted, updated, unchanged, filtered, rejected/audit issue counts, issue
details, and output destination. Browser ownership, monitoring, scheduler,
search/filter/table counters, shutdown, and Monitoring CSV semantics remain
unchanged. Automatic downloading, authentication automation, and schema
redesign are outside this completed local-file integration scope.

Validation evidence: focused workflow/storage/UI recovery tests pass (52 tests),
focused importer/reference/source-policy/contract tests pass (101 tests), and
the complete suite passes (299 tests). Production modules compile and the final
diff passes whitespace validation.

#### P.33.6. Manual validation fixes — Completed

P.33.6 completes two changes identified by manual validation. The Monitoring CSV
action is labelled `Load Monitoring CSV` consistently in the button, file dialog,
and PRISMA-import rejection guidance without renaming its established internal
APIs or the separate `Import PRISMA Export` action. The cumulative `Auctions`
worksheet now receives one deterministic header-keyed set of column widths after
pandas creates the staged workbook. Widths are verified with a numeric tolerance
by the existing openpyxl validation boundary before atomic publication, for both
header-only and populated output. An exact retry therefore repairs an otherwise
valid legacy workbook with default widths from authoritative SQLite data without
mutating auction rows or changing source-operation semantics. Microsoft Excel is
not required.

Historical Market / Storage backfill was investigated but is deliberately not
implemented in P.33.6. Automatic backfill during normal import/update is rejected.
Existing nonblank values must never be overwritten because their provenance and
possible user edits are unknown. A future explicit maintenance operation may
enrich only blank single-side rows whose direction is exactly `entry` or `exit`,
whose retained network point is present, and for which the current reference
catalog returns one exact side-aware canonical match. Unknown, ambiguous,
missing-identity, and insufficient-identity rows must be skipped and audited.
Historical bundle rows cannot be reconstructed safely because SQLite does not
retain both original side-specific source identities. `network_point_id` must not
be used until an authoritative mapping exists. Fuzzy, substring, TSO-based, and
display-text guessing are prohibited.

Any future historical maintenance operation must be explicit, transactional,
idempotent, rollback-safe, and auditable at row level. Its execution surface and
durable audit format remain product decisions. P.33.6 does not add a migration,
GUI maintenance action, CLI, automatic backfill, database mutation, or new
maintenance module, and it does not claim that historical rows were modified.

Acceptance criteria: the UI-label fix and Excel-width fix are implemented and
covered by focused regression tests; legacy default-width output is repairable by
exact retry without database-row changes; the backfill safety investigation and
its constraints are documented; implementation of an explicit historical
maintenance backfill remains a deferred follow-up. Focused and complete tests,
Python compilation, and whitespace validation pass.

#### P.33.7. Explicit historical Market / Storage backfill — Completed

`AuctionStorage.backfill_historical_market_storage()` is the sole public launch
point. It is never called by schema creation, application startup, CSV import,
daily update, export, or storage opening. There is no overwrite mode. The
existing immutable `DEFAULT_PRISMA_REFERENCES` catalog, or an explicitly supplied
`PrismaReferenceCatalog`, remains the only mapping authority.

Storage initialization enables and verifies foreign keys outside a transaction,
then acquires `BEGIN IMMEDIATE` before reading any schema fingerprint. Concurrent
initializers therefore serialize through SQLite's configured busy timeout: a short
overlap waits and reclassifies the committed current schema, while an expired timeout
raises SQLite's lock error without leaving a partial schema. One backfill call likewise
acquires `BEGIN IMMEDIATE` before its first `SELECT`, then examines every
stored auction in stable SQLite `id` order and performs classification, validation,
updates, run/audit insertion, and commit in that transaction. Valid `entry` and
`exit` rows use exact side-aware lookup of the retained `network_point`. NULL or
whitespace-only required-side values are missing. Trimmed, case-insensitive canonical
equivalents retain their original representation; genuine conflicts leave the entire
row unchanged. Unknown aliases are skipped. Malformed dates, reversed intervals,
missing identities/product types, and invalid or non-finite persisted numerics are invalid;
naive flow timestamps are compared only with naive timestamps, aware timestamps are
compared as instants, and mixed-awareness or otherwise unorderable pairs are invalid;
bundle rows are skipped because both original side identities were not retained.

The typed `HistoricalBackfillSummary` includes a collision-safe `run_id` and reports `examined`, `updated`, `unchanged`,
`skipped`, `conflicts`, `invalid`, `committed`, and ordered row audit. Mutually
exclusive row counts equal `examined`. Each `HistoricalBackfillAudit` contains
the SQLite row id and composite key, previous and resolved values, status,
machine-readable reason, English message, and changed flag. Statuses are
`updated`, `unchanged/already_complete`, `skipped/unresolvable`, `conflict`, and
`invalid`. Reasons are `missing_values_filled`, `already_complete`,
`reference_unresolvable`, `insufficient_bundle_identity`, `reference_conflict`,
and `invalid_historical_row`.

Each successful invocation appends a UTC-timestamped `committed` record to
`historical_market_storage_runs` and exactly one positioned row record per examined
physical auction to `historical_market_storage_audit`; `(run_id, auction_row_id)` is
the row-audit primary key. Both foreign keys use `ON DELETE RESTRICT`, and every
storage connection enables and verifies `PRAGMA foreign_keys = ON`. The unreleased
single-column experimental audit table is replaced only when its ordered column name,
declared type, NULL/default/PK metadata, foreign keys, and indexes exactly match that
one known fingerprint. The current runs/audit tables are likewise accepted only with
their exact `table_info`, foreign-key, and index fingerprints, including the stable
`auction_row_id` index. Any unknown, extended, or partial schema fails closed before
mutation. Migration uses separate DDL statements in one explicit transaction: dropping
the experimental table and creating runs, audit, and indexes commit or roll back together,
and `auctions` is never dropped or rebuilt. Ordinary pre-P.33.7 databases initialize
normally. Every production storage connection is closed exactly once after transaction
completion on both success and exception paths. A close failure after success remains
visible; while another failure is active, rollback and close diagnostics are attached
best-effort, and failure of that diagnostic mechanism never replaces the primary
exception or traceback. If SQLite rollback itself fails, only preservation of the primary
exception and a deterministic close attempt are guaranteed. When rollback succeeds,
processing, SQL, audit, or validation exceptions roll back auctions, the run, and row
audit and return no success summary. A successful repeat changes no auction rows, appends its own
run/audit history, and reports them as already complete. Invocation remains API-only.

#### P.33.8. Expanded authoritative Market / Storage mapping — Completed

The immutable default reference catalog now covers every exact side-specific
network-point name that the checked-in `Auction_overview.csv` explicitly marks as
`RESERVOIR`: 37 Exit aliases and 37 Entry aliases. The existing five Market pairs
remain the exact mappings from `mapping.csv`; no market identity was derived from
TSO, EIC, display text, or geography.

Storage aliases are declared separately for Exit and Entry. An alias observed on
only one side is not assumed to be valid on the other side. Exact source strings
that occur on both sides share one catalog entry, while different injection and
withdrawal names remain distinct instead of being grouped heuristically. The
established `VGS Storage Hub` canonical display name is preserved for backward
compatibility. Lookup normalization remains limited to surrounding whitespace and
case, and constructor conflict detection is unchanged.

Regression coverage derives the authoritative Storage sets from the checked-in
export and proves both completeness and absence of unevidenced Storage aliases for
each side. It also verifies that a one-sided Storage alias cannot resolve on the
unevidenced side. Import contracts, normalized row fields, persistence schemas,
backfill semantics, and UI behavior are unchanged.

### P.34.1. Safe auction deduplication — Completed

Every imported auction requires the nonblank selected network-point ID for its
normalized direction: `Network Point ID Entry` for Entry, `Network Point ID Exit`
for Exit, and `Network Point ID Exit/Entry` for Exit/Entry. Blank and
whitespace-only selected IDs are rejected as audited source rows with reason code
`missing_network_point_id`, the exact selected field name, the original source
value, and the applicable `entry` or `exit` side; bundle issues have no single
side. Existing normalization trims surrounding whitespace while preserving valid
identifier text, including leading zeroes.

Network-point names are display and enrichment values, not identity fallbacks.
The persisted identity remains the existing five fields: `auction_id`,
`network_point_id`, `direction`, `flow_start`, and `flow_end`.

`AuctionStorage` validates the complete caller-supplied batch before its first
auction `INSERT` or `UPDATE`. A blank or whitespace-only `network_point_id` fails
with `AuctionStorageError`. Identical rows sharing one identity remain idempotent
and retain the established processed/inserted/updated/unchanged accounting.
Different persisted values sharing one identity are a conflicting batch and fail
closed with `AuctionStorageError`; no row from that batch can insert or modify an
auction, so existing stored auctions remain unchanged.

P.34.1 does not change or rebuild the SQLite `auctions` schema or its unique
constraint. It performs no migration, deletion, or modification of historical
rows. P.26 runtime-data-path work is explicitly outside this increment.

Acceptance evidence covers Entry, Exit, and Exit/Entry audit context;
whitespace-only IDs; preservation of valid IDs; identical duplicates; conflicts
against empty and populated databases; direct storage validation; reference
enrichment; and the integrated import workflow. Focused and complete tests,
Python compilation, and whitespace validation are required.

### P.24. Persist monitoring checks and status transitions

Status: **Completed**.

Every actual live lookup is stored in the runtime SQLite database at
`RuntimePaths.database`. The monitoring schema is additive and semantically
independent from PRISMA Export auctions, source-operation ledgers, and historical
backfill tables. It contains an immutable check history, a transition history
linked to its originating check by an enforced foreign key, and one latest
successful status row per exact textual auction ID. Schema creation uses
`CREATE TABLE IF NOT EXISTS`, deterministic indexes, verified foreign-key
enforcement, and a write-reserving transaction, preserving existing database
content.

The live lookup runs without holding a database transaction. When its observation
is ready to persist, the storage transaction reads the latest successfully
persisted status for that exact auction ID. If none exists, the caller-supplied
Monitoring CSV `last_known_status` is the initial baseline; the CSV is never
rewritten. Storage, rather than the engine or caller, derives the final
`previous_status`, `status_changed`, and `Success`/`Changed` classification. A
successful observation always advances latest state. It produces a transition
only when its current status differs from that authoritative effective baseline.
Repeated observations therefore remain visible as checks without duplicate transitions.
An `Error` check retains the effective baseline as both previous and fallback
current status, is audited, and neither advances state nor creates a transition.
`Skipped` means that no live lookup occurred and is not persisted.

Authoritative baseline resolution, canonical classification, the check, its
optional transition, and successful latest-state update occur in one
`BEGIN IMMEDIATE` transaction. Rollback and close diagnostics never
replace the primary failure. Event timestamps come from application-owned,
timezone-aware datetimes and are normalized to ISO-8601 UTC with a `Z` suffix;
SQLite `CURRENT_TIMESTAMP` is not used for monitoring event time. Short-lived
connections make the abstraction safe for the existing worker-thread model.
The worker persists synchronously before the scheduler callback emits results
to Qt. A persistence failure terminates the run, returns the GUI to its
retryable idle state, shows a stable English error, and does not emit the
unpersisted cycle as a successful UI update. Reopening the application or a new
persistence object against the same database restores the baseline.

Deterministically ordered read APIs expose all checks and transitions with an
optional auction-ID filter, plus latest-status lookup for one auction or a set.
The records returned by these APIs are immutable typed dataclasses. P.24 adds no
notification behavior or UI; user-visible status-change notifications remain
exclusively P.25.

Automated validation covers additive schema initialization, foreign keys,
unchanged and changed observations, repeated and sequential transitions, error
and skipped semantics, rollback, restart restoration, stale-CSV override,
independent IDs, ordering, timezone normalization, runtime-path wiring, worker
ordering/failure recovery, and existing monitoring/import/storage/packaging
regressions. No manual live-session or installed-package validation is claimed
for P.24.

### P.25. User-visible status-change notifications

Status: **Completed; manual Windows visual/accessibility validation remains recommended**.

Notifications are derived only from the persisted `MonitoringResult` objects
delivered for the current monitoring cycle through the existing
`monitoring_results` Qt signal. An immutable notification value object owns the
independently testable decision and exact message formatting. A result is
eligible only when `status_changed` is true, `result` is exactly `Changed`, and
trimmed previous and current statuses are both nonempty and different. Its
stable English message is `Auction <auction_id>: <previous_status> →
<current_status>`.

Initial baselines, successful unchanged checks, skipped or disabled records,
lookup errors, persistence failures, malformed empty or equal statuses, cycle
summaries, and historical transitions read after restart do not create
notifications. No notification history is persisted or replayed; P.24 remains
the sole persistence authority. No toast, tray, email, sound, network, modal,
or background-service behavior was added.

Eligible transitions appear in scheduler result order directly below the one
existing aggregate summary for that cycle in Recent activity. Status-change
entries carry an explicit textual label, bold emphasis, contrasting foreground,
an accessible description, and a typed item role, so distinction does not rely
on color. Notifications and ordinary activity share the existing newest-first
50-item bound and Clear action. All widget mutation remains in the Qt main-thread
slot reached through the existing signal/slot boundary.

Focused automated validation covers exact eligibility and formatting, one and
multiple ordered changes, unchanged/baseline/error/skipped/malformed results,
mixed bounded history, accessible presentation, Qt signal delivery, and exactly
one aggregate cycle summary. The complete pytest suite, Python compilation, and
whitespace validation passed for this increment. A manual Windows smoke check
of visual contrast, screen-reader wording, and live-transition appearance is
still recommended; no such manual validation is claimed here.

### P.26. Move writable runtime data to the user data directory

Status: **Completed; manual installed-package migration smoke testing remains recommended**.

One authoritative runtime-path module resolves source and frozen execution to
the same Windows user-data root. `LOCALAPPDATA` must be absolute; when it is
missing, the deterministic Windows-compatible fallback is
`%USERPROFILE%\AppData\Local` (or the equivalent home directory). The
application never uses its installation directory, bundle directory, current
working directory, or temporary directory as a normal-write fallback.

Final layout:

```text
%LOCALAPPDATA%\PrismaFunction\
  data\prisma_monitor.db
  data\result\prisma_auctions.xlsx
  state\prisma_import_state.json
  logs\prisma-function.log[.1-.3]
```

At startup, Qt is created first so path failures can be reported visibly. The
runtime paths are then validated once and the required file logger is opened in
the new location before migration begins. If that handler cannot be created,
startup stops and migration is not called; no claim is made that file
diagnostics exist. Migration then covers only paths confirmed by the
application's prior code: `data\prisma_monitor.db`,
`data\result\prisma_auctions.xlsx`, and `data\prisma_import_state.json` beside
the source tree or packaged executable, plus the former
`%TEMP%\PrismaFunction\logs\prisma-function.log[.1-.3]` logging fallback.
User-selected CSV files and unrelated files are never scanned or moved.

The legacy current log normally conflicts with the newly opened current log, so
it is retained as a deterministic `.legacy-<digest>` copy rather than replacing
the active handler's file. Rotated legacy logs follow the same conflict policy.

An atomically created lock directory with a unique PID/token owner record
serializes concurrent launches. A briefly empty or malformed new lock is never
removed. Recovery requires a minimum age and a non-running or unreadable stale
owner. On Windows, stale removal and release open the directory with read-only
identity/query plus synchronization/delete rights, verify its volume/file ID,
and rename that exact handle to quarantine; this prevents a path replacement
from being removed. Release also checks the exact owner token. Process liveness
uses read-only `OpenProcess` and `WaitForSingleObject` queries with guaranteed
handle cleanup, never process signaling. SQLite uses the
SQLite backup API and an integrity check, incorporating committed WAL content
without copying `-wal` or `-shm` blindly. Source and destination are compared as
consistent verified snapshots using deterministic logical content, never as a
normalized backup versus raw live bytes. Other artifacts are copied to a staged
file, SHA-256 verified, and atomically published. Repeated migration treats an
identical destination as complete. A different destination is preserved and
the legacy version is retained beside it as `.legacy-<digest>`; the original
source also remains available. Staged files are removed after interruption and
migration retries on the next launch. Path escape outside the confirmed roots
is rejected.

If the user-data root, SQLite backup, verification, or migration lock cannot be
used safely, startup stops with an actionable data error; it does not create a
new empty database over uncertain legacy data. For recovery, close other
PrismaFunction processes, preserve both legacy and user-data copies, confirm
`LOCALAPPDATA`, and retry. Conflict copies can be inspected or restored
manually after closing PrismaFunction; no conflict is overwritten silently.

### P.27. Package the application with PyInstaller

Status: **Completed; same-machine interactive launch smoke testing remains manual**.

The authoritative `PrismaFunction.spec` now produces a Windows `onedir`,
windowed `PrismaFunction.exe` with no console window. PyInstaller hooks collect
PySide6 and its Windows platform plugin, while the specification explicitly
collects Playwright modules and data, including its Node driver. Application
dependencies are discovered from the production entry point; pytest,
setuptools, source files, caches, and other developer-only content are excluded.
The existing 1.0.0 Windows file and product metadata remain attached.

`validate_package.py` deterministically verifies the executable, Python runtime,
required Qt libraries and platform plugin, and Playwright driver. It also
rejects source/developer files and pre-created writable database, workbook,
state, or log artifacts. Packaged runtime writes continue to resolve only below
`%LOCALAPPDATA%\PrismaFunction`; the distribution is not a write target.
Exact build, structural validation, metadata verification, and isolated
same-machine startup commands are documented in `BUILDING.md`. Clean-machine
validation remains P.28, and no P.32 installer work is included.

### P.28. Validate the executable on a clean Windows environment

Status: **In progress — the 2026-07-18 physical Windows result is Partial / Blocked, not Pass**.

The dated evidence in `P28_VALIDATION_2026-07-18.md` records successful
non-elevated packaged startup, English UI rendering, Chrome launch, public
PRISMA monitoring, header-only export processing, workbook opening, user-data
placement, process cleanup, and relaunch. It also records the remaining blockers:
the computer had developer tools installed, the account was a local
Administrators-group member, the export had no data rows, Edge and unsupported
default browsers were not tested, and disappearing live auction IDs prevented
restart baseline revalidation. A fully clean physical Windows test is still
required; neither P.22 nor P.28 is fully passed.

## 6. Definition of Done

Етап вважається завершеним, коли:

- реалізовано тільки погоджений scope;
- UI text is English;
- CSV headers and values are English;
- помилки обробляються;
- retry працює;
- ресурси очищаються;
- focused tests проходять;
- full test suite проходить;
- each increment demonstrates that it remains consistent with the authoritative customer requirements;
- Copilot review не має невиправлених critical findings;
- зміни об’єднані з `main`;
- feature branch видалена.

### P.34.2. Maximize the managed browser window — Completed

The Playwright-managed Chrome or Edge window launches with Chromium's
`--start-maximized` argument. Its page is created with `no_viewport=True`, so
Playwright does not constrain the rendered PRISMA page to the default fixed
viewport and instead follows the native maximized window size.

Regression coverage verifies both launch settings while preserving default
browser detection, lifecycle ownership, filtering, monitoring, cleanup, and
retry behavior. Focused browser tests, the complete 418-test suite, Python compilation,
whitespace validation, and the manual Windows maximized-window smoke check passed.

### P.35. Authoritative PRISMA reference catalog expansion — Completed

The updated checked-in `Auction_overview.csv` is the only authoritative evidence
for this expansion. The immutable Storage catalog contains every exact nonblank
`Network Point Name Exit` and `Network Point Name Entry` explicitly classified as
`RESERVOIR`: exactly 50 Exit aliases and 51 Entry aliases. Aliases are admitted
only on the side where the export provides that classification.

No cross-side equivalence, canonical grouping, geography, TSO relationship, EIC
relationship, or Market mapping is inferred. The established `VGS Storage Hub`
canonical-name compatibility behavior is preserved, and the five explicit
`mapping.csv` Market mappings are unchanged. Import logic, normalized contracts,
persistence, historical backfill behavior, schemas, and UI behavior are also
unchanged.

Regression coverage derives both exact side-specific sets from the authoritative
export, proves catalog completeness and the absence of unevidenced Storage aliases,
and focuses on newly introduced aliases plus aliases evidenced on only one side.

#### P.35.1. Expand authoritative Market mapping catalog (Batch 1) — Completed

The immutable default Market catalog includes exactly two additional customer-approved,
side-specific network-point aliases: the Entry alias `Arnoldstein importazione
(35718301)` resolves to PSV, and the Exit alias `VIP DK-THE (H646) (H646)` resolves
to THE. Each accepted alias is linked by the same exact Auction ID between
`evidence/p35-1/Auction_overview.csv` and the Market Area on the stated page of
`evidence/p35-1/Auction_Overview.pdf`, and has normalized booked capacity of at least
1000 kWh/h. The filenames, SHA-256 digests, accepted rows, canonical markets,
Marketed Capacity values and units, and PDF pages are recorded in
`evidence/p35-1/EVIDENCE_MANIFEST.md`.

Twelve aliases from the preliminary 14-row candidate set were rejected because their
booked capacity normalizes below 1000 kWh/h. Other rows sharing an Auction ID between
the evidence files were not reviewed or accepted in Batch 1, even where their capacity
may meet the threshold. They remain outside P.35.1 and provide no mappings. This batch
adds no bundle or `RESERVOIR` aliases and makes no inferred, fuzzy, substring,
identifier-only, geographic, TSO, EIC, or automatic mapping available. Aliases remain
strictly side-specific. All earlier Market mappings and the complete Storage catalog
are preserved. Lookup normalization, import behavior, normalized output contracts,
persistence, schemas, historical backfill, UI, and browser behavior are unchanged.
P.35.1 accepts exactly two mappings and makes no completeness claim.

Focused regression coverage proves exact canonical Market resolution for both aliases,
opposite-side rejection for each alias, continued rejection of representative fuzzy,
substring, and identifier-only values, the exact complete Market alias set, and the
existing complete Storage catalog contract.

#### P.35.2-P.35.5 — Cancelled (2026-07-28)

An uncommitted working-tree implementation of automated/paired official CSV+PDF
acquisition (deterministic staging, geometry-based PDF parsing, a paired-operation
ledger) was in progress under this line. It was cancelled without ever being
committed, because `Prisma Function.odt` — adopted as the sole authoritative business
specification — requires a **manual** official-CSV download and processing workflow
(manual open/close of PRISMA, manual date selection and download by the user, manual
file hand-off to the program), not automated or paired source acquisition. The
cancelled diff was backed up to `Prisma-function-backups/p35.2-cancelled-2026-07-28/`
before removal. `ROADMAP.md`'s "Authoritative specification pivot" and "P.36 roadmap"
sections are now the authoritative forward plan and list the open questions that must
be answered before implementing each new increment; they take precedence over any
remaining automated-acquisition assumptions elsewhere in this document.

#### P.36.2. Manual "Open Prisma" / "Close Prisma" lifecycle — Completed (2026-08-01)

Both former P.36.2 prerequisites are now resolved by explicit customer decisions recorded
in `ROADMAP.md`'s "Resolved specification questions":

- The manual CSV workflow **replaces** the existing live PRISMA monitoring dashboard,
  scheduler, and automated monitoring workflow (P.7-P.25, P.31); they are not intended to
  coexist in the final product.
- "Open Prisma" must open exactly
  `https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions` — the
  same URL the superseded monitoring subsystem already targeted.

`prisma_lifecycle.py` adds `PrismaLifecycleController`, a UI-independent, thread-based
lifecycle boundary that owns exactly one browser session at a time. `open()` launches the
Windows default browser (reusing `DefaultBrowserDetector`) and navigates only to the
approved `PRISMA_OFFICIAL_URL` (re-exported from `browser.PRISMA_AUCTIONS_URL`, the single
source of truth for the approved URL); it performs no login, filtering, date selection,
download, monitoring, or polling automation. Repeating `open()` while a session is already
opening, open, still closing (`CLOSING`), or stuck with unconfirmed cleanup (`CLOSE_FAILED`,
see below) is a deterministic no-op returning the existing generation, so no uncontrolled
duplicate session can be created even across a rapid Close-then-Open click. `close()` only
signals cancellation; it returns immediately without waiting for cleanup and is idempotent
when nothing is open, a close is already in progress, or a prior close's cleanup could not
be confirmed. The controller stays in `CLOSING` — never reporting `IDLE` — until the
background worker thread has actually called `browser.close()` and `playwright.stop()`.

Both cleanup calls are tracked independently and neither exception is swallowed silently: if
`browser.close()` **or** `playwright.stop()` raises, the failure is logged with full
diagnostic context (`exc_info=True`) but the controller never transitions to `IDLE` and never
publishes a successful close-completed event. Instead it moves to a dedicated
`CLOSE_FAILED` state, keeps the owned `_browser`/`_playwright` references (rather than
discarding the only handles to resources that may still be alive), and publishes a typed,
non-sensitive failure event (`kind="close"`, `success=False`,
`"The PRISMA browser could not be confirmed closed."` — no raw exception text crosses the
controller/UI boundary). `CLOSE_FAILED` behaves like `CLOSING` for safety purposes — `open()`
still refuses a new generation and `close()` is a no-op — so the application can never
silently start a second session or report a clean shutdown while an owned browser process
may still be running. There is deliberately no automatic retry of the failed cleanup call
itself (Playwright's sync-API objects are only valid on the worker thread that created them,
and a bare retry of the exact same call that just failed has no expected effect); recovering
from `CLOSE_FAILED` requires restarting PrismaFunction. Only when both cleanup calls succeed
does the controller transition to `IDLE` and publish the close-completed event
(`kind="close"`, `success=True`).

`join(timeout=...)` lets a caller wait deterministically for that same owned worker thread
(and only that thread) to finish, without touching any unrelated browser, profile, or
process — but a finished worker thread by itself does **not** mean cleanup succeeded (the
thread exits normally either way, since the cleanup exceptions are caught); callers that need
to know whether the browser was actually confirmed closed must also check
`PrismaLifecycleController.state`.

**Real-runtime evidence log for manual-closure detection (do not delete; each fix attempt below
was independently retested on real Windows and the outcome is recorded exactly as observed).**

1. *First attempt.* Made `browser.is_connected()` polling unconditional instead of gated on
   `browser.on("disconnected", ...)` attachment success. **Failed real X-button retest**: the
   browser window closed but PrismaFunction kept reporting "Prisma open" indefinitely.
2. *Second attempt.* Added `page.on("close", ...)`, `context.on("close", ...)`, and
   `page.is_closed()` polling, reasoning that closing the visible window closes only its owned
   `Page`/`BrowserContext` while the underlying `Browser` (e.g. a Chrome/Edge process that keeps
   running in the background after its last window closes) can stay connected. **Failed real
   X-button retest again**: `browser.on("disconnected")`, `browser.is_connected()` polling,
   `page.on("close")`, `page.is_closed()` polling, and `context.on("close")` all failed to fire
   or change state on the real machine. This means the previous paragraph's "verified technical
   cause" claim was wrong, or at least incomplete: Playwright's own `Page`/`BrowserContext`/
   `Browser` objects can *all* keep reporting "alive" after the real, visible window the user
   interacted with has disappeared, and no theory for why has been confirmed against real
   Windows telemetry.
3. *Third attempt.* Rather than add a further speculative combination of the same high-level
   Playwright signals, this attempt added one independent, lower-level signal: a browser-level
   CDP session (`browser.new_browser_cdp_session()`) subscribes to the Chrome DevTools Protocol
   `Target` domain — the ground-truth layer Playwright's own `Page`/`BrowserContext` wrappers are
   themselves built on. Immediately after `browser.new_page()`, a one-time `Target.getTargets`
   baseline identifies the sole existing `"page"`-type target as the owned target (an
   approximation: if zero or more than one page-type target already exists, the owned target is
   left unidentified rather than guessed, and detection falls back to the existing page/browser
   signals only, with a logged warning). A `Target.targetDestroyed` event naming that owned
   target ID is treated as a manual closure. This is layered on top of, not instead of, every
   previously attempted signal — none were removed, since none were confirmed harmful, only
   confirmed insufficient alone. To correlate this attempt's outcome, narrowly scoped, non-
   sensitive diagnostic logging (a periodic owned-object/target snapshot, a UI-side poll
   heartbeat, and per-CDP-event logging) was temporarily added on top of this signal; it recorded
   only opaque target IDs, counts, types, and booleans — never URLs, titles, or other page
   content. **Passed real X-button retest**: on 2026-08-01, PRISMA was opened from the
   application, the managed browser window was closed with its own X button, and the
   application correctly transitioned to "Prisma closed", re-enabled "Open Prisma", disabled
   "Close Prisma", and recorded "Prisma closed manually" — confirming the CDP
   `Target.targetDestroyed` signal is what corrected the previously observed real defect. Only
   the system's configured default browser was exercised in this test; separate validation of
   the other supported browser (Chrome or Edge, whichever was not the default at test time)
   was not performed and remains open for a future manual check, not a P.36.2 blocker since the
   controller applies the same detection logic regardless of which supported browser is
   launched.

Once this result was confirmed, the temporary diagnostic logging described in the third attempt
(periodic snapshot, UI poll heartbeat, per-CDP-event logging, and the associated tick counters)
was removed as no longer appropriate for normal production use, since it never logged page
content but did log at a volume unsuitable for routine operation. The CDP
`Target.targetDestroyed` detection logic itself, its correlation with the owned page target at
open time, and the existing Page/BrowserContext/Browser fallback signals are unchanged and
retained. A single `WARNING`-level log line remains for the case where the CDP baseline cannot
uniquely identify the owned target (ambiguous or zero page targets at open time), since that is
an actionable setup/correlation condition, not routine noise.

`app.py`'s `PrismaMonitorApp` adds an "Open Prisma" and a "Close Prisma" sidebar control
that call only `PrismaLifecycleController.open()` / `.get_events()` / `.close()` / `.join()`
and render typed states through a dedicated `prisma_badge` and status text; no browser,
Playwright, or process handle is ever held by the Qt layer — ownership stays entirely inside
`PrismaLifecycleController`. A `QTimer` polls `get_events()` on the Qt thread so Playwright
launch/navigation runs off the UI thread without blocking the event loop. Each poll drains
and processes *every* event `get_events()` returns for the active generation, in order,
instead of reacting to only the first match: `get_events()` permanently removes events from
the controller's queue, so returning after the first one silently discarded any further
event already pulled out of that same drain (e.g. a successful "open" immediately followed
by a manual "closed" once the browser closes before the next 50 ms poll tick). Processing
stops only once a terminal event for that generation has been applied (a failed "open", a
manual `closed`, or an application close-completed `close`), so a later terminal event from
the same drain is never lost and a stale-generation event mixed into the same batch (e.g.
after a manual-closure retry started a new generation) is skipped rather than misapplied;
this also guarantees at most one error dialog / activity entry per terminal transition.
Clicking "Close Prisma" no longer reports "Prisma closed" immediately: the UI enters a
stable "Closing Prisma…" state, disables both "Open Prisma" and "Close Prisma", and keeps
polling `get_events()` on the running timer — with no blocking call on the Qt thread — until
the controller's typed close-completed event for the active generation arrives; only then
does the badge show "Prisma closed" and "Open Prisma" re-enable. Because `open()` itself
now refuses a new generation while `CLOSING`, and the UI additionally keeps
`_active_prisma_generation` set (and both buttons disabled) for the whole closing window, a
rapid Close-then-Open click cannot create a second owned browser session.

A `close` event's `success` flag is also respected rather than assumed: a `success=False`
close-completed event (the controller's cleanup-failure report) never reaches the "Prisma
closed" / retryable branch. It instead calls `_prisma_close_failed`, which logs the raw
diagnostic via `safe_log`, shows a stable English critical dialog and status text explaining
that cleanup could not be confirmed and PrismaFunction should be restarted after checking
Task Manager, and sets a dedicated `_prisma_close_error` lock. That lock keeps both "Open
Prisma" and "Close Prisma" permanently disabled (`_update_controls` treats it exactly like
the closing-in-progress lock) — there is no working retry button, matching the controller's
own `CLOSE_FAILED` state, which likewise refuses `open()` and treats `close()` as a no-op.
This is intentionally conservative: with no automatic retry of the failed cleanup call and no
safe way to force-terminate the browser from the Qt thread (see the shutdown discussion
below), the only correct alternative to a dead-end lock would be to let the user open a
second, possibly-overlapping session against a browser that might still be alive — which the
no-overlap contract established earlier in this increment must not allow.

Application shutdown (`closeEvent`) signals the owned Prisma session to close and then waits
for that same owned worker thread via `PrismaLifecycleController.join(timeout=0.05)`,
re-checked in small non-blocking increments through the existing `QTimer.singleShot`
shutdown-retry mechanism already used for monitoring/import threads, so the Qt event loop
stays responsive throughout. For the first `PRISMA_SHUTDOWN_GRACE_SECONDS = 5s` this is
reported as a normal "finishing safely" status. Critically, shutdown **never accepts the
close event while `join()` still reports the worker alive**, even after that grace period —
there is no fallback that forces the close to succeed anyway. Once the grace period elapses
the status text instead explains that closing is taking longer than expected, and the
non-blocking retry continues indefinitely until the worker actually finishes; only then is
the window allowed to close. This was a deliberate choice between the two options the
increment considered: force-terminating the owned browser/Playwright process from the Qt
thread, or keeping shutdown visibly blocked until the worker finishes on its own. The former
was rejected because Playwright's sync API objects (`Browser`, `Playwright`) are only valid
on the thread that created them — the lifecycle worker thread — so the Qt thread cannot
safely call into them, and Python's Playwright bindings do not expose the owned browser's OS
process handle for an out-of-band kill; attempting one from the wrong thread or against the
wrong handle would risk hanging, raising, or — worse — targeting a process PrismaFunction
does not own. Keeping shutdown blocked with a stable, truthful status message guarantees the
application can never exit while it still owns a live browser/Playwright worker, so no
process is ever silently orphaned.

The same principle extends to a confirmed cleanup **failure**, not just an in-progress one:
once `join()` reports the worker thread has finished, `closeEvent` additionally checks
`PrismaLifecycleController.state`. A finished worker thread alone is not proof of a clean
close — the worker's cleanup exceptions are caught internally so the thread always exits
normally, whether or not `browser.close()`/`playwright.stop()` actually succeeded. If the
state is `CLOSE_FAILED`, shutdown ignores the close event and keeps retrying — with a status
message telling the user to close the browser window manually and check Task Manager —
exactly as it does for a still-alive worker, so a confirmed cleanup failure can never be
silently accepted as a successful, safe shutdown either.

Per the replacement decision, the old "Open Browser" / "Stop Browser" controls, "Load
Monitoring CSV", "Start Monitoring", "Stop Monitoring", and their status badges are hidden
(`QWidget.hide()`) so they cannot be triggered through the UI and no longer appear as an
active product workflow alongside the new controls. Their underlying code, tests, and
`BrowserController` are intentionally left in place — this increment does not perform the
repository-wide monitoring removal assigned to P.36.10; it only disconnects the UI surface
that would otherwise conflict with "Open Prisma" / "Close Prisma".

Regression coverage in `tests/test_prisma_lifecycle.py` covers the exact approved URL
boundary, successful open (navigating only to that URL, no other page interaction),
repeated open while opening/open (safe no-op), close with no active session (idempotent),
repeated close after open (idempotent), manual browser closure and retry with a new
generation, browser startup failure, close targeting only this controller's owned browser
instance, navigation failure, stopping mid-launch, `close()` staying in `CLOSING` (not
reporting `IDLE`) until `browser.close()`/`playwright.stop()` cleanup actually completes,
`open()` during `CLOSING` being a deterministic no-op that never launches a second browser,
a rapid Close-then-Open sequence not producing an overlapping session, `join()` waiting only
for this controller's own worker thread, `close()` reporting failure (never success) when
`browser.close()` raises, when `playwright.stop()` raises, and when both raise — in every
case landing in `CLOSE_FAILED` rather than `IDLE` — `open()` and `close()` both being refused
after a close failure, and a manually closed browser still being detected and reported via
the `is_connected()` fallback when `browser.on("disconnected", ...)` registration itself
raises. Further coverage proves the browser-level connectivity signal alone (not a
directly-invoked mocked `"disconnected"` callback): a manual closure is still detected by
polling when the handler attaches without raising but the event itself is never emitted, and
retrying `open()` after a polling-detected closure starts a new, non-overlapping generation.
Reproducing the confirmed real-world defect, dedicated page-level coverage proves the owned
`Page`, not the `Browser`, is what actually drives detection: a manual closure is detected
when the owned page closes silently (no `"close"` event delivered, `browser.is_connected()`
still `True`) purely via `page.is_closed()` polling; the same closure is detected via the real
`page.on("close", ...)` event, again with the browser still reporting connected; exactly one
typed `closed` event is published even when the page-close and browser-disconnect signals both
fire for the same closure; retrying `open()` after a page-detected closure starts a new,
non-overlapping generation; and a normal, application-requested `close()` is never
misclassified as a manual closure even when Playwright's realistic `"close"` cascade to the
owned page fires while cleanup is already in progress. `tests/test_app.py`
adds coverage for the new controls' state transitions, stable
English error presentation, the asynchronous "Closing Prisma…" UI state that only resolves
once the close-completed event lands, Open being a no-op during closing, a rapid
Close-then-Open not overlapping sessions at the UI layer, a single `get_events()` drain
containing a successful open followed by a manual `closed` event, a single drain containing a
successful open followed by a close-completed `close` event, a single drain mixing
stale-generation events with active-generation ones, a terminal open failure followed by a
spurious event not producing a duplicate error dialog, a `close` cleanup-failure event
locking both controls with a stable error (and proving Open/Close clicks are then no-ops),
shutdown never accepting the close event while the owned lifecycle worker reports itself
alive (including past the grace period), shutdown never accepting once cleanup is confirmed
failed (`CLOSE_FAILED`) even though the worker thread itself has finished, and proof that the
superseded monitoring controls are hidden while their code paths remain callable. The full
pytest suite (489 tests), Python compilation, and whitespace validation passed for this
increment; no packaging files, browser runtime dependencies, entry points, or bundled
resources changed, so no packaging validation was required.

Three subsequent manual-closure-detection change rounds followed (all still within P.36.2, no
scope change), each retested on real Windows hardware by the user. Rounds one and two are the
"first attempt" and "second attempt" in the real-runtime evidence log above; **both failed real
X-button retest** — the browser window closed but PrismaFunction kept reporting "Prisma open"
indefinitely both times, so neither `is_connected()`-only polling nor the
Page/Context-close-event-and-poll combination was actually sufficient, despite earlier revisions
of this document having called the second one "verified." Round three ("third attempt" above)
added the CDP `Target.targetDestroyed` ground-truth signal, together with the additional
`tests/test_prisma_lifecycle.py` coverage listed above (six tests: CDP-target-destroyed
detection while the page/browser signals stay silent, resilience when CDP session creation
itself fails, graceful fallback when the CDP baseline is ambiguous, exactly-one-event with CDP
and page signals both firing, retry without overlap after a CDP-detected closure, and the
CLOSING-state guard against a cascading `Target.targetDestroyed` during a normal close). **Round
three passed real X-button retest** on 2026-08-01, confirming the CDP owned-target-destruction
signal is the real-runtime-validated fix. The temporary diagnostics added alongside round three
to correlate that test were removed afterward per the note above; the CDP detection logic and
its regression coverage were retained unchanged. The full pytest suite (503 tests), Python
compilation (project-wide `compileall`, excluding `.venv`, `build`, `.git`, `__pycache__`, and
backup/cache directories), `validate_package.py`, and `git diff --check` all passed after
diagnostic removal.

**Final lifecycle contract.** `PrismaLifecycleController` owns exactly one manual, unautomated
PRISMA browser session per the semantics described earlier in this section (`open()`/`close()`/
`join()`, the `IDLE`/`OPENING`/`OPEN`/`CLOSING`/`CLOSE_FAILED` states, and the typed `open`/
`close`/`closed` events). Manual closure is detected by, in order of how they were introduced:
the browser-level `disconnected` event and `is_connected()` polling; the owned page's `close`
event and `is_closed()` polling; and the CDP `Target.targetDestroyed` event for the owned page's
target identified at open time. All are layered together as independent, non-exclusive signals;
whichever fires first calls `mark_manual_closure`, which is idempotent (at most one typed
`closed` event per generation) and inert while an application-requested close is already in
progress. Only concise operational logging remains: session opened (default-browser detection,
browser created, navigation completed), manual closure detected (including which signal source
fired), application-requested closure, the final cleanup result (state, classification, whether
cleanup failed), and actionable CDP setup/correlation failures (attach/session-creation failure,
or an ambiguous owned-target baseline) — never periodic snapshots, heartbeats, or a log line per
CDP target-create/info-change event, and never URLs, titles, page content, credentials, cookies,
storage, or form data.

Not yet done: `P.36.4` onward (CSV selection, mapping, output writing), and the physical removal
of the superseded monitoring/dashboard/scheduler code (P.36.10). P.36.2 itself is complete: the
real Windows X-button test above confirms the accepted behavior, the temporary diagnostics used
to correlate that test have been removed, the focused and full test suites pass, and no critical
review finding remains open.

#### P.36.3. Documents-based or user-selected download directory — Completed (2026-08-01)

Per `Prisma Function.odt` ("папку для завантаження створюємо в document користувача або
пропонувати вибір папки користувачу" — the download folder is created under the user's Documents
folder, or the user is offered a folder choice), this increment tracks only which existing,
accessible directory the user currently expects their manually downloaded PRISMA CSV to be in.
It performs no download, staging, scanning, or monitoring of that directory — file acquisition
stays entirely manual per the authoritative specification, and CSV selection/validation is
separately scoped to P.36.4.

`download_directory.py` adds a Qt-independent, browser-automation-independent boundary:

- `default_download_directory()` resolves the current Windows user's Documents folder in three
  tiers, none of which hardcode a username or machine-specific path: first the
  `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders`
  registry `Personal` value (so a redirected Documents folder, e.g. by OneDrive or a domain
  policy, is honored), then `%USERPROFILE%\Documents`, then the interpreter's own home-directory
  resolution — mirroring `runtime_paths.windows_local_app_data()`'s existing fallback style for
  consistency. Every tier is dependency-injectable (`environ`, `registry`, `platform` parameters)
  so tests never depend on the developer machine's real registry, username, or profile layout.
- `validate_download_directory()` is a typed boundary: it accepts only a path that exists,
  resolves to a directory (not a file), and is readable, raising `DownloadDirectoryError`
  otherwise. It never silently falls back to a different directory.
- `DownloadDirectorySelection` tracks exactly one active directory for the running session. Its
  constructor also calls `validate_download_directory()` on the initial value, so a missing,
  inaccessible, or file-path initial directory raises `DownloadDirectoryError` immediately instead
  of becoming a silently-accepted, unvalidated `current` (fixed as a P.36.3 review finding; see
  below). Its `select()` method calls the same validator and only replaces `current` on success; a
  rejected candidate leaves `current` unchanged, matching the required no-silent-fallback contract.

**Persistence decision (recorded, not inferred).** The selected directory is session-scoped only
and is not written to disk. The repository's only existing persistence mechanisms are the SQLite
operations ledger and the legacy `prisma_import_state.json` (see `prisma_import_workflow.py`),
both narrowly typed to the PRISMA source-import acceptance lifecycle (accepted sources, their
SHA-256 digests, and dates) — not a general-purpose UI-preference store. Repurposing either for
an unrelated single UI selection, or inventing a new settings file, was judged out of scope for
this bounded increment per the task's own explicit fallback rule ("if persistence is not
authorized by the specification or existing architecture, keep the selection session-scoped and
document that decision"); `Prisma Function.odt` itself does not require the choice to survive a
restart. A future increment may introduce a general settings mechanism if the authoritative
specification or customer explicitly requests persisted UI preferences.

`app.py`'s `PrismaMonitorApp` adds a "DOWNLOAD FOLDER" sidebar group with a "Choose Download
Folder" button and a label showing the current expected directory, using stable English UI text
throughout. `main()` resolves `default_download_directory()` once at startup inside the same
guarded initialization block already used for `runtime_paths()`/logging/migration, so a resolution
failure surfaces through the existing fatal "PrismaFunction Data Error" dialog instead of an
unhandled crash; the resolved value is passed into `PrismaMonitorApp.__init__`, which owns exactly
one `DownloadDirectorySelection` instance — no Qt widget holds path-validation logic itself.
`_select_download_directory()` opens `QFileDialog.getExistingDirectory` seeded with the current
directory; an empty result (Cancel) is a no-op that leaves the active directory and label
untouched; a validated selection updates both the label and the active directory; a rejected
selection logs the concrete `DownloadDirectoryError` via `safe_log` (preserving error context for
diagnostics) but shows only a generic, path-free English message in the UI dialog, so a rejected
path is never echoed back to the user. This increment does not change the completed P.36.2 "Open
Prisma" / "Close Prisma" lifecycle, does not configure Playwright/browser downloads, and does not
create, clean, or scan any directory.

Regression coverage in `tests/test_download_directory.py` covers: default resolution via the
registry `Personal` value, including `%VAR%` expansion; fallback to `USERPROFILE` when the
registry is unavailable; fallback to the interpreter's home directory when `USERPROFILE` is
unset; the registry tier being skipped off Windows; the resolved default not being nested under
the application's own `LOCALAPPDATA`-based runtime-data root; acceptance of an existing directory;
rejection of a missing path, a file path, and an inaccessible directory, in every case via the
typed `DownloadDirectoryError`; and `DownloadDirectorySelection` starting at its initial directory,
updating on a valid selection, and leaving `current` unchanged after a rejected missing-path or
file-path selection. `tests/test_app.py` adds coverage for the sidebar label reflecting the
constructor-supplied default directory, a valid chooser selection updating both state and label,
a cancelled chooser dialog leaving the active directory and label unchanged, and an invalid
selection showing a generic "Download Folder" error dialog whose message text does not contain
the rejected path while the active directory and label remain unchanged; the existing `window`
fixture now constructs `PrismaMonitorApp` with an explicit `tmp_path`-based Documents directory so
no test depends on the developer machine's real Documents folder or username. The full pytest
suite (525 tests, up from 503), project-wide Python compilation (`compileall`, excluding `.venv`,
`build`, `.git`, `__pycache__`, and cache/backup directories), and `git diff --check` all passed
for this increment; no packaging files, bundled resources, or dependencies changed (only stdlib
`os`/`pathlib`/`winreg` are used), so `validate_package.py` was not required.

**Review correction (2026-08-01).** A confirmed review finding noted that
`DownloadDirectorySelection.__init__` stored its `initial` argument as-is (`Path(initial)`)
without validating it, so a missing, inaccessible, or file-path initial directory would become an
unvalidated `current` instead of raising, breaking the class's own documented invariant that it
tracks only an existing, accessible directory. The constructor now calls
`validate_download_directory(initial)` and raises the existing typed `DownloadDirectoryError` for
an invalid initial value; it creates no directory and applies no silent fallback, matching
`select()`'s existing contract. `tests/test_download_directory.py` adds
`test_selection_normalizes_initial_directory`, `test_selection_rejects_missing_initial_directory`,
`test_selection_rejects_file_initial_path`, and
`test_selection_rejects_inaccessible_initial_directory` to cover an existing initial directory
being accepted and resolved, and a missing, file-path, or inaccessible initial directory being
rejected. No other P.36.3 behavior or scope exclusion changed.

#### P.36.4. Manual CSV selection and validation — Completed (2026-08-01)

Per `Prisma Function.odt`, PrismaFunction never scans, monitors, or auto-discovers the manually
downloaded official CSV: the user hands the program exactly one file, and the program validates
it against the exact official contract before accepting it. This increment adds only that
selection-and-validation control; it performs no row processing, filtering, mapping,
accumulation, deduplication, or output writing, and it does not change the existing "Import
PRISMA Export" button/pipeline, which remains a separate, unmodified control scoped to later
P.36 increments — `P.36.15` (transformation) and `P.36.16` (publication), per `ROADMAP.md`'s "P.36
roadmap correction (2026-08-02)"; the originally referenced `P.36.6`/`P.36.7`/`P.36.9` slots are
suspended/superseded and were replaced by that correction.

`manual_csv_selection.py` adds a Qt-independent, filesystem-only boundary:

- `validate_manual_csv()` opens the candidate once and returns an immutable
  `ManualCsvValidationResult` (a frozen dataclass wrapping a typed `ManualCsvOutcome` enum and,
  only on acceptance, the resolved `Path`). Checks run in order — existence, regular-file, opened
  and non-empty, absence of a standard BOM signature (checked against the first four bytes: UTF-8,
  UTF-16 LE/BE, and UTF-32 LE/BE all fold into the same `BOM_DETECTED` outcome, since the accepted
  contract is simply "no BOM" and never distinguishes which encoding a BOM implies), strict
  `cp1252` decoding of the header line, presence of the `;` delimiter, an exact tuple match
  against `csv_contracts.PRISMA_EXPORT_COLUMNS` (imported, not duplicated) for the header, and
  finally strict `cp1252` decoding of the *entire remaining file*, read in bounded 64 KiB chunks
  via `_validate_remaining_encoding()` so the complete file is never held in memory at once and no
  chunk, row, or decoded text is parsed, retained, returned, or logged — so every rejection is
  distinguishable as exactly one of `NOT_FOUND`, `NOT_A_FILE`, `UNREADABLE`, `EMPTY_FILE`,
  `BOM_DETECTED`, `ENCODING` (whether the invalid byte is in the header or anywhere later in the
  file), `DELIMITER`, or `HEADER_MISMATCH` (covering missing, extra, reordered, and duplicate
  columns alike, since only an exact-order, exact-membership tuple match is accepted). Any I/O
  error while reading any part of the file, including after the header has already validated,
  is caught by one outer boundary and reported as `UNREADABLE`. There is no delimiter guessing,
  encoding fallback, header normalization, or partial header matching anywhere in the function.
- `describe_rejection()` maps each non-accepted outcome to a stable, English, path-free message
  from a fixed dictionary; no candidate path or file content ever reaches a returned message.
- `ManualCsvSelection` tracks at most one currently accepted file for the running session,
  starting at `current = None` (there is no default, unlike the download directory). Its
  `select()` calls `validate_manual_csv()` and only updates `current` on acceptance; a rejected
  candidate always leaves the previous `current` unchanged, matching
  `DownloadDirectorySelection`'s existing no-silent-fallback contract. The selection is
  session-scoped only, for the same reasons already recorded for P.36.3.

`app.py`'s `PrismaMonitorApp` adds a "PRISMA EXPORT CSV" sidebar group (placed directly under
"DOWNLOAD FOLDER") with a "Select CSV" button and a label defaulting to "No CSV selected", plus
one `ManualCsvSelection` instance owned by the window (no Qt widget holds validation logic).
`_select_manual_csv()` opens `QFileDialog.getOpenFileName` restricted to `*.csv` and seeded with
`self._download_directory.current` (the current session's validated download directory), so the
chooser always starts where the user was told to expect the download; an empty result (Cancel) is
a strict no-op — no state mutation, no dialog, no status-bar text. A validated selection updates
both `ManualCsvSelection.current` and the label (to `Path.name`, the safe basename only, never the
full path) and appends an activity entry; a rejected selection logs the typed `ManualCsvOutcome`
value via `safe_log` (never the candidate path or file content) and shows a generic, path-free
English `QMessageBox` titled "Select CSV" via the existing `_show_error()` helper, leaving the
prior accepted selection and label untouched. This increment does not read, transform, or persist
any row from the selected file, does not add PDF support, does not scan or monitor the download
directory, does not configure browser downloads or automate PRISMA navigation, and does not change
the completed P.36.2 "Open Prisma" / "Close Prisma" lifecycle or the P.36.3 download-directory
contract.

Regression coverage in `tests/test_manual_csv_selection.py` (35 tests) covers: acceptance of the
exact official header; rejection of a missing path, a directory path, an unreadable file
(`Path.open` failure), an empty file, each of the five standard BOM signatures (UTF-8, UTF-16
LE/BE, UTF-32 LE/BE, parametrized), an undefined-in-`cp1252` byte in the header (wrong encoding),
a comma-delimited header (wrong delimiter), a missing/extra/reordered/duplicate header column
(all `HEADER_MISMATCH`), and non-`.csv`-extension files in both directions (content-based
rejection of a `.txt` file with garbage content, and content-based acceptance of a valid `.dat`
file), proving the extension and dialog filter are never trusted; acceptance of a valid header
followed by valid `cp1252` data; rejection of an invalid `cp1252` byte occurring only after a
valid header, both within and beyond the first bounded chunk (the latter via a monkeypatched
smaller `_CHUNK_SIZE` forcing multiple read iterations); rejection via `UNREADABLE` of a
simulated I/O failure that occurs only after the header has already been read successfully (a
`Path.open` wrapper that fails reads once the header is consumed); every non-accepted
`ManualCsvOutcome` maps to a non-empty, ASCII (path-free) message; and `ManualCsvSelection`
starting with no current file, updating only on a valid candidate, and leaving `current` unchanged
after a rejected candidate both before and after an initial valid selection, including after a
mid-file encoding failure, with the rejection message proven not to contain the rejected path.
`tests/test_app.py` adds coverage for the chooser starting in the current download directory,
Cancel being a strict no-op, a valid selection updating both state and label, an invalid
(missing-path) selection showing a generic "Select CSV" error whose message excludes the rejected
path while state and label stay at the previous valid selection, and a header-mismatch rejection
likewise preserving the previous selection without exposing the rejected path. The full pytest
suite (565 tests, up from 556), project-wide Python compilation (`compileall`, excluding `.venv`,
`build`, `.git`, `__pycache__`, and cache/backup directories), `git diff --check`, and
`git diff --no-ext-diff` all passed for this increment; no packaging files
(`PrismaFunction.spec`, `requirements.txt`, the Inno Setup installer), bundled resources, or
dependencies changed — `manual_csv_selection.py` uses only the stdlib (`csv`, `dataclasses`,
`enum`, `pathlib`) plus the existing `csv_contracts` module already bundled via `app.py`'s
PyInstaller analysis — so `validate_package.py` was not required.

**Review correction (2026-08-01).** A confirmed review finding noted two gaps: (1)
`validate_manual_csv()` decoded only the first physical line as `cp1252`, so a file with an exact,
ASCII-compatible header but invalid-`cp1252` bytes later in the file was accepted incorrectly,
even though the accepted contract requires the whole file to be `cp1252`; and (2) BOM detection
recognized only the UTF-8 signature, so a UTF-16 or UTF-32 BOM was misclassified as a delimiter or
header failure instead of `BOM_DETECTED`, even though the accepted contract is simply "no BOM."
`validate_manual_csv()` now also validates strict `cp1252` decoding across the complete remaining
file after the header matches, via `_validate_remaining_encoding()`, reading bounded 64 KiB chunks
so memory use stays constant regardless of file size and no chunk, row, or decoded text is parsed,
retained, returned, or logged; any I/O error anywhere in that read, not only at `open()`, is caught
by the same outer boundary and reported as `UNREADABLE`. BOM detection now recognizes the standard
UTF-8, UTF-16 LE, UTF-16 BE, UTF-32 LE, and UTF-32 BE signatures against the file's first four
bytes and reports `BOM_DETECTED` for any of them identically, since the contract never needs to
distinguish which encoding a BOM implies. The exact-header source of truth
(`csv_contracts.PRISMA_EXPORT_COLUMNS`), exact semicolon-delimited header matching, immutable
typed outcomes, session-state preservation after rejection, path-free UI messages and logs, and
every existing P.36.2/P.36.3 behavior and P.36.4 exclusion are unchanged. Nine tests were added to
`tests/test_manual_csv_selection.py` (26 to 35) covering the six scenarios above plus the
UTF-16/UTF-32 BOM variants; no `tests/test_app.py` change was needed since the UI layer only
consumes the already-typed `ManualCsvOutcome`/`describe_rejection()` boundary, which did not
change shape.

Not yet done: `P.36.8` (mapping display), `P.36.10` (obsolete-code removal), `P.36.11`
(packaging/installer validation), `P.36.12` (final regression/acceptance), and the `P.36.13`-`P.36.16`
replacement increments (date-range selection, application-managed download, transformation into the
corrected 12-column output CSV contract, and publication) defined in `ROADMAP.md`'s "P.36 roadmap
correction (2026-08-02)". See the `P.36.5` completion note immediately below for the resolved PDF
scope (still authoritative) and the output-column-structure decision it originally recorded (later
found incorrect and corrected on 2026-08-02). The former `P.36.6`/`P.36.7`/`P.36.9` slots this note
previously referenced are suspended/superseded and must not be implemented. This new "Select CSV"
control is not yet wired into the existing "Import PRISMA Export" pipeline (`start_processing()`);
that remains a later increment's decision, consistent with this increment's explicit "no processing,
filtering, mapping, accumulation, deduplication, persistence, or output-row writing" scope boundary.

#### P.36.5. Resolve PDF scope and output-column structure — Completed (2026-08-01)

> **2026-08-02 correction.** The "Output-column structure" decision recorded below (four separate
> `Exit Market`/`Exit Storage`/`Entry Market`/`Entry Storage` columns, 14 fields total) was found
> incorrect and is withdrawn. The authoritative output contract reverts to the original `Prisma
> Function.odt` 12-field structure: a single `Exit Market` column (market or storage name) and a
> single `Entry Market` column (market or storage name), with no separate Storage columns. See
> `ROADMAP.md`'s "Resolved specification questions" (2026-08-02 entry) and "P.36 roadmap correction
> (2026-08-02)" for the corrected record. The **PDF-scope decision** recorded below is unaffected and
> remains authoritative. This note's original text is preserved below for the historical record only
> and must not be treated as a current instruction where it describes the 14-field/four-column
> structure. The former `P.36.6` slot this note originally unblocked is suspended/superseded; do not
> implement it. The replacement increments are `P.36.13`-`P.36.16`.

This increment is documentation and contracts only; it changes no application behavior, adds no
row processing, filtering, conversion, mapping, output writing, UI, or persistence code, and
removes no PDF library, evidence, test, or code (dependency and obsolete-code removal remain
`P.36.10`). It records two explicit customer decisions that resolve both remaining specification
questions left open by `P.36.1`.

**PDF scope.** PDF input and PDF processing are excluded from the current product version. "CSV
файл (за потреби pdf)" is treated as fully satisfied by the CSV-only manual workflow already
implemented through `P.36.4`: no PDF file is selected, parsed, paired, staged, required, or used as
runtime input in the current version. The `P.36.5` roadmap slot in `ROADMAP.md` previously named
"Optional PDF support" is cancelled/superseded by this decision; it does not remain blocked or
planned. Historical PDF evidence already used for approved mapping catalog entries — for example
`evidence/p35-1/Auction_Overview.pdf`, referenced by the `P.35.1` completion note above — is
unaffected: excluding runtime PDF support does not invalidate or delete historical evidence or its
manifests, and no PDF-related dependency, test, or code is removed by this decision.

**Output-column structure.** Exit/Entry Market and Storage values use four separate, always-present
output columns instead of the specification's single combined "Ринок виходу або Хранилище" /
"Ринок входу або Хранилище" field per side. The authoritative output contract is now 14 fields, in
this exact order:

1. Auction Date
2. `Exit Market`
3. `Exit Storage`
4. `Entry Market`
5. `Entry Storage`
6. Capacity Type (entry/exit/bundle)
7. Network Point Name
8. Product Type
9. Flow Start (date and time)
10. Flow End (date and time)
11. Booked Capacity
12. Flow Duration Hours
13. Tariff Price
14. Premium Price

Each side's classification is mutually exclusive under `P.33.3`'s `ReferenceClassification`
(`market` or `storage`): a resolved side is never both. If approved side-specific evidence resolves
a side to a Market, that side's Market column is populated and its Storage column is left empty
because it is non-applicable to that resolution, not because the value is unresolved; the same
applies symmetrically when a side resolves to a Storage facility, leaving that side's Market column
empty. This intentionally empty non-applicable counterpart column is not an unresolved-value
fallback and must not, by itself, reject the row. No value is copied into both columns, and no
opposite-side value is inferred (`Exit Market`/`Exit Storage` come only from exit-side evidence,
`Entry Market`/`Entry Storage` only from entry-side evidence).

The genuinely unresolved case is distinct and is already fixed by the existing `P.33.3`
Market/Storage enrichment rule, not newly decided here or deferred to `P.36.6`: if a required side
is missing, or a required side's network point cannot be resolved to either an approved Market
alias or an approved Storage alias, the entire row is rejected, with a typed enrichment reason code
plus the affected field, side, and unchanged source-value context. This is distinct from the
separate `P.33.6`/`P.33.7` historical-backfill skip-and-audit behavior, which applies only to
already-persisted rows under an explicit, opt-in maintenance operation that `P.33.7` confirms is
never invoked during CSV import or export, so it does not apply to the P.36 output contract.

Both decisions were recorded as approved customer clarifications in `ROADMAP.md`'s "Resolved
specification questions" section rather than as edits to `Prisma Function.odt` itself, which is not
version-controlled in this repository. At the time, `P.36.6` (filtering, calculation, conversion, and
mapping for the 14-field contract) was unblocked and recorded as the next recommended implementation
increment. **This is superseded by the 2026-08-02 correction noted at the top of this section: the
output-column-structure decision was withdrawn, `P.36.6` (and the dependent `P.36.7`/`P.36.9`
definitions) are suspended and must not be implemented, and the next recommended increment is now
`P.36.13`.**

Not yet done: `P.36.8` (mapping display), `P.36.10` (obsolete-code removal), `P.36.11`
(packaging/installer validation), `P.36.12` (final regression/acceptance), and the `P.36.13`-`P.36.16`
replacement increments defined in `ROADMAP.md`'s "P.36 roadmap correction (2026-08-02)".

#### P.36.13. Date-range selection inside Prisma Function — Implemented, pending review and merge (2026-08-02)

Per `ROADMAP.md`'s "P.36 roadmap correction (2026-08-02)", `P.36.13` is the current forward increment:
it lets the user select and validate a start date and an end date inside Prisma Function, independent
from PRISMA navigation, download, transformation, mapping, or publication, which remain scoped to
`P.36.14`-`P.36.16`. This increment is implemented on `feature/p36-13-date-range-selection` but has
not been merged to `main` and the feature branch has not been deleted, so it is not marked Completed
under the project Definition of Done; see the "Verified evidence" paragraph below.

`date_range_selection.py` adds a Qt-independent boundary, matching the existing
`download_directory.py`/`manual_csv_selection.py` pattern:

- `DateRange` is a frozen `start`/`end` dataclass — the immutable typed accepted value.
- `DateRangeOutcome` is a typed `str` enum: `ACCEPTED`, `MISSING_START_DATE`, `MISSING_END_DATE`,
  `END_BEFORE_START`.
- `validate_date_range(start: date | None, end: date | None) -> DateRangeValidationResult` checks, in
  a fixed order, missing start, then missing end, then `end < start`, so a candidate missing both
  dates deterministically reports `MISSING_START_DATE` rather than an ambiguous or non-reproducible
  outcome. It never reads the system clock (no `date.today()`/`datetime.now()` anywhere in the
  module); both dates are supplied by the caller.
- `DateRangeValidationResult` is a frozen dataclass wrapping the outcome and, only on acceptance, the
  `DateRange`; its `accepted` property is `outcome is DateRangeOutcome.ACCEPTED`.
- `describe_rejection()` maps each non-accepted outcome to a stable, English message from a fixed
  dictionary: "A start date is required.", "An end date is required.", and "The end date must not be
  earlier than the start date."
- `DateRangeSelection` tracks at most one currently accepted range for the running session, starting
  at `current = None` (there is no current-date default, matching `ManualCsvSelection`'s no-default
  contract rather than `DownloadDirectorySelection`'s required-initial-value contract, since an
  invented default range would prevent the required missing-date state from being represented and
  tested). Its `select()` calls `validate_date_range()` and only updates `current` on acceptance; a
  rejected candidate always leaves the previous `current` unchanged.

`app.py`'s `PrismaMonitorApp` adds a "DATE RANGE" sidebar group (placed directly under "PRISMA EXPORT
CSV") with `start_date_edit`/`end_date_edit` (`QDateEdit`, `setCalendarPopup(True)`,
`setDisplayFormat("yyyy-MM-dd")`) and a "Validate Date Range" button, plus one `DateRangeSelection`
instance owned by the window (no Qt widget holds validation logic). Each `QDateEdit` uses
`setSpecialValueText("Not set")` together with its own Qt-default `minimumDate()` (14 September 1752,
already Qt's built-in default — no new minimum or PRISMA-specific limit is imposed) as a sentinel for
"no date selected"; `_read_optional_date()` returns `None` when a control's current value equals its
`minimumDate()`, and a real `date` otherwise. `_validate_date_range()` reads both controls, calls
`DateRangeSelection.select()`, and on rejection logs the typed outcome via `safe_log` and shows a
generic English `QMessageBox` titled "Date Range" via the existing `_show_error()` helper, leaving the
prior accepted range and both controls' current values untouched so the user can correct and retry.
On acceptance, `_set_date_range_widgets()` sets both controls to the accepted `start`/`end` (keeping
them consistent with `current`) and `date_range_label` is set to
`"Accepted: {start.isoformat()} to {end.isoformat()}"`; the status bar and activity log both record
"Date range accepted". This increment reads no browser, lifecycle, filesystem, CSV, or processing
state and writes none; it does not call `QFileDialog`, `BrowserController`, `PrismaLifecycleController`,
`load_auction_csv()`, `validate_manual_csv()`, `run_prisma_import_workflow()`, or start any
`threading.Thread`, and it is not wired into `Open Prisma`, `Close Prisma`, `Select CSV`, `Import
PRISMA Export`, or any download workflow. The pre-existing "PRISMA EXPORT DATE" `import_date`
`QDateEdit` (used only by the unrelated, unmodified `start_processing()`/"Import PRISMA Export" legacy
pipeline) is untouched and remains a separate control.

Regression coverage in `tests/test_date_range_selection.py` (17 tests) covers: accepted same-day and
multi-day ranges; rejection of a missing start date, a missing end date, and both dates missing
(deterministically `MISSING_START_DATE`); rejection of a reversed range; `DateRange`'s immutability;
`describe_rejection()`'s exact English messages for every non-accepted outcome; `DateRangeSelection`
starting with `current is None`; successful same-day and multi-day selection; preservation of the
previous accepted range after a missing-start, missing-end, and reversed-range rejection, both before
and after an initial acceptance; successful retry after correcting a rejected candidate; and a stable
typed result object whose `date_range` is the same object as the updated `current`.

`tests/test_app.py` adds 10 focused P.36.13 UI tests: the date controls and "Validate Date Range"
action are constructed, attached under the same top-level window, not explicitly hidden, and enabled
(proved via `isHidden()`/`isEnabled()`/`window()`, since the `window` test fixture never calls
`show()` on the top-level `QMainWindow`, so `isVisible()` is always `False` regardless of hide state
and cannot be used); the deterministic initial state (both controls at their `minimumDate()`,
`_date_range_selection.current is None`, label reading "No date range selected"); successful same-day
and multi-day acceptance updating state, both controls, the label, and the activity log; rejection of
a missing start date, a missing end date, and a reversed range, each showing the exact expected
English `QMessageBox` message and preserving the previous accepted range and label; the controls
remaining enabled after an error; a successful retry after correcting a rejected candidate; and that
accepting or rejecting a range triggers no `BrowserController.open()`, no `PrismaLifecycleController`
`open()`/`close()`, no `QFileDialog`, and no `threading.Thread.start()` call, while the download
directory and manual CSV selection remain unchanged. Every existing P.36.2-P.36.4 test in
`tests/test_app.py` is unmodified and continues to pass, confirming that lifecycle open/close, download
directory selection, and manual CSV selection behavior is preserved unchanged.

**Verified evidence (2026-08-02, not yet merged).** `tests/test_date_range_selection.py` (17 tests)
and the 10 focused P.36.13 tests in `tests/test_app.py` passed. The complete pytest suite passed with
592 tests (up from 565, the exact +27 expected from this increment), in 15.33s. Project-wide Python
compilation (`compileall`, excluding `.venv`, `build`, `.git`, `__pycache__`) exited 0; the run also
emitted one pre-existing, unrelated `Can't list '.\.pytest_tmp'` warning from a permission-restricted
directory dated 2026-07-19 that predates this increment and was not created or modified by it.
`git diff --check` passed. No real browser, no real PRISMA session, no filesystem or CSV I/O, no
publication, and no `P.36.14`-`P.36.16` behavior was added or exercised by this increment or its
tests; all Qt tests run under `QT_QPA_PLATFORM=offscreen` with deterministic fixed dates, never the
developer machine's current date, locale, timezone, Documents directory, browser, or network. This
increment is not merged to `main`, and `feature/p36-13-date-range-selection` has not been deleted.

**Fresh packaging evidence (2026-08-02, final-review follow-up).** The packaging check recorded above
at the time had validated a pre-existing `dist/PrismaFunction` build (dated 2026-07-19) that predated
this increment's `app.py` and `date_range_selection.py` changes, so it did not prove the packaged
distribution actually contained P.36.13's code. This was corrected by rebuilding from the current
source and revalidating that build specifically:

- `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` — succeeded; produced a fresh
  `dist/PrismaFunction/PrismaFunction.exe` dated 2026-08-02 (replacing the stale 2026-07-19 build). The
  spec's `Analysis(["app.py"], ...)` entry point performs static import discovery from `app.py`, so no
  spec change was needed for the new `date_range_selection` import; the only PyInstaller warning
  (`Hidden import "jinja2" not found!`) is a pre-existing Playwright-hook artifact unrelated to this
  increment.
- `python validate_package.py` — passed against the fresh distribution (structural contents, required
  Qt/Playwright files, and absence of developer/runtime files all verified against the current build).
- Smoke check — the fresh `PrismaFunction.exe` was launched with an isolated `LOCALAPPDATA` (a temporary
  directory outside the repository) and a working directory outside the repository, matching the
  existing P.27 same-machine smoke-check pattern in `BUILDING.md`. After an 8-second startup wait, the
  process was alive with a non-zero `MainWindowHandle`, `MainWindowTitle` `"PRISMA Monitor v1.0.0"`, and
  `Qt6Widgets.dll` loaded — proving `main()` reached `PrismaMonitorApp.__init__()` (which imports
  `date_range_selection` and constructs the "DATE RANGE" sidebar group) and `window.show()` without
  error, i.e. the fresh build imports all current production modules and initializes the main UI.
  `CloseMainWindow()` then closed the window and the process exited with code `0` inside a 6-second
  wait — a clean shutdown with no forced kill required. No `chrome.exe`, `msedge.exe`, or `node.exe`
  process appeared during the run (checked against the pre-existing set of such processes already
  running on the host), no `PrismaFunction.exe` process remained afterward, and the isolated smoke
  `LOCALAPPDATA` contained only its own log file — no writes reached the repository, the
  `dist/PrismaFunction` distribution itself, or a real Documents directory. No CSV selection,
  transformation, or publication action occurred.
- `git diff --check` was rerun after these checks and passed; no production code was changed by this
  follow-up, only this documentation.

No real PRISMA session, network activity, or manual interactive Windows validation (mouse/keyboard use
of the running application) is claimed by this smoke check — it proves process-level startup,
UI-object initialization, and clean shutdown only.

Not yet done: `P.36.14` (application-managed download, blocked by its decision gate), `P.36.15`
(transformation), `P.36.16` (publication, blocked by its decision gate), `P.36.8` (mapping display),
`P.36.10` (obsolete-code removal), `P.36.11` (packaging/installer validation), and `P.36.12` (final
regression/acceptance).
