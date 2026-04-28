import os
from unittest.mock import MagicMock, patch

import pytest
from eth_abi import encode
from eth_utils import keccak
from web3 import Web3

from helpers import SAFE_TX_CONSTANTS, make_mock_safe, make_typed_data
from src.eip712_typed_data import get_typed_data, get_typed_data_hash, sign

SAFE_TX_TYPEHASH = Web3.to_bytes(
    hexstr="0xbb8310d486368db6bd6f849402fdd73ad53d316b5a4b2644ad6efe0f941286d8"
)

TO = "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B"
RAW_DATA = "0x1234"


class TestGetTypedData:
    def test_populates_all_fields(self):
        safe = make_mock_safe(nonce=5, chain_id=8453)
        result = get_typed_data(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS)

        assert result["primaryType"] == "SafeTx"
        assert result["message"]["to"] == TO
        assert result["message"]["data"] == RAW_DATA
        assert result["message"]["operation"] == 1
        assert result["message"]["nonce"] == 5
        assert result["domain"]["chainId"] == 8453
        assert result["domain"]["verifyingContract"] == safe.address

    def test_uses_constants(self):
        safe = make_mock_safe()
        result = get_typed_data(safe, TO, RAW_DATA, 0, SAFE_TX_CONSTANTS)

        assert result["message"]["value"] == SAFE_TX_CONSTANTS["VALUE_SAFE_TX"]
        assert result["message"]["safeTxGas"] == SAFE_TX_CONSTANTS["SAFE_TX_GAS"]
        assert result["message"]["gasToken"] == SAFE_TX_CONSTANTS["GAS_TOKEN"]
        assert (
            result["message"]["refundReceiver"] == SAFE_TX_CONSTANTS["REFUND_RECEIVER"]
        )

    def test_calls_safe_contract(self):
        safe = make_mock_safe()
        get_typed_data(safe, TO, RAW_DATA, 0, SAFE_TX_CONSTANTS)

        safe.functions.nonce.assert_called_once()
        safe.functions.getChainId.assert_called_once()

    def test_missing_constant_key_raises(self):
        safe = make_mock_safe()
        incomplete = {k: v for k, v in SAFE_TX_CONSTANTS.items() if k != "GAS_TOKEN"}
        with pytest.raises(KeyError):
            get_typed_data(safe, TO, RAW_DATA, 0, incomplete)

    def test_nonce_call_failure_propagates(self):
        safe = make_mock_safe()
        safe.functions.nonce.return_value.call.side_effect = Exception("RPC error")
        with pytest.raises(Exception, match="RPC error"):
            get_typed_data(safe, TO, RAW_DATA, 0, SAFE_TX_CONSTANTS)

    def test_chain_id_call_failure_propagates(self):
        safe = make_mock_safe()
        safe.functions.getChainId.return_value.call.side_effect = Exception("RPC error")
        with pytest.raises(Exception, match="RPC error"):
            get_typed_data(safe, TO, RAW_DATA, 0, SAFE_TX_CONSTANTS)


class TestGetTypedDataHash:
    def test_deterministic(self):
        data = make_typed_data()
        hash1 = get_typed_data_hash(data)
        hash2 = get_typed_data_hash(data)
        assert hash1 == hash2

    def test_returns_32_bytes(self):
        data = make_typed_data()
        result = get_typed_data_hash(data)
        assert len(result) == 32

    def test_different_nonce_different_hash(self):
        data1 = make_typed_data(nonce=0)
        data2 = make_typed_data(nonce=1)
        assert get_typed_data_hash(data1) != get_typed_data_hash(data2)

    def test_different_data_different_hash(self):
        data1 = make_typed_data()
        data2 = make_typed_data(data="0xdeadbeef")
        assert get_typed_data_hash(data1) != get_typed_data_hash(data2)

    def test_matches_manual_computation(self):
        data = make_typed_data()
        expected = keccak(
            encode(
                [
                    "bytes32",
                    "address",
                    "uint256",
                    "bytes32",
                    "uint8",
                    "uint256",
                    "uint256",
                    "uint256",
                    "address",
                    "address",
                    "uint256",
                ],
                [
                    SAFE_TX_TYPEHASH,
                    TO,
                    0,
                    keccak(hexstr=RAW_DATA),
                    1,
                    0,
                    0,
                    0,
                    "0x0000000000000000000000000000000000000000",
                    "0x0000000000000000000000000000000000000000",
                    0,
                ],
            )
        )
        assert get_typed_data_hash(data) == expected

    def test_missing_message_field_raises(self):
        data = make_typed_data()
        del data["message"]["nonce"]
        with pytest.raises(KeyError):
            get_typed_data_hash(data)

    def test_invalid_hex_data_raises(self):
        data = make_typed_data()
        data["message"]["data"] = "not_hex"
        with pytest.raises(Exception):
            get_typed_data_hash(data)

    def test_different_operation_different_hash(self):
        data1 = make_typed_data(operation=0)
        data2 = make_typed_data(operation=1)
        assert get_typed_data_hash(data1) != get_typed_data_hash(data2)

    def test_different_to_different_hash(self):
        data1 = make_typed_data()
        data2 = make_typed_data(to="0x0000000000000000000000000000000000000001")
        assert get_typed_data_hash(data1) != get_typed_data_hash(data2)


