from __future__ import annotations

from prisma_function.entsog_reference_data import (
    curated_fallback_index,
    operator_point_direction_index,
    operator_point_directions,
    operator_key_by_tso_eic,
    operators,
    prisma_tso_aliases,
)


def test_operator_point_directions_load_and_are_compact() -> None:
    records = operator_point_directions()
    assert len(records) > 500
    for record in records:
        assert record.point_eic
        assert record.tso_eic
        assert record.direction in ("entry", "exit")


def test_operator_point_direction_index_is_keyed_by_exact_triple() -> None:
    index = operator_point_direction_index()
    record = index[("21Z000000000163R", "21X-AT-B-A0A0A-K", "exit")]
    assert record.own_zone == "Austria"
    assert record.adjacent_zone == "Slovakia"


def test_operators_load_with_a_unique_tso_eic_reverse_index() -> None:
    reverse = operator_key_by_tso_eic()
    assert reverse["21X-AT-B-A0A0A-K"] == "AT-TSO-0001"
    assert len(operators()) == len(reverse)


def test_prisma_tso_aliases_cover_the_evidenced_names() -> None:
    aliases = prisma_tso_aliases()
    assert len(aliases) == 29
    assert aliases["SNAM RETE GAS S.P.A."] == ("IT-TSO-0001", "21X-IT-A-A0A0A-7")
    assert aliases["TAG GmbH"] == ("AT-TSO-0003", "21X-AT-C-A0A0A-B")


def test_curated_fallback_index_has_no_duplicate_keys_across_routes() -> None:
    index = curated_fallback_index()
    assert ("21Z000000000053Y", "DE-TSO-0005", "exit") in index
    entry = index[("21Z000000000053Y", "DE-TSO-0005", "exit")]
    assert entry.exit_market == "DE THE BZ"
    assert entry.entry_market == "Norway"
