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
(packaging/installer validation), `P.36.12` (final regression/acceptance), and the `P.36.14`-`P.36.16`
replacement increments defined in `ROADMAP.md`'s "P.36 roadmap correction (2026-08-02)". `P.36.13` is
completed; see the section immediately below.

#### P.36.13. Date-range selection inside Prisma Function — Completed, merged to `main` (2026-08-02)

Per `ROADMAP.md`'s "P.36 roadmap correction (2026-08-02)", `P.36.13` was the current forward increment:
it lets the user select and validate a start date and an end date inside Prisma Function, independent
from PRISMA navigation, download, transformation, mapping, or publication, which remain scoped to
`P.36.14`-`P.36.16`. This increment was implemented on `feature/p36-13-date-range-selection` and merged
to `main` via PR #59 (merge commit `ff07b68`, containing implementation commit `fb0cc89`). The
`feature/p36-13-date-range-selection` branch has not been deleted yet; that cleanup is a separate open
action and does not change this increment's completed status. See the "Verified evidence" paragraph
below.

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

**Verified evidence (2026-08-02, merged via PR #59, merge commit `ff07b68`).** `tests/test_date_range_selection.py` (17 tests)
and the 10 focused P.36.13 tests in `tests/test_app.py` passed. The complete pytest suite passed with
592 tests (up from 565, the exact +27 expected from this increment), in 15.33s. Project-wide Python
compilation (`compileall`, excluding `.venv`, `build`, `.git`, `__pycache__`) exited 0; the run also
emitted one pre-existing, unrelated `Can't list '.\.pytest_tmp'` warning from a permission-restricted
directory dated 2026-07-19 that predates this increment and was not created or modified by it.
`git diff --check` passed. No real browser, no real PRISMA session, no filesystem or CSV I/O, no
publication, and no `P.36.14`-`P.36.16` behavior was added or exercised by this increment or its
tests; all Qt tests run under `QT_QPA_PLATFORM=offscreen` with deterministic fixed dates, never the
developer machine's current date, locale, timezone, Documents directory, browser, or network. This
increment is merged to `main` via PR #59 (merge commit `ff07b68`); `feature/p36-13-date-range-selection`
has not been deleted yet.

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

Not yet done at the time P.36.13 merged: `P.36.14` (application-managed download, then blocked by its
decision gate), `P.36.15` (transformation), `P.36.16` (publication, blocked by its decision gate),
`P.36.8` (mapping display), `P.36.10` (obsolete-code removal), `P.36.11` (packaging/installer
validation), and `P.36.12` (final regression/acceptance). See the section immediately below for
`P.36.14`'s resolved decision gate and implementation.

#### P.36.14.✅ Completed User-initiated, application-managed PRISMA CSV download — Implemented and automated-tested, pending fully-automated live validation (2026-08-02)

**Decision gate resolution (2026-08-02, customer-approved).** P.36.14 was blocked on four explicit
questions; the customer resolved all four before implementation began:

1. **File naming:** keep PRISMA/the browser's own suggested filename, but insert the selected filter
   date range (ISO `YYYY-MM-DD`) before the extension: `<original-stem>_<start>_<end>.csv`, e.g.
   `Auction_overview_2026-08-01_2026-08-31.csv`.
2. **Collision behavior:** never overwrite; on a name collision, append an incrementing numeric suffix
   before the extension (`..._2.csv`, `..._3.csv`, ...), and the name reservation itself must be
   race-safe (not a check-then-write).
3. **Download directory:** an installer-or-first-run application-managed default at
   `<User Downloads>\PrismaFunction`, auto-created by the application if the installer does not reliably
   create it; the user may still override it with any other existing writable directory via the
   unchanged P.36.3 folder picker; only this one managed default is ever auto-created.
4. **Completion detection / browser mechanism** *(corrected 2026-08-02 — see below)*: reuse the one
   Playwright browser/page P.36.2 already owns (no second browser or context); after the approved PRISMA
   URL, fill PRISMA's own date filter, apply it, and detect completion purely from Playwright's
   `"download"` event, with no filesystem polling loop. The original text of this item said the user
   always presses PRISMA's own download control and PrismaFunction never clicks it; that was an incorrect
   assumption about the authoritative workflow and was corrected by the customer — PrismaFunction now
   activates the CSV control itself. See "Decision-gate correction" below for the full record.

**Implementation.** This was built on `feature/p36-14-managed-prisma-download` as three layers:

- `prisma_download.py` (new) is a Qt-independent, Playwright-session-independent module — the "dedicated
  download orchestration component" the task required, kept separate from `prisma_lifecycle.py` so the
  reusable business logic (precondition validation, naming/collision, and the two PRISMA-page automation
  steps) is not entangled with UI code or with `PrismaLifecycleController`'s thread/generation
  bookkeeping. It exposes: `validate_download_configuration(date_range, download_directory)` (typed
  `PrismaDownloadValidationOutcome`: `ACCEPTED`, `MISSING_DATE_RANGE`, `MISSING_DOWNLOAD_DIRECTORY`,
  `INVALID_DOWNLOAD_DIRECTORY`); `build_dated_filename()`/`reserve_unique_download_path()` (the approved
  naming/collision rule, the latter using `os.O_CREAT | os.O_EXCL` exclusive creation so the reservation
  cannot lose a race, returning a self-created placeholder the caller then overwrites via
  `Download.save_as()`); and `PrismaDownloadOrchestrator`, whose `configure(page, date_range)` performs no
  navigation (the already-open PRISMA Auctions page is the reporting page), opens the real Active Filter
  panel, fills and verifies the real date-range controls, applies the filter, then registers the
  `"download"` listener and activates the real CSV control — see the date-filter and decision-gate-correction
  records below for the exact live-verified DOM contract and the reasoning for this ordering — while
  `await_and_finalize(waiter, date_range, download_directory, cancel_event, deadline=...)` is a single
  non-blocking poll step (`None` = not resolved yet) rather than a blocking wait, specifically so the
  caller can interleave it with other polling instead of dedicating a thread to it. Typed
  `PrismaDownloadOutcome`/`PrismaDownloadResult` cover only the post-`configure()` phase (`SUCCESS`,
  `DOWNLOAD_TIMEOUT`, `DOWNLOAD_CANCELLED`, `DOWNLOAD_INTERRUPTED`, `NOT_CSV`, `SAVE_FAILED`), each with a
  stable, path-free English message via `describe_download_failure()`; pre-configuration failures raise
  specific exceptions instead (`PrismaAuthenticationRequiredError`, `PrismaInvalidSessionError`,
  `PrismaDateFilterPanelError`, `PrismaDateFilterControlsNotFoundError`, `PrismaDateValueRejectedError`,
  `PrismaDownloadListenerError`, `PrismaDownloadControlError`).
- `prisma_lifecycle.py`'s `PrismaLifecycleController` (P.36.2) gained optional `open(*, date_range=None,
  download_directory=None)` parameters; omitting both is byte-for-byte the pre-P.36.14 behavior (proven
  by the unchanged `FakePage.__getattr__` guard in every pre-existing test). When both are supplied, the
  worker thread calls `PrismaDownloadOrchestrator.configure()` right after the approved PRISMA URL loads
  (a `configure()` failure is caught by the *same* `except Exception` that already handles a navigation
  failure, so "Open Prisma must fail ... if download configuration fails" reuses the existing typed
  open-failure event rather than inventing a new failure channel), then the existing `kind="open"` success
  event is announced as before (browser now under user control), and `await_and_finalize()` is called once
  per tick from *inside* the controller's existing `cancel_event.wait(0.1)` idle loop — the same loop that
  already polls `page.is_closed()`/`browser.is_connected()` for manual closure. This was the key design
  decision: a second blocking wait (e.g. Playwright's `page.wait_for_event("download", timeout=...)`)
  would have starved Close-Prisma responsiveness and manual-closure detection for the whole download
  timeout window; folding the poll into the existing loop keeps both working concurrently with no new
  thread and no filesystem polling. Resolution publishes a new `kind="download"` `PrismaLifecycleEvent`
  (added an optional `csv_path: Path | None` field, defaulting to `None` so every existing event
  construction/comparison in `tests/test_prisma_lifecycle.py` is unaffected); the PRISMA session itself
  stays open regardless of the download's outcome.
- `app.py`: `_open_prisma_session()` now calls `validate_download_configuration()` before touching the
  browser at all, showing a `QMessageBox` titled "Open Prisma" and returning without calling
  `prisma_lifecycle.open()` if the date range or directory is missing/invalid (an intentional, in-scope
  extension of Open Prisma's own precondition contract — four pre-existing P.36.2 tests were updated to
  first accept a date range, since they exercise the "open succeeds" path and `prisma_lifecycle.open()`'s
  call signature genuinely changed). `_poll_prisma_lifecycle()` routes `kind="download"` events to a new
  `_handle_download_event()`, which on success reuses the existing P.36.4 `ManualCsvSelection` boundary
  (`self._manual_csv_selection.select(csv_path)`) — the downloaded file passes through the exact same
  official-export contract check as a manually selected CSV before the existing "PRISMA EXPORT CSV" label,
  status, and activity log are updated; this reuse is also how "expose the downloaded CSV path to the next
  processing stage" is satisfied, since `self._manual_csv_selection.current` is the boundary P.36.15 will
  read from. A typed download failure or a downloaded file that fails the P.36.4 contract shows a stable
  English error via the existing `_show_error()` helper and never touches the CSV selection. No new
  permanent UI element was added; the "PRISMA", "DOWNLOAD FOLDER", "DATE RANGE", and "PRISMA EXPORT CSV"
  sidebar groups are reused exactly as they exist today.
- `download_directory.py` gained the approved application-managed default without touching the existing
  P.36.3 Documents default: `default_downloads_directory()` mirrors `default_download_directory()`'s exact
  tiered resolution (Shell Folders registry, then `%USERPROFILE%`, then `Path.home()`), substituting the
  Downloads Known Folder GUID (`{374DE290-123F-4565-9164-39C4925E467B}`) for the Documents `"Personal"`
  value; `default_managed_download_directory()` appends `PrismaFunction`; `ensure_directory_exists()`
  idempotently creates only that one path and re-validates it. `app.py`'s `main()` now initializes
  `DownloadDirectorySelection` from `ensure_directory_exists(default_managed_download_directory())`
  instead of the former Documents default; the user can still change it through the unchanged "Choose
  Download Folder" control. `default_download_directory()` itself, and every existing P.36.3 test, are
  unmodified.

**Regression coverage.** New `tests/test_prisma_download.py` (29 tests): configuration validation
(accepted; each missing/invalid precondition, with missing-date-range taking precedence); the
naming/collision rule (exact name when free, deterministic `_2`/`_3` increment, never overwriting);
`configure()` (navigation, ISO date fill, listener registration, and each of its three failure modes);
and `await_and_finalize()` (not-yet-resolved; timeout; cancellation before any download; a successful save
with the dated name; a collision-safe save; non-CSV rejection without saving; cancelled/interrupted
classification from `Download.failure()`; a `save_as()` failure; and a failure reported only after
`save_as()` succeeds). `tests/test_prisma_lifecycle.py` gained 9 integration tests (46 total, up from 37):
the unchanged no-managed-download path; reporting-page navigation and ISO date fill; a `configure()`
failure reported through the existing open-failure event; a successful download event with the saved
path; typed not-CSV/cancelled/interrupted failure events; a timeout event; and proof that the bounded
download wait does not block manual-closure detection (a simulated `"disconnected"` event during the wait
is still detected). `tests/test_download_directory.py` gained 9 tests (27 total) for the Downloads
resolution tiers, the managed-default subdirectory, and `ensure_directory_exists()`. `tests/test_app.py`
gained 6 tests (87 total): the Open-Prisma validation gate (missing date range; a download directory that
became invalid after selection) and the `"download"` event UI wiring (success; typed failure; a
downloaded file failing the P.36.4 contract; routing through `_poll_prisma_lifecycle()` without disturbing
an already-open session).

**Verified evidence (2026-08-02, `feature/p36-14-managed-prisma-download`, not yet merged).** The complete
pytest suite passed with **645 tests (up from 592, the exact +53 expected from this increment)**.
Project-wide `python -m compileall` (the file list in `BUILDING.md` plus `prisma_download.py`) exited `0`.
`git diff --check` passed. Every test uses fakes/mocks for Playwright and `tmp_path` for filesystem
checks; no real browser, real PRISMA session, or packaging validation was exercised by this increment's
automated evidence.

**Real-site validation attempt and correction (2026-08-02).** A first real-PRISMA validation was run: the
packaged application was rebuilt, and the actual shipped `PrismaLifecycleController`/
`PrismaDownloadOrchestrator` code (not a reimplementation) was driven against the live, public
`https://app.prisma-capacity.eu` site using this machine's real default browser and real
`Downloads\PrismaFunction` directory. `Open Prisma` reached the real PRISMA auctions page correctly — the
same page P.23.1–P.23.3 already validated — proving the base lifecycle/browser reuse is unaffected. The
P.36.14-added second navigation, however, used a guessed literal
(`https://app.prisma-capacity.eu/reporting/reports/short-and-long-term-auctions`) that had never been
approved or confirmed; live evidence (a body-text dump of the resulting page) showed it resolved to
PRISMA's own generic navigation shell with no "From date"/"To date" fields, so `Locator.fill()` correctly
timed out after 30 seconds and the whole `Open Prisma` attempt failed as a typed
`DOWNLOAD_CONFIGURATION_FAILED` open failure — exactly the failure path this increment's validation
requirements describe, and it behaved correctly end-to-end for that failure. This proved the guessed URL
itself, not the failure-handling design, was the defect.

The customer then provided the authoritative correction: **the approved reporting page for
short-and-long-term auctions is the same page already opened by `PrismaLifecycleController` at the very
start of every session** — `browser.PRISMA_AUCTIONS_URL`
(`https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions`) — there was never a
separate "reporting" page to navigate to. The fix: `prisma_download.py` no longer defines its own literal;
it imports `PRISMA_AUCTIONS_URL` from `browser.py` and sets `DEFAULT_REPORTING_URL = PRISMA_AUCTIONS_URL`,
so the codebase has exactly one canonical URL constant and both the initial lifecycle navigation and the
managed-download reporting-page navigation always target it (verified by
`test_default_reporting_url_is_the_same_object_as_the_canonical_browser_constant`, which asserts object
identity, not just equality). A new regression test
(`test_no_stale_reporting_url_literal_remains_in_production_code`) scans every repository-root production
`.py` file for the stale literal so it cannot silently reappear. `tests/test_prisma_lifecycle.py`'s
managed-download navigation test was strengthened to assert both `goto()` calls use the exact approved URL
string, not only that two (previously independently-defined) constants equal each other. `prisma_page.py`'s
unrelated `PUBLIC_PATH` session-validation constant was left untouched — it is a different, pre-existing,
already-correct P.23 constant for a different purpose, not a duplicate introduced by this fix.

