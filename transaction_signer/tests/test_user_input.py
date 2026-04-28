from unittest.mock import patch

import pytest

from src.user_input import get_chain, get_relayer, get_safe, get_signer

CHAINS = [
    {"name": "Base", "chain_id": 8453, "rpc_name": "RPC_BASE"},
    {"name": "Optimism", "chain_id": 10, "rpc_name": "RPC_OPTIMISM"},
]

SAFES = [
    {"name": "Safe A", "address": "0x1111111111111111111111111111111111111111"},
    {"name": "Safe B", "address": "0x2222222222222222222222222222222222222222"},
]

SIGNERS = [
    {"name": "Signer A", "address": "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
    {"name": "Signer B", "address": "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"},
]

RELAYERS = [
    {"name": "Relayer A", "address": "0xCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"},
    {"name": "Relayer B", "address": "0xDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"},
]


class TestGetChain:
    @patch("src.user_input.inquirer.prompt")
    def test_selects_first_chain(self, mock_prompt):
        mock_prompt.return_value = {"chains": "Base (Chain Id: 8453)"}
        result = get_chain(CHAINS)
        assert result == CHAINS[0]
        assert result["chain_id"] == 8453

    @patch("src.user_input.inquirer.prompt")
    def test_selects_second_chain(self, mock_prompt):
        mock_prompt.return_value = {"chains": "Optimism (Chain Id: 10)"}
        result = get_chain(CHAINS)
        assert result == CHAINS[1]
        assert result["rpc_name"] == "RPC_OPTIMISM"

    @patch("src.user_input.inquirer.prompt")
    def test_parses_chain_id_from_formatted_string(self, mock_prompt):
        mock_prompt.return_value = {"chains": "Some Chain (Chain Id: 42161)"}
        chains = [{"name": "Some Chain", "chain_id": 42161, "rpc_name": "RPC_ARB"}]
        result = get_chain(chains)
        assert result["chain_id"] == 42161


class TestGetSafe:
    @patch("src.user_input.inquirer.prompt")
    def test_selects_safe_by_address(self, mock_prompt):
        mock_prompt.return_value = {
            "safes": "Safe A (0x1111111111111111111111111111111111111111)"
        }
        result = get_safe(SAFES)
        assert result == SAFES[0]

    @patch("src.user_input.inquirer.prompt")
    def test_selects_second_safe(self, mock_prompt):
        mock_prompt.return_value = {
            "safes": "Safe B (0x2222222222222222222222222222222222222222)"
        }
        result = get_safe(SAFES)
        assert result == SAFES[1]


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


class TestGetChainMalformedResponse:
    @patch("src.user_input.inquirer.prompt")
    def test_missing_chain_id_format_raises(self, mock_prompt):
        mock_prompt.return_value = {"chains": "Base"}
        with pytest.raises(IndexError):
            get_chain(CHAINS)


class TestGetChainNoMatch:
    @patch("src.user_input.inquirer.prompt")
    def test_unmatched_chain_id_raises(self, mock_prompt):
        mock_prompt.return_value = {"chains": "Fake (Chain Id: 99999)"}
        with pytest.raises(ValueError):
            get_chain(CHAINS)


class TestGetSafeNoMatch:
    @patch("src.user_input.inquirer.prompt")
    def test_unmatched_address_raises(self, mock_prompt):
        mock_prompt.return_value = {
            "safes": "Unknown (0x0000000000000000000000000000000000000000)"
        }
        with pytest.raises(ValueError):
            get_safe(SAFES)


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


class TestGetChainSingleItem:
    @patch("src.user_input.inquirer.prompt")
    def test_single_chain(self, mock_prompt):
        single = [CHAINS[0]]
        mock_prompt.return_value = {"chains": "Base (Chain Id: 8453)"}
        result = get_chain(single)
        assert result == single[0]


class TestGetSafeSingleItem:
    @patch("src.user_input.inquirer.prompt")
    def test_single_safe(self, mock_prompt):
        single = [SAFES[0]]
        mock_prompt.return_value = {
            "safes": "Safe A (0x1111111111111111111111111111111111111111)"
        }
        result = get_safe(single)
        assert result == single[0]
