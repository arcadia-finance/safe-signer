from unittest.mock import MagicMock, patch

import pytest

from helpers import make_mock_safe
from src.utils.validate_signer import validate

SIGNER = {"name": "Signer One", "address": "0x2222222222222222222222222222222222222222"}
TX_HASH = "abc123"


class TestValidateSignerIsOwnerNoExistingSig:
    def test_returns_true(self):
        safe = make_mock_safe(is_owner=True)
        all_signatures = {}
        assert validate(safe, all_signatures, TX_HASH, SIGNER) is True

    def test_returns_true_when_hash_exists_but_signer_not_in_it(self):
        safe = make_mock_safe(is_owner=True)
        all_signatures = {TX_HASH: {"0xOtherAddress": "some_sig"}}
        assert validate(safe, all_signatures, TX_HASH, SIGNER) is True


class TestValidateSignerIsOwnerExistingSig:
    @patch("src.utils.validate_signer.inquirer.prompt")
    def test_overwrite_yes_returns_true(self, mock_prompt):
        mock_prompt.return_value = {"overwrite signature": "Yes"}
        safe = make_mock_safe(is_owner=True)
        all_signatures = {TX_HASH: {SIGNER["address"]: "existing_sig"}}
        assert validate(safe, all_signatures, TX_HASH, SIGNER) is True

    @patch("src.utils.validate_signer.inquirer.prompt")
    def test_overwrite_no_returns_false(self, mock_prompt):
        mock_prompt.return_value = {"overwrite signature": "No"}
        safe = make_mock_safe(is_owner=True)
        all_signatures = {TX_HASH: {SIGNER["address"]: "existing_sig"}}
        assert validate(safe, all_signatures, TX_HASH, SIGNER) is False


class TestValidateSignerNotOwner:
    def test_returns_false(self):
        safe = make_mock_safe(is_owner=False)
        assert validate(safe, {}, TX_HASH, SIGNER) is False

    def test_prints_error_message(self, capsys):
        safe = make_mock_safe(is_owner=False)
        validate(safe, {}, TX_HASH, SIGNER)
        captured = capsys.readouterr()
        assert "is not an owner" in captured.out
        assert SIGNER["address"] in captured.out


class TestValidateSignerEdgeCases:
    def test_empty_string_signature_treated_as_no_existing(self):
        safe = make_mock_safe(is_owner=True)
        all_signatures = {TX_HASH: {SIGNER["address"]: ""}}
        assert validate(safe, all_signatures, TX_HASH, SIGNER) is True

    def test_is_owner_rpc_failure_propagates(self):
        safe = MagicMock()
        safe.functions.isOwner.return_value.call.side_effect = Exception("RPC error")
        with pytest.raises(Exception, match="RPC error"):
            validate(safe, {}, TX_HASH, SIGNER)

    def test_different_tx_hash_no_collision(self):
        safe = make_mock_safe(is_owner=True)
        all_signatures = {"other_hash": {SIGNER["address"]: "existing_sig"}}
        assert validate(safe, all_signatures, TX_HASH, SIGNER) is True
