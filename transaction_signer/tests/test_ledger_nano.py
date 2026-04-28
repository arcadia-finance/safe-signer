import struct
from unittest.mock import MagicMock, patch

from ledgerblue.commException import CommException

from helpers import HW_DOMAIN_HASH as DOMAIN_HASH
from helpers import HW_MESSAGE_HASH as MESSAGE_HASH
from helpers import HW_SIGNER_ADDRESS as SIGNER_ADDRESS
from helpers import HW_UNSIGNED_TX as UNSIGNED_TX
from src.wallets.ledger_nano import (
    _sign_typed_data_hash,
    get_address,
    get_path,
    parse_bip32_path,
    sign_transaction,
    sign_typed_data_hash,
)


class TestGetPath:
    def test_index_zero(self):
        assert get_path(0) == "m/44'/60'/0'/0/0"

    def test_index_five(self):
        assert get_path(5) == "m/44'/60'/5'/0/0"

    def test_index_in_third_position_hardened(self):
        assert get_path(7) == "m/44'/60'/7'/0/0"


class TestParseBip32Path:
    def test_standard_path_bytes(self):
        result = parse_bip32_path("m/44'/60'/0'/0/0")
        expected = (
            struct.pack(">I", 0x80000000 | 44)
            + struct.pack(">I", 0x80000000 | 60)
            + struct.pack(">I", 0x80000000 | 0)
            + struct.pack(">I", 0)
            + struct.pack(">I", 0)
        )
        assert result == expected

    def test_hardened_elements_have_high_bit(self):
        result = parse_bip32_path("m/44'/60'/0'/0/0")
        first_element = struct.unpack(">I", result[0:4])[0]
        assert first_element == 0x80000000 | 44

    def test_non_hardened_elements_are_plain(self):
        result = parse_bip32_path("m/44'/60'/0'/0/0")
        fourth_element = struct.unpack(">I", result[12:16])[0]
        assert fourth_element == 0

    def test_result_length_five_elements(self):
        result = parse_bip32_path("m/44'/60'/0'/0/0")
        assert len(result) == 20

    def test_big_endian_packing(self):
        result = parse_bip32_path("m/44'/60'/0'/0/0")
        assert result[0:4] == b"\x80\x00\x00\x2c"


class TestGetAddress:
    def test_parses_address_from_apdu_response(self):
        address_str = b"1234567890abcdef1234567890abcdef12345678"
        pubkey_len = 65
        # response: pubkey_len byte, pubkey bytes, address_len byte, address ASCII
        mock_response = (
            bytes([pubkey_len])
            + b"\x00" * pubkey_len
            + bytes([len(address_str)])
            + address_str
        )
        mock_dongle = MagicMock()
        mock_dongle.exchange.return_value = mock_response
        dongle_path = parse_bip32_path("m/44'/60'/0'/0/0")

        result = get_address(mock_dongle, dongle_path)

        assert result == "0x1234567890abcdef1234567890abcdef12345678"

    def test_sends_correct_apdu_prefix(self):
        address_str = b"abcdefabcdefabcdefabcdefabcdefabcdefabcd"
        mock_response = bytes([65]) + b"\x00" * 65 + bytes([40]) + address_str
        mock_dongle = MagicMock()
        mock_dongle.exchange.return_value = mock_response
        dongle_path = parse_bip32_path("m/44'/60'/0'/0/0")

        get_address(mock_dongle, dongle_path)

        sent_apdu = mock_dongle.exchange.call_args[0][0]
        assert sent_apdu[:4] == bytes.fromhex("e0020100")


class TestInternalSignTypedDataHash:
    def test_sends_correct_apdu_command(self):
        mock_dongle = MagicMock()
        v = b"\x1b"
        r = b"\x01" * 32
        s = b"\x02" * 32
        mock_dongle.exchange.return_value = v + r + s
        dongle_path = parse_bip32_path("m/44'/60'/0'/0/0")

        _sign_typed_data_hash(mock_dongle, dongle_path, DOMAIN_HASH, MESSAGE_HASH)

        sent_apdu = mock_dongle.exchange.call_args[0][0]
        assert sent_apdu[:4] == bytes.fromhex("e00c0000")

    def test_payload_contains_path_and_hashes(self):
        mock_dongle = MagicMock()
        mock_dongle.exchange.return_value = b"\x1b" + b"\x01" * 32 + b"\x02" * 32
        dongle_path = parse_bip32_path("m/44'/60'/0'/0/0")

        _sign_typed_data_hash(mock_dongle, dongle_path, DOMAIN_HASH, MESSAGE_HASH)

        sent_apdu = mock_dongle.exchange.call_args[0][0]
        # Payload starts after command (4) + length (1) + path count (1)
        payload_start = 6
        payload = sent_apdu[payload_start:]
        assert dongle_path in payload
        assert DOMAIN_HASH in payload
        assert MESSAGE_HASH in payload

    def test_returns_r_s_v_concatenated(self):
        mock_dongle = MagicMock()
        v = b"\x1b"
        r = b"\xaa" * 32
        s = b"\xbb" * 32
        mock_dongle.exchange.return_value = v + r + s

        dongle_path = parse_bip32_path("m/44'/60'/0'/0/0")
        result = _sign_typed_data_hash(
            mock_dongle, dongle_path, DOMAIN_HASH, MESSAGE_HASH
        )

        # Source reorders to r + s + v
        assert result == r + s + v
        assert len(result) == 65


