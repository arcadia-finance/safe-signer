import re

VALID_WALLET_TYPES = {"HOT", "T", "1", "L"}
SETTINGS = ("to", "operation", "gas", "max_fee_per_gas", "max_priority_fee_per_gas")
TRANSACTION_KEYS = {"chain", "safe", "raw_data", "nonce", "name", *SETTINGS}
HEX_DATA = re.compile(r"0x([0-9a-fA-F]{2})*")


def validate(safes: list, signers: list, relayers: list, chains: list):
    for chain in chains:
        name = chain["name"]
        if name.find("(") >= 0 or name.find(")") >= 0:
            raise Exception("Name can't contain characters '(' or ').")
    _validate_unique_names(chains, "Chain")

    # Safe Name can't contain certain characters.
    for safe in safes:
        name = safe["name"]
        if name.find("(") >= 0 or name.find(")") >= 0:
            raise Exception("Name can't contain characters '(' or ').")
    _validate_unique_names(safes, "Safe")

    addresses = []
    for signer in signers:
        # Name can't contain certain characters.
        name = signer["name"]
        if name.find("(") >= 0 or name.find(")") >= 0:
            raise Exception("Name can't contain characters '(' or ').")

        wallet = signer.get("wallet")
        if wallet not in VALID_WALLET_TYPES:
            raise Exception(
                f"Invalid wallet type '{wallet}' for signer '{name}'. Must be one of {sorted(VALID_WALLET_TYPES)}."
            )
        _validate_wallet_fields(signer)

        addresses.append(signer["address"])

    # All signers must be unique.
    if len(addresses) != len(set(addresses)):
        raise Exception("All signing addresses must be unique.")

    addresses = []
    for relayer in relayers:
        # Name can't contain certain characters.
        name = relayer["name"]
        if name.find("(") >= 0 or name.find(")") >= 0:
            raise Exception("Name can't contain characters '(' or ').")

        wallet = relayer.get("wallet")
        if wallet not in VALID_WALLET_TYPES:
            raise Exception(
                f"Invalid wallet type '{wallet}' for relayer '{name}'. Must be one of {sorted(VALID_WALLET_TYPES)}."
            )
        _validate_wallet_fields(relayer)

        addresses.append(relayer["address"])

    # All relayers must be unique.
    if len(addresses) != len(set(addresses)):
        raise Exception("All relayer addresses must be unique.")


def validate_operation(operation: int, to: str):
    if operation != 0 and operation != 1:
        raise Exception("Operation must be 0 or 1")
    if operation == 1 and to != "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B":
        raise Exception(
            "Inconsistent input, to-address must always be '0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B' for operation '1'"
        )


def validate_transactions(transactions: list, chains: list, safes: list):
    if not transactions:
        raise Exception("The config must list at least one transaction.")

    chain_names = {chain["name"] for chain in chains}
    safe_addresses = {safe["name"]: safe["address"].lower() for safe in safes}
    pins = {}
    repeats = {}
    for number, transaction in enumerate(transactions, start=1):
        for key in ("chain", "safe", "raw_data"):
            if key not in transaction:
                raise Exception(f"transaction #{number} is missing '{key}'.")
        for key in transaction:
            if key not in TRANSACTION_KEYS:
                raise Exception(f"transaction #{number} has unknown key '{key}'.")

        if transaction["chain"] not in chain_names:
            raise Exception(
                f"Unknown chain '{transaction['chain']}' in transaction #{number}."
            )
        if transaction["safe"] not in safe_addresses:
            raise Exception(
                f"Unknown safe '{transaction['safe']}' in transaction #{number}."
            )
        if not HEX_DATA.fullmatch(transaction["raw_data"]):
            raise Exception(
                f"raw_data of transaction #{number} is not 0x-prefixed even-length hex."
            )

        name = transaction.get("name")
        if name is not None and (type(name) is not str or not name):
            raise Exception(
                f"name of transaction #{number} must be a non-empty string."
            )

        safe_key = (transaction["chain"], safe_addresses[transaction["safe"]])
        nonce = transaction.get("nonce")
        if nonce == "repeat":
            if safe_key in repeats:
                raise Exception(
                    f"transactions #{repeats[safe_key]} and #{number} are both 'repeat' on the same safe; the nonce order cannot be resolved."
                )
            repeats[safe_key] = number
            continue
        if nonce is None:
            if safe_key in repeats:
                raise Exception(
                    f"one-off transaction #{number} comes after the repeat transaction #{repeats[safe_key]} on the same safe; the nonce order cannot be resolved."
                )
            continue
        if type(nonce) is not int or nonce < 0:
            raise Exception(
                f"nonce of transaction #{number} must be an integer >= 0 or 'repeat'."
            )
        key = (*safe_key, nonce)
        if key in pins:
            raise Exception(
                f"transactions #{pins[key]} and #{number} both pin nonce {nonce} on the same safe."
            )
        pins[key] = number


def _validate_unique_names(items: list, kind: str):
    names = [item["name"] for item in items]
    if len(names) != len(set(names)):
        raise Exception(f"{kind} names must be unique.")


def _validate_wallet_fields(entry: dict):
    wallet = entry["wallet"]
    name = entry["name"]
    if wallet == "HOT":
        if "key_name" not in entry:
            raise Exception(f"HOT wallet '{name}' must have a 'key_name' field.")
    else:
        if "index" not in entry:
            raise Exception(
                f"Hardware wallet '{name}' (type '{wallet}') must have an 'index' field."
            )
