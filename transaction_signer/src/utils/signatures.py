import json
import os

from json.decoder import JSONDecodeError


def sort_by_signer(signers_to_signatures: dict) -> list:
    items = list(signers_to_signatures.items())
    items.sort(key=lambda x: int(x[0], 16))
    return items


def load(path: str) -> dict:
    try:
        with open(os.path.join(path, "out/signatures.txt")) as f:
            data = json.load(f)
    except (JSONDecodeError, FileNotFoundError):
        return {}

    if not isinstance(data, dict):
        raise TypeError(f"Expected dict in signatures file, got {type(data).__name__}")
    return data


def concatenate(signers_and_signatures: list) -> str:
    result = "0x"
    for _, signature in signers_and_signatures:
        result += signature
    return result
