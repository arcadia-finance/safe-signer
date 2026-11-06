import os

import toml

from src.transactions import resolve_settings
from src.utils.validate_config import SETTINGS, validate, validate_transactions

CONFIG = os.path.join(os.path.dirname(__file__), "data", "config.toml")


def test_config_file_resolves():
    config = toml.load(CONFIG)

    validate(config["safes"], config["signers"], config["relayers"], config["chains"])
    validate_transactions(config["transactions"], config["chains"], config["safes"])
    defaults = {key: config[key] for key in SETTINGS if key in config}
    entries = resolve_settings(
        config["transactions"], config["chains"], config["safes"], defaults
    )

    rewards, payout, pinned = entries
    assert (rewards["name"], rewards["nonce_setting"]) == ("Rewards", "repeat")
    assert (rewards["gas"], rewards["operation"]) == (0, 1)
    assert (payout["name"], payout["nonce_setting"]) == (None, None)
    assert (payout["gas"], payout["max_priority_fee_per_gas"]) == (500000, 0)
    assert pinned["nonce_setting"] == 7
    assert (pinned["operation"], pinned["to"]) == (
        0,
        "0x5555555555555555555555555555555555555555",
    )
