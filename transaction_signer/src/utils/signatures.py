import json
import os

from json.decoder import JSONDecodeError


def sort_by_signer(signers_to_signatures: dict) -> list:
    items = list(signers_to_signatures.items())
    items.sort(key=lambda x: int(x[0], 16))
    return items


def load(path: str) -> dict:
    file_path = os.path.join(path, "out/signatures.txt")
    try:
        with open(file_path) as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    except JSONDecodeError as e:
        raise ValueError(
            f"Could not parse {file_path}: {e}. Signing now would overwrite the "
            'collected signatures. Resolve the file, or write "{}" to start over.'
        ) from e

    if not isinstance(data, dict):
        raise TypeError(f"Expected dict in signatures file, got {type(data).__name__}")
    return data


def concatenate(signers_and_signatures: list) -> str:
    result = "0x"
    for _, signature in signers_and_signatures:
        result += signature
    return result
