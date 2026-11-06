import json
import os


def load(path: str) -> dict:
    file_path = os.path.join(path, "out/history.jsonl")
    try:
        with open(file_path) as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {}

    executions = {}
    watermarks = {}
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Malformed record on line {number} of {file_path}: {e}."
            ) from None

        key = (record["chain"], record["safe"])
        if "scanned_to" in record:
            current = watermarks.get(key)
            if current is None or record["scanned_to"] > current["scanned_to"]:
                watermarks[key] = record
            continue

        execution = (record["tx_hash"], record["success"], record["block"])
        existing = executions.setdefault(key, {}).get(record["nonce"])
        if existing is not None and existing[0] != execution:
            raise ValueError(
                f"Lines {existing[1]} and {number} of {file_path} record different "
                f"executions for nonce {record['nonce']} of {key[1]} on {key[0]}."
            )
        executions[key][record["nonce"]] = (execution, number)

    return {
        key: {
            "scanned_to": watermark["scanned_to"],
            "nonce": watermark["nonce"],
            "history": {
                nonce: execution
                for nonce, (execution, _) in executions.get(key, {}).items()
                if execution[2] <= watermark["scanned_to"]
            },
        }
        for key, watermark in watermarks.items()
    }


def append(
    path: str,
    chain: str,
    safe: str,
    executions: list,
    scanned_to: int,
    nonce: int,
) -> None:
    file_path = os.path.join(path, "out/history.jsonl")
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    separator = ""
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            if f.read(1) != b"\n":
                separator = "\n"

    records = [
        {
            "chain": chain,
            "safe": safe,
            "nonce": execution_nonce,
            "block": block,
            "tx_hash": tx_hash,
            "success": success,
        }
        for execution_nonce, tx_hash, success, block in executions
    ]
    records.append(
        {"chain": chain, "safe": safe, "scanned_to": scanned_to, "nonce": nonce}
    )
    with open(file_path, "a") as f:
        f.write(
            separator
            + "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records)
        )