Automated evidence for this correction: the complete pytest suite passed with **649 tests (up from 645,
+4 exactly)** — `test_default_reporting_url_is_the_approved_auctions_url`,
`test_default_reporting_url_is_the_same_object_as_the_canonical_browser_constant`,
`test_orchestrator_defaults_to_the_canonical_reporting_url`, and
`test_no_stale_reporting_url_literal_remains_in_production_code`. `python -m compileall` exited `0`.
`git diff --check` passed. The package was rebuilt with `python -m PyInstaller --clean --noconfirm
PrismaFunction.spec` and revalidated with `python validate_package.py` (see the packaging note recorded
alongside this correction for the exact result).

**URL fix re-verified live (2026-08-02, same session).** The package was rebuilt
(`PyInstaller --clean --noconfirm` + `validate_package.py`, both passing) and the live attempt was rerun
with only the fix applied. Confirmed: the managed-download navigation now lands exactly on
`https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions` with page title
`"PRISMA"` — a real page, not a 404/error page. The specific reported defect ("the application opens a
PRISMA 404 page") is fixed and verified against the live site.

That rerun also confirmed a **separate, already-known issue was not fixed by the URL correction**: the
date-filter fill step failed (`Locator.fill: Timeout 30000ms exceeded` on
`get_by_label(/from\s*date/i)`), so `Open Prisma` still failed overall as a typed
`DOWNLOAD_CONFIGURATION_FAILED` open failure. `page.inner_text("body")` on the real page showed PRISMA's
left-navigation shell and a banner reading "Use the new PRISMA Platform design - clearer workflow, better
experience" — the live site was promoting a redesigned UI. This issue was fixed next, as recorded below.

**Date-filter contract fix (2026-08-02, live-verified).** Live DOM inspection (screenshots plus a
JS-injected element inventory capturing only non-sensitive structural attributes — no credentials,
cookies, tokens, or account data) found the real contract: a collapsed "Active Filter:" panel toggle
(`role=button`, name matching `/^Active\s+Filter:/i` — the same collapsed-filter-panel pattern
`PrismaAuctionFilter` in `browser.py` already uses for the unrelated Marketed Capacity field on this same
page); two masked date-time inputs reached via `data-testid="startOfAuctionFrom"`/`"startOfAuctionTo"`
(format `DD.MM.YYYY HH:mm`, widened to a full-day window — `00:00`/`23:59`); and a "Filter" apply button
(`role=button`, exact name `Filter`). A live fill/read-back experiment found a masked-input quirk: filling
the "from" field (pre-populated with PRISMA's own default) without first clearing it only updates the date
segment, leaving the time segment stuck at its placeholder, which fails verification; clearing first
(`Control+A` then `Delete`) before every fill fixed this for both fields regardless of starting state.
`configure()` was rewritten around this real contract with no second navigation and specific typed
exceptions per failure mode (`PrismaDateFilterPanelError`, `PrismaDateFilterControlsNotFoundError`,
`PrismaDateValueRejectedError`) instead of a raw Playwright timeout. Live re-validation confirmed `Open
Prisma` fills and verifies both dates and applies the filter successfully against the real site.

**Decision-gate correction: PrismaFunction activates the download, not the user (2026-08-02, customer
correction).** Two live-acceptance attempts under the original "user presses PRISMA's own download
control" design reached a successful `Open Prisma` (dates filled, filter applied) but then timed out
waiting for a download that never arrived: the first because the diagnostic harness had launched the
browser under a sandboxed execution context that isolates GUI windows from the visible interactive
desktop (rerunning with sandboxing explicitly disabled fixed window visibility), and on the second attempt
it became clear the manual-press premise itself was wrong — pressing a control on the PRISMA website was
never the intended workflow. The customer corrected the authoritative workflow: the user selects dates and
a download directory in PrismaFunction, presses the single existing "Open Prisma" action, and
PrismaFunction does everything else, including activating PRISMA's own CSV download control, with no
further user interaction on the PRISMA website. The real control had already been captured as DOM evidence
during the date-filter investigation: a plain `<button type="button">CSV</button>` (present both before and
after the Active Filter panel opens, alongside an unrelated "PDF" button of the same shape) with no test id
or ARIA attributes, so its accessible name — computed natively from its own visible text — is the most
stable available locator (`get_by_role("button", name="CSV", exact=True)`; priority 2, since no test id
exists for it). `configure()` now, after applying the date filter: waits (bounded, best-effort, non-fatal)
for PRISMA's own asynchronous filtered-results refresh via `wait_for_load_state("networkidle")`; locates
the CSV control; registers the `"download"` listener; and only then activates the control — the listener
is always registered strictly before the click. A new typed `PrismaDownloadControlError` ("could not be
found" / "could not be activated") replaces what would otherwise be a generic timeout. The stale
`DOWNLOAD_TIMEOUT` message ("Press the PRISMA download button, then try again.") was rewritten, since the
user no longer presses anything on the PRISMA website. `PrismaLifecycleController` required no functional
change — the activation is fully encapsulated inside `configure()` — only its docstrings were updated.
`app.py`'s existing "Open Prisma" action is reused unchanged as the single CSV-download action (no new
permanent UI); only the "Choose Download Folder" tooltip was corrected from "the manually downloaded
PRISMA CSV" to "the downloaded PRISMA CSV is saved".

`tests/test_prisma_download.py` gained 6 tests (exact-accessible-name activation; registration-before-activation
ordering; control-not-found and control-activation-failure typed errors; tolerance of a slow/unsupported
`networkidle` wait; the `DOWNLOAD_TIMEOUT` message no longer asking the user to press anything).
`tests/test_prisma_lifecycle.py` gained 2 integration tests for the same control-not-found/activation-failure
paths reported as typed open failures, and its existing managed-download test now also asserts the CSV
control was clicked exactly once. The complete pytest suite passed with **668 tests**. Project-wide
`python -m compileall` and `git diff --check` both passed. The package was rebuilt
(`PyInstaller --clean --noconfirm`) and `python validate_package.py` passed against the fresh distribution.

**Not yet done / outstanding before ✅ Completed (superseded by the 2026-08-02 diagnostic and fix round
below):** a full live pass of the corrected, fully-automated flow — including PrismaFunction itself
activating the CSV control and an actual CSV file being downloaded, named, and propagated to
`ManualCsvSelection` — has not yet been recorded. Automated tests and package validation pass, but per the
customer's explicit instruction this increment stays 🟡 until that live download succeeds with zero manual
browser interaction. Also not yet done: review, merge to `main`, feature-branch deletion, and `P.36.15`
(transformation), which must not begin before this increment's validation and merge.

### P.36.14 — real-site diagnostic round and two narrowly scoped fixes (2026-08-02)

**Diagnostic runs supplied by the customer, no code changed during diagnosis.** Two independent live
attempts against the shipped executable were reported before this fix round started:

- **Run A:** the CSV control click succeeded, but no page-scoped `"download"` event was ever received;
  visual observation indicated the export actually opens in a new browser tab.
- **Run B:** the browser opened, the correct PRISMA page loaded, date filters were populated and applied,
  and the CSV control was visible/enabled/stable — but the click failed because PRISMA's fixed
  cookie-consent banner intercepted pointer events at the control's location. This was correctly surfaced
  as a typed `PrismaDownloadControlError`, proving the existing failure-handling design itself was sound;
  only the missing banner handling and the page-scoped listener were defects.

**Authorized scope for this fix round.** Exactly two fixes, both inside `PrismaDownloadOrchestrator`: (1)
deterministic cookie-banner handling before the CSV control is activated; (2) download observation across
the existing `BrowserContext` rather than only the originating `Page`, so a download reported by a newly
opened tab is not missed. The canonical URL, date-selection behavior, the filename/collision contract, the
directory contract, the UI workflow, and unrelated lifecycle logic were explicitly out of scope and were
not touched.

**Cookie-banner contract (live-verified, 2026-08-02).** A headless fetch of the real public PRISMA page
found the banner P.23.1 already named "research-consent banner" (it discloses gathering usage data "via
browser cookies") has no test id or ARIA landmark: a fixed-bottom panel headed "Take part in PRISMA
usability research" with two plain, unattributed controls — an `<a>` "More Information" and two
`<button>`s, "Decline" and "Accept & Close". `PrismaDownloadOrchestrator._dismiss_cookie_consent_banner()`
tries "Decline" first (an automated tool should not opt a human user into usability-research data
collection on their behalf) and falls back to "Accept & Close" for a hypothetical banner variant offering
only a single accept-style control, each located by its own bounded, visible accessible-name locator
(`_COOKIE_BANNER_DETECT_TIMEOUT_MS = 3000`). Absence of the banner within that bounded wait is the normal
case, not an error. No DOM element is ever removed via JavaScript: a supported user control is always
available for this banner, so that fallback the requirements allow for is never exercised. If the control
is found but the click fails, or the banner does not report `state="hidden"` afterward, a new
`PrismaCookieConsentBannerError` is raised — never a silent continue and never `force=True`.

**Obstruction verification and the scroll-into-view correction.** After locating the CSV control and
handling the banner, `_ensure_control_not_obstructed()` calls `document.elementFromPoint()` at the
control's own bounding-box center and raises `PrismaCookieConsentBannerError` if the returned element is
not the control itself (or does not contain it), instead of ever passing `force=True` through to the
click. A first live run of this check against the real site produced a **false positive**: the CSV
control's live bounding box put its center below `window.innerHeight` (the PRISMA results page is ~2300px
tall; the button sits at the very bottom), so `elementFromPoint` correctly returned `null` for an
off-screen point, which the check misread as "obstructed". The fix — `control.scroll_into_view_if_needed()`
before computing the bounding box, mirroring what Playwright's own `click()` actionability protocol already
does internally — was verified live: a follow-up run reported "Obstruction check: OK (CSV control not
obstructed)" for the same control.

**Context-level download observation.** `configure()` now registers the `"download"` listener on
`page.context` (via `PrismaDownloadWaiter.attach()`/`context.on("download", waiter.on_download)`) instead
of `page.on(...)`, so a download reported by any page sharing that context — including one opened by a new
tab — is observed. No second browser or context is ever created; the existing owned context is reused.
`PrismaDownloadWaiter.on_download()` now rejects a second download explicitly: the first is captured as
before, but every later event is best-effort cancelled immediately and recorded via `waiter.multiple`,
which `_finalize()` checks both before and after `save_as()` (covering the race where the second event
lands mid-save) and reports as a new typed `PrismaDownloadOutcome.MULTIPLE_DOWNLOADS` outcome — the first
download is also cancelled/discarded in that case rather than silently reported as success.
`PrismaDownloadWaiter.detach()` idempotently removes the registered listener from the context; it is called
both immediately when a download result resolves (success, timeout, or any typed failure, inside
`PrismaLifecycleController._run()`'s `emit_download_result()`) and unconditionally in `_run()`'s `finally`
block, so cancellation-before-resolution, browser close, and configure()-time errors are covered too — no
listener is ever left attached past the end of the attempt that registered it, and Close Prisma's
responsiveness (the existing `cancel_event.wait(0.1)` idle loop) is unchanged.

**Automated evidence (2026-08-02, same branch, still unmerged).** `tests/test_prisma_download.py` gained
focused tests for: banner absent; banner dismissed via "Decline"; banner dismissed via "Accept & Close"
when "Decline" is not offered; the banner control failing to click; the banner not closing after being
clicked; the CSV control remaining obstructed after banner handling; never using `force=True` on either
control; the scroll-into-view step itself (and its tolerance of failure, mirrored on the existing
`networkidle`-wait tolerance pattern); the obstruction check's own tolerance of `evaluate()` failing;
context-level (not page-level) listener registration; a second download event being rejected and cancelled
(both before and during `save_as()`); a download accepted from the originating page; a download reported
via a different originating page (the new-tab scenario); and `PrismaDownloadWaiter.detach()` (removes the
listener, is idempotent, is a safe no-op if never attached, and tolerates `remove_listener()` raising).
`tests/test_prisma_lifecycle.py` gained integration tests for: the cookie banner being dismissed during a
full managed-download `open()` before the CSV control is clicked; a banner that cannot be dismissed
reported as a typed open failure; a download reported by a second `FakePage` sharing the first page's
`context` (the new-tab scenario) still resolving as a normal success; a second download event being
rejected end-to-end; and the context listener being removed after success, after a timeout, and after
cancellation before the download ever resolved. The complete pytest suite passed with **695 tests**
(`tests/test_prisma_download.py`: 68; `tests/test_prisma_lifecycle.py`: 57). Project-wide
`python -m compileall` and `git diff --check` both passed. `python -m PyInstaller --clean --noconfirm
PrismaFunction.spec` was rerun and succeeded; `python validate_package.py` passed against the fresh
distribution; an isolated-`LOCALAPPDATA` smoke launch of `PrismaFunction.exe` reached a live main window
(`PRISMA Monitor v1.0.0`) and shut down cleanly via `CloseMainWindow()` (exit code `0`, no forced kill, no
`chrome.exe`/`msedge.exe`/`node.exe` spawned by the smoke run itself).

**Live verification of the two fixes themselves (2026-08-02, headless Chromium against the real public
site, driving the actual `PrismaDownloadOrchestrator` code — not a reimplementation).** Calling
`_dismiss_cookie_consent_banner()` against a fresh session confirmed the real banner text ("Take part in
PRISMA usability research") was present, that "Decline" was clicked, and that the banner's own text was
gone from `document.body.innerText` immediately afterward — the same run also captured PRISMA's own
"Successfully saved cookie preference!" confirmation toast, independent live proof the real control was
actually activated, not just located. `_ensure_control_not_obstructed()` (after the scroll-into-view fix)
then reported the CSV control genuinely reachable. Registering the listener on `page.context` and
`waiter.detach()` were both exercised directly against the real page/context objects and behaved as
implemented.

**Newly confirmed, out-of-scope blocker: the existing date-filter automation no longer matches the live
site (2026-08-02).** While attempting a full live single-click-download proof, the existing, *unmodified*
`_open_filter_panel()`/`_locate_date_fields()` step (the "Active Filter:" toggle plus
`startOfAuctionFrom`/`startOfAuctionTo` test-id inputs, live-verified and unchanged since the entry earlier
in this section) failed reproducibly: `data-testid="startOfAuctionFrom"`/`"startOfAuctionTo"` are no longer
present anywhere in the live DOM, before or after the toggle click. Live screenshots showed clicking the
toggle instead removes PRISMA's own pre-populated default "Start of Auction" filter chip entirely and
surfaces PRISMA's own validation toast, "Please specify auction interval start date" — a different
interaction than the one this code was built against. This reproduced identically with and without the
cookie banner handled first, ruling out the banner as the cause. This is a genuine drift in PRISMA's own
live UI since the date-filter contract was originally verified, not a defect in either of the two fixes
delivered in this round, and per this fix round's explicit scope ("do not change date-selection behavior")
it was left untouched and unfixed. As a direct consequence, this round could not produce a full
single-click, zero-manual-interaction live download recording end-to-end; the increment stays 🟡.

**Side discovery, also out of scope: a large-result-set download confirmation modal.** Because the
date-filter step above could not be used to narrow the result set, a diagnostic click on the CSV control
against PRISMA's full ~10,000-row unfiltered result set surfaced a PRISMA-native modal — "Warning: Your
download contains only 5000 of 10068 items." — with its own second "CSV" button that must be clicked to
actually start the download; the outer button alone only opens this modal in that condition, which explains
the zero download events and zero network requests observed in that diagnostic run. This was not observed,
and is not expected to be encountered, with a real narrow date range (matching that the customer's own Run
A/Run B reports never mentioned it), and is flagged here rather than silently patched since handling a
second confirmation click is outside this round's two-item authorized scope. Whether it needs handling is
a decision for whoever next fixes the date-filter drift above, once real narrow-range result sizes can be
observed against the live site again.

### P.36.14 — date-filter contract re-verification and large-result-modal handling (2026-08-02, later same-day round)

**Authorized scope for this round.** Two items, both explicitly requested: (1) re-investigate the live
PRISMA Auctions page and restore/fix the date-filter contract, since the previous round reported it no
longer matching; (2) detect and confirm PRISMA's own large-result confirmation modal so a sufficiently wide
date range no longer silently blocks the automated CSV export.

**Part 1 investigation and finding.** Live DOM inspection was performed directly against the real public
`https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions` page — first with a
headless Chromium instance (Playwright's own bundled build, launched via an explicit `executable_path`
override since the environment's default headless-shell binary was missing), then cross-checked against the
real installed Chrome executable — rather than guessed. The finding: `data-testid="startOfAuctionFrom"`/
`"startOfAuctionTo"` **are** present under the "Active Filter:" panel today, with the exact same masked
`DD.MM.YYYY      HH:mm` contract, pre-populated "from" value, and clear-before-fill quirk originally
documented. The existing `_open_filter_panel()`/`_locate_date_fields()`/`_fill_field()` logic in
`prisma_download.py` required no locator change and worked unmodified against the live site in every
successful run. The page also exposes a visible toggle labelled "Deactivate New Design" (aria-label), which
is direct evidence PRISMA can serve more than one UI variant to a session; a later re-verification attempt
in this same round did reproduce a `PrismaDateFilterControlsNotFoundError` once, live, exactly as the typed
failure is designed to report — which supports "intermittent PRISMA-side A/B variance" as the most likely
explanation for the earlier round's "controls no longer present" finding, rather than a permanent redesign
this fix needed to chase. No selector in this round was guessed or restored from memory; every one was
confirmed present in the live DOM before being used.

Since the underlying locators turned out to already be correct, the actual gap against this round's
requirements was the missing **post-application** verification ("verify after applying the filter that ...
the filtered state is active before export begins" — not previously implemented; the prior fill-time
verification only proved the *input* accepted the typed text, not that PRISMA's own results were actually
re-filtered). Live DOM inspection found the applied range is echoed back into a dedicated filter-chip
element, `data-testid="filter-startOfAuctionFrom"` (observed text: `"Start of Auction\n01.08.2026, 00:00 -
02.08.2026, 23:59"`), once "Filter" is clicked — the same collapsed-chip "Tag" component pattern PRISMA uses
elsewhere on this page. `PrismaDownloadOrchestrator._verify_filter_applied()` is a new step, called
immediately after `_apply_filter()` and before the download control is ever located:

1. Waits for the chip to become visible at all — `PrismaDateFilterPanelError` ("could not be confirmed as
   applied") if it never does, matching the "filter application failure" typed-failure category.
2. Confirms the chip's content contains both formatted dates (`DD.MM.YYYY` for the accepted start and end) —
   `PrismaDateValueRejectedError` ("does not match the selected range") if it never does, matching the
   "rejected date" category.
3. Checks for any visible `role="alert"` element on the page as a stable, semantic "no validation error"
   signal (`page.get_by_role("alert")`, an accessible-role locator — priority 2 in the requested selector
   preference order, since no dedicated test id exists for a generic validation alert) —
   `PrismaDateValueRejectedError` with the alert's own text if one is found and visible.

**Timing bug found and fixed during live validation.** A first version of step 2 read the chip's
`inner_text()` exactly once, immediately after `chip.wait_for(state="visible")`. Driving the *actual*
production code path end-to-end (`PrismaLifecycleController`, the real installed Chrome executable via
`DefaultBrowserDetector`, not a reimplementation) surfaced a genuine defect: PRISMA's own chip re-render can
lag slightly behind the "Filter" click, and the existing best-effort `_apply_filter()` `networkidle` wait
only waits for network activity to settle, not for PRISMA's own React re-render to complete — so the single
immediate read intermittently observed the *pre-filter* chip content (PRISMA's own default value) and was
misreported as a rejected date, exactly the `PrismaDateValueRejectedError` failure a genuinely wrong date
should produce. The fix replaces the single read with Playwright's own polling `wait_for`:
`chip.filter(has_text=<compiled pattern requiring both formatted dates via lookahead>)`, bounded at a new
`_FILTER_CHIP_VERIFY_TIMEOUT_MS = 5_000` and re-evaluated live against the DOM on each poll rather than
decided from one snapshot. A follow-up live run through the exact same production path (real Chrome,
`PrismaLifecycleController.open(date_range=..., download_directory=...)`) confirmed the fix: the reported
`kind="open"` event now has `success=True` reliably, with the filter-chip verification step included.

**Part 2 investigation and finding: the large-result confirmation modal is real and now handled.** A live
run with a genuinely narrow one-day range (`2026-08-01` to `2026-08-02`) still returned over 11,000 line
items for that particular date, reproducing the modal side-discovery flagged (but explicitly left unfixed)
by the prior round. Live DOM inspection of the dialog found: `role="dialog"` (`data-sentry-component`
happens to read `"LimitWarningModal"`, though that Sentry-instrumentation attribute is not relied on as a
selector), a heading reading "Warning", body text `"Your download contains only 5000 of 11667 items."`, a
visually hidden "Dismiss popup" button, an `aria-label="Close modal"` icon button, and — critically — its
own plain `<button type="button">CSV</button>` confirm control with no test id or distinguishing ARIA
attribute, i.e. the exact same accessible name as the main page's CSV control. `_confirm_large_result_modal_if_present()`
is a new step, called immediately after `_activate_download_control()`:

- Waits up to a new `_LARGE_RESULT_MODAL_DETECT_TIMEOUT_MS = 3_000` (matching the existing cookie-banner
  detection bound) for `page.get_by_role("dialog").filter(has_text=<pattern matching "contains only N of M
  items", case-insensitive>)` to become visible. Absence within that bound is treated as normal — a
  sufficiently narrow date range never shows this dialog, and no fatal error is raised for its absence.
- When present, locates the confirm button **scoped to the dialog locator itself**
  (`dialog.get_by_role("button", name="CSV", exact=True)`), so it is never confused with the main page's own
  "CSV" button sharing the same accessible name, and clicks it — proceeding with the truncated export. A new
  `PrismaLargeResultConfirmationError` is raised if this control cannot be found or activated. The modal's
  own close/dismiss controls are never used, since that would cancel the download instead of confirming it,
  and the selected date range is never altered merely to dodge the modal.
- Because the download listener was already registered on `page.context` strictly before the very first CSV
  click (unchanged from the existing decision-gate-correction design), no second listener registration is
  needed for the confirmation click to be observed.

A live run confirmed the complete sequence end-to-end (headless Chromium against the real site, driving
`PrismaDownloadOrchestrator.configure()` directly): filter applied and chip-verified, modal detected,
dialog-scoped confirm button clicked, and the resulting Playwright `"download"` event captured with
`suggested_filename="Auction_overview.csv"` — which the existing, unmodified naming/collision logic
(`build_dated_filename()`/`reserve_unique_download_path()`) then processed exactly as before.

**New, orthogonal blocker found while proving the above through the full production pipeline: real-Chrome
download-event delivery.** Driving `PrismaLifecycleController.open(date_range=..., download_directory=...)`
directly — the exact production code path, real installed Chrome executable via `DefaultBrowserDetector`,
not a reimplementation — reached `kind="open"` `success=True` reliably (dates filled, filter-chip verified,
CSV control activated, and, when present, the large-result modal confirmed), but no `kind="download"` event
was ever observed within a 240-second wait, and no file appeared in the configured download directory. A
screenshot taken immediately after `configure()` returned showed the real Chrome window's own native
"Download complete." toast, proving a download genuinely did complete from the browser's own point of view.

This was isolated with a minimal, targeted repro rather than accepted at face value: `context.on("download",
...)` was tested directly (bypassing the full orchestrator) against the real PRISMA CSV-export click across
four variants — (a) Playwright-bundled Chromium, `headless=True`: reliably captured the event on every
attempt, including the full detect-modal-confirm-capture sequence above; (b) Playwright-bundled Chromium,
`headless=False`: did not capture it; (c) the real installed Chrome executable, `headless=False` (matching
exactly how `PrismaLifecycleController` always launches it): did not capture it, even with an explicit
`accept_downloads=True`; (d) the real installed Chrome executable, `headless=True`: also did not reliably
capture it in this round's attempts. Playwright's own managed temp/artifact directories
(`%TEMP%\playwright-artifacts-*`) were inspected directly and found empty of any downloaded file, indicating
the real Chrome build's download manager completes the download through a path that bypasses Playwright's
CDP-based download interception in this environment, rather than the event merely being slow to arrive.

This gap is orthogonal to both fixes in this round: neither `_verify_filter_applied()` nor
`_confirm_large_result_modal_if_present()` touches download-event wiring, which is unchanged from the
already-live-verified `PrismaDownloadWaiter`/context-registration design (see the prior round's entry
above). It was not caught by any prior round because no earlier live verification had completed a full
download capture through the real installed browser executable end-to-end — the prior round's own "Live
verification of the two fixes" was explicitly performed with "headless Chromium against the real public
site," not the real installed browser. Root cause is not yet fully diagnosed (candidate explanations include
a Chrome-version/CDP-protocol mismatch specific to this real, frequently auto-updated Chrome build, or a
change in Chrome's own native download-UI/"download bubble" handling in recent versions) and diagnosing it
further was out of this round's authorized two-item scope in any case. A direct interactive-user validation
pass on a normal Windows desktop, outside this automated coding session, is recommended as the next concrete
step: a prior P.36.14 round found that a sandboxed execution context could hide the browser window entirely
and that disabling that constraint fixed visibility, so a genuinely normal interactive session remains the
most direct way to rule in or out an environment-specific cause here too — though this round's own attempt
to disable equivalent sandboxing from within the same automated session did not, by itself, resolve the
download-capture gap.

**Automated evidence.** `tests/test_prisma_download.py` gained tests covering: the applied-filter chip being
checked (in the correct order, after both date test-ids and before the download control) before the download
control is located; the chip never appearing; the chip's content not matching the selected range; a visible
validation alert after applying the filter (download control never clicked); a present-but-not-visible alert
being correctly ignored; the large-result modal's absence being treated as normal; the modal being confirmed
automatically via its own dialog-scoped "CSV" button (asserting the main control and the modal's control are
each clicked exactly once, and are never confused); the modal's confirm control failing to be found or
activated (`PrismaLargeResultConfirmationError`); the date range never being altered to avoid the modal; and
a download still being captured end-to-end (through `await_and_finalize()`) after a modal confirmation.
`FakeConfigurePage` gained `applied_filter_chip` (defaulting to a fake that dynamically reflects whatever was
actually filled into the two date fields, so every pre-existing `configure()` test automatically exercises
the "verification succeeds" path without needing to know the specific date range in use), `alerts` (empty by
default), and `large_result_dialog` (absent by default) — plus a `FakeFilteredChipLocator` that mirrors
Playwright's own `Locator.filter(has_text=...)` polling semantics (re-evaluating the base locator's *current*
text at `wait_for` time, not once at `filter()` time), so the timing-bug regression itself is exercisable at
the unit level. `tests/test_prisma_lifecycle.py`'s `FakeManagedPage` gained the same three fakes (via a
locally duplicated, lifecycle-focused `FakeAppliedFilterChip`/`FakeAlertLocator`/`FakeLargeResultDialog`/
`FakeDialogQuery`/`FakeFilteredChipLocator` set, keeping the existing "unit-level DOM contract lives in
test_prisma_download.py, lifecycle-level tests stay focused on controller wiring" split) and gained five new
integration tests: a filter-verification failure reported as a typed open failure with the download control
never clicked; the large-result modal being confirmed automatically during a full managed `open()`; the
modal's confirm control failing reported as a typed open failure; the modal's absence being normal; and the
downloaded CSV still being captured, named, and saved correctly when it followed a modal confirmation. The
complete pytest suite passed with **711 tests** (up from 695): `tests/test_prisma_download.py` 79 (up from
68, +11), `tests/test_prisma_lifecycle.py` 62 (up from 57, +5). Project-wide `python -m compileall` (same
file list as prior entries) exited `0`, with only the same pre-existing, unrelated `.pytest_tmp` permission
warning noted in earlier entries. `git diff --check` passed (one informational CRLF-normalization notice on
`tests/test_prisma_lifecycle.py`, not a whitespace error). `python -m PyInstaller --clean --noconfirm
PrismaFunction.spec` was rerun and succeeded; `python validate_package.py` passed against the fresh
distribution; an isolated-`LOCALAPPDATA` smoke launch of the rebuilt `PrismaFunction.exe` reached a live main
window (`MainWindowHandle` non-zero, title `PRISMA Monitor v1.0.0`, `Qt6Core`/`Qt6Gui`/`Qt6Widgets` loaded)
and shut down cleanly via `CloseMainWindow()` (exit code `0`, no forced kill); no `PrismaFunction.exe`
process remained afterward.

**Live evidence summary.** Both of this round's fixes were live-verified end-to-end, independently, against
the real public PRISMA site: (1) the date-filter contract, including the new post-application chip
verification and its timing fix, confirmed via a full run through the actual `PrismaLifecycleController`
production code path reporting `success=True`; (2) the large-result confirmation modal, confirmed via a
narrow-range run that reproduced the modal, auto-confirmed it, and captured the resulting download with the
correct suggested filename. All live verification in this round used a real network connection to
`https://app.prisma-capacity.eu`; no credentials, login automation, or PRISMA authentication bypass was
used; the cookie-consent banner was dismissed via its own "Decline" control exactly as the existing,
unmodified `_dismiss_cookie_consent_banner()` already does. No PDF acquisition, transformation, mapping, or
publication behavior was added or exercised.

**Outstanding before this increment can be marked ✅ Completed.** The real-Chrome download-event delivery
gap described above blocks the one remaining acceptance item: a full production-mode (`headless=False`, the
real installed browser exactly as shipped) pass with an actual CSV file downloaded, named, and propagated to
`ManualCsvSelection`, with zero manual browser interaction. Per the customer's explicit instruction, P.36.14
stays 🟡 until that full pass succeeds; this round's two authorized fixes are each independently complete,
tested, and live-verified on their own terms.

### P.36.14 — approved bounded-filesystem-observation production fallback (2026-08-03, customer decision)

**Decision.** The real-Chrome download-event delivery gap above is not required to be root-caused before
P.36.14 can proceed: the customer approved proceeding without relying exclusively on the Playwright
`BrowserContext` `"download"` event. The Playwright event stays the primary mechanism; if the real installed
Chrome/Edge executable completes a download but no Playwright event is delivered, a bounded filesystem
observation of the configured download directory is now an approved production fallback, with these explicit
constraints: snapshot the directory before activating the PRISMA CSV control; consider only files created
after that snapshot; ignore partial files such as `.crdownload`; accept only one new `.csv` file; wait until
its size is stable across multiple checks; verify the file can be opened for reading; reject zero files,
multiple files, timeout, and interrupted downloads; remain cancellable so Close Prisma stays responsive; use
a fixed timeout and bounded polling interval; and never scan outside the configured download directory. After
completion, the existing dated filename and collision rules apply exactly as they do for a Playwright-observed
download, and the final path is propagated the same way.

**Implementation.** `prisma_download.py` adds `PrismaDownloadFilesystemWaiter`: `snapshot(directory)` records
the directory's current top-level contents (non-recursive `iterdir()`, never a scan outside that one
directory); `poll()` is a non-blocking, per-call check of the directory's current state, returning one of
`not_ready`, `ready` (with the resolved path), `multiple`, or `interrupted`. A new file is only ever
recognized if its name was absent from the snapshot; a `.crdownload`-suffixed new file is tracked only to
distinguish a genuinely interrupted download (the partial file disappears without ever producing a completed
`.csv`, debounced across `_FILESYSTEM_INTERRUPTED_GRACE_POLLS = 3` consecutive polls to tolerate the brief
instant a browser's own partial-to-final rename can appear as neither file existing) from one still in
progress; it is never itself a candidate result. A single new `.csv` candidate must report the same file size
across `_FILESYSTEM_STABILITY_CHECKS = 3` consecutive polls and then be openable for reading (`open(path,
"rb")`) before it is accepted; more than one new `.csv` candidate at any poll is rejected as `multiple`
without deleting either file. `PrismaDownloadOrchestrator.configure()` gained an optional third
`download_directory` parameter: when supplied, it takes the snapshot immediately after the Playwright
`"download"` listener is registered on the context and strictly before the CSV control is activated (omitting
it, the pre-existing two-argument call, leaves the fallback disabled — unchanged behavior for every caller
that does not pass it). `PrismaDownloadOrchestrator.await_and_finalize()` still checks the Playwright event
first (unchanged, primary path); only when that has not fired does it poll `waiter.filesystem_fallback` (when
present) and translate `ready`/`multiple`/`interrupted` into the same typed `PrismaDownloadResult` outcomes the
primary path already reports (`SUCCESS`/`MULTIPLE_DOWNLOADS`/`DOWNLOAD_INTERRUPTED`); a `ready` result still
yields to a Playwright event that arrived in the same instant, since the primary path carries the real
`Download` object. A `ready` fallback result is finalized by the new `_finalize_from_filesystem()`: it applies
the exact same `build_dated_filename()`/`reserve_unique_download_path()` naming/collision rule as the primary
path, then moves the already-downloaded file into the reserved placeholder path via `os.replace()` (atomic,
same-directory rename; there is no `Download` object to call `save_as()` on). Zero files at the deadline still
report `DOWNLOAD_TIMEOUT` exactly as before. `PrismaLifecycleController._run()`'s existing call now passes
`download_directory` through to `configure()`; no new wait loop, thread, or filesystem-polling mechanism was
added — the fallback's `poll()` is consulted from inside the exact same non-blocking `await_and_finalize()`
call already interleaved with the existing `cancel_event.wait(0.1)` idle loop, so Close Prisma's responsiveness
and manual-closure detection are unaffected.

**Automated evidence (2026-08-03).** `tests/test_prisma_download.py` gained 12 tests: `configure()` snapshotting
before activation and excluding a pre-existing file from the fallback; `configure()` without a directory
leaving the fallback disabled (unchanged pre-fallback behavior); a `.crdownload` partial being ignored; size
stabilization requiring the configured number of consecutive matching reads before acceptance; multiple new
`.csv` files being rejected; the fallback never scanning outside its configured directory; a full fallback
success through `await_and_finalize()` with the dated name applied and the source file moved (not copied)
into place; a late Playwright event still winning over an already-ready fallback result; the fallback never
overwriting an existing dated-name file; multiple files found via the fallback being rejected through
`await_and_finalize()`; the fallback timing out like the primary path when nothing ever appears; and
cancellation returning `None` with the fallback pending, exactly like the primary path. `tests/test_prisma_lifecycle.py`
gained 2 integration tests: a full managed `open()` succeeding via the filesystem fallback alone (no
Playwright `"download"` event fired) with the CSV named, dated, and reported through the existing
`kind="download"` event; and proof that an actively polling filesystem fallback does not delay manual-closure
detection (a browser `"disconnected"` event during the wait is still detected and reported promptly). The
complete pytest suite passed with **725 tests** (up from 711; `tests/test_prisma_download.py`: 91, up from 79;
`tests/test_prisma_lifecycle.py`: 64, up from 62). Project-wide `python -m compileall` and `git diff --check`
both passed (the same informational CRLF-normalization notice on `tests/test_prisma_lifecycle.py` as noted in
prior entries, not a whitespace error).

**Scope.** This change is strictly additive and confined to the fallback path: the canonical URL, date-filter
contract, filter-chip verification, cookie-consent handling, large-result-modal handling, the naming/collision
rule, and the download-directory contract are all unchanged and untouched. The real-Chrome download-event
delivery gap itself remains undiagnosed at the root-cause level; this fallback is the customer-approved way to
proceed without that diagnosis blocking the increment.

### P.36.14 — real-Windows defect fix: selected dates not actually applied to PRISMA (2026-08-03)

**Reported defect (real Windows, confirmed).** The start and end dates selected in Prisma Function were not
actually applied to the official PRISMA reporting page, even though the managed-download automation reported
no error.

**Investigation method.** Per this project's standing rule against guessed selectors/contracts, the
investigation used live DOM and network inspection against the real public
`https://app.prisma-capacity.eu/reporting/auctions/short-and-long-term-auctions` site (headless Chromium,
driving the actual `PrismaDownloadOrchestrator` code directly, not a reimplementation) rather than reasoning
from the code alone. This surfaced two concrete, evidence-backed gaps in the *verification* logic — not a
fill-format, locator, or navigation defect:

1. Filling the same text with a single space (the production code's own `_format_filter_datetime` format) and
   with the field's own placeholder spacing (six spaces, `"DD.MM.YYYY      HH:mm"`) produced an identical
   result — ruling out a format/spacing theory.
2. `field.evaluate()` DOM inspection found the field exposes an additional attribute,
   `data-test-iso-value`, holding an ISO-8601 UTC instant. Capturing the real outbound network requests
   (`GET .../rest/auctions/report?...` and `GET .../rest/auctions/report/csv?...`) confirmed this attribute's
   value is the *exact* value later used as the `startOfAuctionFrom`/`startOfAuctionTo` query parameters — it
   is the framework's real committed state, not merely display text.
3. `_verify_field_value` (existing code) only ever checked that the formatted *date* substring appeared in
   `input_value()` (the visible masked text) — never the time-of-day segment, and never `data-test-iso-value`.
   Since `_fill_field`'s own docstring already documents a failure mode where the time segment can silently
   stay unset while the date segment updates, a value that visually looked accepted could still carry the
   wrong time (and, in principle, an uncommitted framework state) without the existing check ever noticing.

**Fix.** Three changes, all confined to `PrismaDownloadOrchestrator` in `prisma_download.py`:

1. `_fill_field()` now calls `field.evaluate("(el) => el.blur()")` immediately after `fill()`, before
   verification — the same interaction a real user performs by tabbing or clicking away from a field, ensuring
   any commit-on-blur logic in the page's own component has run before the value is treated as accepted,
   rather than relying on an incidental later blur from focusing the next control or button.
2. `_verify_field_value()` now independently requires both the date and the `time_of_day` substring to appear
   in the masked text (two separate `in` checks, not one combined formatted string, since the real control's
   display text is padded with extra internal whitespace a single formatted substring would not match), then
   calls the new `_verify_committed_field_state()`.
3. `_verify_committed_field_state()` reads `data-test-iso-value` via `field.evaluate(...)` and compares the
   committed instant to the requested date/time.

**A first version of item 3 was itself found to be wrong by further live testing, and corrected before being
used** — directly relevant since the customer's own instruction was to identify the actual root cause instead
of a timing-only (or otherwise superficial) workaround. The first version converted the committed ISO instant
back to wall-clock text using the *browser's own* local-timezone `Date` getters (`getDate()`/`getHours()`/
etc.) and compared that to the expected `DD.MM.YYYY HH:mm` text. Running this against the real page produced a
concrete, reproducible failure: filling `"01.08.2026 00:00"` produced `data-test-iso-value =
"2026-07-31T22:00:00.000Z"`, but the browser-local-timezone conversion computed `"01.08.2026 01:00"` — a
one-hour mismatch — because this sandboxed test environment's own system timezone offset did not match the
offset PRISMA itself used when it originally converted the typed text to that ISO instant. A follow-up,
targeted experiment isolated the cause deliberately rather than guessing: the identical fill was run against
the real page four times, once under each of four different Playwright browser-context timezones
(`Europe/Berlin`, `America/New_York`, `Asia/Tokyo`, `UTC`); all four produced the *exact same*
`data-test-iso-value`. This proves PRISMA always interprets the typed local text as fixed Europe/Berlin time,
regardless of the machine's own configured timezone (a reasonable design for a EU energy-market platform) — so
the first version's approach of converting back via the *browser's* local timezone would have produced false
rejections (a new, machine-dependent defect) on any real Windows machine not already configured to
Europe/Berlin, which is likely most machines outside continental Europe. This would have been a strictly worse
outcome than the reported defect: a `PrismaDateValueRejectedError` on every managed download attempt for anyone
outside CET/CEST, rather than a silently wrong range.

The corrected `_verify_committed_field_state()` never uses the browser's own local timezone. It computes,
entirely inside the browser via one `field.evaluate(...)` call using `Intl.DateTimeFormat` with an explicit
`timeZone: 'Europe/Berlin'` option, the UTC instant that corresponds to the requested wall-clock date/time in
that fixed zone — correctly handling the CET/CEST daylight-saving boundary via the standard "format a UTC
guess in the target zone, then correct by the resulting offset" technique, live-verified against both an
August (CEST, UTC+2) and a January (CET, UTC+1) date — and compares that computed instant directly to
`data-test-iso-value`, tolerant of small (<60s) rounding. This is compared, never parsed in Python, so the
verification is not exposed to whatever timezone the machine running PrismaFunction happens to be configured
to. A future PRISMA build without the `data-test-iso-value` attribute is tolerated (the method returns without
raising): the text-based date+time check in `_verify_field_value` already ran and is the fallback signal in
that case.

`_verify_filter_applied()`'s applied-filter-chip check (the independent, stronger signal checked after
"Filter" is clicked) gained the equivalent fix at its own layer: it previously required only the two formatted
dates to appear in the chip text; it now also independently requires both the `00:00` and `23:59` time-of-day
substrings, closing the same class of gap one layer later, using the same "separate substring checks, not one
combined formatted string" approach for the same reason (the chip's own separator between date and time is not
part of the contract being verified).

Any of the above failing raises the existing `PrismaDateValueRejectedError` — the same typed managed-download
failure path Open Prisma already surfaces as a normal failed attempt — never continuing with a potentially
wrong date range. No unbounded sleep was introduced anywhere in this fix; every new wait reuses the existing
bounded `_CONTROL_TIMEOUT_MS` via Playwright's own `timeout` parameter on `evaluate()`.

**Scope discipline.** Nothing outside `_fill_field`/`_verify_field_value`/`_verify_committed_field_state`/
`_verify_filter_applied` in `prisma_download.py` was touched. The canonical reporting URL, the "Active Filter"
panel toggle, the date-field locators themselves, the cookie-consent banner handling, the large-result-modal
handling, `build_dated_filename()`/`reserve_unique_download_path()`, the download-directory contract, the
filesystem-observation fallback (`PrismaDownloadFilesystemWaiter`), the 12-column output contract, the manual
CSV fallback (P.36.4), and unrelated UI are all unchanged.

**Test fakes updated to model the real contract.** `tests/test_prisma_download.py`'s `FakeFieldLocator` and
`tests/test_prisma_lifecycle.py`'s `FakeDateFieldLocator` both gained an `evaluate(script, arg=None,
timeout=None)` method: for a blur script it records the call and returns `None`; for the committed-value read
it returns a boolean by default (`True`, matching "committed correctly" — mirroring the existing `echo_fill`
default so every pre-existing test continues to exercise the successful path without needing to know the
specific date/time in use), overridable to `False` (simulate a mismatch) or `None` (simulate an absent
attribute, exercising the tolerate-absence path) via a new `iso_committed_override` constructor parameter;
separate `blur_error`/`committed_read_error` parameters (download-level fake only) let a test simulate either
`evaluate()` call failing independently, since both go through the same method at different points in the
sequence. The one pre-existing test that asserted the exact `action_order` sequence
(`test_configure_clears_each_field_before_filling_it`) was updated to include the new `"evaluate:blur"` step at
the end of the expected sequence — an intentional update reflecting the new, correct behavior, not unrelated
churn.

**Automated evidence (2026-08-03).** `tests/test_prisma_download.py` gained 9 tests: both fields filled with
the exact requested date and time; the exact click→clear→fill→blur event sequence, asserted per field; blur
failure surfaced as the existing typed field-rejection error; a field that echoes the right date but a wrong
(unrequested) time now caught by the new time-of-day check; a committed value that does not match the visible
text now caught by the new committed-state check (the direct regression test for the reported defect); a field
lacking the committed-value attribute tolerated (falls back to the text-based check, no false failure); the
committed-value read itself failing surfaced as a typed failure (with blur confirmed to have still succeeded
first); the applied-filter chip requiring both dates and times (one test with a wrong time on the chip, which
would have incorrectly passed before this fix, now correctly rejected; one test with a fully matching chip
confirmed to still pass). `tests/test_prisma_lifecycle.py` gained 1 full-trace integration test
(`test_managed_download_reports_as_an_open_failure_when_a_date_is_not_actually_committed`): a date that fails
the new committed-state check is reported through the existing typed `kind="open"` failure event with
`success=False` and an error message containing "start date value was not committed", and the CSV download
control is confirmed never activated (`page.download_button.click_calls == 0`) — proving the full trace from a
selected date through `PrismaLifecycleController.open()` into the page automation fails safely rather than
silently proceeding. The complete pytest suite passed with **735 tests** (up from 725, the exact +10 expected:
+9 in `test_prisma_download.py` — 100 total, up from 91 — and +1 in `test_prisma_lifecycle.py` — 65 total, up
from 64). Project-wide `python -m compileall` (same file list as prior entries) exited `0`. `git diff --check`
passed (the same informational CRLF-normalization notice on `tests/test_prisma_lifecycle.py` noted in prior
entries, not a whitespace error). `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun and
succeeded; `python validate_package.py` passed against the fresh distribution.

**Live evidence (2026-08-03, headless Chromium, real public site, driving the actual fixed
`PrismaDownloadOrchestrator.configure()` code end-to-end, not a reimplementation).** `configure()` completed
without raising for a two-day range (2026-08-01 to 2026-08-02), and the real outbound CSV export request
(`GET https://platform.prisma-capacity.eu/rest/auctions/report/csv?...`) was captured carrying exactly
`startOfAuctionFrom=2026-07-31T22:00:00.000Z&startOfAuctionTo=2026-08-02T21:59:00.000Z` — the correct UTC
instants for the requested local Europe/Berlin range — confirming the fix closes the reported gap all the way
through to the real request PRISMA's backend receives, not merely at the field level. The identical check was
then rerun with the Playwright browser context's `timezone_id` forced to `America/New_York`, `Asia/Tokyo`, and
`Pacific/Auckland` in turn, specifically to confirm the corrected Europe/Berlin-fixed comparison does not
reintroduce the false-rejection regression the first (browser-local-time) version of the check would have
caused; all three completed without a false rejection.

**Outstanding.** This sandboxed development environment has no installed `chrome.exe`/`msedge.exe` (confirmed
via both `where chrome.exe`/`where msedge.exe` and direct filesystem checks), so all live evidence above used
Playwright's own bundled Chromium build, not the real installed browser `PrismaLifecycleController` always
launches in production. Manual validation is still explicitly required on a real Windows desktop against the
official PRISMA page before this fix can be considered fully accepted: choose a clearly distinguishable start
and end date in Prisma Function, start the managed download, confirm both exact dates appear in the PRISMA
Active Filter controls, and confirm the resulting request/download uses that exact range. This is in addition
to, not a replacement for, the still-outstanding real-installed-Chrome production-mode acceptance pass recorded
in this section's immediately preceding entry (the real-Chrome download-event-delivery gap and its approved
filesystem-observation fallback).

### P.36.14 — real-Windows defect fix: DATE RANGE controls initializing to Qt's minimum date (2026-08-03)

**Reported defect (real Windows, screenshot-confirmed).** On real Windows, both `start_date_edit` and
`end_date_edit` in the "DATE RANGE" sidebar group initialized to values near Qt's minimum supported
`QDate` — `1752-09-25` and `1752-09-29` respectively — instead of a usable application date. This
contradicted the P.36.13 implemented-result record, which intended construction-time `minimumDate()` to
render as the configured `specialValueText("Not set")`, not as a literal near-1752 date.

**Root cause.** `PrismaMonitorApp.__init__` explicitly initialized each control with
`self.start_date_edit.setDate(self.start_date_edit.minimumDate())` (and the matching call for
`end_date_edit`). `QDateEdit.minimumDate()` is an implementation-defined value (Qt/PySide6, per platform)
never intended to be shown to a user; the assumption that assigning it as the initial value would always
render as `specialValueText` instead of literal digits did not hold on the real Windows target. This was a
display-defaulting defect, not a validation or data-flow defect: `date_range_selection.py`'s validation
boundary, `DateRangeSelection`'s session-scoped `current` (`None` until an explicit "Validate Date Range"
click), and P.36.14's `validate_download_configuration()` precondition gate were all unaffected and
required no change.

