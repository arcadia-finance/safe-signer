import inquirer


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
                return i
        raise ValueError(f"No signer found with address {signer_address}")


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
                return i
        raise ValueError(f"No relayer found with address {relayer_address}")


def describe_transaction(entry: dict) -> str:
    parts = [entry["chain"]["name"], entry["safe_config"]["name"]]
    if entry["name"]:
        parts.insert(0, entry["name"])
    return f"#{entry['number']} " + " · ".join(parts)


def get_transaction(entries: list, all_signatures: dict) -> dict | bool:
    shown = [entry for entry in entries if entry["status"] != "executed"]
    with_names = any(entry["name"] for entry in shown)
    rows = []
    for entry in shown:
        row = [f"#{entry['number']}"]
        if with_names:
            row.append(entry["name"] or "")
        row += [entry["chain"]["name"], entry["safe_config"]["name"]]
        if entry["status"] == "unresolved":
            row.append("unresolved")
        else:
            signed = len(all_signatures.get(entry["transaction_hash"], {}))
            row += [
                f"nonce {entry['nonce']}",
                f"{signed}/{entry['threshold']} signed",
                entry["status"],
            ]
        rows.append(row)
    choices = _align(rows) + ["Exit"]

    questions = [
        inquirer.List(
            "transactions",
            message="Which transaction?",
            choices=choices,
        ),
    ]
    answer = inquirer.prompt(questions)
    if answer is None or answer["transactions"] == "Exit":
        return False
    return shown[choices.index(answer["transactions"])]


def _align(rows: list[list[str]]) -> list[str]:
    widths = {}
    for row in rows:
        for i, cell in enumerate(row[:-1]):
            widths[i] = max(widths.get(i, 0), len(cell))
    lines = []
    for row in rows:
        cells = [cell.ljust(widths[i]) for i, cell in enumerate(row[:-1])] + row[-1:]
        lines.append(f"{cells[0]} " + " · ".join(cells[1:]))
    return lines
