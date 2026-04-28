import os
from unittest.mock import MagicMock, patch

import pytest

from helpers import MULTISEND_ADDRESS, RELAY_TX_CONSTANTS, make_mock_safe
from src.safe_transaction import create, sign

TO = MULTISEND_ADDRESS
RAW_DATA = "0xabcdef"
SIGNATURES = "0xaabbccdd"
RELAYER_ADDR = "0x3333333333333333333333333333333333333333"


def make_mock_w3(nonce=0, gas_estimate=200000, gas_price=1000000000):
    w3 = MagicMock()
    w3.eth.get_transaction_count.return_value = nonce
    w3.eth.estimate_gas.return_value = gas_estimate
    w3.eth.gas_price = gas_price
    return w3


class TestCreateGasBranching:
    def test_gas_zero_estimates_dynamically(self):
        w3 = make_mock_w3(gas_estimate=300000)
        safe = make_mock_safe()

        result = create(
            w3,
            safe,
            TO,
            RELAY_TX_CONSTANTS,
            RAW_DATA,
            0,
            SIGNATURES,
            RELAYER_ADDR,
            gas=0,
            max_fee_per_gas=100,
            max_priority_fee_per_gas=10,
        )

        w3.eth.estimate_gas.assert_called_once()
        assert result["gas"] == int(300000 * 1.2)

    def test_gas_nonzero_uses_provided(self):
        w3 = make_mock_w3()
        safe = make_mock_safe()

        result = create(
            w3,
            safe,
            TO,
            RELAY_TX_CONSTANTS,
            RAW_DATA,
            0,
            SIGNATURES,
            RELAYER_ADDR,
            gas=500000,
            max_fee_per_gas=100,
            max_priority_fee_per_gas=10,
        )

        w3.eth.estimate_gas.assert_not_called()
        assert result["gas"] == 500000

    def test_gas_estimate_failure_propagates(self):
        w3 = make_mock_w3()
        w3.eth.estimate_gas.side_effect = Exception("estimation failed")
        safe = make_mock_safe()

        with pytest.raises(Exception, match="estimation failed"):
            create(
                w3,
                safe,
                TO,
                RELAY_TX_CONSTANTS,
                RAW_DATA,
                0,
                SIGNATURES,
                RELAYER_ADDR,
                gas=0,
                max_fee_per_gas=100,
                max_priority_fee_per_gas=10,
            )


class TestCreateNonceAndChainId:
    def test_fetches_nonce_from_relayer_address(self):
        w3 = make_mock_w3(nonce=42)
        safe = make_mock_safe()

        create(
            w3,
            safe,
            TO,
            RELAY_TX_CONSTANTS,
            RAW_DATA,
            0,
            SIGNATURES,
            RELAYER_ADDR,
            gas=100000,
            max_fee_per_gas=100,
            max_priority_fee_per_gas=10,
        )

        w3.eth.get_transaction_count.assert_called_once_with(RELAYER_ADDR)

    def test_fetches_chain_id_from_safe(self):
        w3 = make_mock_w3()
        safe = make_mock_safe(chain_id=10)

        create(
            w3,
            safe,
            TO,
            RELAY_TX_CONSTANTS,
            RAW_DATA,
            0,
            SIGNATURES,
            RELAYER_ADDR,
            gas=100000,
            max_fee_per_gas=100,
            max_priority_fee_per_gas=10,
        )

        safe.functions.getChainId.assert_called_once()


class TestCreateMaxFeeBranching:
    def test_max_fee_zero_calculates_from_gas_price(self):
        w3 = make_mock_w3(gas_price=2000000000)
        safe = make_mock_safe()
        priority_fee = 1000000

        result = create(
            w3,
            safe,
            TO,
            RELAY_TX_CONSTANTS,
            RAW_DATA,
            0,
            SIGNATURES,
            RELAYER_ADDR,
            gas=100000,
            max_fee_per_gas=0,
            max_priority_fee_per_gas=priority_fee,
        )

        assert result["maxFeePerGas"] == 2000000000 + priority_fee

    def test_max_fee_nonzero_uses_provided(self):
        w3 = make_mock_w3()
        safe = make_mock_safe()

        result = create(
            w3,
            safe,
            TO,
            RELAY_TX_CONSTANTS,
            RAW_DATA,
            0,
            SIGNATURES,
            RELAYER_ADDR,
            gas=100000,
            max_fee_per_gas=5000000000,
            max_priority_fee_per_gas=10,
        )

        assert result["maxFeePerGas"] == 5000000000

    def test_priority_fee_always_set(self):
        w3 = make_mock_w3()
        safe = make_mock_safe()

        result = create(
            w3,
            safe,
            TO,
            RELAY_TX_CONSTANTS,
            RAW_DATA,
            0,
            SIGNATURES,
            RELAYER_ADDR,
            gas=100000,
            max_fee_per_gas=100,
            max_priority_fee_per_gas=42,
        )

        assert result["maxPriorityFeePerGas"] == 42


