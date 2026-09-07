import json

import pytest

from src.utils.signatures import append, load


HASH_A = "a" * 64
HASH_B = "b" * 64
ADDR_1 = "0x" + "1" * 40
ADDR_2 = "0x" + "2" * 40
SIG_1 = "c" * 130
SIG_2 = "d" * 130


def write(tmp_path, content: str):
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "signatures.txt").write_text(content)


def read(tmp_path) -> str:
    return (tmp_path / "out" / "signatures.txt").read_text()


class TestSignatureLoadingHappyPath:
    def test_single_record(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n")
        assert load(str(tmp_path)) == {HASH_A: {ADDR_1: SIG_1}}

    def test_multiple_signers_per_transaction(self, tmp_path):
        write(
            tmp_path,
            f"{HASH_A} {ADDR_1} {SIG_1}\n{HASH_A} {ADDR_2} {SIG_2}\n"
            f"{HASH_B} {ADDR_1} {SIG_2}\n",
        )
        assert load(str(tmp_path)) == {
            HASH_A: {ADDR_1: SIG_1, ADDR_2: SIG_2},
            HASH_B: {ADDR_1: SIG_2},
        }

    def test_blank_lines_are_skipped(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n\n\n{HASH_B} {ADDR_2} {SIG_2}\n")
        assert load(str(tmp_path)) == {
            HASH_A: {ADDR_1: SIG_1},
            HASH_B: {ADDR_2: SIG_2},
        }

    def test_final_newline_is_optional(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}")
        assert load(str(tmp_path)) == {HASH_A: {ADDR_1: SIG_1}}

    def test_repeated_identical_record_is_idempotent(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n" * 2)
        assert load(str(tmp_path)) == {HASH_A: {ADDR_1: SIG_1}}


class TestSignatureLoadingNoFile:
    def test_missing_file(self, tmp_path):
        assert load(str(tmp_path)) == {}

    def test_missing_out_directory(self, tmp_path):
        assert load(str(tmp_path)) == {}

    def test_empty_file(self, tmp_path):
        write(tmp_path, "")
        assert load(str(tmp_path)) == {}


class TestSignatureLoadingMalformedRaises:
    def test_too_few_fields(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1}\n")
        with pytest.raises(ValueError, match="line 1.*expected 3 fields, got 2"):
            load(str(tmp_path))

    def test_too_many_fields(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1} extra\n")
        with pytest.raises(ValueError, match="line 1.*expected 3 fields, got 4"):
            load(str(tmp_path))

    def test_reports_the_offending_line_number(self, tmp_path):
        write(
            tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n{HASH_B} {ADDR_2} {SIG_2}\nbroken\n"
        )
        with pytest.raises(ValueError, match="Malformed record on line 3"):
            load(str(tmp_path))

    def test_truncated_transaction_hash(self, tmp_path):
        write(tmp_path, f"{HASH_A[:-1]} {ADDR_1} {SIG_1}\n")
        with pytest.raises(ValueError, match="invalid transaction hash"):
            load(str(tmp_path))

    def test_address_without_prefix(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1[2:]} {SIG_1}\n")
        with pytest.raises(ValueError, match="invalid signer address"):
            load(str(tmp_path))

    def test_truncated_signature(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1[:-1]}\n")
        with pytest.raises(ValueError, match="invalid signature"):
            load(str(tmp_path))

    def test_previous_json_format(self, tmp_path):
        write(tmp_path, json.dumps({HASH_A: {ADDR_1: SIG_1}}))
        with pytest.raises(ValueError, match="Malformed record on line 1"):
            load(str(tmp_path))

    def test_unresolved_merge_conflict(self, tmp_path):
        write(
            tmp_path,
            f"<<<<<<< HEAD\n{HASH_A} {ADDR_1} {SIG_1}\n=======\n"
            f"{HASH_B} {ADDR_2} {SIG_2}\n>>>>>>> origin/main\n",
        )
        with pytest.raises(ValueError, match="Malformed record on line 1"):
            load(str(tmp_path))


class TestSignatureLoadingConflictingSignatureRaises:
    def test_same_signer_and_transaction_with_different_signature(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n{HASH_A} {ADDR_1} {SIG_2}\n")
        with pytest.raises(ValueError, match="a different signature"):
            load(str(tmp_path))

    def test_same_signer_on_different_transactions_is_allowed(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n{HASH_B} {ADDR_1} {SIG_2}\n")
        assert load(str(tmp_path)) == {
            HASH_A: {ADDR_1: SIG_1},
            HASH_B: {ADDR_1: SIG_2},
        }


class TestSignatureAppend:
    def test_creates_the_file_and_directory(self, tmp_path):
        append(str(tmp_path), HASH_A, ADDR_1, SIG_1)
        assert load(str(tmp_path)) == {HASH_A: {ADDR_1: SIG_1}}

    def test_preserves_existing_records(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n")
        append(str(tmp_path), HASH_B, ADDR_2, SIG_2)
        assert load(str(tmp_path)) == {
            HASH_A: {ADDR_1: SIG_1},
            HASH_B: {ADDR_2: SIG_2},
        }

    def test_only_adds_one_line(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}\n")
        append(str(tmp_path), HASH_B, ADDR_2, SIG_2)
        assert (
            read(tmp_path) == f"{HASH_A} {ADDR_1} {SIG_1}\n{HASH_B} {ADDR_2} {SIG_2}\n"
        )

    def test_appends_to_a_file_without_a_final_newline(self, tmp_path):
        write(tmp_path, f"{HASH_A} {ADDR_1} {SIG_1}")
        append(str(tmp_path), HASH_B, ADDR_2, SIG_2)
        assert (
            read(tmp_path) == f"{HASH_A} {ADDR_1} {SIG_1}\n{HASH_B} {ADDR_2} {SIG_2}\n"
        )

    def test_rejects_a_malformed_record(self, tmp_path):
        with pytest.raises(ValueError, match="invalid signer address"):
            append(str(tmp_path), HASH_A, "not_an_address", SIG_1)

    def test_rejects_without_creating_a_file(self, tmp_path):
        with pytest.raises(ValueError):
            append(str(tmp_path), HASH_A, "not_an_address", SIG_1)
        assert load(str(tmp_path)) == {}
