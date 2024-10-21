from eth_account.messages import encode_typed_data


def sign_typed_data(signer_key: str, signer_address: str, w3: any, data: dict) -> str:
    """
    Sign an Ethereum typed data hash using a private key stored in .env.

    :param signer_key: The private key to sign the message.
    :param signer_address: The address of the signer.
    :param w3: The Web3 object.
    :param message: The message to sign.
    :return: Signature.
    """

    address = w3.eth.account.from_key(signer_key).address
    if address != signer_address:
        print(
            f"Signer Address ({signer_address}) does not match address from private key ({address})"
        )
        return None

    message = encode_typed_data(full_message=data)
    signature = w3.eth.account.sign_message(message, private_key=signer_key)
    return signature.signature.hex()


def sign_transaction(
    signer_key: str, signer_address: str, w3: any, unsigned_safe_tx: dict
) -> str:
    """
    Sign an Ethereum transaction using a private key stored in .env.

    :param signer_key: The private key to sign the transaction.
    :param signer_address: The address of the signer.
    :param w3: The Web3 object.
    :param unsigned_safe_tx: The unsigned transaction to sign.
    :return: Signed transaction.
    """

    address = w3.eth.account.from_key(signer_key).address
    if address != signer_address:
        print(
            f"Signer Address ({signer_address}) does not match address from private key ({address})"
        )
        return None

    signed_tx = w3.eth.account.sign_transaction(
        unsigned_safe_tx, private_key=signer_key
    )
    return signed_tx
