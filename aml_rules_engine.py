from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import re


HIGH_RISK_COUNTRIES = {"AF", "IR", "KP", "MM", "SY"}
SANCTIONED_NAMES = {
    "bad actor llc",
    "blocked person",
    "shadow imports ltd",
}
# Demo simplification: amount-based threshold rules run only for transactions
# explicitly denominated in USD. Other currencies are skipped instead of converted.
THRESHOLD_CURRENCY = "USD"
LARGE_CASH_THRESHOLD = 10_000
HIGH_VALUE_WIRE_THRESHOLD = 50_000
HIGH_24H_VALUE_THRESHOLD = 100_000
HIGH_24H_COUNT_THRESHOLD = 5
STRUCTURING_LOWER_BOUND = 9_000


def normalize_name(name: str) -> str:
    normalized = name.lower().strip()
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def normalize_country_code(country_code: str) -> str:
    return country_code.strip().upper()


def normalize_currency(currency: str) -> str:
    return currency.strip().upper()


def normalize_channel(channel: str) -> str:
    return channel.strip().lower()


def normalize_risk_label(risk_label: str) -> str:
    return risk_label.strip().lower()


@dataclass
class Customer:
    customer_id: str
    full_name: str
    country_code: str
    is_pep: bool
    industry: str
    onboarding_risk: str


@dataclass
class Transaction:
    tx_id: str
    customer_id: str
    timestamp: datetime
    amount: float
    currency: str
    country_code: str
    channel: str
    counterparty_name: str
    counterparty_country: str


@dataclass
class Alert:
    code: str
    severity: str
    message: str
    score: int


@dataclass
class Decision:
    outcome: str
    total_score: int
    alerts: List[Alert] = field(default_factory=list)


class AMLRulesEngine:
    def __init__(self, tx_history: Dict[str, List[Transaction]]):
        self.tx_history = tx_history

    def evaluate(self, customer: Customer, tx: Transaction) -> Decision:
        alerts: List[Alert] = []
        alerts.extend(self._check_sanctions(tx))
        alerts.extend(self._check_customer_risk(customer))
        alerts.extend(self._check_geography(customer, tx))
        alerts.extend(self._check_large_transactions(tx))
        alerts.extend(self._check_velocity(tx))
        alerts.extend(self._check_structuring(tx))

        total_score = sum(alert.score for alert in alerts)
        outcome = self._decision(alerts, total_score)
        return Decision(outcome=outcome, total_score=total_score, alerts=alerts)

    def _uses_threshold_currency(self, tx: Transaction) -> bool:
        """Return True when USD-only threshold rules should evaluate the transaction."""
        return normalize_currency(tx.currency) == THRESHOLD_CURRENCY

    def _check_sanctions(self, tx: Transaction) -> List[Alert]:
        if normalize_name(tx.counterparty_name) in SANCTIONED_NAMES:
            return [
                Alert(
                    code="SANCTIONS_MATCH",
                    severity="critical",
                    message=f"Counterparty matched sanctions list: {tx.counterparty_name}",
                    score=100,
                )
            ]
        return []

    def _check_customer_risk(self, customer: Customer) -> List[Alert]:
        alerts = []

        if customer.is_pep:
            alerts.append(
                Alert(
                    code="PEP_CUSTOMER",
                    severity="high",
                    message="Customer is a politically exposed person",
                    score=30,
                )
            )

        if normalize_risk_label(customer.onboarding_risk) == "high":
            alerts.append(
                Alert(
                    code="HIGH_ONBOARDING_RISK",
                    severity="medium",
                    message="Customer has high onboarding risk classification",
                    score=20,
                )
            )

        if customer.industry.strip().lower() in {"casino", "crypto exchange", "money services business"}:
            alerts.append(
                Alert(
                    code="HIGH_RISK_INDUSTRY",
                    severity="medium",
                    message=f"Customer operates in high-risk industry: {customer.industry}",
                    score=20,
                )
            )

        return alerts

    def _check_geography(self, customer: Customer, tx: Transaction) -> List[Alert]:
        alerts = []
        customer_country_code = normalize_country_code(customer.country_code)
        transaction_country_code = normalize_country_code(tx.country_code)
        counterparty_country_code = normalize_country_code(tx.counterparty_country)

        if customer_country_code in HIGH_RISK_COUNTRIES:
            alerts.append(
                Alert(
                    code="CUSTOMER_HIGH_RISK_GEO",
                    severity="high",
                    message=f"Customer linked to high-risk geography: {customer_country_code}",
                    score=25,
                )
            )

        if transaction_country_code in HIGH_RISK_COUNTRIES:
            alerts.append(
                Alert(
                    code="TRANSACTION_HIGH_RISK_GEO",
                    severity="high",
                    message=f"Transaction linked to high-risk geography: {transaction_country_code}",
                    score=25,
                )
            )

        if counterparty_country_code in HIGH_RISK_COUNTRIES:
            alerts.append(
                Alert(
                    code="COUNTERPARTY_HIGH_RISK_GEO",
                    severity="high",
                    message=f"Counterparty linked to high-risk geography: {counterparty_country_code}",
                    score=25,
                )
            )

        return alerts

    def _check_large_transactions(self, tx: Transaction) -> List[Alert]:
        """Apply USD-only large cash and high-value wire thresholds."""
        alerts = []
        normalized_channel = normalize_channel(tx.channel)

        if self._uses_threshold_currency(tx) and normalized_channel == "cash" and tx.amount >= LARGE_CASH_THRESHOLD:
            alerts.append(
                Alert(
                    code="LARGE_CASH_TX",
                    severity="high",
                    message=f"Large cash transaction: {tx.amount} {tx.currency}",
                    score=35,
                )
            )

        if self._uses_threshold_currency(tx) and normalized_channel == "wire" and tx.amount >= HIGH_VALUE_WIRE_THRESHOLD:
            alerts.append(
                Alert(
                    code="HIGH_VALUE_WIRE",
                    severity="medium",
                    message=f"High-value wire transaction: {tx.amount} {tx.currency}",
                    score=20,
                )
            )

        return alerts

    def _check_velocity(self, tx: Transaction) -> List[Alert]:
        """Apply USD-only 24-hour transaction velocity thresholds."""
        if not self._uses_threshold_currency(tx):
            return []

        one_day_ago = tx.timestamp - timedelta(days=1)
        recent = [
            prior_tx
            for prior_tx in self.tx_history.get(tx.customer_id, [])
            if one_day_ago <= prior_tx.timestamp < tx.timestamp
            and normalize_currency(prior_tx.currency) == normalize_currency(tx.currency)
        ]

        total_24h = sum(prior_tx.amount for prior_tx in recent) + tx.amount
        count_24h = len(recent) + 1
        alerts = []

        if count_24h >= HIGH_24H_COUNT_THRESHOLD:
            alerts.append(
                Alert(
                    code="TX_VELOCITY_COUNT",
                    severity="medium",
                    message=f"High transaction count in 24h: {count_24h}",
                    score=15,
                )
            )

        if total_24h >= HIGH_24H_VALUE_THRESHOLD:
            alerts.append(
                Alert(
                    code="TX_VELOCITY_VALUE",
                    severity="high",
                    message=f"High aggregate transaction value in 24h: {total_24h}",
                    score=30,
                )
            )

        return alerts

    def _check_structuring(self, tx: Transaction) -> List[Alert]:
        """Apply USD-only structuring checks to cash transactions."""
        if normalize_channel(tx.channel) != "cash" or not self._uses_threshold_currency(tx):
            return []

        one_day_ago = tx.timestamp - timedelta(days=1)
        recent_cash = [
            prior_tx
            for prior_tx in self.tx_history.get(tx.customer_id, [])
            if one_day_ago <= prior_tx.timestamp < tx.timestamp
            and normalize_channel(prior_tx.channel) == "cash"
            and normalize_currency(prior_tx.currency) == normalize_currency(tx.currency)
        ]
        prior_near_threshold = [
            prior_tx
            for prior_tx in recent_cash
            if STRUCTURING_LOWER_BOUND <= prior_tx.amount < LARGE_CASH_THRESHOLD
        ]
        current_near_threshold = STRUCTURING_LOWER_BOUND <= tx.amount < LARGE_CASH_THRESHOLD

        if len(prior_near_threshold) >= 2 and current_near_threshold:
            return [
                Alert(
                    code="STRUCTURING_PATTERN",
                    severity="high",
                    message="Multiple sub-threshold cash transactions suggest structuring",
                    score=40,
                )
            ]

        return []

    def _decision(self, alerts: List[Alert], total_score: int) -> str:
        if any(alert.code == "SANCTIONS_MATCH" for alert in alerts):
            return "BLOCK"
        if total_score >= 70:
            return "REVIEW"
        if total_score >= 30:
            return "MONITOR"
        return "APPROVE"


