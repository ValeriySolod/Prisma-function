from pathlib import Path

import pytest

import manual_csv_selection as manual_csv_selection_module
from csv_contracts import PRISMA_EXPORT_COLUMNS
from manual_csv_selection import (
    ManualCsvOutcome,
    ManualCsvSelection,
    describe_rejection,
    validate_manual_csv,
)

_VALID_HEADER = ";".join(PRISMA_EXPORT_COLUMNS)


def _write(path: Path, text: str, *, encoding: str = "cp1252", newline: bytes = b"\r\n") -> None:
    path.write_bytes(text.encode(encoding) + newline)


def _valid_csv(tmp_path: Path, name: str = "export.csv") -> Path:
    target = tmp_path / name
    _write(target, _VALID_HEADER)
    return target


def test_accepts_exact_official_header(tmp_path):
    target = _valid_csv(tmp_path)

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.ACCEPTED
    assert result.path == target.resolve()
    assert result.accepted is True


def test_rejects_missing_path(tmp_path):
    missing = tmp_path / "does-not-exist.csv"

    result = validate_manual_csv(missing)

    assert result.outcome is ManualCsvOutcome.NOT_FOUND
    assert result.path is None


def test_rejects_directory_path(tmp_path):
    directory = tmp_path / "a-directory"
    directory.mkdir()

    result = validate_manual_csv(directory)

    assert result.outcome is ManualCsvOutcome.NOT_A_FILE


