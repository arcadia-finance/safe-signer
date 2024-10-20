def validate(safes, signers, relayers, operation, to):
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

        addresses.append(relayer["address"])

    # All signers must be unique.
    if len(addresses) != len(set(addresses)):
        raise Exception("All relayer addresses must be unique.")
