import inquirer
import json
import os
import requests
import toml

import utils.eip712 as eip712
import utils.tenderly as tenderly
import utils.validate_user_input as validate_user_input
import wallets.hot_wallet as hot_wallet
import wallets.ledger_nano as ledger_nano
import wallets.trezor_1 as trezor_1
import wallets.trezor_t as trezor_t

from dotenv import load_dotenv, find_dotenv
from eth_utils import keccak
from json.decoder import JSONDecodeError
from pathlib import Path
from web3 import Web3


def get_user_action():
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

    if action == "Sign Message":
        get_signer()

    elif action == "Simulate on Tenderly":
        simulate_tx_on_tenderly()

    elif action == "Create unsigned Safe tx":
        generate_unsigned_safe_tx()

    elif action == "Create signed Safe tx":
        sign_safe_tx()

    elif action == "Broadcast signed Safe tx":
        sign_and_broadcast_safe_tx()


def get_signer():
    # Get signers from input file
    choices = [f"{signer['name']} ({signer['address']})" for signer in signers]
    choices.append("Back")

    questions = [
        inquirer.List(
            "signers",
            message="Who is signing?",
            choices=choices,
        ),
    ]
    answer = inquirer.prompt(questions)["signers"]

    if answer != "Back":
        # Get signer information
        signer_address = answer.split("(")[1].split(")")[0]
        for i in signers:
            if signer_address == i["address"]:
                signer = i
                break

        if safe.functions.isOwner(signer_address).call():
            # Check if signer already has a signature for the given message hash.
            if all_signatures.get(transaction_hash, {}).get(signer_address, "") != "":
                # If yes, user must confirm to sign again.
                questions = [
                    inquirer.List(
                        "overwrite signature",
                        message="Signature for signer already exists, overwrite it?",
                        choices=["Yes", "No"],
                    ),
                ]
                answer = inquirer.prompt(questions)["overwrite signature"]
                if answer == "Yes":
                    sign_message(signer)
            else:
                sign_message(signer)

        else:
            print(
                f'Signer {signer["name"]} ({signer["address"]}) is not an owner of the safe {safe_address}.'
            )

    get_user_action()


def sign_message(signer: dict):
    if signer["wallet"] == "HOT":
        key_signer = os.getenv(signer["key_name"])
        if not key_signer:
            print(f"Private key for signer {signer['name']} not found in .env file.")
            return None
        signature = hot_wallet.sign_typed_data(
            key_signer, signer["address"], w3, typed_data
        )

    else:
        input(
            f'Signer {signer["name"]} ({signer["address"]}), please connect your Device and sign the data with wallet at index {signer["index"]}.\nPress Enter to continue...'
        )
        # Sign Message.
        if signer["wallet"] == "T":
            signature = trezor_t.sign_typed_data(
                signer["index"], signer["address"], typed_data
            )
        elif signer["wallet"] == "1":
            signature = trezor_1.sign_typed_data_hash(
                signer["index"],
                signer["address"],
                domain_hash,
                message_hash,
            )
        elif signer["wallet"] == "L":
            signature = ledger_nano.sign_typed_data_hash(
                signer["index"],
                signer["address"],
                domain_hash,
                message_hash,
            )
        else:
            raise Exception("Unknown wallet type.")

    if signature != None:
        print(f"Signature: {signature}")

        # Save the signature in the output file.
        if not all_signatures.get(transaction_hash, False):
            all_signatures[transaction_hash] = {}
        all_signatures[transaction_hash].update({signer["address"]: signature})

        # Update existing signatures and signers.
        current_signers = list(all_signatures.get(transaction_hash, {}).keys())
        print(
            f"{len(current_signers)}/{required_signatures} signatures are collected, from {current_signers}"
        )

        with open(os.path.join(path, "signatures.txt"), "w") as f:
            json.dump(all_signatures, f)


def simulate_tx_on_tenderly():
    tenderly.simulate(safe, to, raw_data, operation, constants, TENDERLY_URL)
    get_user_action()


def generate_unsigned_safe_tx():
    relayer = get_relayer()
    print(_generate_unsigned_safe_tx(relayer["address"]))
    get_user_action()


