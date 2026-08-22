from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
    Qt,
)
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QTableView, QToolTip

from prisma_function.mapping_presentation import MAPPING_DISPLAY_FIELDS, MappingDisplayRow
from prisma_function.mapping_table_sizing import compute_mapping_column_widths


APP_STYLE = """
QMainWindow, QWidget#workspace { background: #f4f7fb; color: #182230; font-family: "Segoe UI"; font-size: 10pt; }
QWidget#contentArea { background: #f4f7fb; color: #182230; }
QWidget#contentArea QLabel { color: #243247; }
QLabel#contentSectionLabel { color: #314157; font-weight: 600; }
QFrame#toolbar { background: #172235; border: none; }
QFrame#toolbar QLabel { color: #d8e1ee; }
QLabel#brand { color: white; font-size: 16pt; font-weight: 700; }
QLabel#subtitle { color: #9fb0c6; font-size: 9pt; }
QLabel#filename { color: white; font-weight: 600; }
QPushButton { min-height: 34px; padding: 3px 12px; border-radius: 7px; border: 1px solid #ccd6e2; background: white; color: #243247; }
QPushButton:hover { border-color: #1686a5; background: #f1fbfd; }
QPushButton:focus { border: 2px solid #1593b5; }
QPushButton:disabled { color: #8e9aaa; background: #e8edf3; border-color: #e0e6ed; }
QPushButton[primary="true"] { color: white; background: #087f9d; border-color: #087f9d; font-weight: 600; }
QFrame#card, QFrame#panel { background: white; border: 1px solid #e1e7ef; border-radius: 10px; }
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
QFrame#statusBar { background: white; border-top: 1px solid #e1e7ef; }
QLabel#statusCounter { color: #56657a; font-weight: 600; }
QLabel#statusBadge { border-radius: 10px; padding: 2px 10px; font-weight: 700; font-size: 8pt; }
QLabel#statusBadge[state="ready"] { background: #eef2f7; color: #56657a; }
QLabel#statusBadge[state="processing"] { background: #e6f4f7; color: #087f9d; }
QLabel#statusBadge[state="success"] { background: #e6f7ee; color: #1f9d55; }
QLabel#statusBadge[state="warning"] { background: #fff6e0; color: #b7791f; }
QLabel#statusBadge[state="error"] { background: #fdecec; color: #c53030; }
QPushButton#detailsButton { min-height: 26px; padding: 2px 12px; font-size: 9pt; }
QLabel#primaryStatus { color: #314157; font-weight: 600; }
"""


class MappingTableModel(QAbstractTableModel):
    """Qt presentation of the authoritative 12-column Mapping rows."""

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
            row.auction_date, row.exit_market, row.entry_market, row.capacity_type,
            row.network_point_name, row.product_type, row.flow_start, row.flow_end,
            row.booked_capacity, row.flow_duration_hours, row.tariff_price,
            row.premium_price,
        )
        return values[index.column()]

    def set_rows(self, rows: tuple[MappingDisplayRow, ...]) -> None:
        """Replace the displayed rows wholesale so no stale row is ever retained."""
        self.beginResetModel()
        self.rows = tuple(rows)
        self.endResetModel()


class TruncationTooltipDelegate(QStyledItemDelegate):
    """Shows the full cell value in a tooltip only when its text is elided."""

    def helpEvent(self, event, view, option, index) -> bool:
        if event is None or event.type() != QEvent.ToolTip:
            return super().helpEvent(event, view, option, index)
        text = index.data(Qt.DisplayRole)
        if not text:
            QToolTip.hideText()
            return True
        cell_option = QStyleOptionViewItem(option)
        self.initStyleOption(cell_option, index)
        metrics = QFontMetrics(cell_option.font)
        cell_padding_px = 8
        available_width = cell_option.rect.width() - cell_padding_px
        if metrics.horizontalAdvance(str(text)) > available_width:
            QToolTip.showText(event.globalPos(), str(text), view)
        else:
            QToolTip.hideText()
        return True


class ResponsiveMappingTableView(QTableView):
    """Mapping table view that keeps the 12 columns readable at any width.

    Column widths are recomputed from `mapping_table_sizing` whenever the
    viewport is resized, while interactive manual resizing by the user
    remains available in between resizes.
    """

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.apply_responsive_column_widths()

    def apply_responsive_column_widths(self) -> None:
        widths = compute_mapping_column_widths(self.viewport().width())
        for column, width in enumerate(widths):
            if self.columnWidth(column) != width:
                self.setColumnWidth(column, width)
