from __future__ import annotations

"""Pure column-width computation for the responsive Mapping table.

Isolated from Qt, from `mapping_presentation`, and from processing/business
logic so that resizing behavior can be reasoned about and tested on its own.
"""

MAPPING_COLUMN_MIN_WIDTHS: tuple[int, ...] = (
    100,  # Auction Date
    105,  # Exit Market
    105,  # Entry Market
    95,  # Capacity Type
    185,  # Network Point Name
    100,  # Product Type
    135,  # Flow Start
    135,  # Flow End
    115,  # Booked Capacity
    130,  # Flow Duration Hours
    105,  # Tariff Price
    110,  # Premium Price
)
"""Minimum readable pixel width for each of the 12 Mapping columns, in the
same order as `mapping_presentation.MAPPING_DISPLAY_FIELDS`."""

_NETWORK_POINT_NAME_COLUMN = 4
_EXPANSION_THRESHOLD_PX = 1385


def compute_mapping_column_widths(viewport_width: int) -> tuple[int, ...]:
    """Return pixel widths for the 12 Mapping columns for a given viewport width.

    At or below the expansion threshold, the minimum readable widths are
    returned unchanged, relying on horizontal scrolling for narrower
    viewports rather than compressing columns further. Above the threshold,
    the additional available width is allocated entirely to the Network
    Point Name column.
    """
    if viewport_width <= _EXPANSION_THRESHOLD_PX:
        return MAPPING_COLUMN_MIN_WIDTHS
    extra = viewport_width - _EXPANSION_THRESHOLD_PX
    widths = list(MAPPING_COLUMN_MIN_WIDTHS)
    widths[_NETWORK_POINT_NAME_COLUMN] += extra
    return tuple(widths)
