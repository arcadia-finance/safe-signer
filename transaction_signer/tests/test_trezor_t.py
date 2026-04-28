from unittest.mock import MagicMock, patch

from trezorlib.transport import TransportException
from web3.datastructures import AttributeDict

from helpers import HW_SIGNER_ADDRESS as SIGNER_ADDRESS
from helpers import HW_UNSIGNED_TX as UNSIGNED_TX
from src.wallets.trezor_t import get_path, sign_transaction, sign_typed_data


class TestGetPath:
    def test_index_zero(self):
        assert get_path(0) == "m/44'/60'/0'/0/0"

    def test_index_five(self):
        assert get_path(5) == "m/44'/60'/0'/0/5"

    def test_large_index(self):
        assert get_path(999999) == "m/44'/60'/0'/0/999999"


class TestSignTypedData:
    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_returns_hex_signature(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_sig = MagicMock()
        mock_sig.signature = b"\xab" * 65
        mock_eth.sign_typed_data.return_value = mock_sig

        result = sign_typed_data(0, SIGNER_ADDRESS, {"some": "data"})

        assert result == (b"\xab" * 65).hex()

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_closes_client_on_success(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_sig = MagicMock()
        mock_sig.signature = b"\xab" * 65
        mock_eth.sign_typed_data.return_value = mock_sig

        sign_typed_data(0, SIGNER_ADDRESS, {"some": "data"})

        mock_client.close.assert_called_once()

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    @patch("src.wallets.trezor_t.parse_path")
    def test_passes_correct_args(
        self, mock_parse, mock_eth, mock_transport, mock_client_cls, mock_ui
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_sig = MagicMock()
        mock_sig.signature = b"\xab" * 65
        mock_eth.sign_typed_data.return_value = mock_sig
        mock_parse.return_value = [44, 60, 0, 0, 3]
        data = {"some": "data"}

        sign_typed_data(3, SIGNER_ADDRESS, data)

        mock_parse.assert_called_once_with("m/44'/60'/0'/0/3")
        mock_eth.sign_typed_data.assert_called_once_with(
            client=mock_client, n=[44, 60, 0, 0, 3], data=data
        )

    @patch("src.wallets.trezor_t.get_transport")
    def test_transport_exception_returns_none(self, mock_transport, capsys):
        mock_transport.side_effect = TransportException("No device")

        result = sign_typed_data(0, SIGNER_ADDRESS, {"some": "data"})

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Trezor device" in captured.out

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_address_mismatch_returns_none(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui, capsys
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = "0xwrongaddress"

        result = sign_typed_data(0, SIGNER_ADDRESS, {"some": "data"})

        assert result is None
        captured = capsys.readouterr()
        assert "does not match" in captured.out
        mock_client.close.assert_called_once()

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_get_address_exception_returns_none(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui, capsys
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.side_effect = Exception("Device error")

        result = sign_typed_data(0, SIGNER_ADDRESS, {"some": "data"})

        assert result is None
        captured = capsys.readouterr()
        assert "An error occurred" in captured.out
        mock_client.close.assert_called_once()

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_sign_typed_data_exception_returns_none(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui, capsys
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_typed_data.side_effect = Exception("Signing failed")

        result = sign_typed_data(0, SIGNER_ADDRESS, {"some": "data"})

        assert result is None
        captured = capsys.readouterr()
        assert "An error occurred" in captured.out
        mock_client.close.assert_called_once()


class TestSignTransaction:
    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_returns_attribute_dict(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert isinstance(result, AttributeDict)
        assert "raw_transaction" in result
        assert "hash" in result
        assert "r" in result
        assert "s" in result
        assert "v" in result

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_raw_transaction_eip1559_prefix(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result.raw_transaction.hex().startswith("02")

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_r_s_are_ints_v_is_original(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
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

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_closes_client_on_success(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        mock_client.close.assert_called_once()

    @patch("src.wallets.trezor_t.get_transport")
    def test_transport_exception_returns_none(self, mock_transport, capsys):
        mock_transport.side_effect = TransportException("No device")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Trezor device" in captured.out

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_address_mismatch_returns_none(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui, capsys
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = "0xwrongaddress"

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "does not match" in captured.out
        mock_client.close.assert_called_once()

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_get_address_exception_returns_none(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui, capsys
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.side_effect = Exception("Device error")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "An error occurred" in captured.out
        mock_client.close.assert_called_once()

    @patch("src.wallets.trezor_t.ClickUI")
    @patch("src.wallets.trezor_t.TrezorClient")
    @patch("src.wallets.trezor_t.get_transport")
    @patch("src.wallets.trezor_t.ethereum")
    def test_sign_tx_exception_returns_none(
        self, mock_eth, mock_transport, mock_client_cls, mock_ui, capsys
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_eth.get_address.return_value = SIGNER_ADDRESS
        mock_eth.sign_tx_eip1559.side_effect = Exception("Signing failed")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "An error occurred while signing transaction" in captured.out
        mock_client.close.assert_called_once()