class TestSignRouting:
    def test_hot_wallet_missing_key_returns_false(self):
        signer = {
            "name": "Test",
            "address": "0x1234",
            "wallet": "HOT",
            "key_name": "NONEXISTENT_KEY",
        }
        with patch.dict(os.environ, {}, clear=True):
            result = sign(MagicMock(), signer, {}, b"", b"")
        assert result is False

    @patch("src.eip712_typed_data.hot_wallet.sign_typed_data")
    def test_hot_wallet_with_key_calls_hot_wallet(self, mock_sign):
        mock_sign.return_value = "0xsig"
        signer = {
            "name": "Test",
            "address": "0x1234",
            "wallet": "HOT",
            "key_name": "TEST_KEY",
        }
        w3 = MagicMock()
        typed_data = {"test": True}

        with patch.dict(os.environ, {"TEST_KEY": "0xprivatekey"}):
            result = sign(w3, signer, typed_data, b"", b"")

        assert result == "0xsig"
        mock_sign.assert_called_once_with("0xprivatekey", "0x1234", w3, typed_data)

    @patch("src.eip712_typed_data.trezor_t.sign_typed_data")
    @patch("builtins.input", return_value="")
    def test_trezor_t_routing(self, _mock_input, mock_sign):
        mock_sign.return_value = "0xsig_t"
        signer = {"name": "Test", "address": "0xABC", "wallet": "T", "index": 2}
        result = sign(MagicMock(), signer, {"data": True}, b"domain", b"msg")

        assert result == "0xsig_t"
        mock_sign.assert_called_once_with(2, "0xABC", {"data": True})

    @patch("src.eip712_typed_data.trezor_1.sign_typed_data_hash")
    @patch("builtins.input", return_value="")
    def test_trezor_1_routing(self, _mock_input, mock_sign):
        mock_sign.return_value = "0xsig_1"
        signer = {"name": "Test", "address": "0xABC", "wallet": "1", "index": 3}
        domain_hash = b"\x01" * 32
        message_hash = b"\x02" * 32

        result = sign(MagicMock(), signer, {}, domain_hash, message_hash)

        assert result == "0xsig_1"
        mock_sign.assert_called_once_with(3, "0xABC", domain_hash, message_hash)

    @patch("src.eip712_typed_data.ledger_nano.sign_typed_data_hash")
    @patch("builtins.input", return_value="")
    def test_ledger_routing(self, _mock_input, mock_sign):
        mock_sign.return_value = "0xsig_l"
        signer = {"name": "Test", "address": "0xABC", "wallet": "L", "index": 1}
        domain_hash = b"\x01" * 32
        message_hash = b"\x02" * 32

        result = sign(MagicMock(), signer, {}, domain_hash, message_hash)

        assert result == "0xsig_l"
        mock_sign.assert_called_once_with(1, "0xABC", domain_hash, message_hash)

    @patch("builtins.input", return_value="")
    def test_unknown_wallet_raises(self, _mock_input):
        signer = {"name": "Test", "address": "0xABC", "wallet": "UNKNOWN", "index": 0}
        with pytest.raises(Exception, match="Unknown wallet type"):
            sign(MagicMock(), signer, {}, b"", b"")

    def test_hot_wallet_missing_key_prints_error(self, capsys):
        signer = {
            "name": "Test",
            "address": "0x1234",
            "wallet": "HOT",
            "key_name": "NONEXISTENT_KEY",
        }
        with patch.dict(os.environ, {}, clear=True):
            sign(MagicMock(), signer, {}, b"", b"")
        captured = capsys.readouterr()
        assert "not found" in captured.out
        assert "Test" in captured.out

    @patch("src.eip712_typed_data.hot_wallet.sign_typed_data")
    def test_hot_wallet_returns_none_on_address_mismatch(self, mock_sign):
        mock_sign.return_value = None
        signer = {
            "name": "Test",
            "address": "0x1234",
            "wallet": "HOT",
            "key_name": "TEST_KEY",
        }
        with patch.dict(os.environ, {"TEST_KEY": "0xprivatekey"}):
            result = sign(MagicMock(), signer, {}, b"", b"")
        assert result is None

    @patch("src.eip712_typed_data.trezor_t.sign_typed_data")
    @patch("builtins.input", return_value="")
    def test_trezor_t_returns_none_on_address_mismatch(self, _mock_input, mock_sign):
        mock_sign.return_value = None
        signer = {"name": "Test", "address": "0xABC", "wallet": "T", "index": 0}
        result = sign(MagicMock(), signer, {}, b"", b"")
        assert result is None

    @patch("src.eip712_typed_data.trezor_1.sign_typed_data_hash")
    @patch("builtins.input", return_value="")
    def test_trezor_1_returns_none_on_address_mismatch(self, _mock_input, mock_sign):
        mock_sign.return_value = None
        signer = {"name": "Test", "address": "0xABC", "wallet": "1", "index": 0}
        result = sign(MagicMock(), signer, {}, b"\x00" * 32, b"\x00" * 32)
        assert result is None

    @patch("src.eip712_typed_data.ledger_nano.sign_typed_data_hash")
    @patch("builtins.input", return_value="")
    def test_ledger_returns_none_on_address_mismatch(self, _mock_input, mock_sign):
        mock_sign.return_value = None
        signer = {"name": "Test", "address": "0xABC", "wallet": "L", "index": 0}
        result = sign(MagicMock(), signer, {}, b"\x00" * 32, b"\x00" * 32)
        assert result is None
