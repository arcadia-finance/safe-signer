import inquirer
import json
import os
import toml

import src.eip712_typed_data as eip712_typed_data
import src.safe_transaction as safe_transaction
import src.tenderly as tenderly
import src.user_input as user_input
import src.utils.validate_config as validate_config
import src.utils.validate_signer as validate_signer

from dotenv import load_dotenv, find_dotenv
from eth_utils import keccak
from json.decoder import JSONDecodeError
from pathlib import Path
from web3 import Web3


def get_user_action() -> bool:
    choices = [
        "Sign Message",
        "Simulate on Tenderly",
        "Create unsigned Safe tx",
        "Create signed Safe tx",
        "Broadcast signed Safe tx",
        "Quit",
    ]
    questions = [
        inquirer.List(
            "actions",
            message="What do you want to do?",
            choices=choices,
        ),
    ]
    action = inquirer.prompt(questions)["actions"]

    if action == "Quit":
        # Stop script.
        return False

    else:
        if action == "Sign Message":
            sign_typed_data()

        elif action == "Simulate on Tenderly":
            simulate_on_tenderly()

        elif action == "Create unsigned Safe tx":
            get_unsigned_safe_tx()

        elif action == "Create signed Safe tx":
            get_signed_safe_tx()

        elif action == "Broadcast signed Safe tx":
            success = sign_and_broadcast_safe_tx()
            # If tx was send out, stop script.
            if success:
                return False

        return True


def sign_typed_data():
    signer = user_input.get_signer(signers)
    # Only continue if signer was selected.
    if not signer:
        return

    # Only continue if signer is valid.
    if not validate_signer.validate(safe, all_signatures, transaction_hash, signer):
        return

    signature = eip712_typed_data.sign(
        w3, signer, typed_data, domain_hash, message_hash
    )

    # Only continue if signature is valid.
    if not signature:
        return

    # Save the signature in the output file.
    if not all_signatures.get(transaction_hash, False):
        all_signatures[transaction_hash] = {}
    all_signatures[transaction_hash].update({signer["address"]: signature})

    # Update existing signatures and signers.
    current_signers = list(all_signatures.get(transaction_hash, {}).keys())
    print(f"Signature: {signature}")
    print(
        f"{len(current_signers)}/{required_signatures} signatures are collected, from {current_signers}"
    )

    with open(os.path.join(path, "out/signatures.txt"), "w") as f:
        json.dump(all_signatures, f)


def simulate_on_tenderly():
    tenderly.simulate(safe, to, raw_data, operation, constants, TENDERLY_URL)


def get_unsigned_safe_tx():
    relayer = user_input.get_relayer(relayers)
    if relayer:
        print(_get_unsigned_safe_tx(relayer))


def _get_unsigned_safe_tx(relayer) -> dict | bool:
    signers_to_signatures = all_signatures.get(transaction_hash, {})

    # Sort the signatures in ascending order according to public addresses.
    signers_and_signatures = list(signers_to_signatures.items())
    signers_and_signatures.sort(key=lambda x: x[0])

    # Only continue if threshold of safe is met.
    if len(signers_and_signatures) >= required_signatures:
        signatures = "0x"
        for _, signature in signers_and_signatures:
            signatures += signature

        # Create the unsigned transaction:
        unsigned_safe_tx = safe_transaction.create(
            w3,
            safe,
            to,
            constants,
            raw_data,
            operation,
            signatures,
            relayer["address"],
            gas,
            max_fee_per_gas,
            max_priority_fee_per_gas,
        )

        return unsigned_safe_tx

    else:
        print(
            f"Only {len(signers_and_signatures)} out of the {required_signatures} required signatures are collected."
        )
        # Return False if not successful.
        return False


def get_signed_safe_tx():
    relayer = user_input.get_relayer(relayers)
    if relayer:
        print(_get_signed_safe_tx(relayer))


