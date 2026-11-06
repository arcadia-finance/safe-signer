import os
import time
from typing import Callable

import requests
from eth_utils import keccak
from web3 import Web3

from src.eip712_typed_data import (
    get_transaction_hash,
    get_typed_data,
    get_typed_data_hash,
)
from src.utils import history
from src.utils.validate_config import SETTINGS, validate_operation

EXECUTION_TOPICS = (
    keccak(text="ExecutionSuccess(bytes32,uint256)"),
    keccak(text="ExecutionFailure(bytes32,uint256)"),
)
INITIAL_RANGE = 1_000_000
RANGE_ERRORS = ("range", "more than", "too many results", "limit exceeded", "-32005")
TRANSIENT_ERRORS = ("429", "rate limit", "timeout")
BACKOFF = (1, 2, 4, 8)
SETTLED_BLOCKS = 100


def resolve_settings(
    transactions: list, chains: list, safes: list, defaults: dict
) -> list[dict]:
    chains_by_name = {chain["name"]: chain for chain in chains}
    safes_by_name = {safe["name"]: safe for safe in safes}
    entries = []
    for number, transaction in enumerate(transactions, start=1):
        chain = chains_by_name[transaction["chain"]]
        safe = safes_by_name[transaction["safe"]]
        entry = {
            "number": number,
            "chain": chain,
            "safe_config": {
                **safe,
                "address": Web3.to_checksum_address(safe["address"]),
            },
            "raw_data": transaction["raw_data"],
            "nonce_setting": transaction.get("nonce"),
            "name": transaction.get("name"),
        }
        for key in SETTINGS:
            for level in (transaction, chain, defaults):
                if key in level:
                    entry[key] = level[key]
                    break
            else:
                raise Exception(f"transaction #{number} has no value for '{key}'.")
        validate_operation(entry["operation"], entry["to"])
        entries.append(entry)
    return entries


def needs_history(nonce_settings: list, live_nonce: int) -> bool:
    return any(
        setting is None or (setting != "repeat" and setting < live_nonce)
        for setting in nonce_settings
    )


def resolve_group(
    entries: list[tuple[int | str | None, Callable[[int], str]]],
    live_nonce: int,
    history: dict[int, tuple[str, bool, int]],
) -> list[tuple[int, str]]:
    if needs_history([setting for setting, _ in entries], live_nonce) and set(
        history
    ) != set(range(live_nonce)):
        raise ValueError(
            f"History has {len(history)} executions, expected {live_nonce}."
        )

    results = [None] * len(entries)
    pinned = set()
    claimed_by_pins = set()
    for i, (setting, hash_at) in enumerate(entries):
        if setting is None or setting == "repeat":
            continue
        pinned.add(setting)
        if setting < live_nonce:
            tx_hash, success, _ = history[setting]
            if success and tx_hash == hash_at(setting):
                results[i] = (setting, "executed")
                claimed_by_pins.add(setting)
            else:
                results[i] = (setting, "unresolved")
        else:
            results[i] = (setting, "next" if setting == live_nonce else "queued")

    for nonce, (tx_hash, success, _) in sorted(history.items()):
        if not success or nonce in claimed_by_pins:
            continue
        for i, (setting, hash_at) in enumerate(entries):
            if setting is None and results[i] is None and hash_at(nonce) == tx_hash:
                results[i] = (nonce, "executed")
                break

    nonce = live_nonce
    for i in range(len(entries)):
        if results[i] is not None:
            continue
        while nonce in pinned:
            nonce += 1
        results[i] = (nonce, "next" if nonce == live_nonce else "queued")
        nonce += 1
    return results


def check_order(numbers: list[int], results: list[tuple[int, str]]) -> None:
    pending = []
    for number, (nonce, status) in zip(numbers, results):
        if status == "executed":
            if pending:
                raise ValueError(
                    f"#{number} executed before #{pending[0][0]}; the order cannot be resolved."
                )
        elif status != "unresolved":
            if pending and pending[-1][1] > nonce:
                raise ValueError(
                    f"#{pending[-1][0]} comes before #{number} but has nonce {pending[-1][1]}, after {nonce}; the order cannot be resolved."
                )
            pending.append((number, nonce))


