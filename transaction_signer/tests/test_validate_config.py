import pytest

from helpers import MULTISEND_ADDRESS
from src.utils.validate_config import validate

VALID_SAFES = [
    {"name": "Test Safe", "address": "0x1111111111111111111111111111111111111111"}
]
VALID_SIGNERS = [
    {
        "name": "Signer One",
        "address": "0x2222222222222222222222222222222222222222",
        "wallet": "T",
        "index": 0,
    }
]
VALID_RELAYERS = [
    {
        "name": "Relayer One",
        "address": "0x3333333333333333333333333333333333333333",
        "wallet": "HOT",
        "key_name": "KEY_TEST",
    }
]
VALID_CHAINS = [
    {"name": "Base", "chain_id": 8453},
]


class TestValidateConfigHappyPath:
    def test_valid_call(self):
        validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, 0, "0x1234")

    def test_valid_delegatecall(self):
        validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, 1, MULTISEND_ADDRESS)

    def test_valid_with_chains(self):
        validate(
            VALID_SAFES,
            VALID_SIGNERS,
            VALID_RELAYERS,
            0,
            "0x1234",
            chains=VALID_CHAINS,
        )


class TestValidateConfigOperation:
    def test_invalid_operation(self):
        with pytest.raises(Exception, match="Operation must be 0 or 1"):
            validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, 2, "0x1234")

    def test_delegatecall_wrong_to(self):
        with pytest.raises(Exception, match="Inconsistent input"):
            validate(
                VALID_SAFES,
                VALID_SIGNERS,
                VALID_RELAYERS,
                1,
                "0x0000000000000000000000000000000000000001",
            )


class TestValidateConfigNames:
    def test_safe_name_with_parens(self):
        bad_safes = [{"name": "Owner (main)", "address": "0x1234"}]
        with pytest.raises(Exception, match="can't contain"):
            validate(bad_safes, VALID_SIGNERS, VALID_RELAYERS, 0, "0x1234")

    def test_signer_name_with_parens(self):
        bad_signers = [
            {
                "name": "Signer (bad)",
                "address": "0x4444444444444444444444444444444444444444",
                "wallet": "T",
                "index": 0,
            }
        ]
        with pytest.raises(Exception, match="can't contain"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, 0, "0x1234")

    def test_relayer_name_with_parens(self):
        bad_relayers = [
            {
                "name": "Relayer (bad)",
                "address": "0x3333333333333333333333333333333333333333",
                "wallet": "HOT",
                "key_name": "KEY_TEST",
            }
        ]
        with pytest.raises(Exception, match="can't contain"):
            validate(VALID_SAFES, VALID_SIGNERS, bad_relayers, 0, "0x1234")

    def test_chain_name_with_parens(self):
        bad_chains = [{"name": "Base (mainnet)", "chain_id": 8453}]
        with pytest.raises(Exception, match="can't contain"):
            validate(
                VALID_SAFES,
                VALID_SIGNERS,
                VALID_RELAYERS,
                0,
                "0x1234",
                chains=bad_chains,
            )


class TestValidateConfigUniqueness:
    def test_duplicate_signer_addresses(self):
        dup_signers = [
            {"name": "Signer A", "address": "0xABC", "wallet": "T", "index": 0},
            {"name": "Signer B", "address": "0xABC", "wallet": "T", "index": 1},
        ]
        with pytest.raises(Exception, match="signing addresses must be unique"):
            validate(VALID_SAFES, dup_signers, VALID_RELAYERS, 0, "0x1234")

    def test_duplicate_relayer_addresses(self):
        dup_relayers = [
            {"name": "Relayer A", "address": "0xABC", "wallet": "HOT", "key_name": "A"},
            {"name": "Relayer B", "address": "0xABC", "wallet": "HOT", "key_name": "B"},
        ]
        with pytest.raises(Exception, match="relayer addresses must be unique"):
            validate(VALID_SAFES, VALID_SIGNERS, dup_relayers, 0, "0x1234")


class TestValidateConfigWalletTypes:
    def test_invalid_signer_wallet_type(self):
        bad_signers = [
            {
                "name": "Signer Bad",
                "address": "0x5555555555555555555555555555555555555555",
                "wallet": "INVALID",
                "index": 0,
            }
        ]
        with pytest.raises(Exception, match="Invalid wallet type"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, 0, "0x1234")

    def test_invalid_relayer_wallet_type(self):
        bad_relayers = [
            {
                "name": "Relayer Bad",
                "address": "0x6666666666666666666666666666666666666666",
                "wallet": "X",
                "key_name": "KEY",
            }
        ]
        with pytest.raises(Exception, match="Invalid wallet type"):
            validate(VALID_SAFES, VALID_SIGNERS, bad_relayers, 0, "0x1234")

    def test_missing_wallet_type_on_signer(self):
        bad_signers = [
            {
                "name": "No Wallet",
                "address": "0x7777777777777777777777777777777777777777",
                "index": 0,
            }
        ]
        with pytest.raises(Exception, match="Invalid wallet type"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, 0, "0x1234")

    def test_all_valid_wallet_types_accepted(self):
        for wtype in ["HOT", "T", "1", "L"]:
            extra = {"key_name": "K"} if wtype == "HOT" else {"index": 0}
            signers = [
                {
                    "name": f"Signer {wtype}",
                    "address": "0x2222222222222222222222222222222222222222",
                    "wallet": wtype,
                    **extra,
                }
            ]
            validate(VALID_SAFES, signers, VALID_RELAYERS, 0, "0x1234")


class TestValidateConfigWalletFields:
    def test_hot_wallet_missing_key_name(self):
        bad_signers = [
            {
                "name": "Hot No Key",
                "address": "0x8888888888888888888888888888888888888888",
                "wallet": "HOT",
                "index": 0,
            }
        ]
        with pytest.raises(Exception, match="must have a 'key_name' field"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, 0, "0x1234")

    def test_hardware_wallet_missing_index(self):
        bad_signers = [
            {
                "name": "Trezor No Index",
                "address": "0x9999999999999999999999999999999999999999",
                "wallet": "T",
            }
        ]
        with pytest.raises(Exception, match="must have an 'index' field"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, 0, "0x1234")

    def test_ledger_signer_missing_index(self):
        bad_signers = [
            {
                "name": "Ledger No Index",
                "address": "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "wallet": "L",
            }
        ]
        with pytest.raises(Exception, match="must have an 'index' field"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, 0, "0x1234")


class TestValidateConfigEmptyLists:
    def test_empty_safes_passes(self):
        validate([], VALID_SIGNERS, VALID_RELAYERS, 0, "0x1234")

    def test_empty_signers_passes(self):
        validate(VALID_SAFES, [], VALID_RELAYERS, 0, "0x1234")

    def test_empty_relayers_passes(self):
        validate(VALID_SAFES, VALID_SIGNERS, [], 0, "0x1234")


class TestValidateConfigOperationBoundary:
    def test_negative_operation_raises(self):
        with pytest.raises(Exception, match="Operation must be 0 or 1"):
            validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, -1, "0x1234")

    def test_operation_0_with_multisend_address_allowed(self):
        validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, 0, MULTISEND_ADDRESS)
