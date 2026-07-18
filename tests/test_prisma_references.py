from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from csv_contracts import PRISMA_EXPORT_COLUMNS
from prisma_references import (
    DEFAULT_PRISMA_REFERENCES,
    PrismaReference,
    PrismaReferenceCatalog,
    ReferenceAlias,
    ReferenceClassification,
    ReferenceSide,
)
from processor import (
    PrismaEnrichmentReasonCode,
    PrismaImportStatus,
    import_prisma_export,
)


BASE = {
    "Auction ID": "000123456789012345",
    "Start of Auction": "01.01.2025 09:00",
    "Marketed Capacity": "1000",
    "Unit Marketed Capacity": "kWh/h",
    "Product Runtime Start": "02.01.2025 00:00",
    "Product Runtime End": "03.01.2025 00:00",
    "Direction": "Entry",
    "Network Point Name Entry": "VGS Storage Hub (4290)",
    "Network Point ID Entry": "ENTRY-ID",
}


def write_csv(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "references.csv"
    pd.DataFrame(rows).reindex(columns=PRISMA_EXPORT_COLUMNS).fillna("").to_csv(
        path, sep=";", encoding="cp1252", index=False
    )
    return path


def test_known_entry_storage_enrichment_and_source_metadata(tmp_path: Path) -> None:
    result = import_prisma_export(write_csv(tmp_path, [BASE]))
    assert result.rows[0]["entry_market"] == "VGS Storage Hub"
    assert result.rows[0]["exit_market"] == ""
    assert result.rows[0]["direction"] == "entry"
    record = result.enriched_records[0]
    assert record.source_row_number == 2
    assert record.raw_row["Network Point Name Entry"] == "VGS Storage Hub (4290)"
    assert record.entry_reference is not None
    assert (
        record.entry_reference.canonical_name,
        record.entry_reference.classification,
        record.entry_reference.side,
    ) == (
        "VGS Storage Hub",
        ReferenceClassification.STORAGE,
        ReferenceSide.ENTRY,
    )
    assert record.exit_reference is None


def test_all_authoritative_reservoir_aliases_are_side_specific_storage() -> None:
    overview = pd.read_csv(
        Path(__file__).parents[1] / "Auction_overview.csv",
        sep=";",
        encoding="cp1252",
        dtype=str,
    ).fillna("")
    for side in ReferenceSide:
        source_side = side.value.title()
        name_column = f"Network Point Name {source_side}"
        type_column = f"Network Point Type {source_side}"
        reservoir_names = set(
            overview.loc[overview[type_column] == "RESERVOIR", name_column]
        ) - {""}
        assert len(reservoir_names) == 37
        for source_value in reservoir_names:
            reference = DEFAULT_PRISMA_REFERENCES.lookup(source_value, side)
            assert reference is not None, (side, source_value)
            assert reference.classification is ReferenceClassification.STORAGE


def test_storage_catalog_contains_only_authoritative_side_aliases() -> None:
    overview = pd.read_csv(
        Path(__file__).parents[1] / "Auction_overview.csv",
        sep=";",
        encoding="cp1252",
        dtype=str,
    ).fillna("")
    for side in ReferenceSide:
        source_side = side.value.title()
        name_column = f"Network Point Name {source_side}"
        type_column = f"Network Point Type {source_side}"
        expected = set(
            overview.loc[overview[type_column] == "RESERVOIR", name_column]
        ) - {""}
        actual = {
            alias.source_value
            for reference in DEFAULT_PRISMA_REFERENCES.entries
            if reference.classification is ReferenceClassification.STORAGE
            for alias in reference.aliases
            if alias.side is side
        }
        assert actual == expected


def test_storage_alias_is_not_assumed_for_unevidenced_side() -> None:
    assert DEFAULT_PRISMA_REFERENCES.lookup(
        "TEP Storage Hub (6257)", ReferenceSide.ENTRY
    ) is None


def test_known_exit_market_exact_alias(tmp_path: Path) -> None:
    row = {
        **BASE,
        "Direction": "Exit",
        "Network Point Name Entry": "",
        "Network Point Name Exit": "Arnoldstein Exit",
        "Network Point ID Exit": "EXIT-ID",
    }
    enriched = import_prisma_export(write_csv(tmp_path, [row])).rows[0]
    assert (enriched["exit_market"], enriched["direction"]) == ("CEGH", "exit")
    reference = import_prisma_export(write_csv(tmp_path, [row])).enriched_records[0].exit_reference
    assert reference is not None
    assert (reference.canonical_name, reference.classification) == (
        "CEGH", ReferenceClassification.MARKET
    )


def test_known_entry_market_and_harmless_normalization(tmp_path: Path) -> None:
    row = {**BASE, "Network Point Name Entry": "  arnoldstein EXIT  "}
    enriched = import_prisma_export(write_csv(tmp_path, [row])).rows[0]
    assert enriched["entry_market"] == "PSV"


def test_bundle_enrichment_derives_capacity_type_from_both_sides(tmp_path: Path) -> None:
    row = {
        **BASE,
        "Direction": "Exit/Entry",
        "Network Point Name Exit": "Arnoldstein Exit",
        "Network Point ID Exit": "EXIT-ID",
        "Network Point Name Entry": "Arnoldstein Exit",
        "Network Point Name Exit/Entry": "Arnoldstein bundle",
        "Network Point ID Exit/Entry": "BUNDLE-ID",
    }
    enriched = import_prisma_export(write_csv(tmp_path, [row])).rows[0]
    assert (enriched["exit_market"], enriched["entry_market"], enriched["direction"]) == (
        "CEGH", "PSV", "bundle"
    )
    record = import_prisma_export(write_csv(tmp_path, [row])).enriched_records[0]
    assert record.exit_reference is not None and record.entry_reference is not None
    assert (
        record.exit_reference.canonical_name,
        record.exit_reference.classification,
        record.entry_reference.canonical_name,
        record.entry_reference.classification,
    ) == (
        "CEGH", ReferenceClassification.MARKET,
        "PSV", ReferenceClassification.MARKET,
    )


@pytest.mark.parametrize(
    ("field", "side", "code"),
    [
        ("Network Point Name Exit", "exit", "unknown_exit_reference"),
        ("Network Point Name Entry", "entry", "unknown_entry_reference"),
    ],
)
def test_unknown_reference_is_auditable(
    tmp_path: Path, field: str, side: str, code: str
) -> None:
    row = {**BASE, "Network Point Name Entry": ""}
    row[field] = "Unknown Source Value"
    row["Direction"] = "Exit" if side == "exit" else "Entry"
    if side == "exit":
        row["Network Point ID Exit"] = "EXIT-ID"
    result = import_prisma_export(write_csv(tmp_path, [row]))
    issue = result.issues[0]
    assert result.rows == []
    assert (issue.source_row_number, issue.status, issue.reason_code) == (
        2, PrismaImportStatus.REJECTED, code
    )
    assert (issue.field_name, issue.side, issue.source_value) == (
        field, side, "Unknown Source Value"
    )


def test_bundle_missing_required_sides_cannot_be_enriched(tmp_path: Path) -> None:
    row = {
        **BASE,
        "Direction": "Exit/Entry",
        "Network Point Name Entry": "",
        "Network Point Name Exit": "",
        "Network Point Name Exit/Entry": "Combined point",
        "Network Point ID Exit/Entry": "BUNDLE-ID",
    }
    result = import_prisma_export(write_csv(tmp_path, [row]))
    assert result.rows == []
    issue = result.issues[0]
    assert issue.reason_code is PrismaEnrichmentReasonCode.MISSING_REQUIRED_EXIT_REFERENCE
    assert (issue.field_name, issue.side, issue.source_value) == (
        "Network Point Name Exit", "exit", ""
    )


@pytest.mark.parametrize(("direction", "required_field", "irrelevant_field", "expected"), [
    ("Entry", "Network Point Name Entry", "Network Point Name Exit", "entry"),
    ("Exit", "Network Point Name Exit", "Network Point Name Entry", "exit"),
])
def test_irrelevant_populated_side_is_ignored_without_changing_direction(
    tmp_path: Path, direction: str, required_field: str, irrelevant_field: str, expected: str
) -> None:
    row = {
        **BASE,
        "Direction": direction,
        required_field: "VGS Storage Hub (4290)",
        irrelevant_field: "Contradictory unknown side",
    }
    if direction == "Exit":
        row["Network Point ID Exit"] = "EXIT-ID"
    result = import_prisma_export(write_csv(tmp_path, [row]))
    assert result.rejected_count == 0
    enriched = result.rows[0]
    assert enriched["direction"] == expected
    assert enriched["network_point"] == "VGS Storage Hub (4290)"
    assert result.enriched_records[0].raw_row[irrelevant_field] == "Contradictory unknown side"


@pytest.mark.parametrize(("direction", "field", "code"), [
    ("Entry", "Network Point Name Entry", PrismaEnrichmentReasonCode.MISSING_REQUIRED_ENTRY_REFERENCE),
    ("Exit", "Network Point Name Exit", PrismaEnrichmentReasonCode.MISSING_REQUIRED_EXIT_REFERENCE),
])
def test_missing_direction_required_side_is_typed_and_auditable(
    tmp_path: Path, direction: str, field: str, code: PrismaEnrichmentReasonCode
) -> None:
    row = {**BASE, "Direction": direction, field: ""}
    result = import_prisma_export(write_csv(tmp_path, [row]))
    issue = result.issues[0]
    assert result.rows == []
    assert issue.reason_code is code
    assert (issue.field_name, issue.side, issue.source_value) == (
        field, "entry" if direction == "Entry" else "exit", ""
    )


def test_duplicate_and_conflicting_aliases_are_rejected() -> None:
    aliases = (ReferenceAlias("Same", ReferenceSide.EXIT),)
    with pytest.raises(ValueError, match="Conflicting or duplicate"):
        PrismaReferenceCatalog((
            PrismaReference("One", ReferenceClassification.MARKET, aliases),
            PrismaReference("Two", ReferenceClassification.STORAGE, aliases),
        ))


def test_duplicate_aliases_within_one_entry_are_rejected() -> None:
    aliases = (
        ReferenceAlias("Same", ReferenceSide.EXIT),
        ReferenceAlias(" same ", ReferenceSide.EXIT),
    )
    with pytest.raises(ValueError, match="Conflicting or duplicate"):
        PrismaReferenceCatalog((
            PrismaReference("One", ReferenceClassification.MARKET, aliases),
        ))


def test_duplicate_canonical_name_cannot_hide_behind_whitespace() -> None:
    with pytest.raises(ValueError, match="surrounding whitespace"):
        PrismaReferenceCatalog((
            PrismaReference("One", ReferenceClassification.MARKET, ()),
            PrismaReference(" One ", ReferenceClassification.STORAGE, ()),
        ))


@pytest.mark.parametrize("value", ["Arnoldstein", "Arnoldstein Exit extra", "noldstein Exit"])
def test_no_fuzzy_or_substring_matching(value: str) -> None:
    assert DEFAULT_PRISMA_REFERENCES.lookup(value, ReferenceSide.EXIT) is None


def test_original_source_value_and_physical_line_are_preserved_in_issue(tmp_path: Path) -> None:
    original = "  Not A Known Hub  "
    result = import_prisma_export(
        write_csv(tmp_path, [{**BASE, "Network Point Name Entry": original}])
    )
    issue = result.issues[0]
    assert issue.source_row_number == 2
    assert issue.source_value == original


def test_rows_and_issues_remain_in_source_order_deterministically(tmp_path: Path) -> None:
    rows = [
        BASE,
        {**BASE, "Auction ID": "2", "Network Point Name Entry": "Unknown B"},
        {**BASE, "Auction ID": "3", "Network Point Name Entry": "Unknown A"},
    ]
    first = import_prisma_export(write_csv(tmp_path, rows))
    second = import_prisma_export(write_csv(tmp_path, rows))
    assert first == second
    assert [issue.source_row_number for issue in first.issues] == [3, 4]