def build_sample_data() -> Tuple[Customer, Dict[str, List[Transaction]], Transaction]:
    """Return illustrative sample data for running the rules engine locally."""
    customer = Customer(
        customer_id="C001",
        full_name="Alice Doe",
        country_code="IR",
        is_pep=True,
        industry="Crypto Exchange",
        onboarding_risk="high",
    )

    history = {
        "C001": [
            Transaction(
                "T100",
                "C001",
                datetime(2026, 9, 26, 9, 0),
                9_500,
                "USD",
                "IR",
                "cash",
                "Local Trader",
                "AE",
            ),
            Transaction(
                "T101",
                "C001",
                datetime(2026, 9, 26, 13, 0),
                9_700,
                "USD",
                "IR",
                "cash",
                "Local Trader",
                "AE",
            ),
            Transaction(
                "T102",
                "C001",
                datetime(2026, 9, 26, 18, 0),
                20_000,
                "USD",
                "IR",
                "wire",
                "Regional Broker",
                "SY",
            ),
        ]
    }

    new_tx = Transaction(
        tx_id="T103",
        customer_id="C001",
        timestamp=datetime(2026, 9, 26, 20, 0),
        amount=9_800,
        currency="USD",
        country_code="IR",
        channel="cash",
        counterparty_name="Shadow Imports Ltd",
        counterparty_country="SY",
    )

    return customer, history, new_tx


def main() -> None:
    customer, history, new_tx = build_sample_data()
    engine = AMLRulesEngine(tx_history=history)
    result = engine.evaluate(customer, new_tx)

    print("Decision:", result.outcome)
    print("Total Score:", result.total_score)
    print("Alerts:")
    for alert in result.alerts:
        print(f"- [{alert.severity}] {alert.code}: {alert.message} (+{alert.score})")


if __name__ == "__main__":
    main()
