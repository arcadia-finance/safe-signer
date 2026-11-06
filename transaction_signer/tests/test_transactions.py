import json
import os
from unittest.mock import MagicMock, PropertyMock, patch

import toml

import pytest
from eth_utils import keccak
from hexbytes import HexBytes
from web3 import Web3

import test_golden_signing as golden

from helpers import MULTISEND_ADDRESS
from src.transactions import (
    check_order,
    connect_chains,
    load,
    resolve_group,
    resolve_settings,
    save_history,
    scan_history,
)
from src.utils import history

CONSTANTS = toml.load(os.path.join(golden.PROJECT_DIR, "data/constants.toml"))

HASH_1 = "11" * 32
HASH_2 = "22" * 32
HASH_3 = "33" * 32

CHAINS = [{"name": "Base", "chain_id": 8453, "rpc_name": "RPC_BASE"}]
SAFES = [{"name": "Treasury", "address": "0xfd6db26edc581d8f381f46ef4a6396a762b66e95"}]
DEFAULTS = {
    "to": MULTISEND_ADDRESS,
    "operation": 1,
    "gas": 0,
    "max_fee_per_gas": 0,
    "max_priority_fee_per_gas": 1000000,
}
OTHER = "0x1234567890123456789012345678901234567890"
LEVEL_VALUES = {
    "to": (MULTISEND_ADDRESS, OTHER, "0x0000000000000000000000000000000000000001"),
    "operation": (1, 0, 0),
    "gas": (0, 100000, 200000),
    "max_fee_per_gas": (0, 1, 2),
    "max_priority_fee_per_gas": (1000000, 0, 5),
}


def _transaction(**overrides):
    return {"chain": "Base", "safe": "Treasury", "raw_data": "0x1234", **overrides}


def _chains(**overrides):
    return [{**CHAINS[0], **overrides}]


def _call_settings(key, top, chain, transaction):
    defaults = {**DEFAULTS, key: top}
    if key == "to":
        defaults["operation"] = 0
    chain_overrides = {} if chain is None else {key: chain}
    transaction_overrides = {} if transaction is None else {key: transaction}
    if key == "to":
        transaction_overrides["operation"] = 0
    return resolve_settings(
        [_transaction(**transaction_overrides)],
        _chains(**chain_overrides),
        SAFES,
        defaults,
    )[0]


class TestResolveSettings:
    @pytest.mark.parametrize("key", list(LEVEL_VALUES))
    def test_top_level_used(self, key):
        top, _, _ = LEVEL_VALUES[key]
        assert _call_settings(key, top, None, None)[key] == top

    @pytest.mark.parametrize("key", list(LEVEL_VALUES))
    def test_chain_overrides_top_level(self, key):
        top, chain, _ = LEVEL_VALUES[key]
        assert _call_settings(key, top, chain, None)[key] == chain

    @pytest.mark.parametrize("key", list(LEVEL_VALUES))
    def test_transaction_overrides_chain(self, key):
        top, chain, transaction = LEVEL_VALUES[key]
        assert _call_settings(key, top, chain, transaction)[key] == transaction

    def test_zero_is_a_value(self):
        entry = resolve_settings(
            [_transaction(gas=0)], CHAINS, SAFES, {**DEFAULTS, "gas": 500000}
        )[0]
        assert entry["gas"] == 0

    def test_missing_everywhere_raises(self):
        defaults = {k: v for k, v in DEFAULTS.items() if k != "gas"}
        with pytest.raises(Exception, match="transaction #1 has no value for 'gas'"):
            resolve_settings([_transaction()], CHAINS, SAFES, defaults)

    def test_multisend_check_on_resolved_values(self):
        with pytest.raises(Exception, match="to-address must always be"):
            resolve_settings([_transaction(to="0x1234")], CHAINS, SAFES, DEFAULTS)

    def test_entry_fields(self):
        entry = resolve_settings(
            [_transaction(), _transaction(nonce="repeat")], CHAINS, SAFES, DEFAULTS
        )[1]
        assert entry["number"] == 2
        assert entry["chain"] == CHAINS[0]
        assert entry["safe_config"]["name"] == "Treasury"
        assert entry["raw_data"] == "0x1234"
        assert entry["nonce_setting"] == "repeat"

    def test_one_off_has_no_nonce_setting(self):
        entry = resolve_settings([_transaction()], CHAINS, SAFES, DEFAULTS)[0]
        assert entry["nonce_setting"] is None

    def test_safe_address_checksummed(self):
        entry = resolve_settings([_transaction()], CHAINS, SAFES, DEFAULTS)[0]
        assert (
            entry["safe_config"]["address"]
            == "0xFd6db26eDc581D8F381f46eF4a6396A762b66E95"
        )


