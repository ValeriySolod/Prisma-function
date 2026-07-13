# Workflow P — Prisma-function

## 1. Призначення

Workflow P визначає послідовність створення, перевірки та розвитку програми **Prisma-function**.

Програма повинна бути невеликою, зрозумілою для користувача та працювати з браузерами **Google Chrome** і **Microsoft Edge**.

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
5. Для реалізації коду використовувати Codex.
6. Після реалізації обов’язково виконувати review через GitHub Copilot без редагування файлів.
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
- `Load CSV`;
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

`%LOCALAPPDATA%\PrismaMonitor\`

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

Status: **In progress — P.23.1 is implemented with live-site verification pending; P.23.2 and P.23.3 remain planned**.

Use the Playwright page owned by the existing browser lifecycle as the live
monitoring source. Authentication/session support and complete recovery for
timeouts, unavailable pages, DOM changes, and manual browser closure are separate
follow-up increments.

#### P.23.1. Implement live PRISMA page adapter

Status: **Implemented; live-site verification pending**.

Implementation note: the default monitoring adapter now dispatches semantic
table reads to the active browser lifecycle thread, matches normalized CSV
records by the stable `Auction ID`, reads `State`/`Status`, and normalizes the
value into the existing monitoring status domain. Parsing and deterministic
missing/ambiguous-match handling are independent of Playwright and covered by
unit tests. Extraction failures are typed and never fall back to CSV state.
The complete automated suite passed. Final completion requires confirming the
semantic table roles and the `Auction ID` plus `State`/`Status` headers in a real
PRISMA browser session. That contract has not been validated against the live
site, and no clean-Windows or final live-site validation is claimed.

#### P.23.2. Add authentication/session handling if required

Status: **Planned**.

Determine the real PRISMA session requirements and add safe authentication or
session handling only if live-site evidence requires it.

#### P.23.3. Harden live-page failure and recovery behavior

Status: **Planned**.

Handle live-page timeouts, unavailable pages, DOM changes, and manually closed
browsers with complete recovery and user-visible lifecycle behavior.

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

Status: **Planned**.

Release preparation is not complete. Finalize documentation, metadata, checks,
and the versioned archive.

## 5. Git workflow для кожного етапу

1. Оновити `main`.
2. Створити окрему feature branch.
3. Реалізувати один завершений етап через Codex.
4. Перевірити:
   - `git status --short`;
   - `git diff --stat`;
   - `git diff`.
5. Запустити тести.
6. Виконати GitHub Copilot review без редагування.
7. За потреби створити окремий Codex prompt для виправлень.
8. Повторно запустити тести.
9. Створити commit.
10. Push branch.
11. Створити Pull Request.
12. Merge у `main`.
13. Оновити локальний `main`.
14. Видалити локальну та remote feature branch.
15. Наступний етап почати в новому чаті.

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
- Copilot review не має невиправлених critical findings;
- зміни об’єднані з `main`;
- feature branch видалена.