**Fix, `app.py`.** Added a single-purpose, module-level `_current_local_date() -> date` (returns
`date.today()`) as the one isolated seam through which `PrismaMonitorApp` reads today's date — mirroring
`date_range_selection.py`'s own stated design of never reading the system clock inside Qt-independent
validation code, by keeping the one real clock read confined to this one construction-time call. Both
`start_date_edit` and `end_date_edit` are now initialized to `QDate(today.year, today.month, today.day)`
computed from it, never to `minimumDate()`. No other default is specified by the authoritative
P.36.13/P.36.14 requirements, so both controls default to the same current date, i.e. a valid same-day
range, satisfying "Start Date must be less than or equal to End Date" trivially at construction time.
`setSpecialValueText("Not set")` and the existing `_read_optional_date()` sentinel comparison
(`widget.date() == widget.minimumDate()` reads as a missing date) are both preserved unchanged — a user
who deliberately scrolls a control's calendar back to its minimum still reads as missing; only the
construction-time default changed.

**Scope discipline.** Confined to the `start_date_edit`/`end_date_edit` construction block in
`PrismaMonitorApp.__init__` and the new `_current_local_date()` helper, plus the `tests/test_app.py`
regression coverage below. PRISMA automation, the managed-download orchestration
(`PrismaDownloadOrchestrator`, `PrismaLifecycleController`), the download-directory contract, the
12-column output contract, mappings, and all other UI are unchanged and untouched.

