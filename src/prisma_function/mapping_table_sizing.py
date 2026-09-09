from __future__ import annotations

"""Pure column-width computation for the responsive Mapping table.

Isolated from Qt, from `mapping_presentation`, and from processing/business
logic so that resizing behavior can be reasoned about and tested on its own.
"""

MAPPING_COLUMN_COMFORTABLE_WIDTHS: tuple[int, ...] = (
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
"""Spacious pixel width for each of the 12 Mapping columns on a full desktop
window, in the same order as `mapping_presentation.MAPPING_DISPLAY_FIELDS`.
Reached once the viewport is wide enough to fit every column at these
widths; any further extra space is then allocated to Network Point Name."""

_COMPACT_SCALE = 0.662
"""Uniform shrink applied to the comfortable widths to derive the tablet
floor below, preserving the same relative priority between long-content and
short-value columns at every viewport width."""

_ABSOLUTE_MIN_COLUMN_WIDTH = 55

MAPPING_COLUMN_COMPACT_WIDTHS: tuple[int, ...] = tuple(
    max(_ABSOLUTE_MIN_COLUMN_WIDTH, round(width * _COMPACT_SCALE))
    for width in MAPPING_COLUMN_COMFORTABLE_WIDTHS
)
"""Narrowest readable pixel width for each column on a tablet-sized window.
The widths sum to comfortably less than the application's enforced minimum
window width, so all 12 columns stay visible -- without horizontal
scrolling -- even at the smallest allowed window size. Genuinely truncated
cell content still surfaces its full value through
`TruncationTooltipDelegate`."""

_NETWORK_POINT_NAME_COLUMN = 4
_COMPACT_VIEWPORT_PX = sum(MAPPING_COLUMN_COMPACT_WIDTHS)
_COMFORTABLE_VIEWPORT_PX = sum(MAPPING_COLUMN_COMFORTABLE_WIDTHS)


def compute_mapping_column_widths(viewport_width: int) -> tuple[int, ...]:
    """Return pixel widths for the 12 Mapping columns for a given viewport width.

    At or below `_COMPACT_VIEWPORT_PX`, every column is held at its
    narrowest readable (compact) width. Between the compact and comfortable
    totals -- the normal desktop/tablet resizing range -- each column is
    scaled linearly from its compact to its comfortable width, so long-
    content columns (led by Network Point Name) gain more pixels than
    compact short-value columns as the window widens. At or above the
    comfortable total, every column sits at its comfortable width and any
    further extra space is allocated entirely to Network Point Name.
    """
    if viewport_width <= _COMPACT_VIEWPORT_PX:
        return MAPPING_COLUMN_COMPACT_WIDTHS
    if viewport_width >= _COMFORTABLE_VIEWPORT_PX:
        widths = list(MAPPING_COLUMN_COMFORTABLE_WIDTHS)
        widths[_NETWORK_POINT_NAME_COLUMN] += viewport_width - _COMFORTABLE_VIEWPORT_PX
        return tuple(widths)
    span = _COMFORTABLE_VIEWPORT_PX - _COMPACT_VIEWPORT_PX
    progress = (viewport_width - _COMPACT_VIEWPORT_PX) / span
    return tuple(
        # Floored (never rounded up) so the interpolated total never exceeds
        # `viewport_width`, which would otherwise trigger an unwanted
        # horizontal scrollbar for a 1-2px rounding overshoot.
        compact + int((comfortable - compact) * progress)
        for compact, comfortable in zip(
            MAPPING_COLUMN_COMPACT_WIDTHS, MAPPING_COLUMN_COMFORTABLE_WIDTHS
        )
    )
