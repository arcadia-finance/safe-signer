import inquirer


def get_safe(safes: list) -> dict:
    # Get safes from input file
    choices = [f"{safe['name']} ({safe['address']})" for safe in safes]
    questions = [
        inquirer.List(
            "safes",
            message="For which Safe do you want to execute a transaction?",
            choices=choices,
        ),
    ]
    answer = inquirer.prompt(questions)["safes"]

    # Get safe information
    safe_address = answer.split("(")[1].split(")")[0]
    for i in safes:
        if safe_address == i["address"]:
            safe = i
            break
    return safe


def get_signer(signers: list) -> dict | bool:
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

    if answer == "Back":
        # Return False if not successful.
        return False
    else:
        # Get signer information
        signer_address = answer.split("(")[1].split(")")[0]
        for i in signers:
            if signer_address == i["address"]:
                signer = i
                break
        return signer


def get_relayer(relayers: list) -> dict | bool:
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

    if answer == "Back":
        # Return False if not successful.
        return False
    else:
        # Get relayer information
        relayer_address = answer.split("(")[1].split(")")[0]
        for i in relayers:
            if relayer_address == i["address"]:
                relayer = i
                break
        return relayer
