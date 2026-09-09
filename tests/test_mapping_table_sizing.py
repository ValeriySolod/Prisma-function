from prisma_function.mapping_table_sizing import (
    MAPPING_COLUMN_COMFORTABLE_WIDTHS,
    MAPPING_COLUMN_COMPACT_WIDTHS,
    compute_mapping_column_widths,
)

_COMPACT_TOTAL = sum(MAPPING_COLUMN_COMPACT_WIDTHS)
_COMFORTABLE_TOTAL = sum(MAPPING_COLUMN_COMFORTABLE_WIDTHS)

# The application enforces a minimum window width of 1080px (see
# `PrismaMonitorApp.setMinimumSize`); after content/panel margins and the
# vertical scrollbar, the Mapping table viewport never drops below this
# floor. All 12 compact widths must fit under it so the table never needs
# horizontal scrolling, even at the smallest allowed window size.
_SMALLEST_REALISTIC_VIEWPORT_PX = 950


def test_compact_widths_fit_within_smallest_realistic_viewport():
    assert _COMPACT_TOTAL <= _SMALLEST_REALISTIC_VIEWPORT_PX


def test_narrow_viewport_uses_compact_widths():
    assert compute_mapping_column_widths(500) == MAPPING_COLUMN_COMPACT_WIDTHS


def test_viewport_at_compact_total_uses_compact_widths():
    assert compute_mapping_column_widths(_COMPACT_TOTAL) == MAPPING_COLUMN_COMPACT_WIDTHS


def test_viewport_at_comfortable_total_uses_comfortable_widths():
    assert compute_mapping_column_widths(_COMFORTABLE_TOTAL) == MAPPING_COLUMN_COMFORTABLE_WIDTHS


def test_wider_viewport_allocates_extra_space_to_network_point_name():
    widths = compute_mapping_column_widths(_COMFORTABLE_TOTAL + 200)

    assert len(widths) == len(MAPPING_COLUMN_COMFORTABLE_WIDTHS)
    for column, (width, comfortable) in enumerate(zip(widths, MAPPING_COLUMN_COMFORTABLE_WIDTHS)):
        if column == 4:
            assert width == comfortable + 200
        else:
            assert width == comfortable


def test_all_columns_never_shrink_below_compact_minimum():
    for viewport_width in (0, 500, _COMPACT_TOTAL, _COMPACT_TOTAL + 1, 5000):
        widths = compute_mapping_column_widths(viewport_width)
        assert all(
            width >= minimum
            for width, minimum in zip(widths, MAPPING_COLUMN_COMPACT_WIDTHS)
        )


def test_intermediate_viewport_scales_between_compact_and_comfortable():
    midpoint = (_COMPACT_TOTAL + _COMFORTABLE_TOTAL) // 2
    widths = compute_mapping_column_widths(midpoint)

    for width, compact, comfortable in zip(
        widths, MAPPING_COLUMN_COMPACT_WIDTHS, MAPPING_COLUMN_COMFORTABLE_WIDTHS
    ):
        assert compact <= width <= comfortable


def test_network_point_name_grows_faster_than_a_compact_column_between_tiers():
    lower = compute_mapping_column_widths(_COMPACT_TOTAL)
    upper = compute_mapping_column_widths(_COMFORTABLE_TOTAL)

    network_point_growth = upper[4] - lower[4]
    capacity_type_growth = upper[3] - lower[3]
    assert network_point_growth > capacity_type_growth


def test_resizing_is_deterministic_for_the_same_width():
    assert compute_mapping_column_widths(1200) == compute_mapping_column_widths(1200)
