"""Unit tests for the Transaction model."""

import json
import pytest

from models.transaction import Transaction, TransactionType, TransactionStatus


class TestTransactionModel:
    """Tests for Transaction serialisation and default values."""

    def test_default_status_is_pending(self):
        tx = Transaction(account_id="ACC-001", amount=100.0)
        assert tx.status == TransactionStatus.PENDING

    def test_default_currency_is_usd(self):
        tx = Transaction(account_id="ACC-001", amount=50.0)
        assert tx.currency == "USD"

    def test_transaction_id_is_auto_generated(self):
        tx1 = Transaction(account_id="ACC-001", amount=10.0)
        tx2 = Transaction(account_id="ACC-001", amount=10.0)
        assert tx1.transaction_id != tx2.transaction_id

    def test_to_json_contains_required_fields(self):
        tx = Transaction(
            account_id="ACC-999",
            transaction_type=TransactionType.DEPOSIT,
            amount=250.0,
            merchant="SuperMart",
            location="New York, US",
        )
        payload = json.loads(tx.to_json())
        assert payload["account_id"] == "ACC-999"
        assert payload["transaction_type"] == "DEPOSIT"
        assert payload["amount"] == 250.0
        assert payload["merchant"] == "SuperMart"
        assert payload["location"] == "New York, US"
        assert payload["status"] == "PENDING"
        assert "transaction_id" in payload
        assert "timestamp" in payload

    def test_roundtrip_serialisation(self):
        original = Transaction(
            account_id="ACC-100",
            transaction_type=TransactionType.TRANSFER,
            amount=1_500.0,
            location="London, UK",
            destination_account_id="ACC-200",
        )
        restored = Transaction.from_json(original.to_json())

        assert restored.transaction_id == original.transaction_id
        assert restored.account_id == original.account_id
        assert restored.transaction_type == original.transaction_type
        assert restored.amount == original.amount
        assert restored.location == original.location
        assert restored.destination_account_id == original.destination_account_id

    def test_from_json_preserves_enum_types(self):
        tx = Transaction(
            account_id="ACC-300",
            transaction_type=TransactionType.WITHDRAWAL,
            status=TransactionStatus.APPROVED,
            amount=99.99,
        )
        restored = Transaction.from_json(tx.to_json())
        assert isinstance(restored.transaction_type, TransactionType)
        assert isinstance(restored.status, TransactionStatus)

    def test_str_representation(self):
        tx = Transaction(
            account_id="ACC-001",
            transaction_type=TransactionType.PAYMENT,
            amount=42.0,
            status=TransactionStatus.APPROVED,
        )
        result = str(tx)
        assert "ACC-001" in result
        assert "PAYMENT" in result
        assert "42.00" in result
        assert "APPROVED" in result

    def test_invalid_json_raises_error(self):
        with pytest.raises(Exception):
            Transaction.from_json("not-valid-json")

    def test_invalid_transaction_type_raises_error(self):
        tx = Transaction(account_id="ACC-001", amount=10.0)
        data = json.loads(tx.to_json())
        data["transaction_type"] = "INVALID_TYPE"
        with pytest.raises(ValueError):
            Transaction.from_json(json.dumps(data))

    @pytest.mark.parametrize("tx_type", list(TransactionType))
    def test_all_transaction_types_serialise(self, tx_type):
        tx = Transaction(
            account_id="ACC-001",
            transaction_type=tx_type,
            amount=1.0,
        )
        restored = Transaction.from_json(tx.to_json())
        assert restored.transaction_type == tx_type

    @pytest.mark.parametrize("status", list(TransactionStatus))
    def test_all_statuses_serialise(self, status):
        tx = Transaction(
            account_id="ACC-001",
            amount=1.0,
            status=status,
        )
        restored = Transaction.from_json(tx.to_json())
        assert restored.status == status
