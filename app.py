from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from auction_csv import AuctionCsvRecord, CsvValidationError, load_auction_csv
from browser import BrowserController
from monitoring import MonitoringEngine
from processor import process_csv
from scheduler import MonitoringScheduler
from storage import AuctionStorage

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
RESULT_DIR = DATA_DIR / "result"
DATABASE_PATH = DATA_DIR / "prisma_monitor.db"
DEFAULT_MONITORING_INTERVAL_SECONDS = 30.0


class PrismaMonitorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PRISMA Monitor")
        self.geometry("940x540")
        self.resizable(False, False)

        DATA_DIR.mkdir(exist_ok=True)
        RESULT_DIR.mkdir(parents=True, exist_ok=True)

        self.browser = BrowserController()
        self._is_closing = False
        self._active_browser_launch: int | None = None
        self._auction_records: list[AuctionCsvRecord] = []
        self._monitoring_thread: threading.Thread | None = None
        self._monitoring_stop_event: threading.Event | None = None
        self.csv_path = tk.StringVar()
        self.browser_name = tk.StringVar(value="Chrome")
        self.status = tk.StringVar(value="Ready")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="PRISMA Monitor", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 18)
        )

        ttk.Label(frame, text="Browser:").grid(row=1, column=0, sticky="w")
        ttk.Combobox(
            frame,
            textvariable=self.browser_name,
            values=("Chrome", "Edge"),
            state="readonly",
            width=18,
        ).grid(row=1, column=1, sticky="w")

        self.open_button = ttk.Button(
            frame, text="Open PRISMA", command=self.open_prisma
        )
        self.open_button.grid(row=1, column=2, padx=(12, 0))

        ttk.Label(frame, text="CSV file:").grid(row=2, column=0, sticky="w", pady=(16, 0))
        ttk.Entry(frame, textvariable=self.csv_path, width=52).grid(
            row=2, column=1, sticky="we", pady=(16, 0)
        )
        ttk.Button(frame, text="Select", command=self.select_csv).grid(
            row=2, column=2, padx=(12, 0), pady=(16, 0)
        )

        ttk.Separator(frame).grid(row=3, column=0, columnspan=3, sticky="ew", pady=18)

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=4, column=0, columnspan=3, sticky="nsew")
        columns = (
            "auction_id", "lot_number", "item_name", "expected_status",
            "last_known_status", "check_interval_seconds", "enabled",
        )
        self.csv_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        widths = (105, 80, 220, 115, 120, 145, 65)
        for column, width in zip(columns, widths, strict=True):
            self.csv_table.heading(column, text=column)
            self.csv_table.column(
                column, width=width, minwidth=55, stretch=column == "item_name"
            )
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.csv_table.yview)
        self.csv_table.configure(yscrollcommand=scrollbar.set)
        self.csv_table.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        controls = ttk.Frame(frame)
        controls.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(18, 0))
        self.process_button = ttk.Button(
            controls, text="Process CSV", command=self.start_processing
        )
        self.process_button.grid(row=0, column=0, padx=(0, 8))

        self.open_result_button = ttk.Button(
            controls, text="Open Result", command=self.open_result
        )
        self.open_result_button.grid(row=0, column=1, padx=(0, 8))
        self.start_monitoring_button = ttk.Button(
            controls, text="Start Monitoring", command=self.start_monitoring
        )
        self.start_monitoring_button.grid(row=0, column=2, padx=(0, 8))
        self.stop_monitoring_button = ttk.Button(
            controls, text="Stop Monitoring", command=self.stop_monitoring, state="disabled"
        )
        self.stop_monitoring_button.grid(row=0, column=3, padx=(0, 8))
        self.stop_browser_button = ttk.Button(
            controls, text="Stop Browser", command=self.stop_work
        )
        self.stop_browser_button.grid(row=0, column=4)

        ttk.Label(frame, text="Status:").grid(row=6, column=0, sticky="nw", pady=(22, 0))
        ttk.Label(
            frame,
            textvariable=self.status,
            wraplength=455,
            justify="left",
        ).grid(row=6, column=1, columnspan=2, sticky="w", pady=(22, 0))

        ttk.Button(frame, text="Close Application", command=self.close_app).grid(
            row=7, column=0, columnspan=3, pady=(22, 0)
        )

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)
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

        self._display_csv_records(records)
        self._auction_records = records
        self.csv_path.set(selected)
        self.status.set(f"Loaded {Path(selected).name}: {len(records)} records")

    def _display_csv_records(self, records: list[AuctionCsvRecord]) -> None:
        self.csv_table.delete(*self.csv_table.get_children())
        for record in records:
            self.csv_table.insert(
                "", "end", values=(
                    record.auction_id,
                    record.lot_number,
                    record.item_name,
                    record.expected_status,
                    record.last_known_status,
                    record.check_interval_seconds,
                    "Yes" if record.enabled else "No",
                )
            )

    def open_prisma(self) -> None:
        browser_name = self.browser_name.get()
        try:
            self.open_button.config(state="disabled")
            self.status.set(f"Starting PRISMA in {browser_name}...")
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
                self._browser_start_failed(result.error or "Unknown error")
            return

        self.after(50, self._poll_browser_launch)

    def _browser_started(self, browser_name: str) -> None:
        if self._is_closing:
            return
        self.open_button.config(state="normal")
        self.status.set(f"PRISMA opened in {browser_name}")

    def _browser_start_failed(self, exc: Exception | str) -> None:
        if self._is_closing:
            return
        self._active_browser_launch = None
        self.open_button.config(state="normal")
        reason = str(exc).strip() or exc.__class__.__name__
        messagebox.showerror(
            "Browser Error",
            f"Failed to open the browser. Reason: {reason}",
        )
        self.status.set("Failed to open the browser")

    def start_processing(self) -> None:
        source = Path(self.csv_path.get())
        if not source.is_file():
            messagebox.showwarning("CSV Not Selected", "Select a CSV file first.")
            return

        self.process_button.config(state="disabled")
        self.status.set("Processing CSV...")
        threading.Thread(target=self._process_worker, args=(source,), daemon=True).start()

    def _process_worker(self, source: Path) -> None:
        try:
            rows = process_csv(source)
            storage = AuctionStorage(DATABASE_PATH)
            stats = storage.upsert(rows)
            result_path = storage.export_excel(RESULT_DIR / "prisma_auctions.xlsx")

            text = (
                f"Done. Processed: {stats['processed']}; "
                f"inserted: {stats['inserted']}; updated: {stats['updated']}; "
                f"unchanged: {stats['unchanged']}. "
                f"Result: {result_path.name}"
            )
            self.after(0, lambda: self.status.set(text))
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Processing Error", str(exc)))
            self.after(0, lambda: self.status.set("Processing failed"))
        finally:
            self.after(0, lambda: self.process_button.config(state="normal"))

    def open_result(self) -> None:
        result = RESULT_DIR / "prisma_auctions.xlsx"
        if not result.exists():
            messagebox.showinfo("Result Not Found", "Process a CSV file first.")
            return
        os.startfile(result)  # Windows only

    def create_monitoring_engine(self) -> MonitoringEngine:
        """Create the engine; override this factory when supplying a live checker."""
        return MonitoringEngine(lambda record: record.last_known_status)

    def create_monitoring_scheduler(
        self, records: list[AuctionCsvRecord]
    ) -> MonitoringScheduler:
        return MonitoringScheduler(self.create_monitoring_engine(), lambda: records)

    def start_monitoring(self) -> None:
        if self._monitoring_thread is not None:
            return

        records = [record for record in self._auction_records if record.enabled]
        if not records:
            self._set_monitoring_idle()
            messagebox.showerror(
                "Monitoring Error", "No usable auction records are available."
            )
            return

        stop_event = threading.Event()
        scheduler = self.create_monitoring_scheduler(records)
        thread = threading.Thread(
            target=self._monitoring_worker,
            args=(scheduler, stop_event),
            daemon=True,
            name="prisma-monitoring",
        )
        self._monitoring_stop_event = stop_event
        self._monitoring_thread = thread
        self.start_monitoring_button.config(state="disabled")
        self.stop_monitoring_button.config(state="normal")
        self.status.set("Monitoring started")
        try:
            thread.start()
        except Exception as exc:
            self._set_monitoring_idle()
            reason = str(exc).strip() or exc.__class__.__name__
            self.status.set("Failed to start monitoring")
            messagebox.showerror(
                "Monitoring Error", f"Failed to start monitoring: {reason}"
            )

    def stop_monitoring(self) -> None:
        if self._monitoring_stop_event is not None:
            self._monitoring_stop_event.set()

    def _monitoring_worker(
        self, scheduler: MonitoringScheduler, stop_event: threading.Event
    ) -> None:
        error: Exception | None = None
        try:
            scheduler.run_forever(stop_event, DEFAULT_MONITORING_INTERVAL_SECONDS)
        except Exception as exc:
            error = exc
        self._schedule_monitoring_finished(error)

    def _schedule_monitoring_finished(self, error: Exception | None) -> None:
        if self._is_closing:
            return
        try:
            self.after(0, lambda: self._monitoring_finished(error))
        except (RuntimeError, tk.TclError):
            return

    def _monitoring_finished(self, error: Exception | None = None) -> None:
        if self._is_closing:
            return
        self._set_monitoring_idle()
        if error is not None:
            reason = str(error).strip() or error.__class__.__name__
            self.status.set("Monitoring failed")
            messagebox.showerror(
                "Monitoring Error", f"Monitoring stopped because of an error: {reason}"
            )
        else:
            self.status.set("Monitoring stopped")

    def _set_monitoring_idle(self) -> None:
        self._monitoring_thread = None
        self._monitoring_stop_event = None
        self.start_monitoring_button.config(state="normal")
        self.stop_monitoring_button.config(state="disabled")

    def stop_work(self) -> None:
        self.browser.stop()
        self._active_browser_launch = None
        self.open_button.config(state="normal")
        self.status.set("Browser closed. Current CSV processing will finish safely.")

    def close_app(self) -> None:
        self._is_closing = True
        self._active_browser_launch = None
        if self._monitoring_stop_event is not None:
            self._monitoring_stop_event.set()
        self.browser.stop()
        self.destroy()


if __name__ == "__main__":
    PrismaMonitorApp().mainloop()