**Test changes, `tests/test_app.py`.** The shared `window` fixture's construction logic was factored into
`_build_app(monkeypatch, tmp_path)`/`_close_app(widget)` helpers (the fixture itself now just calls them)
so a new test can construct a `PrismaMonitorApp` with a monkeypatched fixed "today" without duplicating
the fixture body. Two new regression tests were added:
`test_date_range_controls_do_not_initialize_to_qts_minimum_date` (proves neither control's initial value
equals its own `minimumDate()`, and that both controls' initial year is greater than `1752` — the direct
regression test for the reported defect) and `test_date_range_controls_initialize_to_a_fixed_current_date`
(constructs the window with `app._current_local_date` monkeypatched to a fixed `date(2026, 3, 15)` and
asserts both controls show exactly `QDate(2026, 3, 15)`, proving the initialization is deterministic and
testable without depending on the real wall-clock date). `test_date_range_initial_state_is_deterministic_and_unset`
was updated to assert both controls equal `QDate.currentDate()` (previously `minimumDate()`); the accepted
range itself (`_date_range_selection.current is None` until validated) is unchanged. The two existing
missing-date tests (`test_validating_with_missing_start_date_shows_error_and_preserves_state`,
`test_validating_with_missing_end_date_shows_error_and_preserves_state`) now explicitly set the untouched
control to its own `minimumDate()` sentinel before validating, since a genuinely missing date is no longer
the construction-time default; both still correctly reject with the unchanged
`MISSING_START_DATE`/`MISSING_END_DATE` messages, proving the sentinel mechanism itself is preserved.
`test_date_range_controls_remain_enabled_and_retryable_after_error` now sets an explicit reversed range
before validating, so it still exercises an actual rejection (it previously relied, likely unintentionally,
on the old missing-start-date default to produce an error).

