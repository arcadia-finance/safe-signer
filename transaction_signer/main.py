import inquirer
import json
import os
import toml

import src.eip712_typed_data as eip712_typed_data
import src.safe_transaction as safe_transaction
import src.tenderly as tenderly
import src.transactions as transactions
import src.user_input as user_input
import src.utils.signatures as signatures
import src.utils.validate_config as validate_config
import src.utils.validate_signer as validate_signer

from dotenv import load_dotenv, find_dotenv
from eth_utils import keccak
from pathlib import Path


ACTIONS = [
    "Sign Message",
    "Simulate on Tenderly",
    "Create unsigned Safe tx",
    "Create signed Safe tx",
    "Broadcast signed Safe tx",
    "Back",
]


def run_entry(entry: dict, ctx: dict):
    while True:
        questions = [
            inquirer.List(
                "actions",
                message="What do you want to do?",
                choices=ACTIONS,
            ),
        ]
        answer = inquirer.prompt(questions)
        if answer is None or answer["actions"] == "Back":
            return

        action = answer["actions"]
        try:
            if action == "Sign Message":
                sign(entry, ctx)
            elif action == "Simulate on Tenderly":
                simulate(entry, ctx)
            elif action == "Create unsigned Safe tx":
                create_unsigned(entry, ctx)
            elif action == "Create signed Safe tx":
                create_signed(entry, ctx)
            elif action == "Broadcast signed Safe tx":
                if broadcast(entry, ctx):
                    return
        except Exception as e:
            print(f"Error: {e}")


def sign(entry: dict, ctx: dict):
    signer = user_input.get_signer(ctx["signers"])
    # Only continue if signer was selected.
    if not signer:
        return

    all_signatures = ctx["all_signatures"]
    transaction_hash = entry["transaction_hash"]
    # Only continue if signer is valid.
    if not validate_signer.validate(
        entry["safe"], all_signatures, transaction_hash, signer
    ):
        return

    signature = eip712_typed_data.sign(
        entry["w3"],
        signer,
        entry["typed_data"],
        entry["domain_hash"],
        entry["message_hash"],
    )

    # Only continue if signature is valid.
    if not signature:
        return

    # Save the signature in the output file.
    all_signatures.setdefault(transaction_hash, {})[signer["address"]] = signature

    current_signers = list(all_signatures[transaction_hash].keys())
    print(f"Signature: {signature}")
    print(
        f"{len(current_signers)}/{entry['threshold']} signatures are collected, from {current_signers}"
    )

    signatures.append(ctx["path"], transaction_hash, signer["address"], signature)
    transactions.save_history(ctx["cache"], entry["history_key"], ctx["path"])


def simulate(entry: dict, ctx: dict):
    if entry["status"] == "queued":
        print(
            "Warning: earlier transactions for this safe have not executed; simulating against current state."
        )
    tenderly.simulate(
        entry["safe"],
        entry["to"],
        entry["raw_data"],
        entry["operation"],
        ctx["constants"],
        ctx["tenderly_url"],
    )


def create_unsigned(entry: dict, ctx: dict):
    if not _is_next(entry):
        return
    relayer = user_input.get_relayer(ctx["relayers"])
    if relayer:
        print(_get_unsigned_safe_tx(entry, ctx, relayer))


def create_signed(entry: dict, ctx: dict):
    if not _is_next(entry):
        return
    relayer = user_input.get_relayer(ctx["relayers"])
    if relayer:
        print(_get_signed_safe_tx(entry, ctx, relayer))


def broadcast(entry: dict, ctx: dict) -> bool:
    if not _is_next(entry):
        return False
    relayer = user_input.get_relayer(ctx["relayers"])
    if not relayer:
        return False
    signed_tx = _get_signed_safe_tx(entry, ctx, relayer)
    if not signed_tx:
        return False

    questions = [
        inquirer.List(
            "actions",
            message=f"Confirm you want to broadcast {user_input.describe_transaction(entry)} · nonce {entry['nonce']} · Safe tx {entry['transaction_hash']} (Chain Id: {entry['chain']['chain_id']})",
            choices=["I Confirm", "Quit"],
        ),
    ]
    answer = inquirer.prompt(questions)
    if answer is None or answer["actions"] != "I Confirm":
        return False

    live_nonce = entry["safe"].functions.nonce().call()
    if live_nonce != entry["nonce"]:
        print(f"The safe's nonce moved to {live_nonce}; refresh and try again.")
        return False

    entry["w3"].eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_hash = f"0x{keccak(signed_tx.raw_transaction).hex()}"
    print(f"Transaction sent: {tx_hash}")
    return True


