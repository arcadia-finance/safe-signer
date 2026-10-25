import json
import os
from unittest.mock import MagicMock, patch

import pytest
import toml
from eth_abi import encode
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak
from web3 import Web3
from web3.providers import BaseProvider

from src import safe_transaction
from src.eip712_typed_data import get_typed_data, get_typed_data_hash
from src.utils import signatures
from src.wallets import ledger_nano, trezor_1, trezor_t
from src.wallets.hot_wallet import sign_typed_data

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")

THROWAWAY_KEY = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f3082e0e50e2872f62"
THROWAWAY_ADDRESS = Account.from_key(THROWAWAY_KEY).address

SAFE_ADDRESS = "0x48aa867Bf61A4B1d850Db76014AA34E4dA8F3367"
MULTISEND_ADDRESS = "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B"
CHAIN_ID = 8453
SAFE_NONCE = 42
RELAYER_NONCE = 7
GAS = 250000
MAX_FEE_PER_GAS = 2000000000
MAX_PRIORITY_FEE_PER_GAS = 1000000
RAW_DATA = (
    "0x8d80ff0a"
    "0000000000000000000000000000000000000000000000000000000000000020"
    "0000000000000000000000000000000000000000000000000000000000000099"
    "00bf5bec5a2711719b5a2c344d17fbc276726ab1b1"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000044"
    "095ea7b3"
    "0000000000000000000000000000000000000000000000000000000000000001"
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    "00000000000000"
)

DOMAIN_TYPEHASH = keccak(text="EIP712Domain(uint256 chainId,address verifyingContract)")
DOMAIN_HASH = keccak(
    encode(["bytes32", "uint256", "address"], [DOMAIN_TYPEHASH, CHAIN_ID, SAFE_ADDRESS])
)

EXPECTED_TRANSACTION_HASH = (
    "af759cf7cdd521922c8c75f10bf3de4c18faec8227f1d4577bf246d5c76134c4"
)
EXPECTED_SIGNATURE = (
    "205e2befebef930db5015e498b70c81791121efc7a346f217df50877fa10eb3b"
    "62539494e141ad7adf6035893fd2ce14ba5f3212122c49db1d6bb24e0c4daf3c"
    "1b"
)
EXPECTED_RAW_TRANSACTION = (
    "02f9035282210507830f424084773594008303d0909448aa867bf61a4b1d850d"
    "b76014aa34e4da8f336780b902e46a761202000000000000000000000000a1da"
    "bef33b3b82c7814b6d82a79e50f4ac44102b0000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000001400000000000000000000000000000"
    "0000000000000000000000000000000000010000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000000000000000002600000000000000000000000000000"
    "0000000000000000000000000000000000e48d80ff0a00000000000000000000"
    "0000000000000000000000000000000000000000002000000000000000000000"
    "0000000000000000000000000000000000000000009900bf5bec5a2711719b5a"
    "2c344d17fbc276726ab1b1000000000000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000000000000000044095ea7b30000000000000000000000000000000000"
    "000000000000000000000000000001ffffffffffffffffffffffffffffffffff"
    "ffffffffffffffffffffffffffffff0000000000000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "000000000000000000000000000000000041205e2befebef930db5015e498b70"
    "c81791121efc7a346f217df50877fa10eb3b62539494e141ad7adf6035893fd2"
    "ce14ba5f3212122c49db1d6bb24e0c4daf3c1b00000000000000000000000000"
    "000000000000000000000000000000000000c080a05c11e376f9afcd8915ce41"
    "67c4b1f23d877b920347fb84a96866172eea3e9688a041726e22cf5d7836bc09"
    "8be7127fe717a0aeae24c6bcd8132cc50b95988055fe"
)
EXPECTED_TX_HASH = "20790c309dca06352645d8ee0ac011dd261fe09ba46650839deabe9bcdb01196"


class FakeProvider(BaseProvider):
    def __init__(self):
        super().__init__()
        self.call_results = {
            keccak(text="getChainId()")[:4]: encode(["uint256"], [CHAIN_ID]),
            keccak(text="nonce()")[:4]: encode(["uint256"], [SAFE_NONCE]),
            keccak(text="domainSeparator()")[:4]: DOMAIN_HASH,
        }

    def is_connected(self, show_traceback=False):
        return True

    def make_request(self, method, params):
        if method == "eth_call":
            selector = bytes.fromhex(params[0]["data"][2:10])
            result = "0x" + self.call_results[selector].hex()
        elif method == "eth_chainId":
            result = hex(CHAIN_ID)
        elif method == "eth_getTransactionCount":
            result = hex(RELAYER_NONCE)
        elif method == "eth_estimateGas":
            result = hex(200000)
        elif method == "eth_maxPriorityFeePerGas":
            result = hex(MAX_PRIORITY_FEE_PER_GAS)
        elif method == "eth_gasPrice":
            result = hex(1000000000)
        elif method == "eth_getBlockByNumber":
            result = {"number": "0x1", "baseFeePerGas": hex(1000000000)}
        else:
            raise NotImplementedError(method)
        return {"jsonrpc": "2.0", "id": 1, "result": result}


