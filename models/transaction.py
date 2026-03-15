"""
Banking transaction data model for Kafka event streaming.
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum


class TransactionType(str, Enum):
    """Types of banking transactions."""

    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    TRANSFER = "TRANSFER"
    PAYMENT = "PAYMENT"


class TransactionStatus(str, Enum):
    """Processing status of a transaction."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    FLAGGED = "FLAGGED"
    REJECTED = "REJECTED"


@dataclass
class Transaction:
    """Represents a single banking transaction event.

    Attributes:
        transaction_id: Unique identifier for the transaction.
        account_id: Source account identifier.
        transaction_type: Type of transaction (DEPOSIT, WITHDRAWAL, etc.).
        amount: Transaction amount in USD.
        currency: ISO 4217 currency code.
        timestamp: UTC timestamp when the transaction was initiated.
        merchant: Name of the merchant or payee (optional).
        location: Geographic location of the transaction (optional).
        status: Current processing status of the transaction.
        destination_account_id: Target account for transfers (optional).
    """

    transaction_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    transaction_type: TransactionType = TransactionType.PAYMENT
    amount: float = 0.0
    currency: str = "USD"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    merchant: str = ""
    location: str = ""
    status: TransactionStatus = TransactionStatus.PENDING
    destination_account_id: str = ""

    def to_json(self) -> str:
        """Serialize the transaction to a JSON string."""
        data = asdict(self)
        data["transaction_type"] = self.transaction_type.value
        data["status"] = self.status.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> "Transaction":
        """Deserialize a transaction from a JSON string.

        Args:
            json_str: JSON-encoded transaction string.

        Returns:
            A Transaction instance.
        """
        data = json.loads(json_str)
        data["transaction_type"] = TransactionType(data["transaction_type"])
        data["status"] = TransactionStatus(data["status"])
        return cls(**data)

    def __str__(self) -> str:
        return (
            f"Transaction(id={self.transaction_id[:8]}, "
            f"account={self.account_id}, "
            f"type={self.transaction_type.value}, "
            f"amount={self.currency} {self.amount:.2f}, "
            f"status={self.status.value})"
        )
