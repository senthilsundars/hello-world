"""
Kafka producer that simulates real-time banking transactions.

Publishes transaction events to the 'bank-transactions' Kafka topic.
"""

import logging
import random
import time
from typing import Callable, Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError

from models.transaction import Transaction, TransactionType

logger = logging.getLogger(__name__)

TRANSACTION_TOPIC = "bank-transactions"

# Sample data used when generating random transactions
_ACCOUNTS = [
    "ACC-1001", "ACC-1002", "ACC-1003",
    "ACC-1004", "ACC-1005", "ACC-1006",
]
_MERCHANTS = [
    "SuperMart", "FuelStation", "OnlineShop",
    "Restaurant", "HospitalBilling", "UtilityBill",
]
_LOCATIONS = [
    "New York, US", "London, UK", "Paris, FR",
    "Tokyo, JP", "Sydney, AU", "Toronto, CA",
]


class TransactionProducer:
    """Kafka producer for banking transaction events.

    Args:
        bootstrap_servers: Kafka broker address(es).
        topic: Kafka topic to publish transactions to.
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = TRANSACTION_TOPIC,
    ) -> None:
        self.topic = topic
        self._producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: v.encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8"),
            acks="all",
            retries=3,
        )
        logger.info("TransactionProducer connected to %s", bootstrap_servers)

    def send_transaction(
        self,
        transaction: Transaction,
        on_success: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ) -> None:
        """Publish a single transaction event to Kafka.

        Args:
            transaction: The transaction to publish.
            on_success: Optional callback invoked on successful delivery.
            on_error: Optional callback invoked on delivery failure.
        """

        def _default_success(record_metadata) -> None:
            logger.info(
                "Sent %s -> topic=%s partition=%d offset=%d",
                transaction,
                record_metadata.topic,
                record_metadata.partition,
                record_metadata.offset,
            )

        def _default_error(exc: KafkaError) -> None:
            logger.error("Failed to send %s: %s", transaction, exc)

        self._producer.send(
            self.topic,
            key=transaction.account_id,
            value=transaction.to_json(),
        ).add_callback(on_success or _default_success).add_errback(
            on_error or _default_error
        )

    def flush(self) -> None:
        """Wait for all pending messages to be delivered."""
        self._producer.flush()

    def close(self) -> None:
        """Flush pending messages and close the producer."""
        self._producer.flush()
        self._producer.close()
        logger.info("TransactionProducer closed")

    # ------------------------------------------------------------------
    # Simulation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_random_transaction(
        high_value_probability: float = 0.05,
    ) -> Transaction:
        """Create a random transaction that mimics real banking activity.

        A small percentage of transactions are intentionally set to high
        amounts to trigger fraud-detection rules during demos.

        Args:
            high_value_probability: Probability (0–1) of generating a
                high-value transaction (amount > $10,000).

        Returns:
            A randomly generated :class:`Transaction`.
        """
        account_id = random.choice(_ACCOUNTS)
        transaction_type = random.choice(list(TransactionType))
        destination = (
            random.choice([a for a in _ACCOUNTS if a != account_id])
            if transaction_type == TransactionType.TRANSFER
            else ""
        )

        if random.random() < high_value_probability:
            amount = round(random.uniform(10_001, 50_000), 2)
        else:
            amount = round(random.uniform(5, 5_000), 2)

        return Transaction(
            account_id=account_id,
            transaction_type=transaction_type,
            amount=amount,
            merchant=random.choice(_MERCHANTS) if not destination else "",
            location=random.choice(_LOCATIONS),
            destination_account_id=destination,
        )

    def simulate(
        self,
        num_transactions: int = 100,
        interval_seconds: float = 0.5,
    ) -> None:
        """Continuously publish randomly generated transactions.

        Args:
            num_transactions: Total number of transactions to send.
                Pass ``0`` to run indefinitely.
            interval_seconds: Delay between consecutive messages.
        """
        count = 0
        try:
            while num_transactions == 0 or count < num_transactions:
                tx = self.generate_random_transaction()
                self.send_transaction(tx)
                count += 1
                if interval_seconds > 0:
                    time.sleep(interval_seconds)
        finally:
            self.flush()
            logger.info("Simulation finished. Sent %d transactions.", count)