class TestSignTypedDataHash:
    @patch("src.wallets.ledger_nano._sign_typed_data_hash")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_returns_hex_signature(self, mock_get_dongle, mock_get_addr, mock_sign):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign.return_value = b"\xab" * 65

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result == (b"\xab" * 65).hex()

    @patch("src.wallets.ledger_nano._sign_typed_data_hash")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_prints_hashes_before_signing(
        self, mock_get_dongle, mock_get_addr, mock_sign, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign.return_value = b"\xab" * 65

        sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        captured = capsys.readouterr()
        assert DOMAIN_HASH.hex() in captured.out
        assert MESSAGE_HASH.hex() in captured.out

    @patch("src.wallets.ledger_nano._sign_typed_data_hash")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_closes_dongle_on_success(self, mock_get_dongle, mock_get_addr, mock_sign):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign.return_value = b"\xab" * 65

        sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano._sign_typed_data_hash")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_signature_is_r_s_v(self, mock_get_dongle, mock_get_addr, mock_sign):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        sig_bytes = b"\x01" * 32 + b"\x02" * 32 + b"\x1b"
        mock_sign.return_value = sig_bytes

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result == sig_bytes.hex()
        assert len(bytes.fromhex(result)) == 65

    @patch("src.wallets.ledger_nano.getDongle")
    def test_comm_exception_on_get_dongle_returns_none(self, mock_get_dongle, capsys):
        mock_get_dongle.side_effect = CommException("connection failed", 0x6985)

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Ledger device" in captured.out

    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_address_mismatch_returns_none(
        self, mock_get_dongle, mock_get_addr, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = "0xwrongaddress"

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        captured = capsys.readouterr()
        assert "does not match" in captured.out
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_comm_exception_during_get_address(
        self, mock_get_dongle, mock_get_addr, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.side_effect = CommException("comm fail", 0x6985)

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Ledger device" in captured.out
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_generic_exception_during_get_address(
        self, mock_get_dongle, mock_get_addr, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.side_effect = Exception("unexpected failure")

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano._sign_typed_data_hash")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_comm_exception_during_signing(
        self, mock_get_dongle, mock_get_addr, mock_sign, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign.side_effect = CommException("signing comm fail", 0x6985)

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Ledger device" in captured.out
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano._sign_typed_data_hash")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_generic_exception_during_signing(
        self, mock_get_dongle, mock_get_addr, mock_sign, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign.side_effect = Exception("signing blew up")

        result = sign_typed_data_hash(0, SIGNER_ADDRESS, DOMAIN_HASH, MESSAGE_HASH)

        assert result is None
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out
        mock_dongle.close.assert_called_once()


class TestSignTransaction:
    @patch("src.wallets.ledger_nano._sign_transaction")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_returns_attribute_dict(self, mock_get_dongle, mock_get_addr, mock_sign_tx):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign_tx.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is not None
        assert hasattr(result, "raw_transaction")
        assert hasattr(result, "hash")
        assert hasattr(result, "r")
        assert hasattr(result, "s")
        assert hasattr(result, "v")

    @patch("src.wallets.ledger_nano._sign_transaction")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_raw_transaction_eip1559_prefix(
        self, mock_get_dongle, mock_get_addr, mock_sign_tx
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign_tx.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result.raw_transaction.hex().startswith("0x02")

    @patch("src.wallets.ledger_nano._sign_transaction")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_r_s_are_ints_v_is_original(
        self, mock_get_dongle, mock_get_addr, mock_sign_tx
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign_tx.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert isinstance(result.r, int)
        assert isinstance(result.s, int)
        assert result.r == int.from_bytes(b"\x01" * 32, "big")
        assert result.s == int.from_bytes(b"\x02" * 32, "big")
        assert result.v == 1

    @patch("src.wallets.ledger_nano._sign_transaction")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_closes_dongle_on_success(
        self, mock_get_dongle, mock_get_addr, mock_sign_tx
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign_tx.return_value = (1, b"\x01" * 32, b"\x02" * 32)

        sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano.getDongle")
    def test_comm_exception_on_get_dongle_returns_none(self, mock_get_dongle, capsys):
        mock_get_dongle.side_effect = CommException("connection failed", 0x6985)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Ledger device" in captured.out

    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_address_mismatch_returns_none(
        self, mock_get_dongle, mock_get_addr, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = "0xwrongaddress"

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "does not match" in captured.out
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_comm_exception_during_get_address(
        self, mock_get_dongle, mock_get_addr, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.side_effect = CommException("comm fail", 0x6985)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_generic_exception_during_get_address(
        self, mock_get_dongle, mock_get_addr, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.side_effect = Exception("unexpected failure")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano._sign_transaction")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_comm_exception_during_signing(
        self, mock_get_dongle, mock_get_addr, mock_sign_tx, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign_tx.side_effect = CommException("signing comm fail", 0x6985)

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "Error communicating with Ledger device" in captured.out
        mock_dongle.close.assert_called_once()

    @patch("src.wallets.ledger_nano._sign_transaction")
    @patch("src.wallets.ledger_nano.get_address")
    @patch("src.wallets.ledger_nano.getDongle")
    def test_generic_exception_during_signing(
        self, mock_get_dongle, mock_get_addr, mock_sign_tx, capsys
    ):
        mock_dongle = MagicMock()
        mock_get_dongle.return_value = mock_dongle
        mock_get_addr.return_value = SIGNER_ADDRESS
        mock_sign_tx.side_effect = Exception("signing blew up")

        result = sign_transaction(0, SIGNER_ADDRESS, UNSIGNED_TX)

        assert result is None
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out
        mock_dongle.close.assert_called_once()
