import rlp
import struct

from eth_utils import keccak, to_bytes
from hexbytes import HexBytes
from ledgerblue.comm import getDongle
from ledgerblue.commException import CommException
from web3.datastructures import AttributeDict


def sign_typed_data_hash(
    signer_index: int, signer_address: str, domain_hash: bytes, message_hash: bytes
) -> str:
    """
    Sign an Ethereum typed data hash using a Ledger device.

    :param signer_index: The index of the BIP32 path of the Ethereum address used for signing.
    :param signer_address: The public address of the signer.
    :param domain_hash: The Domain Hash according to EIP712.
    :param message_hash: The Typed Data Hash according to EIP712.
    :return: Signature.
    """

    # Parse Dongle Path.
    path = get_path(signer_index)
    dongle_path = parse_bip32_path(path)

    # Connect Ledger.
    try:
        dongle = getDongle(False)
    except CommException as e:
        print(f"Error communicating with Ledger device: {e}")
        return None

    # Verify that the given public address matches the address at the BIP32 path.
    try:
        address = get_address(dongle, dongle_path)
        if address.lower() != signer_address.lower():
            dongle.close()
            print(
                f"Address at given index ({address}) does not match signers address ({signer_address})"
            )
            return None
    except CommException as e:
        dongle.close()
        print(f"Error communicating with Ledger device: {e}")
        return None
    except Exception as e:
        dongle.close()
        print(f"Unexpected error: {e}")
        return None

    # Sign the hashed message.
    try:
        print(f"Domain Hash is: {domain_hash.hex()}")
        print(f"Message Hash is: {message_hash.hex()}")
        signature = _sign_typed_data_hash(
            dongle, dongle_path, domain_hash, message_hash
        )
        dongle.close()
        return signature.hex()
    except CommException as e:
        dongle.close()
        print(f"Error communicating with Ledger device: {e}")
        return None
    except Exception as e:
        dongle.close()
        print(f"Unexpected error: {e}")
        return None


def sign_transaction(
    signer_index: int, signer_address: str, unsigned_safe_tx: dict
) -> str:
    """
    Sign an Ethereum transaction using a Ledger device.

    :param signer_index: The index of the BIP32 path of the Ethereum address used for signing.
    :param signer_address: The public address of the signer.
    :param unsigned_safe_tx: The unsigned transaction to sign.
    :return: the signed transaction.
    """

    # Parse Dongle Path.
    path = get_path(signer_index)
    dongle_path = parse_bip32_path(path)

    # Connect Ledger.
    try:
        dongle = getDongle(False)
    except CommException as e:
        print(f"Error communicating with Ledger device: {e}")
        return None

    # Verify that the given public address matches the address at the BIP32 path.
    try:
        address = get_address(dongle, dongle_path)
        if address.lower() != signer_address.lower():
            dongle.close()
            print(
                f"Address at given index ({address}) does not match signers address ({signer_address})"
            )
            return None
    except CommException as e:
        dongle.close()
        print(f"Error communicating with Ledger device: {e}")
        return None
    except Exception as e:
        dongle.close()
        print(f"Unexpected error: {e}")
        return None

    # Sign transaction.
    try:
        (v, r, s) = _sign_transaction(dongle, dongle_path, unsigned_safe_tx)
        dongle.close()

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
                    int.from_bytes(r, "big"),
                    int.from_bytes(s, "big"),
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
    except CommException as e:
        dongle.close()
        print(f"Error communicating with Ledger device: {e}")
        return None
    except Exception as e:
        dongle.close()
        print(f"Unexpected error: {e}")
        return None


def get_path(index: int) -> str:
    """
    returns the BIP32 path for an Ethereum address for a given index.

    :param index: The BIP32 path to the Ethereum address used for signing.
    :return: The BIP32 path of the Ethereum address.
    """
    path = f"m/44'/60'/{index}'/0/0"
    return path


def parse_bip32_path(path: str) -> bytes:
    """
    Parses the BIP32 path to a format compatible with Ledger devices.

    :param path: The BIP32 path to the Ethereum address used for signing.
    :return: Parsed Path.
    """

    result = b""
    elements = path.split("/")
    for pathElement in elements[1:]:
        element = pathElement.split("'")
        if len(element) == 1:
            result = result + struct.pack(">I", int(element[0]))
        else:
            result = result + struct.pack(">I", 0x80000000 | int(element[0]))
    return result


def get_address(dongle: any, dongle_path: bytes) -> str:
    # Prepare the APDU command.
    apdu = bytearray.fromhex("e0020100")
    apdu.append(len(dongle_path) + 1)  # length payload
    apdu.append(len(dongle_path) // 4)
    apdu += dongle_path  # payload

    # Get address from dongle.
    result = dongle.exchange(bytes(apdu))

    # Parse address.
    offset = 1 + result[0]
    address = result[offset + 1 : offset + 1 + result[offset]]
    address = f"0x{address.decode()}"
    return address


def _sign_typed_data_hash(
    dongle: any, dongle_path: bytes, domain_hash: bytes, message_hash: bytes
) -> str:
    # Calculate the message hash.
    encoded_tx = domain_hash + message_hash

    # Prepare the APDU command for signing.
    apdu = bytearray.fromhex("e00c0000")  # command
    apdu.append(len(dongle_path) + 1 + len(encoded_tx))  # length payload
    apdu.append(len(dongle_path) // 4)
    apdu += dongle_path + encoded_tx  # payload

    # Get signature from dongle.
    result = dongle.exchange(bytes(apdu))
    v = result[0:1]
    r = result[1 : 1 + 32]
    s = result[1 + 32 : 1 + 64]

    signature = r + s + v
    return signature


def _sign_transaction(dongle: any, dongle_path: bytes, unsigned_safe_tx: dict) -> tuple:
    # RLP-encode the unsigned EIP-1559 transaction.
    encoded_tx = rlp.encode(
        [
            unsigned_safe_tx["chainId"],
            unsigned_safe_tx["nonce"],
            unsigned_safe_tx["maxPriorityFeePerGas"],
            unsigned_safe_tx["maxFeePerGas"],
            unsigned_safe_tx["gas"],
            to_bytes(hexstr=unsigned_safe_tx["to"]),
            unsigned_safe_tx["value"],
            to_bytes(hexstr=unsigned_safe_tx["data"]),
            [],
        ],
        sedes=None,
    )
    # EIP-1559 tx type prefix.
    payload = b"\x02" + encoded_tx

    # First chunk includes the BIP32 path.
    path_len = len(dongle_path) // 4
    first_chunk = bytes([path_len]) + dongle_path + payload
    chunks = [first_chunk]

    # The Ledger Ethereum app accepts up to 255 bytes per APDU payload.
    while len(chunks[-1]) > 255:
        oversized = chunks.pop()
        chunks.append(oversized[:255])
        chunks.append(oversized[255:])

    result = None
    for i, chunk in enumerate(chunks):
        # P1: 0x00 for first chunk, 0x80 for subsequent chunks.
        p1 = 0x00 if i == 0 else 0x80
        apdu = bytearray.fromhex("e004") + bytes([p1, 0x02])
        apdu.append(len(chunk))
        apdu += chunk
        result = dongle.exchange(bytes(apdu))

    v = result[0]
    r = bytes(result[1 : 1 + 32])
    s = bytes(result[1 + 32 : 1 + 64])
    return (v, r, s)