def h(name):
    return lambda n: f"{name}@{n}"


def hist(live, executed=None):
    executed = executed or {}
    history = {n: (f"other@{n}", True, n) for n in range(live)}
    for n, (tx_hash, success) in executed.items():
        history[n] = (tx_hash, success, n)
    return history


class TestResolveGroup:
    def test_one_offs_nothing_executed(self):
        result = resolve_group([(None, h("a")), (None, h("b"))], 10, hist(10))
        assert result == [(10, "next"), (11, "queued")]

    def test_one_off_executed(self):
        result = resolve_group(
            [(None, h("a")), (None, h("b"))], 11, hist(11, {10: ("a@10", True)})
        )
        assert result == [(10, "executed"), (11, "next")]

    def test_one_offs_all_executed(self):
        executed = {10: ("a@10", True), 11: ("b@11", True), 12: ("c@12", True)}
        result = resolve_group(
            [(None, h("a")), (None, h("b")), (None, h("c"))], 13, hist(13, executed)
        )
        assert result == [(10, "executed"), (11, "executed"), (12, "executed")]

    def test_one_off_executed_long_ago(self):
        result = resolve_group(
            [(None, h("a")), (None, h("b"))], 13, hist(13, {10: ("a@10", True)})
        )
        assert result == [(10, "executed"), (13, "next")]

    def test_unrelated_took_nonce(self):
        result = resolve_group([(None, h("a")), (None, h("b"))], 11, hist(11))
        assert result == [(11, "next"), (12, "queued")]

    def test_failure_not_executed(self):
        result = resolve_group(
            [(None, h("a")), (None, h("b"))], 11, hist(11, {10: ("a@10", False)})
        )
        assert result == [(11, "next"), (12, "queued")]

    def test_duplicate_one_offs_claim_one_execution_each(self):
        result = resolve_group(
            [(None, h("same")), (None, h("same"))],
            11,
            hist(11, {10: ("same@10", True)}),
        )
        assert result == [(10, "executed"), (11, "next")]

    def test_reordered_with_executed(self):
        result = resolve_group(
            [(None, h("b")), (None, h("a"))], 11, hist(11, {10: ("a@10", True)})
        )
        assert result == [(11, "next"), (10, "executed")]

    def test_repeat_never_executed(self):
        result = resolve_group([("repeat", h("r"))], 11, hist(11, {10: ("r@10", True)}))
        assert result == [(11, "next")]

    def test_repeat_needs_no_history(self):
        assert resolve_group([("repeat", h("r"))], 11, {}) == [(11, "next")]

    def test_pin_executed(self):
        result = resolve_group([(10, h("p"))], 12, hist(12, {10: ("p@10", True)}))
        assert result == [(10, "executed")]

    def test_pin_taken_by_other_transaction(self):
        assert resolve_group([(10, h("p"))], 12, hist(12)) == [(10, "unresolved")]

    def test_pin_next_and_queued(self):
        assert resolve_group([(10, h("p")), (12, h("q"))], 10, {}) == [
            (10, "next"),
            (12, "queued"),
        ]

    def test_one_off_does_not_claim_pinned_nonce(self):
        result = resolve_group(
            [(None, h("p")), (10, h("p"))], 11, hist(11, {10: ("p@10", True)})
        )
        assert result == [(11, "next"), (10, "executed")]

    def test_one_off_executed_at_unresolved_pin(self):
        result = resolve_group(
            [(None, h("a")), (10, h("p"))], 11, hist(11, {10: ("a@10", True)})
        )
        assert result == [(10, "executed"), (10, "unresolved")]

    def test_pin_failed_execution_unresolved(self):
        result = resolve_group([(10, h("p"))], 11, hist(11, {10: ("p@10", False)}))
        assert result == [(10, "unresolved")]

    def test_free_nonces_skip_pins(self):
        result = resolve_group(
            [(None, h("a")), (11, h("p")), ("repeat", h("r"))], 10, hist(10)
        )
        assert result == [(10, "next"), (11, "queued"), (12, "queued")]

    def test_live_nonce_zero(self):
        assert resolve_group([(None, h("a")), (None, h("b"))], 0, {}) == [
            (0, "next"),
            (1, "queued"),
        ]

    def test_incomplete_history_raises(self):
        history = hist(3)
        del history[1]
        with pytest.raises(ValueError, match="History"):
            resolve_group([(None, h("a"))], 3, history)


