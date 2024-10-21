import os

import src.wallets.hot_wallet as hot_wallet
import src.wallets.trezor_t as trezor_t

from eth_utils import to_bytes


def create(
    w3: any,
    safe: any,
    to: str,
    constants: dict,
    raw_data: str,
    operation: int,
    signatures: str,
    relayer: dict,
    gas: int,
    max_fee_per_gas: int,
    max_priority_fee_per_gas: int,
) -> dict:
    unsigned_safe_tx = safe.functions.execTransaction(
        to,
        constants["VALUE_SAFE_TX"],
        to_bytes(hexstr=raw_data),
        operation,
        constants["SAFE_TX_GAS"],
        constants["BASE_GAS"],
        constants["GAS_PRICE"],
        constants["GAS_TOKEN"],
        constants["REFUND_RECEIVER"],
        to_bytes(hexstr=signatures),
    ).build_transaction(
        {
            "nonce": w3.eth.get_transaction_count(relayer),
            "value": constants["VALUE_RELAY_TX"],
            "type": constants["TYPE"],
            "chainId": safe.functions.getChainId().call(),
            "gas": 0,
        }
    )

    # Use dynamic gas usage if 'gas' is set to 0 by the user.
    if gas == 0:
        unsigned_safe_tx.update({"gas": int(w3.eth.estimate_gas(unsigned_safe_tx))})
    else:
        unsigned_safe_tx.update({"gas": gas})

    # Use dynamic gas_price if 'max_fee_per_gas' is set to 0 by the user.
    if max_fee_per_gas == 0:
        unsigned_safe_tx.update(
            {"maxFeePerGas": int(w3.eth.gas_price + max_priority_fee_per_gas)}
        )
    else:
        unsigned_safe_tx.update({"maxFeePerGas": max_fee_per_gas})
    unsigned_safe_tx.update({"maxPriorityFeePerGas": max_priority_fee_per_gas})

    return unsigned_safe_tx


def sign(w3: any, unsigned_safe_tx: dict, relayer: dict) -> dict:
    if relayer["wallet"] == "HOT":
        key_relayer = os.getenv(relayer["key_name"])
        if not key_relayer:
            print(f"Private key for relayer {relayer['name']} not found in .env file.")
            # Return False if not successful.
            return False
        signed_tx = hot_wallet.sign_transaction(
            key_relayer, relayer["address"], w3, unsigned_safe_tx
        )
    else:
        input(
            f'Relayer {relayer["name"]} ({relayer["address"]}), please connect your Device and sign the transaction with wallet at index {relayer["index"]}.\nPress Enter to continue...'
        )
        if relayer["wallet"] == "T":
            signed_tx = trezor_t.sign_transaction(
                relayer["index"], relayer["address"], unsigned_safe_tx
            )
        else:
            raise Exception("Unknown or unsupported wallet type.")

    return signed_tx
