from eth_abi import encode
from eth_utils import keccak
from web3 import Web3


def get_typed_data(
    safe: any, to: str, raw_data: str, operation: int, constants: dict
) -> dict:
    typed_data = {
        "types": {
            "EIP712Domain": [
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "SafeTx": [
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "data", "type": "bytes"},
                {"name": "operation", "type": "uint8"},
                {"name": "safeTxGas", "type": "uint256"},
                {"name": "baseGas", "type": "uint256"},
                {"name": "gasPrice", "type": "uint256"},
                {"name": "gasToken", "type": "address"},
                {"name": "refundReceiver", "type": "address"},
                {"name": "nonce", "type": "uint256"},
            ],
        },
        "primaryType": "SafeTx",
        "message": {
            "to": to,
            "value": constants["VALUE_SAFE_TX"],
            "data": raw_data,
            "operation": operation,
            "safeTxGas": constants["SAFE_TX_GAS"],
            "baseGas": constants["BASE_GAS"],
            "gasPrice": constants["GAS_PRICE"],
            "gasToken": constants["GAS_TOKEN"],
            "refundReceiver": constants["REFUND_RECEIVER"],
            "nonce": safe.functions.nonce().call(),
        },
        "domain": {
            "chainId": safe.functions.getChainId().call(),
            "verifyingContract": safe.address,
        },
    }
    return typed_data


def get_typed_data_hash(data: dict) -> bytes:
    return keccak(
        encode(
            [
                "bytes32",
                "address",
                "uint256",
                "bytes32",
                "uint8",
                "uint256",
                "uint256",
                "uint256",
                "address",
                "address",
                "uint256",
            ],
            [
                Web3.to_bytes(
                    hexstr="0xbb8310d486368db6bd6f849402fdd73ad53d316b5a4b2644ad6efe0f941286d8"
                ),
                data["message"]["to"],
                data["message"]["value"],
                keccak(hexstr=data["message"]["data"]),
                data["message"]["operation"],
                data["message"]["safeTxGas"],
                data["message"]["baseGas"],
                data["message"]["gasPrice"],
                data["message"]["gasToken"],
                data["message"]["refundReceiver"],
                data["message"]["nonce"],
            ],
        )
    )
