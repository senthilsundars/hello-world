#!/usr/bin/env python
"""
Entry point: run the banking transaction producer simulation.

Usage:
    python run_producer.py [--count N] [--interval SECONDS]

Arguments:
    --count     Number of transactions to produce (default: 100; 0 = infinite)
    --interval  Delay between messages in seconds (default: 0.5)
"""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from producer.transaction_producer import TransactionProducer


def main() -> None:
    parser = argparse.ArgumentParser(description="Banking Kafka Transaction Producer")
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of transactions to produce (0 = run indefinitely)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Seconds between each message (default: 0.5)",
    )
    parser.add_argument(
        "--brokers",
        default="localhost:9092",
        help="Kafka bootstrap servers (default: localhost:9092)",
    )
    args = parser.parse_args()

    producer = TransactionProducer(bootstrap_servers=args.brokers)
    try:
        producer.simulate(
            num_transactions=args.count,
            interval_seconds=args.interval,
        )
    finally:
        producer.close()


if __name__ == "__main__":
    main()