def scan_history(
    w3,
    safe_address: str,
    block: int,
    live_nonce: int,
    start: dict | None,
    chain_state: dict,
) -> dict:
    if start is None:
        first_nonce, known = 0, {}
        logs = _collect(w3, safe_address, 0, block, live_nonce, chain_state)
    else:
        first_nonce, known = start["nonce"], start["history"]
        logs = []
        if block > start["scanned_to"]:
            logs = _collect(
                w3, safe_address, start["scanned_to"] + 1, block, None, chain_state
            )

    expected = live_nonce - first_nonce
    if len(logs) != expected:
        raise ValueError(
            f"Found {len(logs)} executions for {safe_address}, expected {expected}."
        )

    logs.sort(key=lambda log: (log["blockNumber"], log["logIndex"]))
    history = dict(known)
    for offset, log in enumerate(logs):
        history[first_nonce + offset] = (
            _tx_hash(log),
            bytes(log["topics"][0]) == EXECUTION_TOPICS[0],
            log["blockNumber"],
        )
    return {"scanned_to": block, "nonce": live_nonce, "history": history}


def _tx_hash(log) -> str:
    if len(log["topics"]) > 1:
        return bytes(log["topics"][1]).hex()
    return bytes(log["data"])[:32].hex()


def _collect(
    w3,
    safe_address: str,
    lowest: int,
    highest: int,
    needed: int | None,
    chain_state: dict,
) -> list:
    chain_state.setdefault("range", INITIAL_RANGE)
    logs = []
    to_block = highest
    queries = 0
    while to_block >= lowest and (needed is None or len(logs) < needed):
        from_block = max(lowest, to_block - chain_state["range"] + 1)
        params = {
            "address": safe_address,
            "topics": [list(EXECUTION_TOPICS)],
            "fromBlock": from_block,
            "toBlock": to_block,
        }
        try:
            logs.extend(_get_logs(w3, params))
        except Exception as e:
            if chain_state["range"] == 1 or not _shrinkable(e):
                raise
            chain_state["range"] //= 2
            continue
        to_block = from_block - 1
        queries += 1
        if queries % 10 == 0:
            print(f"Scanning history of {safe_address}, at block {from_block}...")
    return logs


def _get_logs(w3, params: dict) -> list:
    for delay in BACKOFF:
        try:
            return w3.eth.get_logs(params)
        except Exception as e:
            if not _transient(e):
                raise
            time.sleep(delay)
    return w3.eth.get_logs(params)


def _transient(error: Exception) -> bool:
    if isinstance(error, (requests.Timeout, requests.ConnectionError)):
        return True
    message = str(error).lower()
    return any(term in message for term in TRANSIENT_ERRORS)


def _shrinkable(error: Exception) -> bool:
    if isinstance(error, requests.Timeout):
        return True
    message = str(error).lower()
    return "timeout" in message or any(term in message for term in RANGE_ERRORS)


def connect_chains(entries: list[dict]) -> dict[str, dict]:
    connections = {}
    for entry in entries:
        chain = entry["chain"]
        if chain["name"] not in connections:
            connections[chain["name"]] = _connect(chain)
    return connections


def _connect(chain: dict) -> dict:
    rpc_url = os.getenv(chain["rpc_name"])
    if not rpc_url:
        return {
            "error": f"RPC URL environment variable '{chain['rpc_name']}' is not set."
        }
    w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": 30}))
    try:
        chain_id = w3.eth.chain_id
    except Exception as e:
        return {"error": str(e)}
    if chain_id != chain["chain_id"]:
        return {"error": f"Chain Id is {chain_id}, expected {chain['chain_id']}"}
    return {"w3": w3, "state": {}}


