import os
from unittest.mock import MagicMock, patch

import pytest

from helpers import MULTISEND_ADDRESS, SAFE_TX_CONSTANTS, make_mock_safe
from src.tenderly import simulate

TO = MULTISEND_ADDRESS
RAW_DATA = "0x1234"
TENDERLY_URL = "https://api.tenderly.co/api/v1/account/test/project/test"


class TestTenderlyMissingKey:
    def test_raises_when_tenderly_key_not_set(self):
        safe = make_mock_safe()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(
                Exception, match="TENDERLY_KEY environment variable is not set"
            ):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)


class TestTenderlyHttpError:
    @patch("src.tenderly.requests.post")
    def test_raises_on_non_200(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            with pytest.raises(Exception, match="Tenderly simulation failed.*401"):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

    @patch("src.tenderly.requests.post")
    def test_raises_on_500(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            with pytest.raises(Exception, match="Tenderly simulation failed.*500"):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)


class TestTenderlyMalformedResponse:
    @patch("src.tenderly.requests.post")
    def test_raises_when_no_simulation_key(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "something went wrong"}
        mock_post.return_value = mock_response

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            with pytest.raises(Exception, match="Unexpected Tenderly response"):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

    @patch("src.tenderly.requests.post")
    def test_raises_when_no_id_in_simulation(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"simulation": {"status": "failed"}}
        mock_post.return_value = mock_response

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            with pytest.raises(Exception, match="Unexpected Tenderly response"):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)


class TestTenderlyHappyPath:
    @patch("src.tenderly.requests.post")
    def test_prints_simulation_url(self, mock_post, capsys):
        sim_response = MagicMock()
        sim_response.status_code = 200
        sim_response.json.return_value = {"simulation": {"id": "sim_abc123"}}

        share_response = MagicMock()
        share_response.status_code = 200

        mock_post.side_effect = [sim_response, share_response]

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

        captured = capsys.readouterr()
        assert "sim_abc123" in captured.out
        assert "tdly.co/shared/simulation" in captured.out

    @patch("src.tenderly.requests.post")
    def test_calls_simulate_then_share(self, mock_post):
        sim_response = MagicMock()
        sim_response.status_code = 200
        sim_response.json.return_value = {"simulation": {"id": "sim_xyz"}}

        share_response = MagicMock()
        mock_post.side_effect = [sim_response, share_response]

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

        assert mock_post.call_count == 2
        assert "simulate" in str(mock_post.call_args_list[0])
        assert "share" in str(mock_post.call_args_list[1])

    @patch("src.tenderly.requests.post")
    def test_sends_correct_headers(self, mock_post):
        sim_response = MagicMock()
        sim_response.status_code = 200
        sim_response.json.return_value = {"simulation": {"id": "sim_1"}}
        share_response = MagicMock()
        mock_post.side_effect = [sim_response, share_response]

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "my_secret_key"}):
            simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

        for call in mock_post.call_args_list:
            headers = call.kwargs.get("headers", {})
            assert headers.get("X-Access-Key") == "my_secret_key"

    @patch("src.tenderly.requests.post")
    def test_uses_first_owner_as_sender(self, mock_post):
        sim_response = MagicMock()
        sim_response.status_code = 200
        sim_response.json.return_value = {"simulation": {"id": "sim_1"}}
        share_response = MagicMock()
        mock_post.side_effect = [sim_response, share_response]

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

        sim_call_body = mock_post.call_args_list[0].kwargs["json"]
        assert sim_call_body["from"] == "0x2222222222222222222222222222222222222222"

    @patch("src.tenderly.requests.post")
    def test_overrides_threshold_to_one(self, mock_post):
        sim_response = MagicMock()
        sim_response.status_code = 200
        sim_response.json.return_value = {"simulation": {"id": "sim_1"}}
        share_response = MagicMock()
        mock_post.side_effect = [sim_response, share_response]

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

        sim_call_body = mock_post.call_args_list[0].kwargs["json"]
        state_objects = sim_call_body["state_objects"]
        assert safe.address in state_objects
        storage = state_objects[safe.address]["storage"]
        threshold_slot = (
            "0x0000000000000000000000000000000000000000000000000000000000000004"
        )
        assert threshold_slot in storage
        assert (
            storage[threshold_slot]
            == "0x0000000000000000000000000000000000000000000000000000000000000001"
        )


class TestTenderlyEmptyOwners:
    def test_raises_on_no_owners(self):
        safe = make_mock_safe(owners=[])
        safe.functions.getOwners.return_value.call.return_value = []

        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            with pytest.raises(IndexError):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)


class TestTenderlyNetworkError:
    @patch("src.tenderly.requests.post")
    def test_connection_error_propagates(self, mock_post):
        import requests

        mock_post.side_effect = requests.ConnectionError("connection refused")

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            with pytest.raises(requests.ConnectionError):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)

    @patch("src.tenderly.requests.post")
    def test_non_json_response_body_raises(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("No JSON")
        mock_post.return_value = mock_response

        safe = make_mock_safe()
        with patch.dict(os.environ, {"TENDERLY_KEY": "test_key"}):
            with pytest.raises(ValueError):
                simulate(safe, TO, RAW_DATA, 1, SAFE_TX_CONSTANTS, TENDERLY_URL)
