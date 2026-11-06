import pytest

from helpers import MULTISEND_ADDRESS
from src.utils.validate_config import (
    validate,
    validate_operation,
    validate_transactions,
)

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
        validate_operation(0, "0x1234")

    def test_valid_delegatecall(self):
        validate_operation(1, MULTISEND_ADDRESS)

    def test_valid_config(self):
        validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, VALID_CHAINS)


class TestValidateConfigOperation:
    def test_invalid_operation(self):
        with pytest.raises(Exception, match="Operation must be 0 or 1"):
            validate_operation(2, "0x1234")

    def test_delegatecall_wrong_to(self):
        with pytest.raises(Exception, match="Inconsistent input"):
            validate_operation(1, "0x0000000000000000000000000000000000000001")


class TestValidateConfigNames:
    def test_safe_name_with_parens(self):
        bad_safes = [{"name": "Owner (main)", "address": "0x1234"}]
        with pytest.raises(Exception, match="can't contain"):
            validate(bad_safes, VALID_SIGNERS, VALID_RELAYERS, VALID_CHAINS)

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
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, VALID_CHAINS)

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
            validate(VALID_SAFES, VALID_SIGNERS, bad_relayers, VALID_CHAINS)

    def test_chain_name_with_parens(self):
        bad_chains = [{"name": "Base (mainnet)", "chain_id": 8453}]
        with pytest.raises(Exception, match="can't contain"):
            validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, bad_chains)


class TestValidateConfigUniqueness:
    def test_duplicate_signer_addresses(self):
        dup_signers = [
            {"name": "Signer A", "address": "0xABC", "wallet": "T", "index": 0},
            {"name": "Signer B", "address": "0xABC", "wallet": "T", "index": 1},
        ]
        with pytest.raises(Exception, match="signing addresses must be unique"):
            validate(VALID_SAFES, dup_signers, VALID_RELAYERS, VALID_CHAINS)

    def test_duplicate_relayer_addresses(self):
        dup_relayers = [
            {"name": "Relayer A", "address": "0xABC", "wallet": "HOT", "key_name": "A"},
            {"name": "Relayer B", "address": "0xABC", "wallet": "HOT", "key_name": "B"},
        ]
        with pytest.raises(Exception, match="relayer addresses must be unique"):
            validate(VALID_SAFES, VALID_SIGNERS, dup_relayers, VALID_CHAINS)


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
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, VALID_CHAINS)

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
            validate(VALID_SAFES, VALID_SIGNERS, bad_relayers, VALID_CHAINS)

    def test_missing_wallet_type_on_signer(self):
        bad_signers = [
            {
                "name": "No Wallet",
                "address": "0x7777777777777777777777777777777777777777",
                "index": 0,
            }
        ]
        with pytest.raises(Exception, match="Invalid wallet type"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, VALID_CHAINS)

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
            validate(VALID_SAFES, signers, VALID_RELAYERS, VALID_CHAINS)


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
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, VALID_CHAINS)

    def test_hardware_wallet_missing_index(self):
        bad_signers = [
            {
                "name": "Trezor No Index",
                "address": "0x9999999999999999999999999999999999999999",
                "wallet": "T",
            }
        ]
        with pytest.raises(Exception, match="must have an 'index' field"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, VALID_CHAINS)

    def test_ledger_signer_missing_index(self):
        bad_signers = [
            {
                "name": "Ledger No Index",
                "address": "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "wallet": "L",
            }
        ]
        with pytest.raises(Exception, match="must have an 'index' field"):
            validate(VALID_SAFES, bad_signers, VALID_RELAYERS, VALID_CHAINS)


class TestValidateConfigEmptyLists:
    def test_empty_safes_passes(self):
        validate([], VALID_SIGNERS, VALID_RELAYERS, VALID_CHAINS)

    def test_empty_signers_passes(self):
        validate(VALID_SAFES, [], VALID_RELAYERS, VALID_CHAINS)

    def test_empty_relayers_passes(self):
        validate(VALID_SAFES, VALID_SIGNERS, [], VALID_CHAINS)


class TestValidateConfigOperationBoundary:
    def test_negative_operation_raises(self):
        with pytest.raises(Exception, match="Operation must be 0 or 1"):
            validate_operation(-1, "0x1234")

    def test_operation_0_with_multisend_address_allowed(self):
        validate_operation(0, MULTISEND_ADDRESS)

    def test_duplicate_chain_names_rejected(self):
        chains = [
            {"name": "Base", "chain_id": 8453},
            {"name": "Base", "chain_id": 84532},
        ]
        with pytest.raises(Exception, match="unique"):
            validate(VALID_SAFES, VALID_SIGNERS, VALID_RELAYERS, chains)

    def test_duplicate_safe_names_rejected(self):
        safes = [
            {
                "name": "Test Safe",
                "address": "0x1111111111111111111111111111111111111111",
            },
            {
                "name": "Test Safe",
                "address": "0x2222222222222222222222222222222222222222",
            },
        ]
        with pytest.raises(Exception, match="unique"):
            validate(safes, VALID_SIGNERS, VALID_RELAYERS, VALID_CHAINS)


def _transaction(**overrides):
    return {"chain": "Base", "safe": "Test Safe", "raw_data": "0x1234", **overrides}


