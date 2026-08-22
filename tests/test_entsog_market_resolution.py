from __future__ import annotations

from prisma_function.entsog_market_resolution import (
    EntsogMarketPair,
    resolve_entsog_market_pair,
)


def test_border_transition_point_resolves_both_sides_from_direct_entsog_join() -> None:
    # Baumgarten (AT/SK), Gas Connect Austria's own operator-point-direction
    # record: own balancing zone Austria, adjacent Slovakia. No curated
    # fallback entry exists for this exact (point_eic, operator_key,
    # direction) key -- it resolves purely from the live ENTSOG join.
    result = resolve_entsog_market_pair(
        point_eic="21Z000000000163R",
        tso_eic="21X-AT-B-A0A0A-K",
        tso_name="GAS CONNECT AUSTRIA GmbH",
        direction="exit",
        point_type="BORDER_TRANSITION_POINT",
    )
    assert result == EntsogMarketPair(exit_market="Austria", entry_market="Slovakia")


def test_border_transition_point_uses_alias_table_when_tso_eic_is_blank() -> None:
    # Same physical point, Entry direction, PRISMA-typical blank TSO EIC on
    # the Entry side -- resolved via the exact PRISMA-TSO-name alias table.
    result = resolve_entsog_market_pair(
        point_eic="21Z000000000163R",
        tso_eic="",
        tso_name="GAS CONNECT AUSTRIA GmbH",
        direction="entry",
        point_type="BORDER_TRANSITION_POINT",
    )
    assert result == EntsogMarketPair(exit_market="Slovakia", entry_market="Austria")


def test_reservoir_populates_only_its_own_side() -> None:
    # Loenhout Storage (Fluxys Belgium, BE-TSO-0001): own zone BeLux. Per the
    # approved RESERVOIR rule, the opposite side stays blank even though it
    # is unused here regardless of ENTSOG data availability.
    result = resolve_entsog_market_pair(
        point_eic="21Z000000000102A",
        tso_eic="",
        tso_name="Fluxys Belgium NV/SA",
        direction="entry",
        point_type="RESERVOIR",
    )
    assert result == EntsogMarketPair(exit_market=None, entry_market="BeLux")


def test_reservoir_exit_direction_populates_only_exit_side() -> None:
    result = resolve_entsog_market_pair(
        point_eic="21Z000000000102A",
        tso_eic="21X-BE-A-A0A0A-Y",
        tso_name="Fluxys Belgium NV/SA",
        direction="exit",
        point_type="RESERVOIR",
    )
    assert result == EntsogMarketPair(exit_market="BeLux", entry_market=None)


def test_curated_fallback_overrides_incomplete_entsog_data() -> None:
    # Dornum: ENTSOG's own operator-point-direction record has own_zone
    # "DE THE BZ" but a blank adjacentZones (Norway is outside ENTSOG's own
    # balancing-zone model). The curated fallback route fills both sides.
    result = resolve_entsog_market_pair(
        point_eic="21Z000000000053Y",
        tso_eic="21X-DE-D-A0A0A-K",
        tso_name="Gasunie Deutschland Transport Services GmbH",
        direction="exit",
        point_type="BORDER_TRANSITION_POINT",
    )
    assert result == EntsogMarketPair(exit_market="DE THE BZ", entry_market="Norway")


def test_curated_fallback_resolves_a_point_entsog_has_no_record_for() -> None:
    # Ellund: PRISMA's point EIC for Energinet's side has no ENTSOG
    # operator-point-direction record at all; only the curated fallback can
    # resolve it.
    result = resolve_entsog_market_pair(
        point_eic="21Z0000000000260",
        tso_eic="10X1001A1001A248",
        tso_name="Energinet",
        direction="exit",
        point_type="BORDER_TRANSITION_POINT",
    )
    assert result == EntsogMarketPair(
        exit_market="Joint Bal Zone DK/SE", entry_market="DE THE BZ"
    )


def test_unsupported_point_type_never_resolves() -> None:
    assert (
        resolve_entsog_market_pair(
            point_eic="21Z000000000163R",
            tso_eic="21X-AT-B-A0A0A-K",
            tso_name="GAS CONNECT AUSTRIA GmbH",
            direction="exit",
            point_type="OTHER_NETWORK_POINT",
        )
        is None
    )


def test_blank_point_eic_never_resolves() -> None:
    assert (
        resolve_entsog_market_pair(
            point_eic="",
            tso_eic="21X-AT-B-A0A0A-K",
            tso_name="GAS CONNECT AUSTRIA GmbH",
            direction="exit",
            point_type="BORDER_TRANSITION_POINT",
        )
        is None
    )


def test_unresolvable_operator_never_resolves() -> None:
    assert (
        resolve_entsog_market_pair(
            point_eic="21Z000000000163R",
            tso_eic="",
            tso_name="An Unknown TSO Never Evidenced Anywhere",
            direction="exit",
            point_type="BORDER_TRANSITION_POINT",
        )
        is None
    )


def test_bacton_entry_resolves_to_ttf_ztp_regardless_of_shared_eic() -> None:
    # Bacton's own point EIC ("48YBI-EC-------0") and operator (National Gas
    # Transmission PLC / UK-TSO-0001) also key the unrelated Moffat curated
    # fallback entry for the same "entry" direction; only the exact Network
    # Point Name distinguishes the two. The explicit exception must win
    # ahead of that (otherwise colliding) curated-fallback lookup.
    result = resolve_entsog_market_pair(
        point_eic="48YBI-EC-------0",
        tso_eic="",
        tso_name="National Gas Transmission PLC",
        direction="entry",
        point_type="BORDER_TRANSITION_POINT",
        point_name="BactonUKEn (48YBI-EC-------0)",
    )
    assert result == EntsogMarketPair(exit_market=None, entry_market="TTF/ZTP")


def test_moffat_entry_is_unaffected_by_the_bacton_exception() -> None:
    # Same point EIC/operator/direction as Bacton's exception above, but a
    # different Network Point Name -- the pre-existing Moffat curated
    # fallback resolution must be completely unchanged.
    result = resolve_entsog_market_pair(
        point_eic="48YBI-EC-------0",
        tso_eic="",
        tso_name="National Gas Transmission PLC",
        direction="entry",
        point_type="BORDER_TRANSITION_POINT",
        point_name="MoffatUKEn (48YBI-EC-------0)",
    )
    assert result == EntsogMarketPair(exit_market="Great Britain", entry_market="Ireland")


def test_bundle_direction_never_resolves() -> None:
    assert (
        resolve_entsog_market_pair(
            point_eic="21Z000000000163R",
            tso_eic="21X-AT-B-A0A0A-K",
            tso_name="GAS CONNECT AUSTRIA GmbH",
            direction="bundle",
            point_type="BORDER_TRANSITION_POINT",
        )
        is None
    )
