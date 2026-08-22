from prisma_function.mapping_table_sizing import (
    MAPPING_COLUMN_MIN_WIDTHS,
    compute_mapping_column_widths,
)


def test_narrow_viewport_keeps_minimum_widths_for_scrolling():
    assert compute_mapping_column_widths(1000) == MAPPING_COLUMN_MIN_WIDTHS


def test_exact_threshold_keeps_minimum_widths():
    assert compute_mapping_column_widths(1385) == MAPPING_COLUMN_MIN_WIDTHS


def test_wider_viewport_allocates_extra_space_to_network_point_name():
    widths = compute_mapping_column_widths(1585)

    assert len(widths) == len(MAPPING_COLUMN_MIN_WIDTHS)
    for column, (width, minimum) in enumerate(zip(widths, MAPPING_COLUMN_MIN_WIDTHS)):
        if column == 4:
            assert width == minimum + 200
        else:
            assert width == minimum


def test_all_columns_never_shrink_below_minimum():
    for viewport_width in (0, 500, 1385, 1386, 5000):
        widths = compute_mapping_column_widths(viewport_width)
        assert all(
            width >= minimum
            for width, minimum in zip(widths, MAPPING_COLUMN_MIN_WIDTHS)
        )