SAFE_ADDRESS = "0xFd6db26eDc581D8F381f46eF4a6396A762b66E95"
SUCCESS = keccak(text="ExecutionSuccess(bytes32,uint256)")
FAILURE = keccak(text="ExecutionFailure(bytes32,uint256)")


def _log(block, tx_hash, success=True, log_index=0, address=SAFE_ADDRESS):
    return {
        "address": address,
        "topics": [HexBytes(SUCCESS if success else FAILURE)],
        "blockNumber": block,
        "logIndex": log_index,
        "data": HexBytes(bytes.fromhex(tx_hash) + bytes(32)),
    }


class FakeEth:
    def __init__(self, logs, reject=None):
        self.logs = logs
        self.reject = reject
        self.calls = []

    def get_logs(self, params):
        self.calls.append(params)
        assert len(self.calls) < 200
        if self.reject:
            error = self.reject(params)
            if error:
                raise error
        topics = {bytes(t) for t in params["topics"][0]}
        return [
            log
            for log in self.logs
            if log["address"] == params["address"]
            and bytes(log["topics"][0]) in topics
            and params["fromBlock"] <= log["blockNumber"] <= params["toBlock"]
        ]


def _w3(logs, reject=None):
    w3 = MagicMock()
    w3.eth = FakeEth(logs, reject)
    return w3


def _span(params):
    return params["toBlock"] - params["fromBlock"] + 1


