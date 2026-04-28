import pytest
from eth_account import Account
from web3 import Web3

from helpers import make_typed_data
from src.wallets.hot_wallet import sign_transaction, sign_typed_data

TEST_KEY = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f3082e0e50e2872f62"
TEST_ACCOUNT = Account.from_key(TEST_KEY)
TEST_ADDRESS = TEST_ACCOUNT.address
WRONG_ADDRESS = "0x0000000000000000000000000000000000000001"

TYPED_DATA = make_typed_data()

w3 = Web3()


class TestSignTypedData:
    def test_happy_path(self):
        result = sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, TYPED_DATA)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_hex_string(self):
        result = sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, TYPED_DATA)
        int(result, 16)

    def test_deterministic(self):
        sig1 = sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, TYPED_DATA)
        sig2 = sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, TYPED_DATA)
        assert sig1 == sig2

    def test_address_mismatch_returns_none(self):
        result = sign_typed_data(TEST_KEY, WRONG_ADDRESS, w3, TYPED_DATA)
        assert result is None

    def test_address_mismatch_prints_error(self, capsys):
        sign_typed_data(TEST_KEY, WRONG_ADDRESS, w3, TYPED_DATA)
        captured = capsys.readouterr()
        assert "does not match" in captured.out
        assert WRONG_ADDRESS in captured.out

    def test_different_data_different_signature(self):
        data2 = make_typed_data(nonce=999)
        sig1 = sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, TYPED_DATA)
        sig2 = sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, data2)
        assert sig1 != sig2

    def test_invalid_private_key_raises(self):
        with pytest.raises(ValueError):
            sign_typed_data("0xinvalid", TEST_ADDRESS, w3, TYPED_DATA)

    def test_empty_private_key_raises(self):
        with pytest.raises(ValueError):
            sign_typed_data("", TEST_ADDRESS, w3, TYPED_DATA)

    def test_missing_typed_data_field_raises(self):
        bad_data = make_typed_data()
        del bad_data["message"]["nonce"]
        with pytest.raises(Exception):
            sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, bad_data)

    def test_signature_is_65_bytes(self):
        result = sign_typed_data(TEST_KEY, TEST_ADDRESS, w3, TYPED_DATA)
        sig_bytes = bytes.fromhex(result.removeprefix("0x"))
        assert len(sig_bytes) == 65


UNSIGNED_TX = {
    "to": "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B",
    "value": 0,
    "gas": 100000,
    "gasPrice": 1000000000,
    "nonce": 0,
    "chainId": 8453,
    "data": "0x",
}


class TestSignTransaction:
    def test_happy_path(self):
        result = sign_transaction(TEST_KEY, TEST_ADDRESS, w3, UNSIGNED_TX)
        assert result is not None
        assert hasattr(result, "rawTransaction") or hasattr(result, "raw_transaction")

    def test_address_mismatch_returns_none(self):
        result = sign_transaction(TEST_KEY, WRONG_ADDRESS, w3, UNSIGNED_TX)
        assert result is None

    def test_address_mismatch_prints_error(self, capsys):
        sign_transaction(TEST_KEY, WRONG_ADDRESS, w3, UNSIGNED_TX)
        captured = capsys.readouterr()
        assert "does not match" in captured.out
        assert WRONG_ADDRESS in captured.out

    def test_invalid_private_key_raises(self):
        with pytest.raises(ValueError):
            sign_transaction("0xinvalid", TEST_ADDRESS, w3, UNSIGNED_TX)

    def test_empty_private_key_raises(self):
        with pytest.raises(ValueError):
            sign_transaction("", TEST_ADDRESS, w3, UNSIGNED_TX)

    def test_malformed_tx_raises(self):
        incomplete_tx = {"to": "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B"}
        with pytest.raises(Exception):
            sign_transaction(TEST_KEY, TEST_ADDRESS, w3, incomplete_tx)
