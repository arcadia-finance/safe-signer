import rlp

from eth_utils import keccak, to_bytes
from hexbytes import HexBytes
from trezorlib import ethereum
from trezorlib.client import TrezorClient
from trezorlib.tools import parse_path
from trezorlib.transport import get_transport, TransportException
from trezorlib.ui import ClickUI
from web3.datastructures import AttributeDict


def sign_typed_data_hash(
    signer_index: int, signer_address: str, domain_hash: bytes, message_hash: bytes
) -> str:
    """
    Sign an Ethereum typed data hash using a Trezor One device.

    :param signer_index: The index of the BIP32 path of the Ethereum address used for signing.
    :param signer_address: The public address of the signer.
    :param domain_hash: The Domain Hash according to EIP712.
    :param message_hash: The Typed Data Hash according to EIP712.
    :return: Signature.
    """
    # Parse BIP32 path.
    path = get_path(signer_index)
    bip32_path = parse_path(path)

    # Connect Trezor.
    try:
        transport = get_transport()
        client = TrezorClient(transport, ui=ClickUI())
    except TransportException as e:
        print(f"Error communicating with Trezor device: {e}")
        return None

    # Verify that the given public address matches the address at the BIP32 path.
    try:
        address = ethereum.get_address(client=client, n=bip32_path)
        if address != signer_address:
            print(
                f"Address at given index ({address}) does not match signers address ({signer_address})"
            )
            return None
    except Exception as e:
        client.close()
        print(f"An error occurred: {e}")
        return None

    # Sign the hashed message.
    try:
        signature = ethereum.sign_typed_data_hash(
            client=client,
            n=bip32_path,
            domain_hash=domain_hash,
            message_hash=message_hash,
        )
        client.close()
        return signature.signature.hex()
    except Exception as e:
        client.close()
        print(f"An error occurred: {e}")
        return None


def sign_transaction(
    signer_index: int, signer_address: str, unsigned_safe_tx: dict
) -> str:
    """
    Sign an Ethereum transaction using a Trezor Model 1 device.

    :param signer_index: The index of the BIP32 path of the Ethereum address used for signing.
    :param signer_address: The public address of the signer.
    :param unsigned_safe_tx: The unsigned transaction to sign.
    :return: the signed transaction.
    """
    # Parse BIP32 path.
    path = get_path(signer_index)
    bip32_path = parse_path(path)

    # Connect Trezor.
    try:
        transport = get_transport()
        client = TrezorClient(transport, ui=ClickUI())
    except TransportException as e:
        print(f"Error communicating with Trezor device: {e}")
        return None

    # Verify that the given public address matches the address at the BIP32 path.
    try:
        address = ethereum.get_address(client=client, n=bip32_path)
        if address != signer_address:
            print(
                f"Address at given index ({address}) does not match signers address ({signer_address})"
            )
            return None
    except Exception as e:
        client.close()
        print(f"An error occurred: {e}")
        return None

    # Sign transaction.
    try:
        (v, r, s) = ethereum.sign_tx_eip1559(
            client=client,
            n=bip32_path,
            nonce=unsigned_safe_tx["nonce"],
            gas_limit=unsigned_safe_tx["gas"],
            to=unsigned_safe_tx["to"],
            value=unsigned_safe_tx["value"],
            data=to_bytes(hexstr=unsigned_safe_tx["data"]),
            chain_id=unsigned_safe_tx["chainId"],
            max_gas_fee=unsigned_safe_tx["maxFeePerGas"],
            max_priority_fee=unsigned_safe_tx["maxPriorityFeePerGas"],
        )
        client.close()

        # RLP encoding
        signed_raw_tx = HexBytes(
            "0x02"
            + rlp.encode(
                [
                    unsigned_safe_tx["chainId"],
                    unsigned_safe_tx["nonce"],
                    unsigned_safe_tx["maxPriorityFeePerGas"],
                    unsigned_safe_tx["maxFeePerGas"],
                    unsigned_safe_tx["gas"],
                    to_bytes(hexstr=unsigned_safe_tx["to"]),
                    unsigned_safe_tx["value"],
                    to_bytes(hexstr=unsigned_safe_tx["data"]),
                    [],  # Access list
                    v,
                    r,
                    s,
                ],
                sedes=None,
            ).hex()
        )

        signed_tx = AttributeDict(
            {
                "raw_transaction": signed_raw_tx,
                "hash": HexBytes(keccak(signed_raw_tx)),
                "r": int.from_bytes(r, "big"),
                "s": int.from_bytes(s, "big"),
                "v": v,
            }
        )
        return signed_tx
    except Exception as e:
        client.close()
        print(f"An error occurred while signing transaction: {e}")
        return None


def get_path(index: int) -> str:
    """
    returns the BIP32 path for an Ethereum address for a given index.

    :param index: The BIP32 path to the Ethereum address used for signing.
    :return: The BIP32 path of the Ethereum address.
    """
    path = f"m/44'/60'/0'/0/{index}"
    return path
