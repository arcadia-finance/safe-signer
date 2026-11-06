from unittest.mock import MagicMock, patch

import pytest

import main

SIGNER = {"name": "Signer", "address": "0x2222222222222222222222222222222222222222"}
RELAYER = {"name": "Relayer", "address": "0x3333333333333333333333333333333333333333"}


def _entry(number=1, status="next", nonce=10, transaction_hash="aa" * 32):
    safe = MagicMock()
    safe.functions.nonce.return_value.call.return_value = nonce
    return {
        "number": number,
        "name": "Staking rewards",
        "chain": {"name": "Base", "chain_id": 8453},
        "safe_config": {"name": "Treasury"},
        "history_key": ("Base", "0xSafe"),
        "w3": MagicMock(),
        "safe": safe,
        "threshold": 1,
        "nonce": nonce,
        "status": status,
        "typed_data": {"typed": number},
        "domain_hash": b"\x01" * 32,
        "message_hash": bytes([number]) * 32,
        "transaction_hash": transaction_hash,
        "to": "0xA1dabEF33b3B82c7814B6D82A79e50F4AC44102B",
        "raw_data": "0x1234",
        "operation": 1,
        "gas": 0,
        "max_fee_per_gas": 0,
        "max_priority_fee_per_gas": 1000000,
        "reason": "RPC down",
    }


def _ctx(all_signatures=None):
    return {
        "signers": [SIGNER],
        "relayers": [RELAYER],
        "all_signatures": {} if all_signatures is None else all_signatures,
        "path": "/repo",
        "constants": {},
        "tenderly_url": "https://tenderly",
        "cache": {},
        "connections": {},
        "safe_abi": [],
    }


def _answers(*values):
    return [None if v is None else {"actions": v} for v in values]


@patch("main.transactions.save_history")
@patch("main.signatures.append")
@patch("main.validate_signer.validate", return_value=True)
@patch("main.eip712_typed_data.sign", return_value="ab" * 65)
@patch("main.user_input.get_signer", return_value=SIGNER)
class TestSign:
    def test_sign_uses_selected_entry(self, _signer, sign, _valid, append, save):
        entry = _entry(number=2, transaction_hash="bb" * 32)
        ctx = _ctx()

        main.sign(entry, ctx)

        assert sign.call_args.args[2:] == (
            entry["typed_data"],
            entry["domain_hash"],
            entry["message_hash"],
        )
        assert append.call_args.args == (
            "/repo",
            "bb" * 32,
            SIGNER["address"],
            "ab" * 65,
        )
        assert ctx["all_signatures"] == {"bb" * 32: {SIGNER["address"]: "ab" * 65}}

    def test_sign_saves_history(self, _signer, _sign, _valid, _append, save):
        ctx = _ctx()

        main.sign(_entry(), ctx)

        save.assert_called_once_with(ctx["cache"], ("Base", "0xSafe"), "/repo")

    def test_no_save_without_signature(self, _signer, sign, _valid, append, save):
        sign.return_value = None

        main.sign(_entry(), _ctx())

        append.assert_not_called()
        save.assert_not_called()


