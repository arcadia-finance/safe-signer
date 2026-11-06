import os

import pytest

from src.utils import history

SAFE = "0xFd6db26eDc581D8F381f46eF4a6396A762b66E95"
HASH_A = "a" * 64
HASH_B = "b" * 64


def _write(tmp_path, *lines):
    os.makedirs(tmp_path / "out", exist_ok=True)
    (tmp_path / "out" / "history.jsonl").write_text(
        "".join(f"{line}\n" for line in lines)
    )


def _execution(nonce, tx_hash, block, success="true"):
    return (
        f'{{"chain":"Base","safe":"{SAFE}","nonce":{nonce},"block":{block},'
        f'"tx_hash":"{tx_hash}","success":{success}}}'
    )


def _watermark(scanned_to, nonce):
    return (
        f'{{"chain":"Base","safe":"{SAFE}","scanned_to":{scanned_to},"nonce":{nonce}}}'
    )


class TestLoad:
    def test_missing_file_empty(self, tmp_path):
        assert history.load(str(tmp_path)) == {}

    def test_round_trip(self, tmp_path):
        history.append(
            str(tmp_path),
            "Base",
            SAFE,
            [(0, HASH_A, True, 10), (1, HASH_B, False, 20)],
            50,
            2,
        )

        assert history.load(str(tmp_path)) == {
            ("Base", SAFE): {
                "scanned_to": 50,
                "nonce": 2,
                "history": {0: (HASH_A, True, 10), 1: (HASH_B, False, 20)},
            }
        }

    def test_duplicate_lines_ignored(self, tmp_path):
        _write(
            tmp_path,
            _execution(0, HASH_A, 10),
            _execution(0, HASH_A, 10),
            _watermark(50, 1),
        )

        assert history.load(str(tmp_path))[("Base", SAFE)]["history"] == {
            0: (HASH_A, True, 10)
        }

    def test_conflicting_execution_rejected(self, tmp_path):
        _write(
            tmp_path,
            _execution(0, HASH_A, 10),
            _watermark(50, 1),
            _execution(0, HASH_B, 10),
        )

        with pytest.raises(ValueError, match="Lines 1 and 3"):
            history.load(str(tmp_path))

    def test_highest_watermark_wins(self, tmp_path):
        _write(
            tmp_path,
            _execution(0, HASH_A, 10),
            _execution(1, HASH_B, 60),
            _watermark(80, 2),
            _watermark(50, 1),
        )

        loaded = history.load(str(tmp_path))[("Base", SAFE)]
        assert (loaded["scanned_to"], loaded["nonce"]) == (80, 2)
        assert set(loaded["history"]) == {0, 1}

    def test_executions_above_watermark_ignored(self, tmp_path):
        _write(
            tmp_path,
            _execution(0, HASH_A, 10),
            _execution(1, HASH_B, 60),
            _watermark(50, 1),
        )

        assert set(history.load(str(tmp_path))[("Base", SAFE)]["history"]) == {0}

    def test_key_without_watermark_absent(self, tmp_path):
        _write(tmp_path, _execution(0, HASH_A, 10))

        assert history.load(str(tmp_path)) == {}

    def test_malformed_line_rejected(self, tmp_path):
        _write(tmp_path, _watermark(50, 0), "{not json")

        with pytest.raises(ValueError, match="line 2"):
            history.load(str(tmp_path))


class TestAppend:
    def test_appends_newline_separator(self, tmp_path):
        os.makedirs(tmp_path / "out")
        (tmp_path / "out" / "history.jsonl").write_text(_watermark(5, 0))

        history.append(str(tmp_path), "Base", SAFE, [], 50, 0)

        lines = (tmp_path / "out" / "history.jsonl").read_text().splitlines()
        assert lines == [_watermark(5, 0), _watermark(50, 0)]