**Automated evidence (2026-08-03).** The complete pytest suite passed with **737 tests** (up from 735;
`tests/test_app.py`: 89, up from 87 — the exact +2 expected from the two new regression tests). Project-wide
`python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`) exited `0`, with the same
pre-existing, unrelated `.pytest_tmp` permission warning recorded in P.36.13's and this file's prior
entries. `git diff --check` passed (the same informational CRLF-normalization notice on
`tests/test_prisma_lifecycle.py` noted in prior entries, not a whitespace error, and predating this fix).
`python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun to produce a fresh distribution
from this fix, and `python validate_package.py` passed against it.

**Outstanding.** Full manual Windows validation — visually confirming, on first launch of the real
`PrismaFunction.exe`, that both DATE RANGE controls show today's date (not `1752-09-25`/`1752-09-29`),
that the calendar popup and manual keyboard entry still work, and that a subsequent "Validate Date Range"
and managed-download attempt still carries the user-selected range through unchanged — has not yet been
performed and remains required before this fix can be considered validated end-to-end. This is in addition
to, not a replacement for, P.36.14's already-recorded outstanding real-installed-Chrome production
acceptance pass.

### P.36.14 — real-Windows defect fix: managed download completed in Chrome but never reached the configured directory (2026-08-03)

**Reported defect (real Windows, confirmed).** `chrome://downloads` showed the PRISMA export completed
under a temporary, browser-generated (UUID-like) name. The configured Prisma Function download directory
existed and was writable, but stayed empty: the managed download never finalized into a non-empty `.csv`
file inside it, even though the approved bounded filesystem-observation fallback added earlier the same
day (see this file's "approved bounded-filesystem-observation production fallback" entry above) was already
in place and running.

**Investigation.** Tracing the real Chrome download from CSV-control activation through to the filesystem,
per this project's standing rule against guessed contracts:

1. `PrismaLifecycleController._run()` (`prisma_lifecycle.py`) launches the browser via
   `playwright.chromium.launch(executable_path=..., headless=False, args=["--start-maximized"])`. No
   `downloads_path` was ever passed.
2. Per Playwright's own documented contract, when `downloads_path` is not specified, accepted downloads are
   written into a Playwright-managed temporary directory it creates and owns itself — not the browser's own
   native default Downloads folder, and not any directory the calling application chose. Real Chrome/Edge's
   CDP-driven download interception (the "allowAndName" behavior Playwright configures on the browser via
   `Browser.setDownloadBehavior`) additionally always assigns the raw artifact a framework-generated,
   UUID-like name inside that directory — this holds regardless of whether `downloads_path` is set; the
   parameter only controls *which* directory the UUID-named artifact is written into, never its name.
3. `PrismaDownloadFilesystemWaiter` (added by the same-day approved fallback) correctly snapshots and polls
   the *configured* download directory — the one the user picked via the existing P.36.3 folder-selection
   workflow — for a new file. But since nothing ever told the browser to write there, the raw artifact
   never appeared in that directory: the fallback was watching the right place, while Chrome was writing to
   a different, untracked place entirely. This explains the exact reported symptom precisely: a completed
   download visible in Chrome's own UI under a temporary name, and a persistently empty configured
   directory.
4. This is a distinct, deeper layer of the same underlying real-Chrome download-observability gap already
   recorded earlier the same day (see this file's dated entries above): the earlier fallback correctly
   assumed Chrome's own download manager could complete a download PrismaFunction never directly observes,
   but implicitly assumed that download would land in a directory PrismaFunction controls without ever
   actually configuring the browser to do so.

**Fix.**

1. `prisma_lifecycle.py`: `_run()` now builds its `launch()` keyword arguments explicitly and adds
   `downloads_path=str(download_directory)` whenever `managed_download` is true (both `date_range` and
   `download_directory` were supplied to `open()`). Omitting either argument — the pre-P.36.14 / manual-CSV
   fallback path — never sets `downloads_path`, so that behavior is exactly unchanged (proven by a new
   regression test, see below). This forces the raw download artifact — captured via the primary Playwright
   `"download"` event, or only ever observed through the fallback — to be written directly inside the exact
   directory the user selected. No hidden staging directory was introduced anywhere: `downloads_path` is
   set to the same, single, user-visible configured directory the fallback already watches and the final
   file is already written to. This does not restore P.35.2–P.35.5's cancelled staging/fingerprinting
   design; it is a single launch-parameter correction confined to `prisma_lifecycle.py`.
2. `prisma_download.py`'s `PrismaDownloadFilesystemWaiter.poll()`: since the raw artifact is now correctly
   written into the configured directory but is still named by the browser/CDP itself (typically UUID-like,
   never necessarily `.csv`), the previous requirement that a candidate have a literal `.csv` suffix would
   have made this exact artifact permanently invisible to the fallback even after fix (1). A candidate is
   now any newly appeared, non-partial file (`.crdownload`-suffixed files are still excluded exactly as
   before, so the native-Chrome-with-a-recognizable-suggested-filename flow is completely unaffected).
   Completion is still decided the same way as before: size stability across
   `_FILESYSTEM_STABILITY_CHECKS` (3) consecutive polls, plus a successful open-for-read — never by name.
   The internal activity-tracking flag that eventually classifies a vanished, never-completed download as
   `INTERRUPTED` was broadened from "a recognized `.crdownload` partial was seen" to "any candidate was
   seen," so a cancelled UUID-named artifact is still correctly classified as interrupted rather than
   silently running out the clock to a generic timeout.
3. `PrismaDownloadOrchestrator._finalize_from_filesystem()` now forces a `.csv` extension explicitly
   (`build_dated_filename(f"{path.stem}.csv", date_range)`) instead of deferring to
   `build_dated_filename`'s own suffix-preserving default, since the raw artifact's own name is a
   browser/CDP-generated identifier, never a trustworthy source of the final extension. This is a pure
   no-op for the pre-existing `.csv`-suffixed case (`Path("Auction_overview.csv").stem` is
   `"Auction_overview"`, producing byte-identical output to before).
4. **Newly found while implementing this fix, and closed in the same change:** neither finalize path
   guarded against a *stable but empty* artifact. `PrismaDownloadFilesystemWaiter._poll_candidate()` now
   classifies a zero-byte file that has otherwise stabilized and is readable as `INTERRUPTED` rather than
   `READY`. `PrismaDownloadOrchestrator._finalize()` (the primary/event path) now checks the size of the
   file `download.save_as()` just wrote; a zero-byte result is reported as `DOWNLOAD_INTERRUPTED` and the
   empty artifact is deleted rather than left behind as a phantom "successful" output.
5. **Also verified while implementing this fix:** `suggested_filename` (from the primary/event path) is
   untrusted, PRISMA/browser-supplied input. `build_dated_filename` already only ever uses
   `Path(original_filename).stem`/`.suffix` — both of which operate on the final path component only and
   therefore already strip any `../` traversal segments before a flat filename is assembled — so a
   traversal-shaped `suggested_filename` was already incapable of escaping the configured directory. This
   was previously true only incidentally; it is now covered by an explicit regression test rather than
   relying on it remaining true by accident of implementation.

**Scope discipline.** Confined to `prisma_lifecycle.py`'s browser-launch call and three methods in
`prisma_download.py` (`PrismaDownloadFilesystemWaiter.poll()`/`_poll_candidate()`,
`PrismaDownloadOrchestrator._finalize()`, `PrismaDownloadOrchestrator._finalize_from_filesystem()`), plus
their direct test coverage. Date handling (P.36.13 and this file's date-range-related entries above), the
12-column output contract, transformations, mappings, the manual CSV fallback (P.36.4), the naming/collision
rule itself (`build_dated_filename`/`reserve_unique_download_path`, unchanged), the download-directory
contract (P.36.3), and unrelated UI are all untouched. The download-listener registration order (registered
on the owned `BrowserContext`, strictly before the CSV control is activated) was inspected against this
defect and confirmed already correct — no change was needed there.

**Automated evidence (2026-08-03).** `tests/test_prisma_download.py` gained 7 tests:
`test_filesystem_fallback_accepts_a_uuid_named_artifact_without_a_csv_suffix` (a UUID-named, suffixless
artifact is recognized as a candidate and reaches `ready` after three stable polls, exactly like the
existing `.csv`-suffixed case);
`test_filesystem_fallback_rejects_multiple_new_files_regardless_of_extension` (two new files, one
UUID-named and one `.csv`, still correctly rejected as ambiguous);
`test_filesystem_fallback_rejects_a_stable_empty_file` (a zero-byte file that stabilizes is classified
`interrupted`, never `ready`);
`test_await_and_finalize_produces_exactly_one_dated_output_when_the_event_wins_the_race` (a raw artifact
appears via the fallback path, then the Playwright event also fires for the same download; only the
primary path's output exists under the dated filename — no duplicate);
`test_await_and_finalize_from_filesystem_forces_a_csv_extension_for_a_suffixless_artifact` (a UUID-named
artifact is finalized into a `<uuid>_<start>_<end>.csv` file with the exact downloaded bytes preserved);
`test_finalize_rejects_a_zero_byte_saved_download` (the primary/event path: a `save_as()` that writes zero
bytes is reported as `DOWNLOAD_INTERRUPTED`, and no empty file is left in the directory); and
`test_finalize_sanitizes_a_path_traversal_suggested_filename_to_stay_inside_the_directory` (a
`"../../evil.csv"` `suggested_filename` still resolves to `evil_<start>_<end>.csv` directly inside the
configured directory, and nothing is ever written two levels above it).

`tests/test_prisma_lifecycle.py` gained 4 integration tests:
`test_managed_download_launches_the_browser_with_downloads_path_set_to_the_configured_directory` (captures
the real `launch()` call's keyword arguments end-to-end through `PrismaLifecycleController.open()` and
confirms `downloads_path == str(download_directory)` exactly — the direct regression test for the reported
defect's root cause);
`test_open_without_download_arguments_never_sets_a_downloads_path` (the pre-P.36.14/manual-fallback `open()`
call, with neither `date_range` nor `download_directory` supplied, never passes `downloads_path` — proving
backward compatibility);
`test_managed_download_succeeds_via_filesystem_fallback_with_a_uuid_named_artifact` (a UUID-named file
appearing in the configured directory, with no Playwright event ever fired, is still finalized end-to-end
into a correctly dated `.csv` and reported as a successful `kind="download"` event); and
`test_managed_download_reports_exactly_one_success_when_the_event_and_fallback_observe_the_same_download`
(both a raw filesystem artifact and a Playwright `"download"` event are observed for the same underlying
download; exactly one `kind="download"` success event and exactly one dated output file result — no
duplicate).

The complete pytest suite passed with **748 tests** (up from 737; `tests/test_prisma_download.py`: 107, up
from 100 — the exact +7 expected; `tests/test_prisma_lifecycle.py`: 69, up from 65 — the exact +4 expected).
Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`) exited `0`, with the
same pre-existing, unrelated `.pytest_tmp` permission warning recorded in every prior entry in this file.
`git diff --check` passed (the same informational CRLF-normalization notice on
`tests/test_prisma_lifecycle.py` noted in prior entries, not a whitespace error, and predating this fix).
`python -m PyInstaller --clean --noconfirm PrismaFunction.spec` was rerun to produce a fresh distribution
from this fix, and `python validate_package.py` passed against it.

**Outstanding.** Full manual Windows validation has not yet been performed and remains required: select
`Downloads\PrismaFunction` as the download folder, choose and validate a clearly distinguishable date
range, start the managed PRISMA download against the real, live PRISMA site in real Chrome, and confirm the
selected directory receives exactly one final, non-empty `.csv` file with a normal (dated, `.csv`-suffixed)
final filename — and specifically confirm no UUID-named or partial file is ever left behind or mistaken for
the final result. This is in addition to, not a replacement for, P.36.14's already-recorded outstanding
real-installed-Chrome production acceptance pass and the DATE RANGE control fix's own outstanding manual
validation recorded in this file's immediately preceding entry.

#### P.36.15. Transform into the exact 12-column output CSV contract — Implemented, reviewed, and merged (2026-08-04, PR #62, merge commit `c84344f`)

Per `ROADMAP.md`'s "P.36 roadmap correction (2026-08-02)", `P.36.15` transforms one already-validated
official PRISMA Export CSV into the exact 12-column output contract (`workflow_p.md` section 1.1, item 5;
`ROADMAP.md`'s "Authoritative output CSV contract"). Implemented on `feature/p36-15-output-writer`, branched
from `main` at merge commit `36b7615` (the P.36.14 merge via PR #61); merged to `main` via PR #62 (merge
commit `c84344f`). Manual real-Windows/real-PRISMA validation remains outstanding — see "Manual validation"
below.

**Design.** New module `prisma_output.py`, Qt- and browser-independent, matching the existing
`date_range_selection.py`/`download_directory.py`/`manual_csv_selection.py`/`prisma_download.py` pattern
(typed `str` `Enum` outcome, immutable frozen-dataclass result with a `succeeded` property, a stable
path-free `describe_*` message function, an explicit `__all__`). It reimplements none of the existing
parsing/normalization/filtering/enrichment/side-specific-resolution rules: `processor.import_prisma_export()`
(P.33/P.36.4, unchanged) is called directly and its `PrismaImportResult`/`PrismaImportIssue` typed outcomes
are threaded straight through, so the existing missing-side (`missing_required_exit_reference`/
`missing_required_entry_reference`) and unknown-alias (`unknown_exit_reference`/`unknown_entry_reference`)
rejection behavior, and its exact side-specific Market/Storage resolution, are preserved unchanged and
un-duplicated.

**Field-level source/transform rules** (from `processor.py`'s already-enriched row dict to the 12-column
contract, no re-derivation):

| Output column | Source field | Rule |
|---|---|---|
| `Auction Date` | `auction_date` | Passed through unchanged: an ISO 8601 string (`datetime.isoformat()`), the same representation `storage.py`'s SQLite/Excel export already treats as authoritative. |
| `Exit Market` | `exit_market` | Passed through unchanged; populated only when the row's direction required and resolved exit-side evidence, empty otherwise — never inferred from the opposite side. |
| `Entry Market` | `entry_market` | Same rule, entry side. |
| `Capacity Type` | `direction` | Passed through unchanged: `"entry"`, `"exit"`, or `"bundle"`, matching the authoritative specification's exact wording (section 1.1, item 5). |
| `Network Point Name` | `network_point` | Passed through unchanged: already the correct side-specific selected name for the row's direction. |
| `Product Type` | `product_type` | Passed through unchanged: `WD`/`Day Ahead`/`Month`/`Quarter`/`Year`, per the existing `_product_type()` rule. |
| `Flow Start` | `flow_start` | Passed through unchanged; ISO 8601, same rule as `Auction Date`. |
| `Flow End` | `flow_end` | Passed through unchanged; ISO 8601, same rule as `Auction Date`. |
| `Booked Capacity` | `booked_capacity_kwh_h` | `str(float)` (always dot-decimal); already normalized to kWh/h by `processor._capacity()`; no additional rounding applied — no authoritative rounding/precision decision exists, so the exact already-normalized value is preserved. |
| `Flow Duration Hours` | `runtime_hours` | `str(float)`; same no-rounding rule. |
| `Tariff Price` | `tariff_eur_mwh_h` | `str(float)`; already normalized to EUR/MWh/h by `processor._price()`; same no-rounding rule. |
| `Premium Price` | `premium_eur_mwh_h` | `str(float)`; same rule. |

**Write path.** `write_prisma_output(source_path, output_directory, *, reference_catalog=DEFAULT_PRISMA_REFERENCES)`
validates the destination directory first (existing, readable, writable — reusing
`download_directory.validate_download_directory` plus an `os.access(..., os.W_OK)` check), never touching the
filesystem for an invalid destination (`INVALID_OUTPUT_DIRECTORY`, no `import_prisma_export()` call, no file
created). It then calls `import_prisma_export()`; a malformed/non-PRISMA-format source raises
`PrismaImportError`/`CsvFormatError`, mapped to `SOURCE_IMPORT_FAILED` with nothing written — "no output is
published on a failed transformation" is satisfied at this boundary. Only accepted rows (`imported.rows`) are
transformed and written; filtered and rejected rows are excluded from the file but remain fully inspectable
via the returned `PrismaImportResult` (`filtered_count`/`rejected_count`/`issues`), satisfying "every source
row has one deterministic typed outcome" without inventing a second issue-tracking mechanism. A source whose
every row is filtered or rejected still produces a valid header-only output file — a successful transformation
of an empty accepted set is not itself a failure.

Writing is atomic and collision-safe: `prisma_download.reserve_unique_download_path()` (the already-approved
P.36.14 naming/collision rule — exclusive `os.O_CREAT | os.O_EXCL` reservation, never overwrites, increments
`_2`/`_3`/... on collision) is reused unchanged rather than reimplemented; the full CSV is staged into a
temporary file in the same destination directory (`tempfile.mkstemp`), flushed and `fsync`ed, and only then
`os.replace()`d onto the reserved placeholder. A failure at any point (staging, the replace itself) leaves the
reserved placeholder removed and no `.staging` temp file behind — proven by dedicated tests that force
`os.replace()` and a mid-write `csv.DictWriter.writerows()` to each raise, both asserting the destination
directory ends up empty.

**Naming decision (documented assumption, not a customer decision).** No approved publication naming/collision
policy exists yet specifically for this transformed output — that is explicitly the blocked `P.36.16` decision
gate's job (destination, filename, overwrite/versioning, accumulation). Absent that, `build_output_filename()`
uses `"<source-stem>_transformed.csv"`, the smallest safe extension of the already-approved
`P.36.14` `"<stem>_<suffix>.csv"` template. This is recorded here as an explicit, reviewable assumption rather
than silently invented; `P.36.16` may replace it entirely without needing to change `prisma_output.py`'s
transform/write internals.

**No accumulation, no UI wiring.** Each `write_prisma_output()` call is a fully independent operation: two
calls over the same source file produce two separate, independently numbered output files with no merging or
deduplication (test-proven), so none of `P.36.16`'s excluded accumulation/cross-file-deduplication/state-
tracking scope was introduced. No UI trigger was added: `app.py`, `PrismaFunction.spec`, and all browser/
lifecycle code are unchanged. None of P.36.15's own acceptance criteria require a UI trigger, and
`self._manual_csv_selection.current` — already exposed by the merged P.36.14 work (see this file's matching
entry above) — remains the exact boundary a later increment will pass to `write_prisma_output()`.

**Review fix (2026-08-04).** A review of the initial implementation found that both `WRITE_FAILED` outcomes
in `write_prisma_output()` — a destination-reservation failure and a staging/atomic-replace failure — dropped
the already-computed `PrismaImportResult`, even though `import_prisma_export()` had already succeeded by that
point in the call. A caller receiving a `WRITE_FAILED` result therefore had no way to see which rows had been
accepted, filtered, or rejected before the write itself failed. Both `return PrismaOutputResult(...)` call
sites now pass `import_result=imported` unchanged, with no change to either path's outcome, message, or safe
error-context behavior.

**Automated evidence (2026-08-04).** New `tests/test_prisma_output.py` (26 tests): the exact ordered
12-column header and exactly 12 fields per row; UTF-8 encoding and `;` delimiter; a representative successful
transformation with exact field-by-field assertions (including summed tariff/premium prices); pure
`transform_row()` mapping in isolation; Exit/Entry placement for entry-only (Storage-classified), exit-only
(Market-classified), and bundle (both sides) directions; unresolved-alias and missing-required-side rows
excluded from the output while remaining recorded as typed rejections; below-threshold rows filtered and
excluded; a mixed accepted/rejected source writing only the accepted row; zero accepted rows still producing
a valid header-only file; a malformed/non-PRISMA source failing the transformation and writing nothing; stable
non-empty messages for every `PrismaOutputOutcome`; a nonexistent, a file-shaped, and a non-writable
destination directory each rejected without any filesystem write; the exact naming rule; collision handling
never overwriting and using the incrementing-suffix rule; two independent calls never merging; a destination-
reservation failure, a simulated `os.replace` failure, and a simulated mid-write failure each leaving zero
files in the destination directory — the three write-failure tests use a source with one accepted, one
filtered, and one rejected row, and each asserts `result.import_result` is not discarded and carries the
exact pre-computed `imported_count`/`filtered_count`/`rejected_count`, the accepted row's data, and the
filtered/rejected issues' reason codes; a successful write leaving no staging artifacts; and a caller-supplied
`PrismaReferenceCatalog` being honored.

The complete pytest suite passed with **774 tests** (up from 748, the exact +26 expected from this
increment). Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`, `dist`)
exited `0`, with the same pre-existing, unrelated `.pytest_tmp` permission warning recorded in every prior
entry in this file. `git diff --check` passed.

**Not run, and why.** `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` /
`python validate_package.py` were not rerun: `prisma_output.py` is not imported by `app.py` or referenced by
`PrismaFunction.spec`, so PyInstaller's static import discovery would not bundle it, and a rebuild would
reproduce the identical distribution already validated after the P.36.14 merge — this increment does not
affect packaging. `tests/test_packaging.py` is included in, and passed as part of, the 774-test full-suite
run above.

**Manual validation.** None is required by this increment's own acceptance criteria: `write_prisma_output()`
consumes only an already-on-disk, already-validated CSV file and performs no browser, network, or PRISMA
session operation. Real-Windows/real-PRISMA end-to-end validation remains appropriate once a later increment
wires this module into the application workflow (a UI trigger, deferred here — see "No accumulation, no UI
wiring" above).

**Scope discipline.** Confined to the new `prisma_output.py` module and its new `tests/test_prisma_output.py`
suite. `processor.py`, `prisma_references.py`, `prisma_download.py`, `download_directory.py`, `app.py`,
`PrismaFunction.spec`, the completed P.36.14 managed-download behavior, and all other existing code are
unmodified. Merged to `main` via PR #62 (merge commit `c84344f`); the `feature/p36-15-output-writer` branch
deletion is a separate post-merge cleanup action not claimed here.

**Outstanding before this increment can be marked ✅ Completed:** final review found no remaining actionable
code defects and the increment is merged to `main`. Per this increment's own criteria, the one remaining
item is manual real-Windows/real-PRISMA validation — see "Manual validation" above.

#### P.36.16. Publish the processed result — Decision gate resolved; implemented, automated-tested, and merged (2026-08-04, PR #63, merge commit `daf4760`)

**Decision gate resolution.** Per this task's approved "option 2" customer decision (2026-08-04),
publication accumulates results across runs into exactly one cumulative CSV per publication directory,
using the existing `P.36.3` Documents-directory-or-user-selected-directory contract as the destination.
Duplicate identity is exact equality of the complete 12-field canonical output row — never a narrower
business key (Auction ID is not one of the 12 output fields), never fuzzy/substring/inferred matching, and
never update-in-place semantics. Exact duplicates are removed both against the existing published rows and
within the current completed import. Ordering is deterministic: existing unique rows keep their original
order, new unique rows are appended in their current import order. Publication is atomic (stage, flush,
`fsync` where supported, `os.replace()`), and a failure at any point preserves the previous valid cumulative
file and the completed `PrismaImportResult`'s accepted/filtered/rejected evidence unchanged. An existing
cumulative file that fails its own contract check (empty, malformed quoting, a blank data row, the header
repeated among data rows, wrong delimiter, undecodable, wrong header, or being a symbolic link) is a typed
failure that leaves the file completely unchanged — no repair is attempted and a symlink is never followed.
Implemented
on `feature/p36-16-cumulative-output`, branched from `main` at merge commit `c84344f` (the P.36.15 merge via
PR #62), so P.36.15's completed implementation is already present on this branch. Merged to `main` via PR
#63 (merge commit `daf4760`, confirmed in Git history).

**Design.** New module `prisma_publication.py`, Qt- and browser-independent, matching the existing
`prisma_output.py`/`prisma_download.py` pattern (typed `str` `Enum` outcome, immutable frozen-dataclass
result with a `succeeded` property, a stable path-free `describe_*` message function, an explicit
`__all__`). It operates on an already-completed `processor.PrismaImportResult` — not a raw source CSV path
— and reuses `prisma_output.transform_row()`/`OUTPUT_CSV_COLUMNS` for row formatting, so there remains
exactly one canonical serialization of the 12-column contract in the codebase. `prisma_output.py` is
completely unmodified by this increment: `write_prisma_output()` remains available unchanged for any
existing caller, satisfying the backward-compatibility requirement with a zero-diff guarantee.

**Merge/deduplication logic.** `publish_cumulative_output(import_result, publication_directory)` validates
the destination directory first (existing, readable, writable — reusing
`download_directory.validate_download_directory` plus the same writability check `prisma_output.py` already
applies). It then reads the existing cumulative file at
`<publication_directory>/Prisma_Output_Published.csv` if present: a missing file means "create from the
current import"; a symbolic link at that path (never followed, read, or replaced), or a file that is
unreadable, empty, undecodable as UTF-8, wrongly delimited, malformed-quoted, missing the exact 12-column
header, containing a blank data row, or repeating the exact header among its data rows returns
`INVALID_EXISTING_FILE` with the file left byte-for-byte unchanged. Each
accepted row (`import_result.rows`) is formatted via `transform_row()` into its exact 12-field tuple; a row
already present among the existing rows, or already emitted earlier in the same import, is dropped. Existing
rows keep their original order; new unique rows are appended in import order. If every row in the current
import already exists in a valid existing file (including a zero-accepted-row import), the file is left
completely untouched rather than rewritten — verified by asserting both unchanged file content and an
unchanged mtime.

**Write path.** The complete merged row set (only ever computed when there is something new to write) is
staged into a temporary file in the same publication directory (`tempfile.mkstemp`), flushed and `fsync`ed,
and only then `os.replace()`d onto the fixed target filename — the same stage-then-replace pattern
`prisma_output.py`'s own `_write_rows()` already uses, reused as a pattern rather than by direct call, since
this module's target is a fixed, reusable filename rather than a freshly reserved, collision-avoided one. A
failure at any point (staging-file creation, write, flush, fsync, or `os.replace()`) leaves the previous
valid cumulative file completely unchanged and removes only the failed attempt's own staging artifact —
proven by dedicated tests that force `tempfile.mkstemp`, `os.replace()`, and a mid-write `csv.writer` call to
each raise, all three asserting the destination directory ends up containing only the one, byte-identical
prior published file.

**Naming decision (documented assumption, not a customer decision).** The approved decision defines the
merge/dedup/atomic-publish *behavior*, not a specific cumulative filename. `PUBLISHED_OUTPUT_FILENAME =
"Prisma_Output_Published.csv"` is the safest available assumption, documented here explicitly per the same
pattern `prisma_output.build_output_filename()` used for its own undecided naming detail in the P.36.15
entry above.

**No UI wiring.** No UI trigger was added: `app.py`, `PrismaFunction.spec`, and all browser/lifecycle code
are unchanged. None of this increment's own acceptance criteria require a UI trigger; a later increment is
expected to pass a caller's completed `PrismaImportResult` (from either `processor.import_prisma_export()`
directly or `prisma_output.write_prisma_output(...).import_result`) into this new boundary.

**Review fix (2026-08-04).** A review of the initial implementation found the existing-cumulative-file
validation was weaker than the approved contract required:

- it parsed the decoded text via `text.splitlines()`, which would incorrectly split a correctly quoted
  field's own embedded newline into two separate CSV records instead of preserving it as one value;
- it used the default non-strict `csv.reader`, silently tolerating malformed quoting instead of rejecting
  it;
- it silently skipped a blank data row rather than treating the file as malformed;
- it never rejected the exact 12-column header if it reappeared among the data rows;
- it never checked whether the target path was a symbolic link before reading through it, risking a read
  of (and an eventual `os.replace()` onto) an unintended external target.

`_read_existing_rows()` now rejects a symlink at the target path before any read is attempted
(`path.is_symlink()`, checked first); parses the decoded text through `io.StringIO(text, newline="")` fed
into `csv.reader(..., delimiter=";", strict=True)` (matching the same `newline=""` convention
`_write_rows()` already uses for writing), translating any `csv.Error` into the existing
`INVALID_EXISTING_FILE` outcome; and explicitly rejects a blank data row and a data row equal to the exact
header tuple, in addition to the existing wrong-field-count check. Every rejection path still leaves the
existing file completely unread-from/unwritten-to — no write is ever attempted once `_read_existing_rows()`
has raised, matching this increment's existing atomicity/preservation guarantees.

**Review fix (2026-08-04, second round).** A further review found `publish_cumulative_output()`'s
`INVALID_PUBLICATION_DIRECTORY` return path (destination directory missing, not a directory, or not
writable) dropped the already-supplied `PrismaImportResult` instead of returning it, unlike every other
outcome (`INVALID_EXISTING_FILE`, `WRITE_FAILED`, `SUCCESS`) — contradicting the documented contract
("carries ... the full `PrismaImportResult` on every outcome") in the "Merge/deduplication logic" section
above. The `except DownloadDirectoryError` branch now passes `import_result=import_result` unchanged, with
no change to the outcome, message, directory-validation order, or filesystem behavior. The existing
reservation-failure write test was also strengthened: it previously used a single-accepted-row import, so
it only ever proved `imported_count` survived a write failure; it now uses a mixed-outcome import (one
accepted, one filtered, one rejected row, the same pattern `test_prisma_output.py`'s own
`_MIXED_OUTCOME_ROWS` established) and asserts the exact `imported_count`/`filtered_count`/`rejected_count`,
the accepted row's data, and the filtered/rejected issues' reason codes — proving the *complete* evidence
survives, not only the accepted rows.

**Automated evidence (2026-08-04).** New `tests/test_prisma_publication.py` (28 tests: 27 passed, 1
platform-conditional skip): first publication creating the cumulative file from the current import;
appending new unique rows to an existing valid file; a duplicate against existing rows not appended;
duplicates within one import written once; a row differing in exactly one of the 12 fields remaining
distinct; existing-row and new-row order both preserved across repeated runs; exactly one header line
surviving three repeated publish runs; a zero-accepted-row import (and an import where every row already
exists) leaving a byte-identical, unmodified existing file (content and mtime both asserted); an empty, a
wrong-delimiter, a non-UTF-8, and a wrong-header existing file each failing with `INVALID_EXISTING_FILE`
with the file provably byte-identical afterward; a correctly quoted field containing an embedded newline
round-tripping through publish and read without corruption — including proof that republishing the exact
same multiline row is recognized as a duplicate (not falsely appended again) and that a distinct-but-similar
multiline value is still recognized as distinct; malformed quoting, a repeated header among data rows, and
a blank data row in an existing file each failing with `INVALID_EXISTING_FILE` with the file provably
byte-identical afterward; a target-path symlink pointing outside the publication directory rejected with
its external target left byte-identical and unreplaced (the test skips only when the platform/user cannot
create a symlink — it skipped in this sandboxed Windows environment, which lacks the required privilege, so
this specific path is not yet exercised here); a simulated staging-reservation failure using a
mixed-outcome import (`tempfile.mkstemp`, now asserting the complete accepted/filtered/rejected evidence —
see "Review fix, second round" above), a simulated `os.replace` failure, and a simulated mid-write failure
each preserving the prior published file's exact content and leaving zero staging artifacts; a
first-publication write failure leaving zero files in the destination directory; a target-directory listing
after each publish containing only the one cumulative file; a decoy file of the same name in a sibling
directory remaining untouched (no read or write escapes the configured publication directory); a
nonexistent, a file-shaped, and a non-writable destination directory each rejected without any filesystem
write; a nonexistent destination directory combined with a mixed-outcome import proving
`result.import_result is` the exact supplied object (identity), its accepted/filtered/rejected counts and
issue evidence remain intact, and no filesystem write occurs; and stable non-empty messages for every
`PrismaPublicationOutcome`.

The complete pytest suite passed with **801 tests passed, 1 skipped** (up from 800 passed/1 skipped before
this correction round; +1 net: one existing test strengthened in place, one new test added). Project-wide
`python -m compileall` (excluding `.venv`, `build`, `.git`, `__pycache__`, `dist`) exited `0`, with the same
pre-existing, unrelated `.pytest_tmp` permission warning recorded in every prior entry in this file. `git
diff --check` passed.

**Not run, and why.** `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` /
`python validate_package.py` were not rerun: `prisma_publication.py` is not imported by `app.py` or
referenced by `PrismaFunction.spec`, so PyInstaller's static import discovery would not bundle it, and a
rebuild would reproduce the identical distribution already validated after the P.36.15 merge — this
increment does not affect packaging, matching the exact rationale `P.36.15` recorded for the same situation.
`tests/test_packaging.py` (10 tests) is included in, and passed as part of, the 801-test full-suite run
above.

**Manual validation.** None is required by this increment's own acceptance criteria:
`publish_cumulative_output()` consumes only an already-computed `PrismaImportResult` and performs no
browser, network, filesystem download, or PRISMA session operation. Real-Windows/real-PRISMA end-to-end
validation remains appropriate once a later increment wires this module into the application workflow (a UI
trigger, deferred here — see "No UI wiring" above). Separately, the symlink-rejection test's
platform-conditional skip means that specific path has automated test *code* but no actual pass recorded
yet in any environment; it should be re-run on a session where symlink creation is permitted (e.g. Windows
Developer Mode enabled, or elevated privileges) so it is genuinely exercised rather than skipped.

**Scope discipline.** Confined to `prisma_publication.py` (the `_read_existing_rows()` validation
strengthening described in "Review fix" above, plus the single-line `INVALID_PUBLICATION_DIRECTORY`
`import_result` fix described in "Review fix, second round") and `tests/test_prisma_publication.py` (the
corresponding new/strengthened tests). `prisma_output.py`, `processor.py`, `prisma_references.py`,
`prisma_download.py`, `download_directory.py`, `app.py`, `PrismaFunction.spec`, the completed
P.36.14/P.36.15 behavior, and all other existing code are unmodified. Not committed, pushed, merged, or
rebased; the feature branch was not deleted.

**Outstanding before this increment can be marked ✅ Completed (updated after the confirmed merge to
`main` via PR #63, merge commit `daf4760`):** manual real-Windows/real-PRISMA validation of the eventual
wired-in workflow once a later increment adds the UI trigger, plus a genuine (non-skipped) run of the
symlink-rejection test on a platform/session that permits symlink creation. Per this increment's own
acceptance criteria, no additional automated work is outstanding. Note: `P.36.8` (see the section
immediately below) adds a UI mapping *display*, not a P.36.14→P.36.15→P.36.16 pipeline trigger — it does
not wire this module in and does not change this outstanding item.

#### P.36.8. Mapping display in the UI — Implemented, automated-tested, and manually validated on real Windows (manual-selection path), not yet merged (2026-08-04)

Per `ROADMAP.md`'s "Remaining support and finalization stages" table, `P.36.8` displays exactly `Exit
Market`, `Entry Market`, `Network Point Name`, `TSO Name Exit`, `TSO Name Entry` (this exact order and
spelling) in the UI without changing the authoritative 12-column output CSV contract. Implemented on
`feature/p36-8-mapping-display`, branched from `main` at merge commit `daf4760` (the P.36.16 merge via PR
#63), so P.36.16's completed implementation is already present on this branch. Not yet merged.

**Decision required and resolved before implementation.** Neither `ROADMAP.md` nor this file wires a
completed P.36.15 import/transformation result into the UI: the "Next recommended increment" list in
`ROADMAP.md` explicitly reserves "wiring a UI trigger for the complete P.36.14→P.36.15→P.36.16 pipeline"
for a later increment, so P.36.8 had no existing trigger to reuse and needed its own read-only source of
mapping evidence. Asked to choose between (a) a new explicit "Preview Mapping" button, or (b)
auto-populating the display from the two already-existing, already-approved CSV-selection success paths
(P.36.4 manual selection, P.36.14 managed download), the customer selected (b): no new button, no new
persistence or publication behavior — the display simply reflects whatever CSV is currently the accepted
selection.

**Design.** New module `mapping_presentation.py`, Qt- and browser-independent, matching the existing
`prisma_output.py`/`prisma_publication.py` pattern (frozen-dataclass row type, an explicit `__all__`, no
parsing/matching/inference of its own). `MAPPING_DISPLAY_FIELDS = ("Exit Market", "Entry Market", "Network
Point Name", "TSO Name Exit", "TSO Name Entry")` is the authoritative five-field order/spelling from
`ROADMAP.md`'s "Authoritative output CSV contract" section. `MappingDisplayRow` is an immutable
five-field row. `build_mapping_rows(import_result)` selects `exit_market`/`entry_market`/`network_point`/
`tso_exit`/`tso_entry` straight through from each row in `import_result.rows` — the same already-accepted,
already-enriched row shape `prisma_output.transform_row()` consumes for the 12-column contract, produced
by `processor.import_prisma_export()` (P.33/P.36.4, unchanged) — with no matching, inference, or
cross-side substitution of its own. Because `PrismaImportResult.rows` already excludes filtered and
rejected rows (they only ever appear in `PrismaImportResult.issues`), a filtered/rejected-only import (or
any import with zero accepted rows) naturally yields an empty tuple, never an error, with no separate
"is this import interesting" branch needed in the presentation boundary itself.

**Qt view/model.** `ui_components.py` adds `MappingTableModel(QAbstractTableModel)`, matching the existing
`AuctionTableModel` construction pattern exactly (fixed `HEADERS`, `rowCount`/`columnCount`/`headerData`/
`data`). `HEADERS = MAPPING_DISPLAY_FIELDS`, so the model can never drift from the presentation module's
authoritative field list. `set_rows()` performs `beginResetModel()`/`self.rows = tuple(rows)`/
`endResetModel()` — a full wholesale replace, never an incremental patch — so a new CSV selection's refresh
can never leave a row from a previous, unrelated selection visible.

**UI wiring.** `app.py` adds one new content panel ("Mapping": `self.mapping_table_model`,
`self.mapping_table`, `self.mapping_empty_label`) alongside the existing auction and activity panels, with
`_update_mapping_empty_state()` toggling the table/empty-label visibility deterministically from
`rowCount()`. `_refresh_mapping_display(path)` is the one shared refresh boundary both existing
CSV-selection success paths call: it invokes `processor.import_prisma_export(path)` — a read-only re-run
of the exact P.36.15 import/enrichment boundary, writing no output file and performing no browser,
network, or publication operation — and on success replaces the table via `build_mapping_rows()`; on a
typed `PrismaImportError`/`CsvFormatError`/`OSError` it clears the table (`set_rows(())`, never leaving a
stale row from the previous selection) and shows one fixed, path-free English message via the existing
`_show_error()` helper ("The mapping evidence for the selected PRISMA Export CSV could not be displayed."),
never the raw exception text or the file path. `_select_manual_csv()` (P.36.4) and `_handle_download_event()`
(P.36.14) each call `_refresh_mapping_display(result.path)` exactly once, and only after their own existing
CSV-contract acceptance check already succeeded — a rejected candidate at that existing boundary still
returns before ever reaching the mapping refresh, exactly as it did before this increment. No other
call site, workflow trigger, persistence contract, or publication behavior was added; `prisma_output.py`,
`prisma_publication.py`, `processor.py`, `prisma_references.py`, and every other existing module are
unmodified.

**Automated evidence (2026-08-04).** New `tests/test_mapping_presentation.py` (11 tests) covers the exact
`MAPPING_DISPLAY_FIELDS` order/spelling; pure field mapping and row-order preservation against a directly
constructed `PrismaImportResult`; an empty accepted result and a filtered/rejected-only result both
yielding an empty tuple; a regression proving an entry-only row's exit-side fields stay exactly empty
rather than being inferred from the entry side; and, through the real `processor.import_prisma_export`
boundary with the authoritative default reference catalog, an exit-only row resolving a Market
(`"VIP DK-THE (H646) (H646)"` → `THE`), an entry-only row resolving a Storage name
(`"VGS Storage Hub (4290)"` → `VGS Storage Hub`), a bundle row using the real evidenced dual-sided alias
`"Arnoldstein Exit"` (which resolves to `CEGH` on the exit side and `PSV` on the entry side under
`prisma_references.DEFAULT_PRISMA_REFERENCES`) proving side-specific resolution is never swapped or
cross-contaminated even when the identical source string appears on both sides of one row, multi-row order
preservation across two accepted rows, and a filtered+rejected-only source (one row below the
booked-capacity threshold, one row with an unknown network-point reference) producing an empty
presentation with zero exceptions raised.

`tests/test_app.py` gained 9 tests: exact mapping-table header order/labels via `headerData()`; the initial
empty/hidden state before any CSV is selected; a header-only (zero-data-row) CSV selection leaving the
display empty and hidden; a two-row CSV populating the table with the exact expected Exit/Entry Market,
Network Point Name, and TSO Name Exit/Entry values in exact source order (one entry-only Storage row, one
exit-only Market row); a filtered+rejected-only CSV leaving the display empty; selecting a second, different
(header-only) CSV after a populated first selection fully replacing the table's rows (proving no stale-row
retention across a replacement selection); a simulated `processor.import_prisma_export` failure (raising
`PrismaImportError` with an internal, file-path-bearing message) clearing the table and showing only the
fixed, path-free error message — proving no internal exception detail or file path leaks into the UI; the
managed-download success path (P.36.14, `_handle_download_event`) also populating the table, proving both
existing trigger points are wired identically; and a regression proving the refresh path never calls
`prisma_output.write_prisma_output` or `prisma_publication.publish_cumulative_output` (each monkeypatched
to raise `AssertionError` if invoked) and records zero additional mock calls against the browser or
PRISMA-lifecycle controllers — proving that rendering/refreshing the mapping view alone triggers no
output-writing, publication, browser, download, or monitoring operation. One pre-existing test,
`test_light_workspace_widgets_use_explicit_contrast_styles`, was updated in place to add "Mapping" to its
expected set of `contentSectionLabel` section headings, since the new panel legitimately changes what that
assertion counts — an in-scope adjustment to an existing assertion the new panel changes, not unrelated
churn.

**Test-infrastructure fix required to keep the suite reliable (2026-08-04).** Adding the new per-window
`MappingTableModel`/`QTableView` — one additional Python-subclassed `QAbstractTableModel` per
`PrismaMonitorApp` instance, alongside the existing `AuctionTableModel` — made a pre-existing, previously
latent shutdown-time defect in `tests/test_app.py`'s `window` fixture reproduce reliably. Every
`PrismaMonitorApp` instance holds self-referencing `QTimer`-to-bound-method cycles (for example
`self._browser_timer` connected to `self._poll_browser_launch`), which plain Python reference counting
never reclaims — only the cyclic garbage collector does, and nothing invoked it between tests. Across the
roughly 90 `PrismaMonitorApp` instances the full `tests/test_app.py` suite creates and closes, this let
unreachable-but-uncollected Qt object graphs accumulate and eventually get torn down in one large,
unordered batch at interpreter shutdown, crashing the test process with a Windows heap-corruption exit
code (`STATUS_HEAP_CORRUPTION`). This was isolated, not guessed: a controlled `git stash` bisection
confirmed the unmodified `main` baseline ran the full suite cleanly across multiple repeated runs with zero
crashes, while the branch with only this increment's production code (and none of its new tests) already
reproduced the crash non-deterministically (passing on some runs, crashing on others) — proving the
trigger was the additional per-window Qt object count, not a defect in any specific new test's logic. The
`window` fixture now explicitly `del`s its `widget`/`browser` references and calls `gc.collect()`
immediately after `_close_app(widget)`, so each window's cyclic garbage is reclaimed promptly and
individually instead of piling up for one large, risky batch at process exit. This fully eliminated the
crash: 4/4 clean runs of `tests/test_app.py` alone and 4/4 clean runs of the complete suite, both before
and after this fix was isolated as the cause. This is a test-infrastructure-only change confined to
`tests/test_app.py`'s fixture teardown; no production code changed as a result, and no other test's
behavior or assertions were altered by it.

The complete pytest suite passed with **821 tests passed, 1 skipped** (up from 801 passed/1 skipped after
the P.36.16 merge; +20, the exact sum of the 11 new `test_mapping_presentation.py` tests and the 9 new
`test_app.py` tests). Project-wide `python -m compileall` (excluding `.venv`, `build`, `.git`,
`__pycache__`, `dist`) exited `0`, with the same pre-existing, unrelated `.pytest_tmp` permission warning
recorded in every prior entry in this file. `git diff --check` passed.

**Packaging evidence (2026-08-04), and why a rebuild was required this time.** Unlike `P.36.15`/`P.36.16`
(neither imported by `app.py`), this increment changes `app.py` itself — the exact file
`PrismaFunction.spec`'s `Analysis(["app.py"], ...)` statically analyzes — adding imports of the new
`mapping_presentation.py` module, `processor.import_prisma_export`/`PrismaImportError`,
`csv_contracts.CsvFormatError`, and `ui_components.MappingTableModel`, plus new widgets constructed in
`_build_ui()`. A packaging rebuild was therefore required and performed, not skipped on the P.36.15/P.36.16
rationale. `python -m PyInstaller --clean --noconfirm PrismaFunction.spec` succeeded and produced a fresh
`dist/PrismaFunction/PrismaFunction.exe`; no `.spec` change was needed, since PyInstaller's static import
discovery picked up `mapping_presentation.py` automatically through `app.py`'s and `ui_components.py`'s own
imports, the same pattern prior P.36 increments recorded for their own new modules. `python
validate_package.py` then passed against that fresh distribution. No packaged-executable launch, real
browser, or real-PRISMA validation was performed beyond this static packaging check.

**Scope discipline.** Confined to `mapping_presentation.py` (new), `ui_components.py` (new
`MappingTableModel` plus its import of `mapping_presentation`), `app.py` (new "Mapping" panel, the
`_update_mapping_empty_state()`/`_refresh_mapping_display()` helpers, and one new call site added at the
end of each of `_select_manual_csv()` and `_handle_download_event()`), `tests/test_mapping_presentation.py`
(new), and `tests/test_app.py` (9 new tests, the `window` fixture's `gc.collect()` cleanup, and the one
pre-existing label-set assertion described above). `prisma_output.py`, `prisma_publication.py`,
`processor.py`, `prisma_references.py`, `prisma_download.py`, `prisma_lifecycle.py`,
`download_directory.py`, `date_range_selection.py`, `manual_csv_selection.py`, the 12-column output CSV
contract, and every other completed P.36.2–P.36.4/P.36.13–P.36.16 behavior are unmodified. Not committed,
pushed, merged, or rebased; the feature branch was not deleted.

**Manual validation.** Not performed and not required by this increment's own acceptance criteria in
isolation (`_refresh_mapping_display()` performs no browser, network, filesystem-download, or PRISMA
session operation — it only re-parses an already-on-disk, already-validated CSV). Real-Windows manual
validation remains appropriate before this increment is marked ✅ Completed: confirm the "Mapping" panel
renders the five fields in the correct order for a real downloaded or manually selected PRISMA Export CSV,
and confirm it refreshes correctly (no stale rows) when a second CSV is selected. (A later validation round
recorded below found there is no user-accessible refresh action that would let a tester move or delete the
selected file between selection and refresh, so that specific scenario is not deterministically reproducible
through the UI and was explicitly skipped rather than treated as outstanding.)

**Review fix (2026-08-04): rejected CSV replacement left stale mapping rows visible.** Review found that
`_refresh_mapping_display()`'s failure branch was the only place clearing the mapping table; both
`_select_manual_csv()` and `_handle_download_event()` return immediately — before ever calling
`_refresh_mapping_display()` — when the existing `ManualCsvSelection`/P.36.4 CSV-contract check rejects the
newly selected/downloaded candidate. Concretely: select a valid CSV (populating the Mapping table), then
select or download a second CSV that fails that existing contract check (wrong header, wrong delimiter,
etc.) — the table still showed the *first* CSV's rows, a stale-mapping-evidence regression against the
approved requirement that a failed replacement must never retain previous mapping rows.

**Fix.** A new shared helper, `_clear_mapping_display()` — wrapping the exact `set_rows(())`/
`_update_mapping_empty_state()` pair `_refresh_mapping_display()`'s own failure branch already used inline
— is now also called from both `_select_manual_csv()`'s and `_handle_download_event()`'s existing `if not
result.accepted:` rejection branches, immediately before their existing `_show_error()` call. Every other
line in both branches — the rejection message, `status` text, `_add_activity()` call, and the preserved
`_manual_csv_selection.current`/`manual_csv_label` state — is unchanged, so all existing P.36.4/P.36.14
rejection behavior is preserved exactly. Two cases outside this fix's scope were deliberately left
untouched: cancelling the manual file-selection dialog (`if not selected: return`, which returns before
`ManualCsvSelection.select()` is ever called — no replacement operation occurred, so the mapping table is
correctly left as-is); and `_handle_download_event()`'s separate `event.success is False` branch (the
managed download itself failed before any candidate CSV existed, so there is nothing to "replace" either).

**Regression tests.** `tests/test_app.py` gained two tests:
`test_rejected_manual_csv_replacement_clears_previous_mapping_rows` (select a valid CSV, confirm the table
has one row, then select a wrong-header CSV and confirm the table is empty and the empty-state label is
shown) and `test_rejected_download_csv_replacement_clears_previous_mapping_rows` (the same sequence via two
`_handle_download_event()` calls). The pre-existing `test_cancelling_manual_csv_dialog_is_a_no_op` test was
left unmodified — cancellation never reaches the mapping-refresh or mapping-clear code path either before
or after this fix, so its existing assertions already fully cover that case; no new assertion was needed to
prove cancellation does not clear mapping rows, since nothing in the cancellation path touches
`mapping_table_model` at all.

**Automated evidence.** The complete pytest suite passed with **823 tests passed, 1 skipped** (up from 821
passed/1 skipped; +2, the two new regression tests above). Project-wide `python -m compileall` (excluding
`.venv`, `build`, `.git`, `__pycache__`, `dist`) exited `0`, with the same pre-existing, unrelated
`.pytest_tmp` permission warning recorded in every prior entry in this file. `git diff --check` passed.
Because this fix changes `app.py` itself, `python -m PyInstaller --clean --noconfirm PrismaFunction.spec`
was rerun (succeeded, fresh `dist/PrismaFunction/PrismaFunction.exe`) and `python validate_package.py`
passed against it, matching this section's own established packaging-rebuild rationale above.

**Scope discipline.** Confined to `app.py` (new `_clear_mapping_display()` helper plus one new call site in
each of `_select_manual_csv()`'s and `_handle_download_event()`'s existing rejection branches) and
`tests/test_app.py` (the two new regression tests). No new trigger, button, persistence behavior, output
writing, publication, browser operation, or dependency was introduced; `mapping_presentation.py`,
`ui_components.py`, `prisma_output.py`, `prisma_publication.py`, `processor.py`, and every other existing
module are unmodified.

**Regression-coverage strengthening (2026-08-04): cancellation after a populated selection.** The existing
`test_cancelling_manual_csv_dialog_is_a_no_op` test only proved cancellation was a no-op starting from the
empty, nothing-selected state; it did not prove cancellation leaves an already-populated Mapping table
untouched. A new test,
`test_cancelling_manual_csv_dialog_after_a_valid_selection_preserves_mapping_rows`, selects a valid CSV
first (populating the Mapping table with one row), then cancels the next manual file-selection dialog, and
asserts the previous selection, label, mapping row count, and table visibility all remain exactly unchanged
and `QMessageBox.critical` is never called — proving `_select_manual_csv()`'s existing `if not selected:
return` early exit (before `ManualCsvSelection.select()`, `_refresh_mapping_display()`, or
`_clear_mapping_display()` are ever reached) genuinely leaves a populated Mapping table alone. The
pre-existing empty-state test was left completely unmodified, so both starting conditions now have
dedicated coverage. No production code changed — this is a pure test-coverage addition confirming the
existing cancellation code path already behaved correctly. The complete pytest suite passed with **824
tests passed, 1 skipped** (up from 823 passed/1 skipped; +1, this new test). Project-wide `python -m
compileall` and `git diff --check` both passed. No packaging rebuild was required or performed: this
change is confined to `tests/test_app.py`, and no production module or `app.py` import changed.

**Real-Windows manual validation (2026-08-04, reported by the customer).** Prisma Function was run from
source (`python app.py`) on a real Windows desktop, not as the packaged executable: the packaged
`PrismaFunction.exe` was blocked by Windows Application Control on that machine, so this validation pass
exercised the same application code from source instead. The Mapping panel was exercised through the manual
CSV-selection (P.36.4) trigger path:

- the Mapping panel rendered the five columns — `Exit Market`, `Entry Market`, `Network Point Name`,
  `TSO Name Exit`, `TSO Name Entry` — in this exact required order;
- selecting a valid PRISMA Export CSV rendered its mapping rows successfully;
- replacement behavior was checked (selecting a further CSV correctly refreshes the table);
- selecting an invalid CSV showed the existing rejection message and correctly cleared all previously
  displayed Mapping rows, confirming this section's "Review fix" above on a real Windows session, not only
  in the automated suite;
- no issues were observed.

This validation exercised only the manual-selection (P.36.4) trigger path. The managed-download (P.36.14)
trigger path (`_handle_download_event`) was **not** exercised on real Windows during this validation pass,
and its real-Windows validation remains outstanding — this record must not be read as covering it. Validating
the packaged `PrismaFunction.exe` itself (rather than a from-source run) also remains outstanding, blocked by
the Windows Application Control restriction noted above.

**Outstanding before this increment can be marked ✅ Completed:** merge to `main`; real-Windows manual
validation of the managed-download (P.36.14) trigger path populating/refreshing/clearing the Mapping panel
identically to the now-validated manual-selection path; and validating the packaged `PrismaFunction.exe`
itself once the Windows Application Control restriction noted above is resolved or an approved machine is
available. Moving/deleting the selected file before a refresh was explicitly not tested and is not tracked
as outstanding: there is no user-accessible refresh action in the current UI (the Mapping display only
refreshes as a side effect of a new CSV selection/download succeeding), so this scenario is not
deterministically reproducible through the UI and was skipped rather than treated as a pending validation
item.
