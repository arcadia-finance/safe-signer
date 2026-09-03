import json

import pytest

from src.utils.signatures import load


class TestSignatureLoadingHappyPath:
    def test_valid_file(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        sigs = {"0xabc123": {"0xSigner": "0xSignature"}}
        (out_dir / "signatures.txt").write_text(json.dumps(sigs))
        assert load(str(tmp_path)) == sigs

    def test_nested_signatures(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        sigs = {
            "hash_a": {"0xAddr1": "sig1", "0xAddr2": "sig2"},
            "hash_b": {"0xAddr3": "sig3"},
        }
        (out_dir / "signatures.txt").write_text(json.dumps(sigs))
        assert load(str(tmp_path)) == sigs


class TestSignatureLoadingNoFile:
    def test_missing_file(self, tmp_path):
        assert load(str(tmp_path)) == {}

    def test_missing_out_directory(self, tmp_path):
        assert load(str(tmp_path)) == {}

    def test_explicit_empty_object(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "signatures.txt").write_text("{}")
        assert load(str(tmp_path)) == {}


class TestSignatureLoadingUnreadableFileRaises:
    def test_empty_file(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "signatures.txt").write_text("")
        with pytest.raises(ValueError, match="Could not parse"):
            load(str(tmp_path))

    def test_malformed_json(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "signatures.txt").write_text("{bad json")
        with pytest.raises(ValueError, match="Could not parse"):
            load(str(tmp_path))

    def test_truncated_file(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        sigs = {"hash_a": {"0xAddr1": "sig1"}}
        (out_dir / "signatures.txt").write_text(json.dumps(sigs)[:-3])
        with pytest.raises(ValueError, match="Could not parse"):
            load(str(tmp_path))

    def test_unresolved_merge_conflict(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "signatures.txt").write_text(
            "<<<<<<< HEAD\n"
            f"{json.dumps({'hash_a': {'0xAddr1': 'sig1'}})}\n"
            "=======\n"
            f"{json.dumps({'hash_b': {'0xAddr2': 'sig2'}})}\n"
            ">>>>>>> origin/main\n"
        )
        with pytest.raises(ValueError, match="Could not parse"):
            load(str(tmp_path))

    def test_json_array_instead_of_dict(self, tmp_path):
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        (out_dir / "signatures.txt").write_text("[1, 2, 3]")
        with pytest.raises(TypeError, match="Expected dict"):
            load(str(tmp_path))
