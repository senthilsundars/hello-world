"""Unit tests for TransactionConsumer (no live Kafka required)."""

from unittest.mock import MagicMock, patch

import pytest

from consumer.fraud_detector import FraudDetector
from consumer.transaction_consumer import TransactionConsumer
from models.transaction import Transaction, TransactionStatus, TransactionType


@pytest.fixture()
def mock_kafka_consumer():
    """Patch KafkaConsumer so tests run without a live broker."""
    with patch("consumer.transaction_consumer.KafkaConsumer") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


def _build_consumer(mock_kafka_consumer) -> TransactionConsumer:
    """Return a consumer wired to the patched Kafka instance."""
    return TransactionConsumer(
        bootstrap_servers="localhost:9092",
        topic="bank-transactions",
        group_id="test-group",
    )


class TestProcessMessage:
    def test_approved_transaction(self, mock_kafka_consumer):
        consumer = _build_consumer(mock_kafka_consumer)
        tx = Transaction(account_id="ACC-001", amount=100.0)
        result = consumer.process_message(tx.to_json())
        assert result.status == TransactionStatus.APPROVED

    def test_high_value_transaction_flagged(self, mock_kafka_consumer):
        detector = FraudDetector(high_value_threshold=500.0)
        consumer = TransactionConsumer(fraud_detector=detector)
        tx = Transaction(account_id="ACC-001", amount=600.0)
        result = consumer.process_message(tx.to_json())
        assert result.status == TransactionStatus.FLAGGED

    def test_returns_transaction_object(self, mock_kafka_consumer):
        consumer = _build_consumer(mock_kafka_consumer)
        tx = Transaction(account_id="ACC-002", amount=50.0)
        result = consumer.process_message(tx.to_json())
        assert isinstance(result, Transaction)
        assert result.account_id == "ACC-002"
        assert result.amount == 50.0

    def test_invalid_json_raises_exception(self, mock_kafka_consumer):
        consumer = _build_consumer(mock_kafka_consumer)
        with pytest.raises(Exception):
            consumer.process_message("{{not-json}}")

    def test_process_message_preserves_transaction_id(self, mock_kafka_consumer):
        consumer = _build_consumer(mock_kafka_consumer)
        tx = Transaction(account_id="ACC-003", amount=200.0)
        result = consumer.process_message(tx.to_json())
        assert result.transaction_id == tx.transaction_id

    def test_all_transaction_types_processed(self, mock_kafka_consumer):
        consumer = _build_consumer(mock_kafka_consumer)
        for tx_type in TransactionType:
            tx = Transaction(
                account_id="ACC-004",
                transaction_type=tx_type,
                amount=99.0,
            )
            result = consumer.process_message(tx.to_json())
            assert result.status in (TransactionStatus.APPROVED, TransactionStatus.FLAGGED)


class TestConsumerWithCustomDetector:
    def test_pluggable_fraud_detector_used(self, mock_kafka_consumer):
        custom_detector = MagicMock(spec=FraudDetector)
        expected_tx = Transaction(
            account_id="ACC-X", amount=1.0, status=TransactionStatus.APPROVED
        )
        custom_detector.evaluate.return_value = expected_tx

        consumer = TransactionConsumer(fraud_detector=custom_detector)
        tx = Transaction(account_id="ACC-X", amount=1.0)
        result = consumer.process_message(tx.to_json())

        custom_detector.evaluate.assert_called_once()
        assert result == expected_tx