@pytest.fixture
def w3():
    return Web3(FakeProvider())


@pytest.fixture
def safe(w3):
    with open(os.path.join(PROJECT_DIR, "data/abis", "safe.json")) as f:
        abi = json.loads(f.read())
    return w3.eth.contract(address=SAFE_ADDRESS, abi=abi)


@pytest.fixture
def constants():
    return toml.load(os.path.join(PROJECT_DIR, "data/constants.toml"))


@pytest.fixture
def typed_data(safe, constants):
    return get_typed_data(safe, MULTISEND_ADDRESS, RAW_DATA, 1, constants)


@pytest.fixture
def signed_relay_tx(w3, safe, constants, typed_data, monkeypatch):
    signature = sign_typed_data(THROWAWAY_KEY, THROWAWAY_ADDRESS, w3, typed_data)
    packed = signatures.concatenate(
        signatures.sort_by_signer({THROWAWAY_ADDRESS: signature})
    )
    unsigned = safe_transaction.create(
        w3,
        safe,
        MULTISEND_ADDRESS,
        constants,
        RAW_DATA,
        1,
        packed,
        THROWAWAY_ADDRESS,
        GAS,
        MAX_FEE_PER_GAS,
        MAX_PRIORITY_FEE_PER_GAS,
    )
    monkeypatch.setenv("GOLDEN_RELAYER_KEY", THROWAWAY_KEY)
    relayer = {
        "name": "golden",
        "address": THROWAWAY_ADDRESS,
        "wallet": "HOT",
        "key_name": "GOLDEN_RELAYER_KEY",
    }
    return unsigned, safe_transaction.sign(w3, unsigned, relayer)


def test_transaction_hash(safe, constants, typed_data):
    domain_hash = safe.functions.domainSeparator().call()
    message_hash = get_typed_data_hash(typed_data)
    msg_to_sign = (
        Web3.to_bytes(hexstr=constants["SIGN_MAGIC"]) + domain_hash + message_hash
    )
    transaction_hash = keccak(msg_to_sign).hex()

    assert transaction_hash == EXPECTED_TRANSACTION_HASH
    assert encode_typed_data(full_message=typed_data).body == message_hash
    assert encode_typed_data(full_message=typed_data).header == domain_hash


def test_typed_data_signature(w3, typed_data):
    signature = sign_typed_data(THROWAWAY_KEY, THROWAWAY_ADDRESS, w3, typed_data)

    assert signature == EXPECTED_SIGNATURE
    assert (
        signatures._record_error(
            [EXPECTED_TRANSACTION_HASH, THROWAWAY_ADDRESS, signature]
        )
        is None
    )
    recovered = Account.recover_message(
        encode_typed_data(full_message=typed_data),
        signature=bytes.fromhex(signature),
    )
    assert recovered == THROWAWAY_ADDRESS


def test_hot_wallet_relay_transaction(signed_relay_tx):
    _, signed = signed_relay_tx

    assert signed.raw_transaction.hex() == EXPECTED_RAW_TRANSACTION
    assert signed.hash.hex() == EXPECTED_TX_HASH
    assert keccak(signed.raw_transaction).hex() == EXPECTED_TX_HASH


@pytest.mark.parametrize("module", [trezor_t, trezor_1])
def test_trezor_relay_encoding(module, signed_relay_tx):
    unsigned, signed = signed_relay_tx
    r = signed.r.to_bytes(32, "big")
    s = signed.s.to_bytes(32, "big")
    name = module.__name__
    with (
        patch(f"{name}._get_client"),
        patch(f"{name}.get_default_session"),
        patch(f"{name}.ethereum") as ethereum,
    ):
        ethereum.get_address.return_value = THROWAWAY_ADDRESS
        ethereum.sign_tx_eip1559.return_value = (signed.v, r, s)
        result = module.sign_transaction(0, THROWAWAY_ADDRESS, unsigned)

    assert result.raw_transaction.hex() == EXPECTED_RAW_TRANSACTION
    assert result.hash.hex() == EXPECTED_TX_HASH


def test_ledger_relay_encoding(signed_relay_tx):
    unsigned, signed = signed_relay_tx
    r = signed.r.to_bytes(32, "big")
    s = signed.s.to_bytes(32, "big")
    with (
        patch.object(ledger_nano, "getDongle", return_value=MagicMock()),
        patch.object(ledger_nano, "get_address", return_value=THROWAWAY_ADDRESS),
        patch.object(ledger_nano, "_sign_transaction", return_value=(signed.v, r, s)),
    ):
        result = ledger_nano.sign_transaction(0, THROWAWAY_ADDRESS, unsigned)

    assert result.raw_transaction.hex() == EXPECTED_RAW_TRANSACTION
    assert result.hash.hex() == EXPECTED_TX_HASH
