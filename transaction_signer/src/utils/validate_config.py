VALID_WALLET_TYPES = {"HOT", "T", "1", "L"}


def validate(
    safes: dict,
    signers: dict,
    relayers: dict,
    operation: int,
    to: str,
    chains: list | None = None,
):
    if chains is not None:
        for chain in chains:
            name = chain["name"]
            if name.find("(") >= 0 or name.find(")") >= 0:
                raise Exception("Name can't contain characters '(' or ').")

    # Safe Name can't contain certain characters.
    for safe in safes:
        name = safe["name"]
        if name.find("(") >= 0 or name.find(")") >= 0:
            raise Exception("Name can't contain characters '(' or ').")

    if operation != 0 and operation != 1:
        raise Exception("Operation must be 0 or 1")
    if operation == 1 and to != "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B":
        raise Exception(
            "Inconsistent input, to-address must always be '0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B' for operation '1'"
        )

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
