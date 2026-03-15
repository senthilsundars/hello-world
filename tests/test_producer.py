"""Unit tests for TransactionProducer (no live Kafka required)."""

from unittest.mock import MagicMock, call, patch

import pytest

from models.transaction import Transaction, TransactionType
from producer.transaction_producer import TransactionProducer


@pytest.fixture()
def mock_kafka_producer():
    """Patch KafkaProducer so tests run without a live broker."""
    with patch("producer.transaction_producer.KafkaProducer") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        # send() returns a Future-like object
        mock_future = MagicMock()
        mock_future.add_callback.return_value = mock_future
        mock_future.add_errback.return_value = mock_future
        mock_instance.send.return_value = mock_future
        yield mock_instance


class TestTransactionProducer:
    def test_send_transaction_calls_kafka_send(self, mock_kafka_producer):
        producer = TransactionProducer(bootstrap_servers="localhost:9092")
        tx = Transaction(account_id="ACC-001", amount=200.0)

        producer.send_transaction(tx)

        mock_kafka_producer.send.assert_called_once()
        _, kwargs = mock_kafka_producer.send.call_args
        assert kwargs["key"] == "ACC-001"
        assert "ACC-001" in kwargs["value"]

    def test_send_transaction_uses_correct_topic(self, mock_kafka_producer):
        producer = TransactionProducer(topic="my-topic")
        tx = Transaction(account_id="ACC-002", amount=10.0)

        producer.send_transaction(tx)

        args, _ = mock_kafka_producer.send.call_args
        assert args[0] == "my-topic"

    def test_flush_called_on_close(self, mock_kafka_producer):
        producer = TransactionProducer()
        producer.close()

        mock_kafka_producer.flush.assert_called()
        mock_kafka_producer.close.assert_called_once()

    def test_custom_success_callback_attached(self, mock_kafka_producer):
        producer = TransactionProducer()
        tx = Transaction(account_id="ACC-003", amount=1.0)
        on_success = MagicMock()
        mock_future = mock_kafka_producer.send.return_value

        producer.send_transaction(tx, on_success=on_success)

        mock_future.add_callback.assert_called_once_with(on_success)

    def test_custom_error_callback_attached(self, mock_kafka_producer):
        producer = TransactionProducer()
        tx = Transaction(account_id="ACC-004", amount=1.0)
        on_error = MagicMock()
        mock_future = mock_kafka_producer.send.return_value

        producer.send_transaction(tx, on_error=on_error)

        mock_future.add_errback.assert_called_once_with(on_error)


class TestGenerateRandomTransaction:
    def test_returns_transaction_instance(self):
        tx = TransactionProducer.generate_random_transaction()
        assert isinstance(tx, Transaction)

    def test_account_id_is_set(self):
        tx = TransactionProducer.generate_random_transaction()
        assert tx.account_id.startswith("ACC-")

    def test_amount_is_positive(self):
        for _ in range(20):
            tx = TransactionProducer.generate_random_transaction()
            assert tx.amount > 0

    def test_high_value_probability_one_always_high(self):
        for _ in range(10):
            tx = TransactionProducer.generate_random_transaction(
                high_value_probability=1.0
            )
            assert tx.amount > 10_000

    def test_high_value_probability_zero_always_normal(self):
        for _ in range(10):
            tx = TransactionProducer.generate_random_transaction(
                high_value_probability=0.0
            )
            assert tx.amount <= 5_000

    def test_transfer_has_destination_account(self):
        found_transfer = False
        for _ in range(200):
            tx = TransactionProducer.generate_random_transaction(
                high_value_probability=0.0
            )
            if tx.transaction_type == TransactionType.TRANSFER:
                assert tx.destination_account_id != ""
                assert tx.destination_account_id != tx.account_id
                found_transfer = True
                break
        assert found_transfer, "No TRANSFER transaction generated in 200 attempts"

    def test_non_transfer_has_no_destination(self):
        for _ in range(200):
            tx = TransactionProducer.generate_random_transaction()
            if tx.transaction_type != TransactionType.TRANSFER:
                assert tx.destination_account_id == ""
                return
        pytest.skip("Only TRANSFER transactions generated; skipping assertion")
