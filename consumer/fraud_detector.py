"""
Rule-based fraud detection engine for real-time banking transactions.

Rules evaluated:
  1. High-value transaction  – amount exceeds a configurable threshold.
  2. Rapid successive transactions – same account sends multiple
     transactions within a short rolling time window.
  3. Geographic anomaly – transaction originates from a location not
     seen in recent activity for that account.
"""

import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, Set

from models.transaction import Transaction, TransactionStatus

logger = logging.getLogger(__name__)

# Default thresholds (can be overridden via constructor)
DEFAULT_HIGH_VALUE_THRESHOLD = 10_000.0   # USD
DEFAULT_RAPID_TX_WINDOW_SECONDS = 60      # 1-minute rolling window
DEFAULT_RAPID_TX_LIMIT = 5               # max transactions per window


class FraudDetector:
    """Stateful fraud detector that evaluates incoming transactions.

    Args:
        high_value_threshold: Transactions above this amount (USD) are
            flagged as potentially fraudulent.
        rapid_tx_window_seconds: Length of the sliding window (seconds)
            used to detect rapid successive transactions.
        rapid_tx_limit: Maximum allowed transactions per account within
            the sliding window before flagging occurs.
    """

    def __init__(
        self,
        high_value_threshold: float = DEFAULT_HIGH_VALUE_THRESHOLD,
        rapid_tx_window_seconds: int = DEFAULT_RAPID_TX_WINDOW_SECONDS,
        rapid_tx_limit: int = DEFAULT_RAPID_TX_LIMIT,
    ) -> None:
        self.high_value_threshold = high_value_threshold
        self.rapid_tx_window_seconds = rapid_tx_window_seconds
        self.rapid_tx_limit = rapid_tx_limit

        # Per-account sliding window of transaction timestamps (ISO strings)
        self._tx_timestamps: Dict[str, Deque[str]] = defaultdict(deque)
        # Per-account set of known locations
        self._known_locations: Dict[str, Set[str]] = defaultdict(set)

    def evaluate(self, transaction: Transaction) -> Transaction:
        """Apply all fraud-detection rules to a transaction.

        The transaction's ``status`` field is updated in place:
        - ``FLAGGED`` if any rule fires.
        - ``APPROVED`` if no rule fires.

        Args:
            transaction: The transaction to evaluate.

        Returns:
            The same transaction object with an updated status.
        """
        reasons = []

        if self._is_high_value(transaction):
            reasons.append(
                f"High-value transaction: {transaction.currency} "
                f"{transaction.amount:.2f} exceeds threshold "
                f"{transaction.currency} {self.high_value_threshold:.2f}"
            )

        if self._is_rapid_succession(transaction):
            reasons.append(
                f"Rapid successive transactions: account "
                f"{transaction.account_id} exceeded {self.rapid_tx_limit} "
                f"transactions within {self.rapid_tx_window_seconds}s"
            )

        if self._is_geographic_anomaly(transaction):
            reasons.append(
                f"Geographic anomaly: unknown location "
                f"'{transaction.location}' for account "
                f"{transaction.account_id}"
            )

        if reasons:
            transaction.status = TransactionStatus.FLAGGED
            for reason in reasons:
                logger.warning("FRAUD ALERT [%s]: %s", transaction.transaction_id[:8], reason)
        else:
            transaction.status = TransactionStatus.APPROVED
            logger.info("APPROVED  [%s]: %s", transaction.transaction_id[:8], transaction)

        # Update rolling state after evaluation
        self._record_transaction(transaction)
        return transaction

    # ------------------------------------------------------------------
    # Individual rules
    # ------------------------------------------------------------------

    def _is_high_value(self, transaction: Transaction) -> bool:
        """Rule 1: Flag transactions exceeding the high-value threshold."""
        return transaction.amount > self.high_value_threshold

    def _is_rapid_succession(self, transaction: Transaction) -> bool:
        """Rule 2: Flag when too many transactions occur in a short window."""
        now = datetime.now(timezone.utc)
        window = self._tx_timestamps[transaction.account_id]

        # Evict timestamps outside the rolling window
        while window:
            oldest = datetime.fromisoformat(window[0])
            if (now - oldest).total_seconds() > self.rapid_tx_window_seconds:
                window.popleft()
            else:
                break

        return len(window) >= self.rapid_tx_limit

    def _is_geographic_anomaly(self, transaction: Transaction) -> bool:
        """Rule 3: Flag transactions from a previously unseen location.

        The first transaction for any account always establishes the
        baseline, so it is never flagged for a geographic anomaly.
        """
        if not transaction.location:
            return False
        known = self._known_locations[transaction.account_id]
        # No history yet – establish baseline, do not flag
        if not known:
            return False
        return transaction.location not in known

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _record_transaction(self, transaction: Transaction) -> None:
        """Persist per-account state needed by subsequent evaluations."""
        self._tx_timestamps[transaction.account_id].append(
            transaction.timestamp
        )
        if transaction.location:
            self._known_locations[transaction.account_id].add(
                transaction.location
            )

    def reset(self) -> None:
        """Clear all accumulated state (useful for testing)."""
        self._tx_timestamps.clear()
        self._known_locations.clear()