class TestValidateTransactions:
    def test_valid(self):
        validate_transactions([_transaction()], VALID_CHAINS, VALID_SAFES)

    def test_valid_with_override(self):
        validate_transactions([_transaction(operation=0)], VALID_CHAINS, VALID_SAFES)

    def test_empty_calldata_allowed(self):
        validate_transactions([_transaction(raw_data="0x")], VALID_CHAINS, VALID_SAFES)

    def test_empty_list_rejected(self):
        with pytest.raises(Exception, match="at least one transaction"):
            validate_transactions([], VALID_CHAINS, VALID_SAFES)

    def test_unknown_chain(self):
        with pytest.raises(Exception, match="Unknown chain 'Nope' in transaction #1"):
            validate_transactions(
                [_transaction(chain="Nope")], VALID_CHAINS, VALID_SAFES
            )

    def test_unknown_safe(self):
        with pytest.raises(Exception, match="Unknown safe 'Nope' in transaction #1"):
            validate_transactions(
                [_transaction(safe="Nope")], VALID_CHAINS, VALID_SAFES
            )

    @pytest.mark.parametrize("key", ["chain", "safe", "raw_data"])
    def test_missing_key(self, key):
        transaction = _transaction()
        del transaction[key]
        with pytest.raises(Exception, match=f"transaction #1 is missing '{key}'"):
            validate_transactions([transaction], VALID_CHAINS, VALID_SAFES)

    def test_unknown_key(self):
        with pytest.raises(Exception, match="transaction #1 has unknown key 'foo'"):
            validate_transactions([_transaction(foo=1)], VALID_CHAINS, VALID_SAFES)

    @pytest.mark.parametrize("raw_data", ["1234", "0xzz", "0x123"])
    def test_bad_raw_data(self, raw_data):
        with pytest.raises(
            Exception,
            match="raw_data of transaction #1 is not 0x-prefixed even-length hex",
        ):
            validate_transactions(
                [_transaction(raw_data=raw_data)], VALID_CHAINS, VALID_SAFES
            )

    def test_numbers_are_config_positions(self):
        with pytest.raises(Exception, match="transaction #2"):
            validate_transactions(
                [_transaction(), _transaction(chain="Nope")], VALID_CHAINS, VALID_SAFES
            )

    @pytest.mark.parametrize("nonce", [0, 47, "repeat"])
    def test_valid_nonce(self, nonce):
        validate_transactions([_transaction(nonce=nonce)], VALID_CHAINS, VALID_SAFES)

    @pytest.mark.parametrize("nonce", [-1, "next", 1.5, True])
    def test_bad_nonce(self, nonce):
        with pytest.raises(
            Exception,
            match="nonce of transaction #1 must be an integer >= 0 or 'repeat'",
        ):
            validate_transactions(
                [_transaction(nonce=nonce)], VALID_CHAINS, VALID_SAFES
            )

    def test_duplicate_pin_rejected(self):
        with pytest.raises(Exception, match="transactions #1 and #2 both pin nonce 5"):
            validate_transactions(
                [_transaction(nonce=5), _transaction(nonce=5, raw_data="0xab")],
                VALID_CHAINS,
                VALID_SAFES,
            )

    def test_same_pin_on_other_safe_allowed(self):
        safes = VALID_SAFES + [
            {"name": "Other", "address": "0x2222222222222222222222222222222222222222"}
        ]
        validate_transactions(
            [_transaction(nonce=5), _transaction(nonce=5, safe="Other")],
            VALID_CHAINS,
            safes,
        )

    def test_name_allowed(self):
        validate_transactions(
            [_transaction(name="Staking rewards")], VALID_CHAINS, VALID_SAFES
        )

    @pytest.mark.parametrize("name", ["", 5])
    def test_bad_name(self, name):
        with pytest.raises(
            Exception, match="name of transaction #1 must be a non-empty string"
        ):
            validate_transactions([_transaction(name=name)], VALID_CHAINS, VALID_SAFES)

    def test_duplicate_pin_through_two_names_rejected(self):
        safes = VALID_SAFES + [
            {
                "name": "Alias",
                "address": VALID_SAFES[0]["address"].upper().replace("0X", "0x"),
            }
        ]
        with pytest.raises(Exception, match="both pin nonce 5"):
            validate_transactions(
                [_transaction(nonce=5), _transaction(nonce=5, safe="Alias")],
                VALID_CHAINS,
                safes,
            )

    def test_two_repeats_on_one_safe_rejected(self):
        with pytest.raises(
            Exception,
            match="transactions #1 and #2 are both 'repeat' on the same safe",
        ):
            validate_transactions(
                [_transaction(nonce="repeat"), _transaction(nonce="repeat")],
                VALID_CHAINS,
                VALID_SAFES,
            )

    def test_one_off_after_repeat_rejected(self):
        with pytest.raises(
            Exception,
            match="one-off transaction #2 comes after the repeat transaction #1",
        ):
            validate_transactions(
                [_transaction(nonce="repeat"), _transaction()],
                VALID_CHAINS,
                VALID_SAFES,
            )

    def test_one_off_before_repeat_allowed(self):
        validate_transactions(
            [_transaction(), _transaction(nonce="repeat")], VALID_CHAINS, VALID_SAFES
        )

    def test_repeat_with_pin_allowed(self):
        validate_transactions(
            [_transaction(nonce="repeat"), _transaction(nonce=7)],
            VALID_CHAINS,
            VALID_SAFES,
        )

    def test_repeats_on_different_safes_allowed(self):
        safes = VALID_SAFES + [
            {"name": "Other", "address": "0x2222222222222222222222222222222222222222"}
        ]
        validate_transactions(
            [_transaction(nonce="repeat"), _transaction(nonce="repeat", safe="Other")],
            VALID_CHAINS,
            safes,
        )
