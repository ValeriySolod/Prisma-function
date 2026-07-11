from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from auction_csv import CsvValidationError, load_auction_csv
from browser import BrowserController
from processor import process_csv
from storage import AuctionStorage

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
RESULT_DIR = DATA_DIR / "result"
DATABASE_PATH = DATA_DIR / "prisma_monitor.db"


class PrismaMonitorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PRISMA Monitor")
        self.geometry("620x330")
        self.resizable(False, False)

        DATA_DIR.mkdir(exist_ok=True)
        RESULT_DIR.mkdir(parents=True, exist_ok=True)

        self.browser = BrowserController()
        self._is_closing = False
        self._active_browser_launch: int | None = None
        self.csv_path = tk.StringVar()
        self.browser_name = tk.StringVar(value="Chrome")
        self.status = tk.StringVar(value="Готово до роботи")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="PRISMA Monitor", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 18)
        )

        ttk.Label(frame, text="Браузер:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            frame,
            textvariable=self.browser_name,
            values=("Chrome", "Edge"),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w")

        self.open_button = ttk.Button(
            frame, text="Відкрити PRISMA", command=self.open_prisma
        )
        self.open_button.grid(row=1, column=2, padx=(12, 0))

        ttk.Label(frame, text="CSV-файл:").grid(row=2, column=0, sticky="w", pady=(16, 0))
        ttk.Entry(frame, textvariable=self.csv_path, width=52).grid(
            row=2, column=1, sticky="we", pady=(16, 0)
        )
        ttk.Button(frame, text="Вибрати", command=self.select_csv).grid(
            row=2, column=2, padx=(12, 0), pady=(16, 0)
        )

        ttk.Separator(frame).grid(row=3, column=0, columnspan=3, sticky="ew", pady=18)

        self.process_button = ttk.Button(frame, text="Обробити CSV", command=self.start_processing)
        self.process_button.grid(row=4, column=0, sticky="w")

        ttk.Button(frame, text="Відкрити результат", command=self.open_result).grid(
            row=4, column=1, sticky="w", padx=(8, 0)
        )
        ttk.Button(frame, text="Зупинити", command=self.stop_work).grid(
            row=4, column=2, sticky="e"
        )

        ttk.Label(frame, text="Статус:").grid(row=5, column=0, sticky="nw", pady=(22, 0))
        ttk.Label(
            frame,
            textvariable=self.status,
            wraplength=455,
            justify="left",
        ).grid(row=5, column=1, columnspan=2, sticky="w", pady=(22, 0))

        ttk.Button(frame, text="Закрити програму", command=self.close_app).grid(
            row=6, column=0, columnspan=3, pady=(28, 0)
        )

        frame.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

    def select_csv(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select Auction_overview.csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not selected:
            return

        try:
            records = load_auction_csv(selected)
        except CsvValidationError as exc:
            messagebox.showerror("CSV Error", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("CSV Error", f"Failed to load CSV: {exc}")
            return

        self.csv_path.set(selected)
        self.status.set(f"Loaded {Path(selected).name}: {len(records)} records")

    def open_prisma(self) -> None:
        browser_name = self.browser_name.get()
        try:
            self.open_button.config(state="disabled")
            self.status.set(f"Запуск PRISMA у {browser_name}...")
            self._active_browser_launch = self.browser.open(browser_name)
            self.after(50, self._poll_browser_launch)
        except Exception as exc:
            self._browser_start_failed(exc)

    def _poll_browser_launch(self) -> None:
        if self._is_closing:
            return

        generation = self._active_browser_launch
        if generation is None:
            return

        for result in self.browser.get_launch_results():
            if result.generation != generation:
                continue
            self._active_browser_launch = None
            if result.success:
                self._browser_started(self.browser_name.get())
            else:
                self._browser_start_failed(result.error or "Невідома помилка")
            return

        self.after(50, self._poll_browser_launch)

    def _browser_started(self, browser_name: str) -> None:
        if self._is_closing:
            return
        self.open_button.config(state="normal")
        self.status.set(f"PRISMA відкрито у {browser_name}")

    def _browser_start_failed(self, exc: Exception | str) -> None:
        if self._is_closing:
            return
        self._active_browser_launch = None
        self.open_button.config(state="normal")
        reason = str(exc).strip() or exc.__class__.__name__
        messagebox.showerror(
            "Помилка браузера",
            f"Не вдалося відкрити браузер. Причина: {reason}",
        )
        self.status.set("Не вдалося відкрити браузер")

    def start_processing(self) -> None:
        source = Path(self.csv_path.get())
        if not source.is_file():
            messagebox.showwarning("CSV не вибрано", "Спочатку виберіть CSV-файл.")
            return

        self.process_button.config(state="disabled")
        self.status.set("Обробка CSV...")
        threading.Thread(target=self._process_worker, args=(source,), daemon=True).start()

    def _process_worker(self, source: Path) -> None:
        try:
            rows = process_csv(source)
            storage = AuctionStorage(DATABASE_PATH)
            stats = storage.upsert(rows)
            result_path = storage.export_excel(RESULT_DIR / "prisma_auctions.xlsx")

            text = (
                f"Готово. Оброблено: {stats['processed']}; "
                f"додано: {stats['inserted']}; оновлено: {stats['updated']}; "
                f"без змін: {stats['unchanged']}. "
                f"Результат: {result_path.name}"
            )
            self.after(0, lambda: self.status.set(text))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Помилка обробки", str(exc)))
            self.after(0, lambda: self.status.set("Обробка завершилася з помилкою"))
        finally:
            self.after(0, lambda: self.process_button.config(state="normal"))

    def open_result(self) -> None:
        result = RESULT_DIR / "prisma_auctions.xlsx"
        if not result.exists():
            messagebox.showinfo("Результат відсутній", "Спочатку обробіть CSV-файл.")
            return
        os.startfile(result)  # Windows only

    def stop_work(self) -> None:
        self.browser.stop()
        self._active_browser_launch = None
        self.open_button.config(state="normal")
        self.status.set("Браузер закрито. Поточна обробка CSV завершиться безпечно.")

    def close_app(self) -> None:
        self._is_closing = True
        self._active_browser_launch = None
        self.browser.stop()
        self.destroy()


if __name__ == "__main__":
    PrismaMonitorApp().mainloop()
