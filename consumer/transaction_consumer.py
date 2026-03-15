"""
Kafka consumer that processes real-time banking transaction events.

Reads from the 'bank-transactions' topic, applies fraud detection,
and prints a live summary to stdout.
"""

import logging
import signal
import sys
from typing import Optional

from kafka import KafkaConsumer
from kafka.errors import KafkaError

from consumer.fraud_detector import FraudDetector
from models.transaction import Transaction, TransactionStatus
from producer.transaction_producer import TRANSACTION_TOPIC

logger = logging.getLogger(__name__)


class TransactionConsumer:
    """Kafka consumer that processes banking transaction events in real time.

    Each consumed message is deserialised into a :class:`Transaction`,
    evaluated by the :class:`FraudDetector`, and reported to stdout.

    Args:
        bootstrap_servers: Kafka broker address(es).
        topic: Kafka topic to consume from.
        group_id: Kafka consumer group identifier.
        fraud_detector: Pluggable fraud-detection engine.  A default
            :class:`FraudDetector` is created when not provided.
        auto_offset_reset: Where to start reading if no committed offset
            exists (``'earliest'`` or ``'latest'``).
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = TRANSACTION_TOPIC,
        group_id: str = "banking-fraud-detection",
        fraud_detector: Optional[FraudDetector] = None,
        auto_offset_reset: str = "earliest",
    ) -> None:
        self.topic = topic
        self.fraud_detector = fraud_detector or FraudDetector()
        self._running = False

        self._consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap_servers,
            group_id=group_id,
            auto_offset_reset=auto_offset_reset,
            value_deserializer=lambda v: v.decode("utf-8"),
            enable_auto_commit=True,
        )
        logger.info(
            "TransactionConsumer connected to %s (topic=%s, group=%s)",
            bootstrap_servers,
            topic,
            group_id,
        )

    def process_message(self, raw_value: str) -> Transaction:
        """Deserialise and evaluate a single raw Kafka message value.

        Args:
            raw_value: JSON string consumed from Kafka.

        Returns:
            The evaluated (and status-updated) :class:`Transaction`.
        """
        transaction = Transaction.from_json(raw_value)
        return self.fraud_detector.evaluate(transaction)

    def run(self) -> None:
        """Start consuming messages in a blocking loop.

        Handles ``SIGINT`` / ``SIGTERM`` gracefully so the process can
        be stopped with Ctrl-C without leaving uncommitted offsets.
        """
        self._running = True
        self._setup_signal_handlers()

        approved = flagged = errors = 0

        logger.info("Listening on topic '%s' … (press Ctrl-C to stop)", self.topic)
        try:
            for message in self._consumer:
                if not self._running:
                    break
                try:
                    tx = self.process_message(message.value)
                    if tx.status == TransactionStatus.FLAGGED:
                        flagged += 1
                    else:
                        approved += 1
                except Exception as exc:  # pylint: disable=broad-except
                    errors += 1
                    logger.error(
                        "Error processing message at offset %d: %s",
                        message.offset,
                        exc,
                    )
        except KafkaError as exc:
            logger.error("Kafka error: %s", exc)
        finally:
            self._print_summary(approved, flagged, errors)
            self.close()

    def close(self) -> None:
        """Stop consuming and close the consumer connection."""
        self._running = False
        self._consumer.close()
        logger.info("TransactionConsumer closed")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _setup_signal_handlers(self) -> None:
        """Register handlers for graceful shutdown on SIGINT / SIGTERM."""

        def _handle(signum, _frame) -> None:
            logger.info("Received signal %d – shutting down …", signum)
            self._running = False

        signal.signal(signal.SIGINT, _handle)
        signal.signal(signal.SIGTERM, _handle)

    @staticmethod
    def _print_summary(approved: int, flagged: int, errors: int) -> None:
        total = approved + flagged
        print("\n" + "=" * 60)
        print("  Banking Kafka Consumer – Session Summary")
        print("=" * 60)
        print(f"  Total processed : {total}")
        print(f"  Approved        : {approved}")
        print(f"  Flagged (fraud) : {flagged}")
        print(f"  Errors          : {errors}")
        if total:
            print(f"  Fraud rate      : {flagged / total * 100:.1f}%")
        print("=" * 60)
