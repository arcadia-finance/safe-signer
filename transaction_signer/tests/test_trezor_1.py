from unittest.mock import MagicMock, patch

import pytest

from trezorlib.cli import get_passphrase
from trezorlib.exceptions import Cancelled
from trezorlib.transport import TransportException

from helpers import HW_DOMAIN_HASH as DOMAIN_HASH
from helpers import HW_MESSAGE_HASH as MESSAGE_HASH
from helpers import HW_SIGNER_ADDRESS as SIGNER_ADDRESS
from helpers import HW_UNSIGNED_TX as UNSIGNED_TX
from src.wallets.trezor_1 import (
    _get_client,
    get_path,
    sign_transaction,
    sign_typed_data_hash,
)


class TestGetPath:
    def test_index_zero(self):
        assert get_path(0) == "m/44'/60'/0'/0/0"

    def test_index_five(self):
        assert get_path(5) == "m/44'/60'/0'/0/5"

    def test_large_index(self):
        assert get_path(999999) == "m/44'/60'/0'/0/999999"


class TestSignTypedDataHash:
    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_returns_hex_signature(self, mock_eth, mock_get_session, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_sig = MagicMock()
        mock_sig.signature = b"\xab" * 65
        mock_eth.sign_typed_data_hash.return_value = mock_sig

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result == (b"\xab" * 65).hex()

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_exits_client_on_success(self, mock_eth, mock_get_session, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_sig = MagicMock()
        mock_sig.signature = b"\xab" * 65
        mock_eth.sign_typed_data_hash.return_value = mock_sig

        sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        mock_client.__exit__.assert_called_once()

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_passes_correct_args_to_sign(
        self, mock_eth, mock_get_session, mock_get_client
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_sig = MagicMock()
        mock_sig.signature = b"\xab" * 65
        mock_eth.sign_typed_data_hash.return_value = mock_sig

        sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        mock_get_session.assert_called_once_with(
            mock_client, passphrase_callback=get_passphrase
        )
        call_kwargs = mock_eth.sign_typed_data_hash.call_args
        assert call_kwargs.args[0] == mock_get_session.return_value
        assert call_kwargs.kwargs["domain_hash"] == DOMAIN_HASH
        assert call_kwargs.kwargs["message_hash"] == MESSAGE_HASH

    @patch("src.wallets.trezor_1._find_transport")
    def test_transport_exception_returns_none(self, mock_find_transport, capsys):
        mock_find_transport.side_effect = TransportException("no device")

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Trezor device" in captured.out

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_address_mismatch_returns_none(
        self, mock_eth, mock_get_session, mock_get_client, capsys
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = "0xwrongaddress"

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        mock_client.__exit__.assert_called_once()
        captured = capsys.readouterr()
        assert "does not match" in captured.out

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_get_address_exception_returns_none(
        self, mock_eth, mock_get_session, mock_get_client, capsys
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.side_effect = Exception("device error")

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        mock_client.__exit__.assert_called_once()
        captured = capsys.readouterr()
        assert "An error occurred" in captured.out

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_sign_exception_returns_none(
        self, mock_eth, mock_get_session, mock_get_client, capsys
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_typed_data_hash.side_effect = Exception("signing failed")

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        mock_client.__exit__.assert_called_once()
        captured = capsys.readouterr()
        assert "An error occurred" in captured.out


class TestSignTransaction:
    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_returns_attribute_dict(self, mock_eth, mock_get_session, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is not None
        assert hasattr(result, "raw_transaction")
        assert hasattr(result, "hash")
        assert hasattr(result, "r")
        assert hasattr(result, "s")
        assert hasattr(result, "v")

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_raw_transaction_eip1559_prefix(
        self, mock_eth, mock_get_session, mock_get_client
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result.raw_transaction.hex().startswith("02")

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_r_s_are_ints_v_is_original(
        self, mock_eth, mock_get_session, mock_get_client
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        v_val = 1
        r_val = b"\x01" * 32
        s_val = b"\x02" * 32
        mock_eth.sign_tx_eip1559.return_value = (v_val, r_val, s_val)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert isinstance(result.r, int)
        assert isinstance(result.s, int)
        assert result.r == int.from_bytes(r_val, "big")
        assert result.s == int.from_bytes(s_val, "big")
        assert result.v == v_val

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_exits_client_on_success(self, mock_eth, mock_get_session, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        mock_client.__exit__.assert_called_once()

    @patch("src.wallets.trezor_1._find_transport")
    def test_transport_exception_returns_none(self, mock_find_transport, capsys):
        mock_find_transport.side_effect = TransportException("no device")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Trezor device" in captured.out

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_address_mismatch_returns_none(
        self, mock_eth, mock_get_session, mock_get_client, capsys
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = "0xwrongaddress"

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        mock_client.__exit__.assert_called_once()
        captured = capsys.readouterr()
        assert "does not match" in captured.out

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_get_address_exception_returns_none(
        self, mock_eth, mock_get_session, mock_get_client, capsys
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.side_effect = Exception("device error")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        mock_client.__exit__.assert_called_once()
        captured = capsys.readouterr()
        assert "An error occurred" in captured.out

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_sign_tx_exception_returns_none(
        self, mock_eth, mock_get_session, mock_get_client, capsys
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.side_effect = Exception("signing failed")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        mock_client.__exit__.assert_called_once()
        captured = capsys.readouterr()
        assert "An error occurred while signing transaction" in captured.out


class TestDeviceCallsUseTheSession:
    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_typed_data_hash_flow(self, mock_eth, mock_get_session, mock_get_client):
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_typed_data_hash.return_value.signature = b"\xab" * 65

        assert (
            sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)
            is not None
        )

        assert [c[0] for c in mock_eth.method_calls] == [
            "get_address",
            "sign_typed_data_hash",
        ]
        for call in mock_eth.method_calls:
            assert call.args[0] is mock_get_session.return_value

    @patch("src.wallets.trezor_1._get_client")
    @patch("src.wallets.trezor_1.get_default_session")
    @patch("src.wallets.trezor_1.ethereum")
    def test_transaction_flow(self, mock_eth, mock_get_session, mock_get_client):
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        assert sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX) is not None

        assert [c[0] for c in mock_eth.method_calls] == [
            "get_address",
            "sign_tx_eip1559",
        ]
        for call in mock_eth.method_calls:
            assert call.args[0] is mock_get_session.return_value


class TestNonTransportTrezorErrors:
    @patch("src.wallets.trezor_1.get_default_client")
    @patch("src.wallets.trezor_1._find_transport")
    def test_cancelled_while_connecting_returns_none(
        self, mock_find_transport, mock_get_default_client, capsys
    ):
        mock_get_default_client.side_effect = Cancelled()

        assert (
            sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH) is None
        )
        assert sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX) is None
        assert (
            capsys.readouterr().out.count("Error communicating with Trezor device") == 2
        )


class TestGetClient:
    @patch("src.wallets.trezor_1.get_default_client")
    @patch("src.wallets.trezor_1.BleTransport")
    @patch("src.wallets.trezor_1.all_transports")
    def test_skips_ble_and_stops_at_first_device(
        self, mock_all_transports, mock_ble, mock_get_default_client, monkeypatch
    ):
        monkeypatch.delenv("TREZOR_PATH", raising=False)
        hid, webusb, bridge = MagicMock(), MagicMock(), MagicMock()
        hid.enumerate.return_value = []
        webusb.enumerate.return_value = ["device"]
        mock_all_transports.return_value = [hid, mock_ble, webusb, bridge]

        _get_client()

        mock_ble.enumerate.assert_not_called()
        bridge.enumerate.assert_not_called()
        assert mock_get_default_client.call_args.args[1] == "device"

    @patch("src.wallets.trezor_1.get_default_client")
    @patch("src.wallets.trezor_1.all_transports")
    def test_no_device_raises(
        self, mock_all_transports, mock_get_default_client, monkeypatch
    ):
        monkeypatch.delenv("TREZOR_PATH", raising=False)
        hid = MagicMock()
        hid.enumerate.return_value = []
        mock_all_transports.return_value = [hid]

        with pytest.raises(TransportException):
            _get_client()
        mock_get_default_client.assert_not_called()

    @patch("src.wallets.trezor_1.get_default_client")
    @patch("src.wallets.trezor_1.all_transports")
    def test_trezor_path_overrides_discovery(
        self, mock_all_transports, mock_get_default_client, monkeypatch
    ):
        monkeypatch.setenv("TREZOR_PATH", "udp:127.0.0.1:21324")

        _get_client()

        mock_all_transports.assert_not_called()
        assert mock_get_default_client.call_args.args[1] == "udp:127.0.0.1:21324"
