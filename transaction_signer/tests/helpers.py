from unittest.mock import MagicMock

SAFE_TX_CONSTANTS = {
    "VALUE_SAFE_TX": 0,
    "SAFE_TX_GAS": 0,
    "BASE_GAS": 0,
    "GAS_PRICE": 0,
    "GAS_TOKEN": "0x0000000000000000000000000000000000000000",
    "REFUND_RECEIVER": "0x0000000000000000000000000000000000000000",
}

RELAY_TX_CONSTANTS = {
    **SAFE_TX_CONSTANTS,
    "VALUE_RELAY_TX": 0,
}

MULTISEND_ADDRESS = "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B"

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

HW_SIGNER_ADDRESS = "0x1234567890abcdef1234567890abcdef12345678"

HW_DOMAIN_HASH = b"\x01" * 32
HW_MESSAGE_HASH = b"\x02" * 32

HW_UNSIGNED_TX = {
    "to": MULTISEND_ADDRESS,
    "value": 0,
    "gas": 100000,
    "nonce": 0,
    "chainId": 8453,
    "data": "0x1234",
    "maxFeePerGas": 1000000000,
    "maxPriorityFeePerGas": 1000000,
}

TYPED_DATA_TEMPLATE = {
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
}


def make_typed_data(
    to=MULTISEND_ADDRESS,
    nonce=0,
    operation=1,
    data="0x1234",
    chain_id=8453,
    verifying_contract="0x1111111111111111111111111111111111111111",
):
    return {
        **TYPED_DATA_TEMPLATE,
        "message": {
            "to": to,
            "value": 0,
            "data": data,
            "operation": operation,
            "safeTxGas": 0,
            "baseGas": 0,
            "gasPrice": 0,
            "gasToken": ZERO_ADDRESS,
            "refundReceiver": ZERO_ADDRESS,
            "nonce": nonce,
        },
        "domain": {
            "chainId": chain_id,
            "verifyingContract": verifying_contract,
        },
    }


def make_mock_safe(
    nonce=0,
    chain_id=8453,
    address="0x1111111111111111111111111111111111111111",
    is_owner=True,
    owners=None,
):
    safe = MagicMock()
    safe.functions.nonce.return_value.call.return_value = nonce
    safe.functions.getChainId.return_value.call.return_value = chain_id
    safe.functions.isOwner.return_value.call.return_value = is_owner
    safe.functions.getOwners.return_value.call.return_value = owners or [
        "0x2222222222222222222222222222222222222222"
    ]
    safe.functions.execTransaction.return_value.build_transaction.return_value = {
        "nonce": 0,
        "value": 0,
        "chainId": chain_id,
        "data": "0xabcdef",
        "to": address,
    }
    safe.address = address
    return safe
