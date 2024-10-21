import inquirer


def validate(
    safe: any, all_signatures: dict, transaction_hash: str, signer: dict
) -> bool:
    if safe.functions.isOwner(signer["address"]).call():
        # Check if signer already has a signature for the given message hash.
        if all_signatures.get(transaction_hash, {}).get(signer["address"], "") != "":
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
                return True
        else:
            return True

    else:
        print(
            f'Signer {signer["name"]} ({signer["address"]}) is not an owner of the safe {safe.address}.'
        )
    # Return False if not successful.
    return False
