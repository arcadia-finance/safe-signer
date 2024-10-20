import os
import requests

from web3 import Web3


def simulate(safe, to, raw_data, operation, constants, tenderly_url):
    # Set signature Threshold of safe to 1.
    storage_slot_threshold = "0x" + Web3.to_bytes(4).rjust(32, b"\0").hex()
    new_threshold = "0x" + Web3.to_bytes(1).rjust(32, b"\0").hex()

    # Create signature where the sender is an owner.
    # the signature is in this case just the address of the sender.
    # we use the first owner of the safe as sender.
    owners = safe.functions.getOwners().call()
    sender = owners[0]
    r = bytearray(Web3.to_bytes(hexstr=sender).rjust(32, b"\0"))
    s = bytearray(Web3.to_bytes(0).rjust(32, b"\0"))
    v = bytearray(Web3.to_bytes(1))
    signature = r + s + v

    tx_data = safe.functions.execTransaction(
        to,
        constants["VALUE_SAFE_TX"],
        Web3.to_bytes(hexstr=raw_data),
        operation,
        constants["SAFE_TX_GAS"],
        constants["BASE_GAS"],
        constants["GAS_PRICE"],
        constants["GAS_TOKEN"],
        constants["REFUND_RECEIVER"],
        Web3.to_bytes(signature),
    ).build_transaction({"gas": 0})

    body = {
        "network_id": safe.functions.getChainId().call(),
        "from": sender,
        "to": safe.address,
        "input": tx_data["data"],
        "save": True,
        "save_if_fails": True,
        "state_objects": {
            safe.address: {"storage": {storage_slot_threshold: new_threshold}}
        },
        "simulation_type": "quick",
    }
    headers = {"X-Access-Key": os.getenv("TENDERLY_KEY")}
    url = tenderly_url + "/simulate"
    r = requests.post(url=url, json=body, headers=headers)
    simulation_id = r.json()["simulation"]["id"]

    # Make url public accessible.
    url = tenderly_url + f"/simulations/{simulation_id}/share"
    requests.post(url=url, headers=headers)

    print(f"see https://www.tdly.co/shared/simulation/{simulation_id}")