@patch("main.inquirer.prompt")
@patch("main.safe_transaction")
@patch("main.user_input.get_relayer", return_value=RELAYER)
class TestBroadcast:
    def _ctx(self, entry):
        return _ctx({entry["transaction_hash"]: {SIGNER["address"]: "ab" * 65}})

    def test_sends_when_next(self, _relayer, safe_transaction, prompt):
        entry = _entry()
        prompt.return_value = {"actions": "I Confirm"}
        safe_transaction.sign.return_value.raw_transaction = b"\x02raw"

        assert main.broadcast(entry, self._ctx(entry)) is True
        entry["w3"].eth.send_raw_transaction.assert_called_once_with(
            safe_transaction.sign.return_value.raw_transaction
        )

    def test_confirmation_names_transaction(self, _relayer, _safe_transaction, prompt):
        entry = _entry()
        prompt.return_value = {"actions": "Quit"}

        main.broadcast(entry, self._ctx(entry))

        message = prompt.call_args.args[0][0].message
        assert "#1 Staking rewards · Base · Treasury" in message
        assert "nonce 10" in message
        assert entry["transaction_hash"] in message

    @pytest.mark.parametrize("status", ["queued", "executed", "unresolved"])
    def test_refused_unless_next(
        self, _relayer, safe_transaction, prompt, status, capsys
    ):
        entry = _entry(status=status)

        assert main.broadcast(entry, self._ctx(entry)) is False
        entry["w3"].eth.send_raw_transaction.assert_not_called()
        assert f"this one is {status}" in capsys.readouterr().out

    def test_refused_when_nonce_moved(
        self, _relayer, _safe_transaction, prompt, capsys
    ):
        entry = _entry()
        entry["safe"].functions.nonce.return_value.call.return_value = 11
        prompt.return_value = {"actions": "I Confirm"}

        assert main.broadcast(entry, self._ctx(entry)) is False
        entry["w3"].eth.send_raw_transaction.assert_not_called()
        assert "nonce moved to 11" in capsys.readouterr().out

    @patch("main.transactions.save_history")
    def test_broadcast_does_not_save_history(
        self, save, _relayer, safe_transaction, prompt
    ):
        entry = _entry()
        prompt.return_value = {"actions": "I Confirm"}
        safe_transaction.sign.return_value.raw_transaction = b"\x02raw"

        main.broadcast(entry, self._ctx(entry))

        save.assert_not_called()

    def test_create_when_next(self, _relayer, safe_transaction, _prompt):
        entry = _entry()

        main.create_unsigned(entry, self._ctx(entry))
        main.create_signed(entry, self._ctx(entry))

        assert safe_transaction.create.call_count == 2
        safe_transaction.sign.assert_called_once()

    @pytest.mark.parametrize("status", ["queued", "executed", "unresolved"])
    def test_create_refused_unless_next(
        self, relayer, safe_transaction, _prompt, status
    ):
        entry = _entry(status=status)

        main.create_unsigned(entry, self._ctx(entry))
        main.create_signed(entry, self._ctx(entry))

        safe_transaction.create.assert_not_called()
        relayer.assert_not_called()


@patch("main.tenderly.simulate")
class TestSimulate:
    def test_queued_warns(self, simulate, capsys):
        main.simulate(_entry(status="queued"), _ctx())

        assert "Warning: earlier transactions" in capsys.readouterr().out
        simulate.assert_called_once()

    def test_next_does_not_warn(self, simulate, capsys):
        main.simulate(_entry(), _ctx())

        assert "Warning" not in capsys.readouterr().out


@patch("main.inquirer.prompt")
class TestRunEntry:
    @patch("main.sign")
    def test_back_returns(self, sign, prompt):
        prompt.side_effect = _answers("Back")

        main.run_entry(_entry(), _ctx())

        sign.assert_not_called()

    @patch("main.sign", side_effect=ValueError("device gone"))
    def test_action_error_returns_to_menu(self, _sign, prompt, capsys):
        prompt.side_effect = _answers("Sign Message", "Back")

        main.run_entry(_entry(), _ctx())

        assert "Error: device gone" in capsys.readouterr().out
        assert prompt.call_count == 2

    @patch("main.broadcast", return_value=True)
    def test_returns_after_broadcast(self, _broadcast, prompt):
        prompt.side_effect = _answers("Broadcast signed Safe tx")

        main.run_entry(_entry(), _ctx())

        assert prompt.call_count == 1


@patch("main.transactions.save_history")
@patch("main.run_entry")
@patch("main.user_input.get_transaction")
@patch("main.transactions.load")
class TestRunList:
    def test_all_executed_exits(self, load, get_transaction, _run_entry, _save, capsys):
        load.return_value = [_entry(status="executed")]
        get_transaction.return_value = False

        main.run_list([_entry()], _ctx())

        assert (
            "All transactions in the config have executed." in capsys.readouterr().out
        )
        get_transaction.assert_not_called()

    def test_startup_summary(self, load, get_transaction, _run_entry, _save, capsys):
        load.return_value = [
            _entry(1, status="executed"),
            _entry(2, status="unresolved"),
        ]
        get_transaction.return_value = False

        main.run_list([_entry()], _ctx())

        out = capsys.readouterr().out
        assert "#1 Staking rewards · Base · Treasury executed at nonce 10" in out
        assert "#2 Staking rewards · Base · Treasury: RPC down" in out

    def test_unresolved_prints_reason_and_returns_to_list(
        self, load, get_transaction, run_entry, _save, capsys
    ):
        unresolved = _entry(status="unresolved")
        load.return_value = [unresolved]
        get_transaction.side_effect = [unresolved, False]

        main.run_list([_entry()], _ctx())

        run_entry.assert_not_called()
        assert get_transaction.call_count == 2

    def test_refresh_after_action(self, load, get_transaction, run_entry, save):
        entry = _entry()
        load.return_value = [entry]
        get_transaction.side_effect = [entry, False]

        main.run_list([_entry()], _ctx())

        run_entry.assert_called_once()
        assert load.call_count == 2
        save.assert_not_called()
