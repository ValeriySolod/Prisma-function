from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    Qt,
)

from mapping_presentation import MAPPING_DISPLAY_FIELDS, MappingDisplayRow


APP_STYLE = """
QMainWindow, QWidget#workspace { background: #f4f7fb; color: #182230; font-family: "Segoe UI"; font-size: 10pt; }
QWidget#contentArea { background: #f4f7fb; color: #182230; }
QWidget#contentArea QLabel { color: #243247; }
QLabel#contentSectionLabel { color: #314157; font-weight: 600; }
QLabel#contentSubtitle { color: #66758a; }
QFrame#sidebar { background: #172235; border: none; }
QFrame#sidebar QLabel { color: #d8e1ee; }
QLabel#brand { color: white; font-size: 20pt; font-weight: 700; }
QLabel#subtitle { color: #9fb0c6; font-size: 9pt; }
QLabel#section { color: #7f93ad; font-size: 8pt; font-weight: 700; }
QLabel#filename { color: white; font-weight: 600; }
QPushButton { min-height: 34px; padding: 3px 12px; border-radius: 7px; border: 1px solid #ccd6e2; background: white; color: #243247; }
QPushButton:hover { border-color: #1686a5; background: #f1fbfd; }
QPushButton:focus { border: 2px solid #1593b5; }
QPushButton:disabled { color: #8e9aaa; background: #e8edf3; border-color: #e0e6ed; }
QPushButton[primary="true"] { color: white; background: #087f9d; border-color: #087f9d; font-weight: 600; }
QPushButton[sidebar="true"] { color: #e9f0f8; background: #223149; border-color: #344861; text-align: left; }
QPushButton[sidebar="true"]:hover { background: #2a405c; border-color: #3c5876; }
QPushButton[sidebar="true"]:disabled { color: #75869c; background: #1c293d; border-color: #29394f; }
QFrame#card, QFrame#panel { background: white; border: 1px solid #e1e7ef; border-radius: 10px; }
QLabel#browserBadge { border-radius: 10px; padding: 4px 10px; font-weight: 600; }
QLabel[state="idle"] { background: #e8edf3; color: #526173; }
QLabel[state="working"] { background: #fff1cc; color: #835b00; }
QLabel[state="ready"] { background: #d9f5e8; color: #176846; }
QLabel[state="error"] { background: #fde2e2; color: #9a2d2d; }
QLineEdit, QComboBox { min-height: 32px; border: 1px solid #ccd6e2; border-radius: 7px; padding: 2px 9px; background: white; color: #243247; selection-background-color: #087f9d; selection-color: white; }
QLineEdit { placeholder-text-color: #718096; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #1593b5; }
QLineEdit:disabled, QComboBox:disabled { background: #e8edf3; color: #758397; border-color: #d8e0e9; }
QComboBox { padding-right: 34px; }
QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border-left: 1px solid #ccd6e2; background: #f2f5f9; border-top-right-radius: 6px; border-bottom-right-radius: 6px; }
QComboBox::drop-down:hover { background: #e6f4f7; }
QComboBox::drop-down:disabled { background: #e1e7ee; border-left-color: #d3dbe5; }
QComboBox QAbstractItemView { background: white; color: #243247; border: 1px solid #ccd6e2; selection-background-color: #dff3f8; selection-color: #172235; outline: none; }
QWidget#contentArea QTableView { border: none; background: white; color: #243247; alternate-background-color: #f8fafc; gridline-color: transparent; selection-background-color: #dff3f8; selection-color: #172235; }
QWidget#contentArea QTableView::item { color: #243247; }
QWidget#contentArea QTableView::item:hover { background: #f0f7fa; color: #172235; }
QWidget#contentArea QTableView::item:selected { background: #dff3f8; color: #172235; }
QWidget#contentArea QTableView::item:selected:hover { background: #d4edf3; color: #172235; }
QWidget#contentArea QTableView:focus { color: #243247; }
QWidget#contentArea QTableView:disabled { background: #f1f4f7; color: #758397; }
QWidget#contentArea QTableView::item:disabled { color: #758397; }
QHeaderView::section { background: #f2f5f9; color: #56657a; border: none; border-bottom: 1px solid #dce4ed; padding: 9px; font-weight: 600; }
QListWidget { border: none; background: white; color: #243247; selection-background-color: #dff3f8; selection-color: #172235; outline: none; }
QListWidget::item { color: #243247; padding: 7px 4px; border-bottom: 1px solid #edf1f5; }
QLabel#primaryStatus { color: #314157; font-weight: 600; }
"""


class MappingTableModel(QAbstractTableModel):
    """P.36.8 Qt presentation of already-resolved mapping evidence.

    Consumes only `mapping_presentation.MappingDisplayRow` values built from
    one already-completed P.36.15 import result; this model performs no
    parsing, resolution, or business logic of its own, and never adds,
    removes, renames, or reorders the five presentation fields.
    """

    HEADERS = MAPPING_DISPLAY_FIELDS

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.rows: tuple[MappingDisplayRow, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role not in (Qt.DisplayRole, Qt.AccessibleTextRole):
            return None
        row = self.rows[index.row()]
        values = (
            row.exit_market, row.entry_market, row.network_point_name,
            row.tso_name_exit, row.tso_name_entry,
        )
        return values[index.column()]

    def set_rows(self, rows: tuple[MappingDisplayRow, ...]) -> None:
        """Replace the displayed rows wholesale so no stale row is ever retained."""
        self.beginResetModel()
        self.rows = tuple(rows)
        self.endResetModel()
