import os

import toml

from src.transactions import resolve_settings
from src.utils.validate_config import SETTINGS, validate, validate_transactions

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..")


def test_example_config_resolves():
    config = toml.load(os.path.join(PROJECT_DIR, "config_transaction_signer.toml"))

    validate(config["safes"], config["signers"], config["relayers"], config["chains"])
    validate_transactions(config["transactions"], config["chains"], config["safes"])
    defaults = {key: config[key] for key in SETTINGS if key in config}
    entries = resolve_settings(
        config["transactions"], config["chains"], config["safes"], defaults
    )

    assert len(entries) >= 2
