import os
import re


FIELD_PATTERNS = (
    ("transaction hash", re.compile(r"[0-9a-fA-F]{64}")),
    ("signer address", re.compile(r"0x[0-9a-fA-F]{40}")),
    ("signature", re.compile(r"[0-9a-fA-F]{130}")),
)


def sort_by_signer(signers_to_signatures: dict) -> list:
    items = list(signers_to_signatures.items())
    items.sort(key=lambda x: int(x[0], 16))
    return items


def _record_error(fields: list) -> str | None:
    if len(fields) != len(FIELD_PATTERNS):
        return f"expected {len(FIELD_PATTERNS)} fields, got {len(fields)}"
    for value, (name, pattern) in zip(fields, FIELD_PATTERNS):
        if not pattern.fullmatch(value):
            return f"invalid {name} {value[:80]!r}"
    return None


def load(path: str) -> dict:
    file_path = os.path.join(path, "out/signatures.txt")
    try:
        with open(file_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    all_signatures = {}
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        fields = line.split()
        error = _record_error(fields)
        if error:
            raise ValueError(
                f"Malformed record on line {number} of {file_path}: {error}."
            )

        transaction_hash, signer, signature = fields
        signers_to_signatures = all_signatures.setdefault(transaction_hash, {})
        existing = signers_to_signatures.get(signer)
        if existing is not None and existing != signature:
            raise ValueError(
                f"Line {number} of {file_path} gives signer {signer} a different "
                f"signature for transaction {transaction_hash} than an earlier line. "
                "Check that the signer's index or key_name matches its address."
            )
        signers_to_signatures[signer] = signature

    return all_signatures


def append(path: str, transaction_hash: str, signer: str, signature: str) -> None:
    error = _record_error([transaction_hash, signer, signature])
    if error:
        raise ValueError(f"Refusing to append a malformed record: {error}.")

    file_path = os.path.join(path, "out/signatures.txt")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    separator = ""
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                separator = "\n"

    with open(file_path, "a") as f:
        f.write(f"{separator}{transaction_hash} {signer} {signature}\n")


def concatenate(signers_and_signatures: list) -> str:
    result = "0x"
    for _, signature in signers_and_signatures:
        result += signature
    return result