class TestSignRouting:
    @patch("src.safe_transaction.hot_wallet.sign_transaction")
    def test_hot_wallet_happy_path(self, mock_sign):
        mock_sign.return_value = {"raw_transaction": "0x"}
        relayer = {
            "name": "R",
            "address": "0xR",
            "wallet": "HOT",
            "key_name": "TEST_KEY",
        }
        w3 = MagicMock()

        with patch.dict(os.environ, {"TEST_KEY": "0xprivatekey"}):
            result = sign(w3, {"tx": True}, relayer)

        assert result == {"raw_transaction": "0x"}
        mock_sign.assert_called_once_with("0xprivatekey", "0xR", w3, {"tx": True})

    def test_hot_wallet_missing_key_returns_false(self):
        relayer = {
            "name": "R",
            "address": "0xR",
            "wallet": "HOT",
            "key_name": "MISSING_KEY",
        }

        with patch.dict(os.environ, {}, clear=True):
            result = sign(MagicMock(), {}, relayer)

        assert result is False

    @patch("src.safe_transaction.trezor_t.sign_transaction")
    @patch("builtins.input", return_value="")
    def test_trezor_t_routing(self, _mock_input, mock_sign):
        mock_sign.return_value = "signed"
        relayer = {"name": "R", "address": "0xR", "wallet": "T", "index": 5}
        unsigned_tx = {"data": "0x"}

        result = sign(MagicMock(), unsigned_tx, relayer)

        assert result == "signed"
        mock_sign.assert_called_once_with(5, "0xR", unsigned_tx)

    @patch("src.safe_transaction.trezor_1.sign_transaction")
    @patch("builtins.input", return_value="")
    def test_trezor_1_routing(self, _mock_input, mock_sign):
        mock_sign.return_value = "signed"
        relayer = {"name": "R", "address": "0xR", "wallet": "1", "index": 3}
        unsigned_tx = {"data": "0x"}

        result = sign(MagicMock(), unsigned_tx, relayer)

        assert result == "signed"
        mock_sign.assert_called_once_with(3, "0xR", unsigned_tx)

    @patch("builtins.input", return_value="")
    def test_unknown_wallet_raises(self, _mock_input):
        relayer = {"name": "R", "address": "0xR", "wallet": "X", "index": 0}

        with pytest.raises(Exception, match="Unknown or unsupported wallet type"):
            sign(MagicMock(), {}, relayer)

    def test_hot_wallet_missing_key_prints_error(self, capsys):
        relayer = {
            "name": "R",
            "address": "0xR",
            "wallet": "HOT",
            "key_name": "MISSING_KEY",
        }
        with patch.dict(os.environ, {}, clear=True):
            sign(MagicMock(), {}, relayer)
        captured = capsys.readouterr()
        assert "not found" in captured.out

    @patch("src.safe_transaction.hot_wallet.sign_transaction")
    def test_hot_wallet_returns_none_on_address_mismatch(self, mock_sign):
        mock_sign.return_value = None
        relayer = {
            "name": "R",
            "address": "0xR",
            "wallet": "HOT",
            "key_name": "TEST_KEY",
        }
        with patch.dict(os.environ, {"TEST_KEY": "0xprivatekey"}):
            result = sign(MagicMock(), {}, relayer)
        assert result is None

    @patch("src.safe_transaction.trezor_t.sign_transaction")
    @patch("builtins.input", return_value="")
    def test_trezor_t_returns_none_on_address_mismatch(self, _mock_input, mock_sign):
        mock_sign.return_value = None
        relayer = {"name": "R", "address": "0xR", "wallet": "T", "index": 0}
        result = sign(MagicMock(), {}, relayer)
        assert result is None

    @patch("src.safe_transaction.trezor_1.sign_transaction")
    @patch("builtins.input", return_value="")
    def test_trezor_1_returns_none_on_address_mismatch(self, _mock_input, mock_sign):
        mock_sign.return_value = None
        relayer = {"name": "R", "address": "0xR", "wallet": "1", "index": 0}
        result = sign(MagicMock(), {}, relayer)
        assert result is None

    @patch("src.safe_transaction.ledger_nano.sign_transaction")
    @patch("builtins.input", return_value="")
    def test_ledger_wallet_routes_to_ledger(self, _mock_input, mock_sign):
        mock_sign.return_value = MagicMock()
        relayer = {"name": "R", "address": "0xR", "wallet": "L", "index": 2}
        sign(MagicMock(), {}, relayer)
        mock_sign.assert_called_once_with(2, "0xR", {})

    @patch("src.safe_transaction.ledger_nano.sign_transaction")
    @patch("builtins.input", return_value="")
    def test_ledger_address_mismatch_returns_none(self, _mock_input, mock_sign):
        mock_sign.return_value = None
        relayer = {"name": "R", "address": "0xR", "wallet": "L", "index": 0}
        result = sign(MagicMock(), {}, relayer)
        assert result is None


class TestCreateMissingConstants:
    def test_missing_constant_key_raises(self):
        w3 = make_mock_w3()
        safe = make_mock_safe()
        incomplete = {
            k: v for k, v in RELAY_TX_CONSTANTS.items() if k != "VALUE_RELAY_TX"
        }
        with pytest.raises(KeyError):
            create(
                w3,
                safe,
                TO,
                incomplete,
                RAW_DATA,
                0,
                SIGNATURES,
                RELAYER_ADDR,
                gas=100000,
                max_fee_per_gas=100,
                max_priority_fee_per_gas=10,
            )

    def test_build_transaction_failure_propagates(self):
        w3 = make_mock_w3()
        safe = make_mock_safe()
        safe.functions.execTransaction.return_value.build_transaction.side_effect = (
            Exception("build failed")
        )
        with pytest.raises(Exception, match="build failed"):
            create(
                w3,
                safe,
                TO,
                RELAY_TX_CONSTANTS,
                RAW_DATA,
                0,
                SIGNATURES,
                RELAYER_ADDR,
                gas=100000,
                max_fee_per_gas=100,
                max_priority_fee_per_gas=10,
            )
