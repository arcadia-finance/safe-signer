import json
import os

import pytest
import toml
from eth_account import Account
from eth_account.messages import encode_typed_data
from trezorlib.client import get_default_client
from trezorlib.debuglink import DebugLink
from trezorlib.transport import get_transport
from web3 import Web3

import test_golden_signing as golden
from src import eip712_typed_data, safe_transaction
from src.eip712_typed_data import get_typed_data, get_typed_data_hash
from src.utils import signatures
from src.wallets import hot_wallet, trezor_1, trezor_t

pytestmark = pytest.mark.skipif(
    os.getenv("TREZOR_EMULATOR") != "1",
    reason="needs a Trezor emulator loaded with the 'all all ... all' mnemonic, set TREZOR_EMULATOR=1",
)

TREZOR_PATH = os.getenv("TREZOR_PATH", "udp:127.0.0.1:21324")
MNEMONIC = " ".join(["all"] * 12)
EMULATOR_ADDRESS = "0x73d0385F4d8E00C5e6504C6030F47BF6212736A8"

Account.enable_unaudited_hdwallet_features()
EMULATOR_KEY = Account.from_mnemonic(
    MNEMONIC, account_path=trezor_t.get_path(0)
).key.to_0x_hex()
WRONG_ADDRESS = golden.THROWAWAY_ADDRESS


class EmulatorUI:
    def __init__(self, debug: DebugLink):
        self.debug = debug

    def button_request(self, br):
        self.debug.press_yes()

    def get_pin(self, request):
        raise AssertionError("Emulator must not have a PIN set")


@pytest.fixture
def emulator(monkeypatch):
    monkeypatch.setenv("TREZOR_PATH", TREZOR_PATH)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    debug = DebugLink(get_transport(TREZOR_PATH).find_debug())
    for module in (trezor_t, trezor_1):
        monkeypatch.setattr(module, "ClickUI", lambda: EmulatorUI(debug))
    client = get_default_client("transaction-signer-test")
    with client:
        model = client.features.model
    yield {"T": trezor_t, "1": trezor_1}[model], model
    debug.close()


@pytest.fixture
def w3():
    return Web3(golden.FakeProvider())


@pytest.fixture
def safe(w3):
    with open(os.path.join(golden.PROJECT_DIR, "data/abis", "safe.json")) as f:
        abi = json.loads(f.read())
    return w3.eth.contract(address=golden.SAFE_ADDRESS, abi=abi)


@pytest.fixture
def constants():
    return toml.load(os.path.join(golden.PROJECT_DIR, "data/constants.toml"))


@pytest.fixture
def typed_data(safe, constants):
    return get_typed_data(safe, golden.MULTISEND_ADDRESS, golden.RAW_DATA, 1, constants)


@pytest.fixture
def unsigned_relay_tx(w3, safe, constants, typed_data):
    signature = hot_wallet.sign_typed_data(
        EMULATOR_KEY, EMULATOR_ADDRESS, w3, typed_data
    )
    packed = signatures.concatenate(
        signatures.sort_by_signer({EMULATOR_ADDRESS: signature})
    )
    return safe_transaction.create(
        w3,
        safe,
        golden.MULTISEND_ADDRESS,
        constants,
        golden.RAW_DATA,
        1,
        packed,
        EMULATOR_ADDRESS,
        golden.GAS,
        golden.MAX_FEE_PER_GAS,
        golden.MAX_PRIORITY_FEE_PER_GAS,
    )


def test_mnemonic_key_matches_known_address():
    assert Account.from_key(EMULATOR_KEY).address == EMULATOR_ADDRESS


def test_typed_data_signature(emulator, w3, safe, typed_data):
    _, model = emulator
    signer = {
        "name": "emulator",
        "address": EMULATOR_ADDRESS,
        "wallet": model,
        "index": 0,
    }
    domain_hash = safe.functions.domainSeparator().call()
    message_hash = get_typed_data_hash(typed_data)

    signature = eip712_typed_data.sign(
        w3, signer, typed_data, domain_hash, message_hash
    )

    expected = hot_wallet.sign_typed_data(
        EMULATOR_KEY, EMULATOR_ADDRESS, w3, typed_data
    )
    assert signature == expected
    recovered = Account.recover_message(
        encode_typed_data(full_message=typed_data),
        signature=bytes.fromhex(signature),
    )
    assert recovered == EMULATOR_ADDRESS


def test_relay_transaction(emulator, w3, unsigned_relay_tx):
    _, model = emulator
    relayer = {
        "name": "emulator",
        "address": EMULATOR_ADDRESS,
        "wallet": model,
        "index": 0,
    }

    signed = safe_transaction.sign(w3, unsigned_relay_tx, relayer)

    expected = hot_wallet.sign_transaction(
        EMULATOR_KEY, EMULATOR_ADDRESS, w3, unsigned_relay_tx
    )
    assert signed.raw_transaction == expected.raw_transaction
    assert signed.hash == expected.hash
    assert (signed.v, signed.r, signed.s) == (expected.v, expected.r, expected.s)
    assert Account.recover_transaction(signed.raw_transaction) == EMULATOR_ADDRESS


def test_address_mismatch_returns_none(emulator, unsigned_relay_tx, capsys):
    module, _ = emulator

    result = module.sign_transaction(0, WRONG_ADDRESS, unsigned_relay_tx)

    assert result is None
    assert "does not match" in capsys.readouterr().out
