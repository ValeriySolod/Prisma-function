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

### P.3. Вибір браузера

Додати вибір браузера:

- `Google Chrome`;
- `Microsoft Edge`.

Програма повинна:

- перевіряти наявність браузера;
- запускати вибраний браузер;
- повідомляти про помилку англійською;
- коректно завершувати browser session;
- не залишати фонові процеси після зупинки.

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

- Chrome launch;
- Edge launch;
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