@patch("src.transactions.time.sleep")
class TestScanHistory:
    def test_full_history_across_windows(self, _sleep):
        w3 = _w3([_log(100, HASH_1), _log(1_200_000, HASH_2), _log(2_400_000, HASH_3)])

        result = scan_history(w3, SAFE_ADDRESS, 2_500_000, 3, None, {})

        assert result == {
            "scanned_to": 2_500_000,
            "nonce": 3,
            "history": {
                0: (HASH_1, True, 100),
                1: (HASH_2, True, 1_200_000),
                2: (HASH_3, True, 2_400_000),
            },
        }

    def test_windows_do_not_overlap(self, _sleep):
        w3 = _w3([_log(1_500_001, HASH_1), _log(2_000_000, HASH_2)])

        result = scan_history(w3, SAFE_ADDRESS, 2_500_000, 2, None, {})

        assert set(result["history"]) == {0, 1}
        windows = sorted((c["fromBlock"], c["toBlock"]) for c in w3.eth.calls)
        for (_, high), (low, _) in zip(windows, windows[1:]):
            assert low == high + 1

    def test_filters_by_safe_and_both_topics(self, _sleep):
        w3 = _w3([_log(10, HASH_1), _log(11, HASH_2, address=OTHER)])

        result = scan_history(w3, SAFE_ADDRESS, 100, 1, None, {})

        assert result["history"] == {0: (HASH_1, True, 10)}
        for call in w3.eth.calls:
            assert call["address"] == SAFE_ADDRESS
            assert [bytes(t) for t in call["topics"][0]] == [SUCCESS, FAILURE]

    def test_failure_event_takes_nonce(self, _sleep):
        w3 = _w3([_log(10, HASH_1), _log(20, HASH_2, success=False)])

        result = scan_history(w3, SAFE_ADDRESS, 100, 2, None, {})

        assert result["history"][1] == (HASH_2, False, 20)

    def test_same_block_ordered_by_log_index(self, _sleep):
        w3 = _w3([_log(10, HASH_2, log_index=5), _log(10, HASH_1, log_index=2)])

        result = scan_history(w3, SAFE_ADDRESS, 100, 2, None, {})

        assert result["history"][0][0] == HASH_1
        assert result["history"][1][0] == HASH_2

    def test_range_rejected_shrinks(self, _sleep):
        state = {}
        w3 = _w3(
            [_log(10, HASH_1), _log(20_000, HASH_2)],
            lambda p: ValueError("block range too large") if _span(p) > 5_000 else None,
        )

        result = scan_history(w3, SAFE_ADDRESS, 30_000, 2, None, state)

        assert set(result["history"]) == {0, 1}
        assert state["range"] <= 5_000

    def test_range_one_still_rejected_raises(self, _sleep):
        w3 = _w3([], lambda p: ValueError("query exceeds max block range"))

        with pytest.raises(ValueError, match="max block range"):
            scan_history(w3, SAFE_ADDRESS, 100, 1, None, {})
        assert len(w3.eth.calls) <= 25

    def test_timeout_after_backoff_shrinks(self, _sleep):
        state = {}
        w3 = _w3(
            [_log(10, HASH_1)],
            lambda p: ValueError("request timeout") if _span(p) > 5_000 else None,
        )

        result = scan_history(w3, SAFE_ADDRESS, 30_000, 1, None, state)

        assert result["history"] == {0: (HASH_1, True, 10)}
        assert state["range"] <= 5_000

    def test_rate_limit_backs_off(self, sleep):
        failures = [ValueError("429 Too Many Requests")] * 2
        state = {}
        w3 = _w3([_log(10, HASH_1)], lambda p: failures.pop() if failures else None)

        scan_history(w3, SAFE_ADDRESS, 100, 1, None, state)

        assert [c.args[0] for c in sleep.call_args_list] == [1, 2]
        assert state["range"] == 1_000_000

    def test_other_error_raises_without_shrinking(self, sleep):
        state = {}
        w3 = _w3([], lambda p: ValueError("500 Internal Server Error"))

        with pytest.raises(ValueError, match="500"):
            scan_history(w3, SAFE_ADDRESS, 100, 1, None, state)
        assert len(w3.eth.calls) == 1
        assert state["range"] == 1_000_000
        sleep.assert_not_called()

    def test_fewer_events_than_nonce_raises(self, _sleep):
        w3 = _w3([_log(10, HASH_1), _log(20, HASH_2)])

        with pytest.raises(ValueError, match="Found 2 executions .* expected 3"):
            scan_history(w3, SAFE_ADDRESS, 100, 3, None, {})

    def test_nonce_zero_no_queries(self, _sleep):
        w3 = _w3([])

        assert scan_history(w3, SAFE_ADDRESS, 100, 0, None, {})["history"] == {}
        assert w3.eth.calls == []

    def test_incremental_from_start(self, _sleep):
        start = {
            "scanned_to": 100,
            "nonce": 2,
            "history": {0: (HASH_1, True, 10), 1: (HASH_2, True, 50)},
        }
        w3 = _w3([_log(10, HASH_1), _log(50, HASH_2), _log(120, HASH_3)])

        result = scan_history(w3, SAFE_ADDRESS, 150, 3, start, {})

        assert result["history"][2] == (HASH_3, True, 120)
        assert len(result["history"]) == 3
        assert all(c["fromBlock"] >= 101 for c in w3.eth.calls)

    def test_start_count_mismatch_raises(self, _sleep):
        start = {"scanned_to": 100, "nonce": 2, "history": {}}
        w3 = _w3([_log(120, HASH_3)])

        with pytest.raises(ValueError, match="expected 2"):
            scan_history(w3, SAFE_ADDRESS, 150, 4, start, {})

    def test_no_new_blocks(self, _sleep):
        start = {"scanned_to": 100, "nonce": 1, "history": {0: (HASH_1, True, 10)}}
        w3 = _w3([])

        result = scan_history(w3, SAFE_ADDRESS, 100, 1, start, {})

        assert result["history"] == start["history"]
        assert w3.eth.calls == []


def _safe_contract(nonce, threshold=2, domain=golden.DOMAIN_HASH):
    safe = MagicMock()
    safe.functions.nonce.return_value.call.return_value = nonce
    safe.functions.getThreshold.return_value.call.return_value = threshold
    safe.functions.domainSeparator.return_value.call.return_value = domain
    return safe


def _connection(safes, block=1000, code=b"\x01"):
    w3 = MagicMock()
    w3.eth.block_number = block
    w3.eth.get_code.return_value = code
    w3.eth.contract.side_effect = lambda address, abi: safes[address]
    return {"w3": w3, "state": {}}