def _get_signed_safe_tx(relayer) -> dict | bool:
    unsigned_safe_tx = _get_unsigned_safe_tx(relayer)
    if not unsigned_safe_tx:
        # Return False if not successful.
        return False

    signed_tx = safe_transaction.sign(w3, unsigned_safe_tx, relayer)

    return signed_tx


def sign_and_broadcast_safe_tx() -> bool:
    relayer = user_input.get_relayer(relayers)
    if relayer:
        signed_tx = _get_signed_safe_tx(relayer)

        if signed_tx:
            choices = [
                "I Confirm",
                "Quit",
            ]
            questions = [
                inquirer.List(
                    "actions",
                    message=f"Confirm you want to broadcast the signed transaction (Chain Id: {w3.eth.chain_id})",
                    choices=choices,
                ),
            ]
            action = inquirer.prompt(questions)["actions"]

            if action == "I Confirm":
                w3.eth.send_raw_transaction(signed_tx.raw_transaction)
                tx_hash = f"0x{keccak(signed_tx.raw_transaction).hex()}"
                print(f"Transaction sent: {tx_hash}")
                # Return True if successful.
                return True
    # Return False if not successful.
    return False


if __name__ == "__main__":
    ##### Set Up #####

    ### User input ###
    path = Path(__file__).parent.resolve()
    config_data = toml.load(os.path.join(path, "config_transaction_signer.toml"))

    safes = config_data["safes"]
    raw_data = config_data["raw_data"]
    operation = config_data["operation"]
    to = config_data["to"]
    signers = config_data["signers"]
    relayers = config_data["relayers"]
    gas = config_data["gas"]
    max_fee_per_gas = config_data["max_fee_per_gas"]
    max_priority_fee_per_gas = config_data["max_priority_fee_per_gas"]

    validate_config.validate(safes, signers, relayers, operation, to)

    ### Constants ###
    constants = toml.load(os.path.join(path, "data/constants.toml"))

    ### Secrets ###
    load_dotenv(find_dotenv())

    ### Web3 ###
    # Rpc provider.
    w3 = Web3(Web3.HTTPProvider(os.getenv("HTTP_PROVIDER")))

    ### Tenderly ###
    TENDERLY_URL = f"https://api.tenderly.co/api/v1/account/{os.getenv('TENDERLY_ACCOUNT')}/project/{os.getenv('TENDERLY_PROJECT')}"

    ### Gnosis safe ###
    # Select the Safe.
    safe = user_input.get_safe(safes)
    with open(os.path.join(path, "data/abis", "safe.json")) as f:
        SAFE_ABI = json.loads(f.read())
    safe = w3.eth.contract(address=safe["address"], abi=SAFE_ABI)

    # Required number of signatures.
    required_signatures = safe.functions.getThreshold().call()

    ### Transaction ###
    # Generate the message that must be signed by the multisig users:
    typed_data = eip712_typed_data.get_typed_data(
        safe, to, raw_data, operation, constants
    )

    # Calculate the Transaction Hash.
    domain_hash = safe.functions.domainSeparator().call()
    message_hash = eip712_typed_data.get_typed_data_hash(typed_data)

    msg_to_sign = (
        Web3.to_bytes(hexstr=constants["SIGN_MAGIC"]) + domain_hash + message_hash
    )
    transaction_hash = keccak(msg_to_sign).hex()
    print(f"Domain Hash is: {domain_hash.hex()}")
    print(f"Message Hash is: {message_hash.hex()}")
    print(f"Transaction Hash is: {transaction_hash}")

    # Fetch the list of existing signatures, if it exists.
    try:
        with open(os.path.join(path, "out/signatures.txt")) as f:
            all_signatures = json.load(f)
    except JSONDecodeError:
        all_signatures = {}

    # Get existing signatures for the Transaction Hash.
    current_signers = list(all_signatures.get(transaction_hash, {}).keys())
    print(
        f"{len(current_signers)}/{required_signatures} signatures are collected, from {current_signers}"
    )

    ##### Run the script #####
    while get_user_action():
        pass