def _generate_unsigned_safe_tx(relayer: str) -> dict:
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
        unsigned_safe_tx = safe.functions.execTransaction(
            to,
            constants["VALUE_SAFE_TX"],
            Web3.to_bytes(hexstr=raw_data),
            operation,
            constants["SAFE_TX_GAS"],
            constants["BASE_GAS"],
            constants["GAS_PRICE"],
            constants["GAS_TOKEN"],
            constants["REFUND_RECEIVER"],
            Web3.to_bytes(hexstr=signatures),
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

    else:
        input(
            f"Only {len(signers_and_signatures)} out of the {required_signatures} required signatures are collected.\nPress Enter to go back..."
        )
        return None


def sign_safe_tx():
    print(_sign_safe_tx())
    get_user_action()


def _sign_safe_tx() -> dict:
    relayer = get_relayer()
    unsigned_safe_tx = _generate_unsigned_safe_tx(relayer["address"])

    if unsigned_safe_tx == None:
        return None

    if relayer["wallet"] == "HOT":
        key_relayer = os.getenv(relayer["key_name"])
        if not key_relayer:
            print(f"Private key for relayer {relayer['name']} not found in .env file.")
            return None
        signed_tx = hot_wallet.sign_transaction(
            key_relayer, relayer["address"], w3, unsigned_safe_tx
        )
    else:
        input(
            f'Relayer {relayer["name"]} ({relayer["address"]}), please connect your Device and sign the transaction with wallet at index {relayer["index"]}.\nPress Enter to continue...'
        )
        # Sign Message.
        if relayer["wallet"] == "T":
            signed_tx = trezor_t.sign_transaction(
                relayer["index"], relayer["address"], unsigned_safe_tx
            )
        else:
            raise Exception("Unknown or unsupported wallet type.")

    return signed_tx


def get_relayer():
    # Get relayers from input file
    choices = [f"{relayer['name']} ({relayer['address']})" for relayer in relayers]
    choices.append("Back")

    questions = [
        inquirer.List(
            "relayers",
            message="Who is the relayer?",
            choices=choices,
        ),
    ]
    answer = inquirer.prompt(questions)["relayers"]

    if answer != "Back":
        # Get relayer information
        relayer_address = answer.split("(")[1].split(")")[0]
        for i in relayers:
            if relayer_address == i["address"]:
                relayer = i
                break
        return relayer
    else:
        get_user_action()


def sign_and_broadcast_safe_tx():
    signed_tx = _sign_safe_tx()

    if signed_tx != None:
        choices = [
            "I Confirm",
            "Quit",
        ]
        questions = [
            inquirer.List(
                "actions",
                message="Confirm you want to broadcast the signed transaction",
                choices=choices,
            ),
        ]
        action = inquirer.prompt(questions)["actions"]

        if action == "I Confirm":
            w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            print(
                f"Transaction sent -- tx_hash: 0x{keccak(signed_tx.raw_transaction).hex()}"
            )

    get_user_action()


### User input ###
path = Path(__file__).parent.resolve()
config_data = toml.load(os.path.join(path, "config_transaction_signer.toml"))

### Parameters ###
safes = config_data["safes"]
raw_data = config_data["raw_data"]
operation = config_data["operation"]
to = config_data["to"]
signers = config_data["signers"]
relayers = config_data["relayers"]

gas = config_data["gas"]
max_fee_per_gas = config_data["max_fee_per_gas"]
max_priority_fee_per_gas = config_data["max_priority_fee_per_gas"]

validate_user_input.validate(safes, signers, relayers, operation, to)

### Constants ###
constants = toml.load(os.path.join(path, "constants.toml"))

### Secrets ###
load_dotenv(find_dotenv())

### Web3 ###
# Rpc provider.
HTTP_PROVIDER = os.getenv("HTTP_PROVIDER")
w3 = Web3(Web3.HTTPProvider(HTTP_PROVIDER))

### Tenderly ###
TENDERLY_URL = f"https://api.tenderly.co/api/v1/account/{os.getenv('TENDERLY_ACCOUNT')}/project/{os.getenv('TENDERLY_PROJECT')}"

# Gnosis safe.
choices = [f"{safe['name']} ({safe['address']})" for safe in safes]
questions = [
    inquirer.List(
        "safes",
        message="For which Safe do you want to execute a transaction?",
        choices=choices,
    ),
]
answer = inquirer.prompt(questions)["safes"]

safe_address = answer.split("(")[1].split(")")[0]
for i in signers:
    if safe_address == i["address"]:
        signer = i
        break

with open(os.path.join(path, "abis", "safe.json")) as f:
    SAFE_ABI = json.loads(f.read())
safe = w3.eth.contract(address=safe_address, abi=SAFE_ABI)

##### Run the script #####
# Required number of signatures.
required_signatures = safe.functions.getThreshold().call()

# Generate the message that must be signed by the multisig users:
typed_data = eip712.get_typed_data(safe, to, raw_data, operation, constants)

# Calculate the Transaction Hash.
domain_hash = safe.functions.domainSeparator().call()
message_hash = eip712.get_typed_data_hash(typed_data)

msg_to_sign = Web3.to_bytes(hexstr=constants["SIGN_MAGIC"]) + domain_hash + message_hash
transaction_hash = keccak(msg_to_sign).hex()
print(f"Domain Hash is: {domain_hash.hex()}")
print(f"Message Hash is: {message_hash.hex()}")
print(f"Transaction Hash is: {transaction_hash}")

# Fetch the list of existing signatures, if it exists.
try:
    with open(os.path.join(path, "signatures.txt")) as f:
        all_signatures = json.load(f)
except JSONDecodeError:
    all_signatures = {}

# Get existing signatures for the Transaction Hash.
current_signers = list(all_signatures.get(transaction_hash, {}).keys())
print(
    f"{len(current_signers)}/{required_signatures} signatures are collected, from {current_signers}"
)

if __name__ == "__main__":
    get_user_action()