def test_rejects_unreadable_file(tmp_path, monkeypatch):
    target = _valid_csv(tmp_path)

    def raise_open(self, *args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(manual_csv_selection_module.Path, "open", raise_open)

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.UNREADABLE


def test_rejects_empty_file(tmp_path):
    target = tmp_path / "empty.csv"
    target.write_bytes(b"")

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.EMPTY_FILE


@pytest.mark.parametrize(
    "bom_bytes",
    [
        b"\xef\xbb\xbf",
        b"\xff\xfe",
        b"\xfe\xff",
        b"\xff\xfe\x00\x00",
        b"\x00\x00\xfe\xff",
    ],
    ids=["utf-8", "utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"],
)
def test_rejects_standard_bom_signatures(tmp_path, bom_bytes):
    target = tmp_path / "bom.csv"
    target.write_bytes(bom_bytes + _VALID_HEADER.encode("cp1252") + b"\r\n")

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.BOM_DETECTED
    assert result.path is None


def test_rejects_wrong_encoding(tmp_path):
    target = tmp_path / "encoding.csv"
    # 0x81 is undefined in cp1252 and raises UnicodeDecodeError under strict decoding.
    target.write_bytes(b"\x81" + _VALID_HEADER.encode("cp1252") + b"\r\n")

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.ENCODING


def test_accepts_valid_header_followed_by_valid_cp1252_data(tmp_path):
    target = tmp_path / "with-data.csv"
    header = _VALID_HEADER.encode("cp1252") + b"\r\n"
    # 0xE9 is "e" (cp1252) - a valid single-byte non-ASCII character.
    data_row = ("1" + ";" * (len(PRISMA_EXPORT_COLUMNS) - 1)).encode("cp1252") + b"\xe9\r\n"
    target.write_bytes(header + data_row)

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.ACCEPTED
    assert result.path == target.resolve()


def test_rejects_invalid_cp1252_byte_after_valid_header(tmp_path):
    target = tmp_path / "bad-data-row.csv"
    header = _VALID_HEADER.encode("cp1252") + b"\r\n"
    # 0x81 is undefined in cp1252 and only appears after the header line.
    data_row = b"1;bad\x81byte\r\n"
    target.write_bytes(header + data_row)

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.ENCODING
    assert result.path is None


def test_rejects_invalid_cp1252_byte_beyond_first_chunk(tmp_path, monkeypatch):
    monkeypatch.setattr(manual_csv_selection_module, "_CHUNK_SIZE", 8)
    target = tmp_path / "bad-data-row-later-chunk.csv"
    header = _VALID_HEADER.encode("cp1252") + b"\r\n"
    padding = b"x" * 64
    data_row = padding + b"\x81"
    target.write_bytes(header + data_row)

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.ENCODING


class _FailAfterHeaderFile:
    """Wraps a real binary file; succeeds through the header, then fails reads."""

    def __init__(self, real_file):
        self._real_file = real_file
        self._header_consumed = False

    def read(self, size=-1):
        if self._header_consumed:
            raise OSError("simulated I/O failure")
        return self._real_file.read(size)

    def readline(self, *args, **kwargs):
        self._header_consumed = True
        return self._real_file.readline(*args, **kwargs)

    def seek(self, *args, **kwargs):
        return self._real_file.seek(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return self._real_file.__exit__(*exc_info)


def test_rejects_read_failure_after_header(tmp_path, monkeypatch):
    target = tmp_path / "fails-after-header.csv"
    header = _VALID_HEADER.encode("cp1252") + b"\r\n"
    target.write_bytes(header + b"more cp1252 data that is never reached\r\n")
    real_open = manual_csv_selection_module.Path.open

    def fake_open(self, *args, **kwargs):
        real_file = real_open(self, *args, **kwargs)
        if self == target:
            return _FailAfterHeaderFile(real_file)
        return real_file

    monkeypatch.setattr(manual_csv_selection_module.Path, "open", fake_open)

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.UNREADABLE
    assert result.path is None


def test_rejects_wrong_delimiter(tmp_path):
    target = tmp_path / "delimiter.csv"
    _write(target, ",".join(PRISMA_EXPORT_COLUMNS))

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.DELIMITER


def test_rejects_missing_header_column(tmp_path):
    target = tmp_path / "missing.csv"
    columns = PRISMA_EXPORT_COLUMNS[:-1]
    _write(target, ";".join(columns))

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.HEADER_MISMATCH


def test_rejects_extra_header_column(tmp_path):
    target = tmp_path / "extra.csv"
    columns = PRISMA_EXPORT_COLUMNS + ("Extra Column",)
    _write(target, ";".join(columns))

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.HEADER_MISMATCH


def test_rejects_reordered_header(tmp_path):
    target = tmp_path / "reordered.csv"
    columns = list(PRISMA_EXPORT_COLUMNS)
    columns[0], columns[1] = columns[1], columns[0]
    _write(target, ";".join(columns))

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.HEADER_MISMATCH


def test_rejects_duplicate_header_column(tmp_path):
    target = tmp_path / "duplicate.csv"
    columns = list(PRISMA_EXPORT_COLUMNS)
    columns[-1] = columns[0]
    _write(target, ";".join(columns))

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.HEADER_MISMATCH


def test_rejects_wrong_extension_content_regardless_of_extension(tmp_path):
    target = tmp_path / "not-really-a-csv.txt"
    target.write_bytes(b"\x00\x01binary garbage, not a PRISMA export\xff\xfe")

    result = validate_manual_csv(target)

    assert result.outcome is not ManualCsvOutcome.ACCEPTED


def test_accepts_valid_content_even_with_non_csv_extension(tmp_path):
    target = tmp_path / "export.dat"
    _write(target, _VALID_HEADER)

    result = validate_manual_csv(target)

    assert result.outcome is ManualCsvOutcome.ACCEPTED


@pytest.mark.parametrize("outcome", [o for o in ManualCsvOutcome if o is not ManualCsvOutcome.ACCEPTED])
def test_every_rejection_has_a_path_free_english_message(outcome):
    message = describe_rejection(outcome)

    assert message
    assert message.isascii()


def test_selection_starts_with_no_current_file():
    selection = ManualCsvSelection()

    assert selection.current is None


def test_selection_updates_current_on_valid_candidate(tmp_path):
    target = _valid_csv(tmp_path)
    selection = ManualCsvSelection()

    result = selection.select(target)

    assert result.accepted is True
    assert selection.current == target.resolve()


def test_selection_rejects_invalid_candidate_without_changing_current(tmp_path):
    target = _valid_csv(tmp_path)
    selection = ManualCsvSelection()
    selection.select(target)
    invalid = tmp_path / "missing.csv"

    result = selection.select(invalid)

    assert result.accepted is False
    assert selection.current == target.resolve()


def test_selection_rejected_candidate_before_any_valid_selection_stays_none(tmp_path):
    selection = ManualCsvSelection()
    invalid = tmp_path / "missing.csv"

    result = selection.select(invalid)

    assert result.accepted is False
    assert selection.current is None


def test_selection_rejects_mid_file_encoding_failure_without_changing_current(tmp_path):
    target = _valid_csv(tmp_path)
    selection = ManualCsvSelection()
    selection.select(target)

    bad = tmp_path / "bad-data-row.csv"
    bad.write_bytes(_VALID_HEADER.encode("cp1252") + b"\r\n1;bad\x81byte\r\n")

    result = selection.select(bad)

    assert result.accepted is False
    assert result.outcome is ManualCsvOutcome.ENCODING
    assert selection.current == target.resolve()
    message = describe_rejection(result.outcome)
    assert str(bad) not in message
    assert str(bad.resolve()) not in message