def _is_next(entry: dict) -> bool:
    if entry["status"] != "next":
        print(
            f"Only the next transaction for this safe can be created or broadcast (this one is {entry['status']})."
        )
        return False
    return True


def _get_unsigned_safe_tx(entry: dict, ctx: dict, relayer: dict) -> dict | bool:
    signers_to_signatures = ctx["all_signatures"].get(entry["transaction_hash"], {})

    # Sort the signatures in ascending order according to public addresses.
    signers_and_signatures = signatures.sort_by_signer(signers_to_signatures)

    # Only continue if threshold of safe is met.
    if len(signers_and_signatures) >= entry["threshold"]:
        packed_signatures = signatures.concatenate(signers_and_signatures)

        # Create the unsigned transaction:
        return safe_transaction.create(
            entry["w3"],
            entry["safe"],
            entry["to"],
            ctx["constants"],
            entry["raw_data"],
            entry["operation"],
            packed_signatures,
            relayer["address"],
            entry["gas"],
            entry["max_fee_per_gas"],
            entry["max_priority_fee_per_gas"],
        )

    print(
        f"Only {len(signers_and_signatures)} out of the {entry['threshold']} required signatures are collected."
    )
    # Return False if not successful.
    return False


def _get_signed_safe_tx(entry: dict, ctx: dict, relayer: dict) -> dict | bool:
    unsigned_safe_tx = _get_unsigned_safe_tx(entry, ctx, relayer)
    if not unsigned_safe_tx:
        # Return False if not successful.
        return False

    return safe_transaction.sign(entry["w3"], unsigned_safe_tx, relayer)


def setup(path: Path) -> tuple[list, dict]:
    config_data = toml.load(os.path.join(path, "config_transaction_signer.toml"))

    chains = config_data["chains"]
    safes = config_data["safes"]
    validate_config.validate(
        safes, config_data["signers"], config_data["relayers"], chains
    )
    validate_config.validate_transactions(config_data["transactions"], chains, safes)
    defaults = {
        key: config_data[key] for key in validate_config.SETTINGS if key in config_data
    }
    entries = transactions.resolve_settings(
        config_data["transactions"], chains, safes, defaults
    )

    load_dotenv(find_dotenv())
    with open(os.path.join(path, "data/abis", "safe.json")) as f:
        safe_abi = json.loads(f.read())

    ctx = {
        "signers": config_data["signers"],
        "relayers": config_data["relayers"],
        "all_signatures": signatures.load(str(path)),
        "path": str(path),
        "constants": toml.load(os.path.join(path, "data/constants.toml")),
        "tenderly_url": f"https://api.tenderly.co/api/v1/account/{os.getenv('TENDERLY_ACCOUNT')}/project/{os.getenv('TENDERLY_PROJECT')}",
        "cache": {},
        "connections": transactions.connect_chains(entries),
        "safe_abi": safe_abi,
    }
    return entries, ctx


def refresh(entries: list, ctx: dict) -> list:
    return transactions.load(
        entries,
        ctx["connections"],
        ctx["safe_abi"],
        ctx["constants"],
        ctx["cache"],
        ctx["path"],
    )


def run_list(entries: list, ctx: dict):
    loaded = refresh(entries, ctx)
    for entry in loaded:
        if entry["status"] == "executed":
            print(
                f"{user_input.describe_transaction(entry)} executed at nonce {entry['nonce']}"
            )
        elif entry["status"] == "unresolved":
            print(f"{user_input.describe_transaction(entry)}: {entry['reason']}")

    while True:
        if all(entry["status"] == "executed" for entry in loaded):
            print("All transactions in the config have executed.")
            return

        entry = user_input.get_transaction(loaded, ctx["all_signatures"])
        if not entry:
            return
        if entry["status"] == "unresolved":
            print(entry["reason"])
            continue

        current_signers = list(
            ctx["all_signatures"].get(entry["transaction_hash"], {}).keys()
        )
        print(f"Domain Hash is: {entry['domain_hash'].hex()}")
        print(f"Message Hash is: {entry['message_hash'].hex()}")
        print(f"Transaction Hash is: {entry['transaction_hash']}")
        print(
            f"{len(current_signers)}/{entry['threshold']} signatures are collected, from {current_signers}"
        )

        run_entry(entry, ctx)
        loaded = refresh(entries, ctx)


if __name__ == "__main__":
    path = Path(__file__).parent.resolve()
    entries, ctx = setup(path)
    run_list(entries, ctx)