def _entries(*overrides, chain=None, safe=None):
    chain = chain or {"name": "Base", "chain_id": 8453, "rpc_name": "RPC_BASE"}
    safe = safe or {"name": "Treasury", "address": golden.SAFE_ADDRESS}
    return [
        {
            "number": number,
            "chain": chain,
            "safe_config": {
                **safe,
                "address": Web3.to_checksum_address(safe["address"]),
            },
            "raw_data": golden.RAW_DATA,
            "nonce_setting": None,
            **DEFAULTS,
            **override,
        }
        for number, override in enumerate(overrides, start=1)
    ]


def _load(entries, connections, tmp_path, cache=None):
    return load(
        entries,
        connections,
        [],
        CONSTANTS,
        {} if cache is None else cache,
        str(tmp_path),
    )


class TestConnectChains:
    @patch("src.transactions.Web3")
    def test_missing_rpc_env_var(self, _web3, monkeypatch):
        monkeypatch.delenv("RPC_BASE", raising=False)

        result = connect_chains(_entries({}))

        assert result == {
            "Base": {"error": "RPC URL environment variable 'RPC_BASE' is not set."}
        }

    @patch("src.transactions.Web3")
    def test_chain_id_mismatch(self, web3, monkeypatch):
        monkeypatch.setenv("RPC_BASE", "http://rpc")
        web3.return_value.eth.chain_id = 10

        assert connect_chains(_entries({}))["Base"] == {
            "error": "Chain Id is 10, expected 8453"
        }

    @patch("src.transactions.Web3")
    def test_connection_error(self, web3, monkeypatch):
        monkeypatch.setenv("RPC_BASE", "http://rpc")
        type(web3.return_value.eth).chain_id = PropertyMock(
            side_effect=ConnectionError("refused")
        )

        assert connect_chains(_entries({}))["Base"] == {"error": "refused"}

    @patch("src.transactions.Web3")
    def test_connected(self, web3, monkeypatch):
        monkeypatch.setenv("RPC_BASE", "http://rpc")
        web3.return_value.eth.chain_id = 8453

        result = connect_chains(_entries({}, {}))

        assert result == {"Base": {"w3": web3.return_value, "state": {}}}
        web3.HTTPProvider.assert_called_once_with(
            "http://rpc", request_kwargs={"timeout": 30}
        )