def load(
    entries: list[dict],
    connections: dict,
    safe_abi: list,
    constants: dict,
    cache: dict,
    path: str,
) -> list[dict]:
    groups = {}
    for entry in entries:
        key = (entry["chain"]["name"], entry["safe_config"]["address"])
        groups.setdefault(key, []).append(entry)

    saved = history.load(path)
    loaded = {}
    for key, group in groups.items():
        connection = connections[key[0]]
        try:
            if "error" in connection:
                raise ValueError(connection["error"])
            results = _load_group(
                key, group, connection, safe_abi, constants, cache, saved
            )
        except Exception as e:
            results = [
                {**entry, "status": "unresolved", "reason": str(e)} for entry in group
            ]
        for result in results:
            loaded[result["number"]] = result
    return [loaded[entry["number"]] for entry in entries]


def _load_group(
    key: tuple,
    group: list,
    connection: dict,
    safe_abi: list,
    constants: dict,
    cache: dict,
    saved: dict,
) -> list[dict]:
    w3 = connection["w3"]
    chain_name, address = key
    chain_id = group[0]["chain"]["chain_id"]
    block = w3.eth.block_number
    if w3.eth.get_code(address, block) == b"":
        raise ValueError(f"No Safe contract at {address} on {chain_name}.")
    safe = w3.eth.contract(address=address, abi=safe_abi)
    live_nonce = safe.functions.nonce().call(block_identifier=block)
    threshold = safe.functions.getThreshold().call(block_identifier=block)
    domain_hash = safe.functions.domainSeparator().call(block_identifier=block)

    settings = [entry["nonce_setting"] for entry in group]
    executions = {}
    if needs_history(settings, live_nonce):
        if key not in cache:
            start = saved.get(key)
            cache[key] = {**start, "saved_to": start["scanned_to"]} if start else None
        start = cache[key]
        scanned = scan_history(
            w3, address, block, live_nonce, start, connection["state"]
        )
        cache[key] = {**scanned, "saved_to": start["saved_to"] if start else -1}
        executions = scanned["history"]

    def build(entry: dict, nonce: int) -> tuple[dict, bytes, str]:
        typed_data = get_typed_data(
            address,
            chain_id,
            entry["to"],
            entry["raw_data"],
            entry["operation"],
            nonce,
            constants,
        )
        message_hash = get_typed_data_hash(typed_data)
        transaction_hash = get_transaction_hash(
            domain_hash, message_hash, constants["SIGN_MAGIC"]
        )
        return typed_data, message_hash, transaction_hash

    results = resolve_group(
        [
            (entry["nonce_setting"], lambda n, entry=entry: build(entry, n)[2])
            for entry in group
        ],
        live_nonce,
        executions,
    )
    check_order([entry["number"] for entry in group], results)

    loaded = []
    for entry, (nonce, status) in zip(group, results):
        typed_data, message_hash, transaction_hash = build(entry, nonce)
        result = {
            **entry,
            "history_key": key,
            "w3": w3,
            "safe": safe,
            "threshold": threshold,
            "nonce": nonce,
            "status": status,
            "typed_data": typed_data,
            "domain_hash": domain_hash,
            "message_hash": message_hash,
            "transaction_hash": transaction_hash,
        }
        if status == "unresolved":
            result["reason"] = (
                f"Nonce {nonce} was used by another transaction 0x{executions[nonce][0]}."
            )
        loaded.append(result)
    return loaded


def save_history(cache: dict, key: tuple, path: str) -> None:
    scanned = cache.get(key)
    if scanned is None:
        return
    settled = scanned["scanned_to"] - SETTLED_BLOCKS
    if settled <= scanned["saved_to"]:
        return
    executions = sorted(scanned["history"].items())
    history.append(
        path,
        key[0],
        key[1],
        [
            (nonce, tx_hash, success, block)
            for nonce, (tx_hash, success, block) in executions
            if scanned["saved_to"] < block <= settled
        ],
        settled,
        sum(1 for _, (_, _, block) in executions if block <= settled),
    )
    scanned["saved_to"] = settled
