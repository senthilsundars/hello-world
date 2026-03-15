"""Unit tests for the FraudDetector engine."""

from datetime import datetime, timedelta, timezone

import pytest

from consumer.fraud_detector import FraudDetector
from models.transaction import Transaction, TransactionStatus, TransactionType


def _make_tx(
    account_id: str = "ACC-001",
    amount: float = 100.0,
    location: str = "New York, US",
    transaction_type: TransactionType = TransactionType.PAYMENT,
) -> Transaction:
    """Helper to build a minimal transaction for testing."""
    return Transaction(
        account_id=account_id,
        transaction_type=transaction_type,
        amount=amount,
        location=location,
    )


class TestHighValueRule:
    """Rule 1: High-value transactions."""

    def test_below_threshold_is_approved(self):
        detector = FraudDetector(high_value_threshold=10_000.0)
        tx = _make_tx(amount=9_999.99)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.APPROVED

    def test_exactly_at_threshold_is_approved(self):
        detector = FraudDetector(high_value_threshold=10_000.0)
        tx = _make_tx(amount=10_000.0)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.APPROVED

    def test_above_threshold_is_flagged(self):
        detector = FraudDetector(high_value_threshold=10_000.0)
        tx = _make_tx(amount=10_000.01)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.FLAGGED

    def test_custom_threshold(self):
        detector = FraudDetector(high_value_threshold=500.0)
        tx = _make_tx(amount=501.0)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.FLAGGED


class TestRapidSuccessionRule:
    """Rule 2: Rapid successive transactions."""

    def test_below_limit_is_approved(self):
        detector = FraudDetector(rapid_tx_window_seconds=60, rapid_tx_limit=5)
        for _ in range(4):
            tx = _make_tx(amount=50.0)
            result = detector.evaluate(tx)
        assert result.status == TransactionStatus.APPROVED

    def test_at_limit_triggers_flag_on_next(self):
        detector = FraudDetector(rapid_tx_window_seconds=60, rapid_tx_limit=3)
        for _ in range(3):
            detector.evaluate(_make_tx(amount=50.0))
        # Fourth transaction should be flagged
        tx = _make_tx(amount=50.0)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.FLAGGED

    def test_different_accounts_do_not_interfere(self):
        detector = FraudDetector(rapid_tx_window_seconds=60, rapid_tx_limit=3)
        for _ in range(3):
            detector.evaluate(_make_tx(account_id="ACC-A", amount=50.0))
        # ACC-B has only one transaction – should be approved
        tx = _make_tx(account_id="ACC-B", amount=50.0)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.APPROVED

    def test_old_transactions_evicted_from_window(self):
        """Timestamps older than the window should not count toward the limit."""
        detector = FraudDetector(rapid_tx_window_seconds=60, rapid_tx_limit=3)

        # Manually inject old timestamps (outside the window)
        old_ts = (
            datetime.now(timezone.utc) - timedelta(seconds=120)
        ).isoformat()
        from collections import deque
        detector._tx_timestamps["ACC-001"] = deque([old_ts, old_ts, old_ts])

        tx = _make_tx(account_id="ACC-001", amount=50.0)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.APPROVED


class TestGeographicAnomalyRule:
    """Rule 3: Geographic anomaly detection."""

    def test_first_transaction_never_flagged(self):
        detector = FraudDetector()
        tx = _make_tx(location="New York, US")
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.APPROVED

    def test_same_location_not_flagged(self):
        detector = FraudDetector()
        detector.evaluate(_make_tx(location="Paris, FR"))
        result = detector.evaluate(_make_tx(location="Paris, FR"))
        assert result.status == TransactionStatus.APPROVED

    def test_new_location_flagged(self):
        detector = FraudDetector()
        detector.evaluate(_make_tx(location="Paris, FR"))
        tx = _make_tx(location="Tokyo, JP")
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.FLAGGED

    def test_multiple_known_locations_not_flagged(self):
        detector = FraudDetector()
        for loc in ("New York, US", "London, UK", "Paris, FR"):
            detector.evaluate(_make_tx(location=loc))
        # All three are now known
        result = detector.evaluate(_make_tx(location="London, UK"))
        assert result.status == TransactionStatus.APPROVED

    def test_empty_location_skips_rule(self):
        detector = FraudDetector()
        detector.evaluate(_make_tx(location="New York, US"))
        tx = _make_tx(location="")
        # No location – rule should not flag it
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.APPROVED


class TestFraudDetectorReset:
    """Detector state management."""

    def test_reset_clears_timestamps(self):
        detector = FraudDetector(rapid_tx_limit=2)
        detector.evaluate(_make_tx(amount=50.0))
        detector.evaluate(_make_tx(amount=50.0))
        detector.reset()
        # After reset, limit counter restarts
        result = detector.evaluate(_make_tx(amount=50.0))
        assert result.status == TransactionStatus.APPROVED

    def test_reset_clears_known_locations(self):
        detector = FraudDetector()
        detector.evaluate(_make_tx(location="New York, US"))
        detector.reset()
        # Location knowledge cleared – first transaction after reset is baseline
        result = detector.evaluate(_make_tx(location="Tokyo, JP"))
        assert result.status == TransactionStatus.APPROVED


class TestMultipleRulesCombined:
    """Ensure multiple rules can fire simultaneously."""

    def test_high_value_and_new_location_both_flag(self):
        detector = FraudDetector(high_value_threshold=1_000.0)
        detector.evaluate(_make_tx(location="New York, US", amount=50.0))
        tx = _make_tx(location="Sydney, AU", amount=5_000.0)
        result = detector.evaluate(tx)
        assert result.status == TransactionStatus.FLAGGED
