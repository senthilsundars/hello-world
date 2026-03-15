# Real-Time Banking Transactions with Apache Kafka

A Python example demonstrating real-time event streaming in a banking scenario using [Apache Kafka](https://kafka.apache.org/).

## Overview

```
┌──────────────────────┐        Kafka Topic         ┌──────────────────────────┐
│  Transaction         │  ──── bank-transactions ──► │  Transaction Consumer    │
│  Producer            │                             │  + Fraud Detector        │
│                      │                             │                          │
│  Simulates deposits, │                             │  Evaluates each event    │
│  withdrawals,        │                             │  using three rules:      │
│  transfers, payments │                             │  1. High-value amount    │
└──────────────────────┘                             │  2. Rapid succession     │
                                                     │  3. Geographic anomaly   │
                                                     └──────────────────────────┘
```

### Fraud Detection Rules

| Rule | Description |
|---|---|
| **High-value transaction** | Flags any transaction exceeding $10,000 |
| **Rapid successive transactions** | Flags an account sending more than 5 transactions within 60 seconds |
| **Geographic anomaly** | Flags a transaction from a location not previously seen for that account |

## Project Structure

```
.
├── models/
│   └── transaction.py          # Transaction dataclass & enums
├── producer/
│   └── transaction_producer.py # Kafka producer + transaction simulator
├── consumer/
│   ├── fraud_detector.py       # Stateful rule-based fraud detector
│   └── transaction_consumer.py # Kafka consumer + session summary
├── tests/
│   ├── test_transaction.py
│   ├── test_fraud_detector.py
│   ├── test_producer.py
│   └── test_consumer.py
├── run_producer.py             # Producer entry point
├── run_consumer.py             # Consumer entry point
├── docker-compose.yml          # Kafka + Zookeeper + Kafka UI
└── requirements.txt
```

## Prerequisites

- Python 3.9+
- Docker & Docker Compose (for the Kafka broker)

## Quick Start

### 1. Start Kafka

```bash
docker compose up -d
```

The following services are started:

| Service | URL |
|---|---|
| Kafka broker | `localhost:9092` |
| Kafka UI | http://localhost:8080 |

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the consumer (in one terminal)

```bash
python run_consumer.py
```

### 4. Start the producer (in another terminal)

```bash
# Send 50 transactions with a 0.5-second interval (default)
python run_producer.py --count 50

# Run indefinitely with a 1-second interval
python run_producer.py --count 0 --interval 1
```

### Example output (consumer)

```
2024-01-15 10:22:01 [INFO]  APPROVED  [3a7f1c2d]: Transaction(id=3a7f1c2d, account=ACC-1002, type=PAYMENT, amount=USD 847.30, status=APPROVED)
2024-01-15 10:22:01 [WARNING] FRAUD ALERT [b9e04a1f]: High-value transaction: USD 24312.50 exceeds threshold USD 10000.00
2024-01-15 10:22:02 [WARNING] FRAUD ALERT [c1f28b3e]: Geographic anomaly: unknown location 'Tokyo, JP' for account ACC-1001

============================================================
  Banking Kafka Consumer – Session Summary
============================================================
  Total processed : 50
  Approved        : 44
  Flagged (fraud) : 6
  Errors          : 0
  Fraud rate      : 12.0%
============================================================
```

## Running the Tests

No Kafka broker is needed to run tests — all Kafka interactions are mocked.

```bash
pytest tests/ -v
```

## Stopping Kafka

```bash
docker compose down
```