@patch("src.transactions.scan_history")
class TestLoad:
    def test_golden_transaction_hash(self, _scan, tmp_path):
        safes = {golden.SAFE_ADDRESS: _safe_contract(golden.SAFE_NONCE)}
        entries = _entries({"nonce_setting": "repeat"})

        loaded = _load(entries, {"Base": _connection(safes)}, tmp_path)[0]

        assert loaded["transaction_hash"] == golden.EXPECTED_TRANSACTION_HASH
        assert (loaded["nonce"], loaded["status"], loaded["threshold"]) == (
            42,
            "next",
            2,
        )

    def test_reads_pinned_to_block(self, scan, tmp_path):
        safe = _safe_contract(0)
        scan.return_value = {"scanned_to": 1000, "nonce": 0, "history": {}}

        _load(
            _entries({}), {"Base": _connection({golden.SAFE_ADDRESS: safe})}, tmp_path
        )

        for name in ("nonce", "getThreshold", "domainSeparator"):
            call = getattr(safe.functions, name).return_value.call
            assert call.call_args.kwargs == {"block_identifier": 1000}
        assert scan.call_args.args[2] == 1000

    def test_one_chain_down_other_usable(self, scan, tmp_path):
        optimism = {"name": "Optimism", "chain_id": 10, "rpc_name": "RPC_OPTIMISM"}
        entries = _entries({}) + [
            {**e, "number": 2} for e in _entries({}, chain=optimism)
        ]
        scan.return_value = {"scanned_to": 1000, "nonce": 0, "history": {}}
        connections = {
            "Base": {"error": "RPC down"},
            "Optimism": _connection({golden.SAFE_ADDRESS: _safe_contract(0)}),
        }

        loaded = _load(entries, connections, tmp_path)

        assert (loaded[0]["status"], loaded[0]["reason"]) == ("unresolved", "RPC down")
        assert loaded[1]["status"] == "next"

    def test_no_contract_at_safe(self, _scan, tmp_path):
        connection = _connection({}, code=b"")

        loaded = _load(_entries({}), {"Base": connection}, tmp_path)[0]

        assert loaded["status"] == "unresolved"
        assert "No Safe contract" in loaded["reason"]

    def test_rpc_error_marks_group_unresolved(self, _scan, tmp_path):
        safe = _safe_contract(0)
        safe.functions.getThreshold.return_value.call.side_effect = ValueError("429")

        loaded = _load(
            _entries({}), {"Base": _connection({golden.SAFE_ADDRESS: safe})}, tmp_path
        )[0]

        assert (loaded["status"], loaded["reason"]) == ("unresolved", "429")

    def test_consecutive_nonces_and_stable_hash_after_execution(self, scan, tmp_path):
        entries = _entries({}, {"raw_data": "0x1234"})
        scan.return_value = {
            "scanned_to": 1000,
            "nonce": 10,
            "history": {n: ("ff" * 32, True, n) for n in range(10)},
        }
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(10)})

        before = _load(entries, {"Base": connection}, tmp_path)

        assert [(e["nonce"], e["status"]) for e in before] == [
            (10, "next"),
            (11, "queued"),
        ]
        history = {
            **scan.return_value["history"],
            10: (before[0]["transaction_hash"], True, 990),
        }
        scan.return_value = {"scanned_to": 1001, "nonce": 11, "history": history}
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(11)})

        after = _load(entries, {"Base": connection}, tmp_path)

        assert [(e["nonce"], e["status"]) for e in after] == [
            (10, "executed"),
            (11, "next"),
        ]
        assert after[1]["transaction_hash"] == before[1]["transaction_hash"]

    def test_pin_taken_reason(self, scan, tmp_path):
        scan.return_value = {
            "scanned_to": 1000,
            "nonce": 1,
            "history": {0: ("ab" * 32, True, 5)},
        }
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(1)})

        loaded = _load(_entries({"nonce_setting": 0}), {"Base": connection}, tmp_path)[
            0
        ]

        assert loaded["status"] == "unresolved"
        assert (
            loaded["reason"]
            == f"Nonce 0 was used by another transaction 0x{'ab' * 32}."
        )

    def test_repeat_only_skips_scan(self, scan, tmp_path):
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(5)})

        _load(_entries({"nonce_setting": "repeat"}), {"Base": connection}, tmp_path)

        scan.assert_not_called()

    def test_seeded_from_saved_history(self, scan, tmp_path):
        history.append(
            str(tmp_path),
            "Base",
            golden.SAFE_ADDRESS,
            [(0, "ab" * 32, True, 5)],
            500,
            1,
        )
        scan.return_value = {
            "scanned_to": 1000,
            "nonce": 1,
            "history": {0: ("ab" * 32, True, 5)},
        }
        cache = {}
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(1)})

        _load(_entries({}), {"Base": connection}, tmp_path, cache)

        assert scan.call_args.args[4]["scanned_to"] == 500
        assert cache[("Base", golden.SAFE_ADDRESS)]["saved_to"] == 500

    def test_cache_reused(self, scan, tmp_path):
        scan.return_value = {"scanned_to": 1000, "nonce": 0, "history": {}}
        cache = {}
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(0)})

        _load(_entries({}), {"Base": connection}, tmp_path, cache)
        _load(_entries({}), {"Base": connection}, tmp_path, cache)

        assert scan.call_args.args[4]["scanned_to"] == 1000

    def test_malformed_history_stops(self, _scan, tmp_path):
        os.makedirs(tmp_path / "out")
        (tmp_path / "out" / "history.jsonl").write_text("{broken\n")
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(1)})

        with pytest.raises(ValueError, match="line 1"):
            _load(_entries({}), {"Base": connection}, tmp_path)

    def test_load_writes_nothing(self, scan, tmp_path):
        scan.return_value = {"scanned_to": 1000, "nonce": 0, "history": {}}
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(0)})

        _load(_entries({}), {"Base": connection}, tmp_path)

        assert not (tmp_path / "out").exists()


