from unittest.mock import patch

import pytest

from src.user_input import (
    describe_transaction,
    get_relayer,
    get_signer,
    get_transaction,
)


SIGNERS = [
    {"name": "Signer A", "address": "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
    {"name": "Signer B", "address": "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"},
]

RELAYERS = [
    {"name": "Relayer A", "address": "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"},
    {"name": "Relayer B", "address": "0xDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"},
]


class TestGetSigner:
    @patch("src.user_input.inquirer.prompt")
    def test_selects_signer(self, mock_prompt):
        mock_prompt.return_value = {
            "signers": "Signer A (0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA)"
        }
        result = get_signer(SIGNERS)
        assert result == SIGNERS[0]

    @patch("src.user_input.inquirer.prompt")
    def test_back_returns_false(self, mock_prompt):
        mock_prompt.return_value = {"signers": "Back"}
        result = get_signer(SIGNERS)
        assert result is False

    @patch("src.user_input.inquirer.prompt")
    def test_choices_include_back(self, mock_prompt):
        mock_prompt.return_value = {"signers": "Back"}
        get_signer(SIGNERS)
        call_args = mock_prompt.call_args[0][0]
        choices = call_args[0].choices
        assert "Back" in choices
        assert len(choices) == len(SIGNERS) + 1


class TestGetRelayer:
    @patch("src.user_input.inquirer.prompt")
    def test_selects_relayer(self, mock_prompt):
        mock_prompt.return_value = {
            "relayers": "Relayer B (0xDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD)"
        }
        result = get_relayer(RELAYERS)
        assert result == RELAYERS[1]

    @patch("src.user_input.inquirer.prompt")
    def test_back_returns_false(self, mock_prompt):
        mock_prompt.return_value = {"relayers": "Back"}
        result = get_relayer(RELAYERS)
        assert result is False

    @patch("src.user_input.inquirer.prompt")
    def test_choices_include_back(self, mock_prompt):
        mock_prompt.return_value = {"relayers": "Back"}
        get_relayer(RELAYERS)
        call_args = mock_prompt.call_args[0][0]
        choices = call_args[0].choices
        assert "Back" in choices
        assert len(choices) == len(RELAYERS) + 1


class TestGetSignerNoMatch:
    @patch("src.user_input.inquirer.prompt")
    def test_unmatched_address_raises(self, mock_prompt):
        mock_prompt.return_value = {
            "signers": "Unknown (0x0000000000000000000000000000000000000000)"
        }
        with pytest.raises(ValueError):
            get_signer(SIGNERS)


class TestGetRelayerNoMatch:
    @patch("src.user_input.inquirer.prompt")
    def test_unmatched_address_raises(self, mock_prompt):
        mock_prompt.return_value = {
            "relayers": "Unknown (0x0000000000000000000000000000000000000000)"
        }
        with pytest.raises(ValueError):
            get_relayer(RELAYERS)


def _entry(number, status="next", nonce=10, name=None, transaction_hash="aa"):
    return {
        "number": number,
        "name": name,
        "chain": {"name": "Base"},
        "safe_config": {"name": "Treasury"},
        "nonce": nonce,
        "threshold": 3,
        "status": status,
        "transaction_hash": transaction_hash,
        "reason": "RPC down",
    }


class TestDescribeTransaction:
    def test_with_name(self):
        assert (
            describe_transaction(_entry(1, name="Staking rewards"))
            == "#1 Staking rewards · Base · Treasury"
        )

    def test_without_name(self):
        assert describe_transaction(_entry(2)) == "#2 Base · Treasury"


class TestGetTransaction:
    def _choices(self, mock_prompt):
        return mock_prompt.call_args.args[0][0].choices

    @patch("src.user_input.inquirer.prompt")
    def test_labels(self, mock_prompt):
        mock_prompt.return_value = {"transactions": "Exit"}
        entries = [
            _entry(1, name="Staking rewards"),
            _entry(2, status="queued", nonce=11, transaction_hash="bb"),
        ]

        get_transaction(entries, {"aa": {"0x1": "s", "0x2": "s"}})

        assert self._choices(mock_prompt) == [
            "#1 Staking rewards · Base · Treasury · nonce 10 · 2/3 signed · next",
            "#2                 · Base · Treasury · nonce 11 · 0/3 signed · queued",
            "Exit",
        ]

    @patch("src.user_input.inquirer.prompt")
    def test_columns_aligned(self, mock_prompt):
        mock_prompt.return_value = {"transactions": "Exit"}
        long_chain = {**_entry(10), "chain": {"name": "Base Sepolia"}}
        long_safe = {**_entry(9, nonce=9), "safe_config": {"name": "Test Safe 1/2"}}

        get_transaction([long_safe, long_chain], {})

        assert self._choices(mock_prompt)[:2] == [
            "#9  Base         · Test Safe 1/2 · nonce 9  · 0/3 signed · next",
            "#10 Base Sepolia · Treasury      · nonce 10 · 0/3 signed · next",
        ]

    @patch("src.user_input.inquirer.prompt")
    def test_unresolved_aligned_with_resolved(self, mock_prompt):
        mock_prompt.return_value = {"transactions": "Exit"}
        unresolved = {
            **_entry(1, status="unresolved"),
            "chain": {"name": "Base Sepolia"},
        }

        get_transaction([unresolved, _entry(2)], {})

        assert self._choices(mock_prompt)[:2] == [
            "#1 Base Sepolia · Treasury · unresolved",
            "#2 Base         · Treasury · nonce 10 · 0/3 signed · next",
        ]

    @patch("src.user_input.inquirer.prompt")
    def test_unresolved_label(self, mock_prompt):
        mock_prompt.return_value = {"transactions": "Exit"}

        get_transaction([_entry(1, status="unresolved")], {})

        assert self._choices(mock_prompt)[0] == "#1 Base · Treasury · unresolved"

    @patch("src.user_input.inquirer.prompt")
    def test_executed_left_out(self, mock_prompt):
        mock_prompt.return_value = {"transactions": "Exit"}

        get_transaction([_entry(1, status="executed"), _entry(2)], {})

        assert len(self._choices(mock_prompt)) == 2

    @patch("src.user_input.inquirer.prompt")
    def test_exit_returns_false(self, mock_prompt):
        mock_prompt.return_value = {"transactions": "Exit"}
        assert get_transaction([_entry(1)], {}) is False

    @patch("src.user_input.inquirer.prompt")
    def test_prompt_none_returns_false(self, mock_prompt):
        mock_prompt.return_value = None
        assert get_transaction([_entry(1)], {}) is False

    @patch("src.user_input.inquirer.prompt")
    def test_returns_selected_entry(self, mock_prompt):
        entries = [_entry(1, status="executed"), _entry(2), _entry(3)]
        mock_prompt.side_effect = lambda q: {"transactions": q[0].choices[1]}

        assert get_transaction(entries, {}) is entries[2]
