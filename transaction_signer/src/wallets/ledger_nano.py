import struct

from ledgerblue.comm import getDongle
from ledgerblue.commException import CommException


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
        dongle = getDongle(True)
    except CommException as e:
        print(f"Error communicating with Ledger device: {e}")
        return None

    # Verify that the given public address matches the address at the BIP32 path.
    try:
        address = get_address(dongle, dongle_path)
        if address != signer_address:
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