class TestSaveHistory:
    KEY = ("Base", golden.SAFE_ADDRESS)

    def test_save_only_settled(self, tmp_path):
        cache = {
            self.KEY: {
                "scanned_to": 1000,
                "nonce": 2,
                "saved_to": -1,
                "history": {0: (HASH_1, True, 800), 1: (HASH_2, True, 950)},
            }
        }

        save_history(cache, self.KEY, str(tmp_path))

        saved = history.load(str(tmp_path))[self.KEY]
        assert (saved["scanned_to"], saved["nonce"]) == (900, 1)
        assert saved["history"] == {0: (HASH_1, True, 800)}
        assert cache[self.KEY]["saved_to"] == 900

    def test_save_includes_execution_at_settled_block(self, tmp_path):
        cache = {
            self.KEY: {
                "scanned_to": 1000,
                "nonce": 1,
                "saved_to": -1,
                "history": {0: (HASH_1, True, 900)},
            }
        }

        save_history(cache, self.KEY, str(tmp_path))

        assert history.load(str(tmp_path))[self.KEY]["history"] == {
            0: (HASH_1, True, 900)
        }

    def test_second_save_appends_only_new_settled(self, tmp_path):
        cache = {
            self.KEY: {
                "scanned_to": 1000,
                "nonce": 2,
                "saved_to": -1,
                "history": {0: (HASH_1, True, 800), 1: (HASH_2, True, 950)},
            }
        }
        save_history(cache, self.KEY, str(tmp_path))
        cache[self.KEY].update(
            {
                "scanned_to": 1200,
                "nonce": 3,
                "history": {**cache[self.KEY]["history"], 2: (HASH_3, True, 1150)},
            }
        )

        save_history(cache, self.KEY, str(tmp_path))

        lines = (tmp_path / "out" / "history.jsonl").read_text().splitlines()
        executions = [json.loads(line) for line in lines if '"tx_hash"' in line]
        assert [(e["nonce"], e["block"]) for e in executions] == [(0, 800), (1, 950)]

    def test_save_nothing_when_not_advanced(self, tmp_path):
        cache = {
            self.KEY: {"scanned_to": 1000, "nonce": 0, "saved_to": 900, "history": {}}
        }

        save_history(cache, self.KEY, str(tmp_path))

        assert not (tmp_path / "out").exists()

    def test_save_nothing_without_scan(self, tmp_path):
        save_history({}, self.KEY, str(tmp_path))

        assert not (tmp_path / "out").exists()


class TestResolveSettingsNonce:
    def test_integer_pin_carried(self):
        entry = resolve_settings([_transaction(nonce=5)], CHAINS, SAFES, DEFAULTS)[0]
        assert entry["nonce_setting"] == 5


class TestResolveSettingsName:
    def test_name_carried(self):
        entry = resolve_settings(
            [_transaction(name="Staking rewards")], CHAINS, SAFES, DEFAULTS
        )[0]
        assert entry["name"] == "Staking rewards"

    def test_name_absent(self):
        assert (
            resolve_settings([_transaction()], CHAINS, SAFES, DEFAULTS)[0]["name"]
            is None
        )


class TestCheckOrder:
    def test_in_order(self):
        check_order([1, 2, 3], [(9, "executed"), (10, "next"), (11, "queued")])

    def test_later_executed_before_earlier(self):
        with pytest.raises(
            ValueError, match="#2 executed before #1; the order cannot be resolved"
        ):
            check_order([1, 2], [(11, "next"), (10, "executed")])

    def test_pin_before_lower_nonce(self):
        with pytest.raises(
            ValueError,
            match="#1 comes before #2 but has nonce 12, after 10; the order cannot be resolved",
        ):
            check_order([1, 2], [(12, "queued"), (10, "next")])

    def test_unresolved_ignored(self):
        check_order([1, 2], [(5, "unresolved"), (10, "next")])


@patch("src.transactions.scan_history")
class TestLoadOrder:
    def test_order_conflict_marks_group_unresolved(self, _scan, tmp_path):
        entries = _entries({"nonce_setting": 12}, {"nonce_setting": "repeat"})
        connection = _connection({golden.SAFE_ADDRESS: _safe_contract(10)})

        loaded = _load(entries, {"Base": connection}, tmp_path)

        assert [e["status"] for e in loaded] == ["unresolved", "unresolved"]
        assert "the order cannot be resolved" in loaded[0]["reason"]
