#!/usr/bin/env python
"""
Entry point: run the banking transaction consumer with fraud detection.

Usage:
    python run_consumer.py [--brokers HOST:PORT] [--group GROUP_ID]
"""

import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from consumer.transaction_consumer import TransactionConsumer


def main() -> None:
    parser = argparse.ArgumentParser(description="Banking Kafka Transaction Consumer")
    parser.add_argument(
        "--brokers",
        default="localhost:9092",
        help="Kafka bootstrap servers (default: localhost:9092)",
    )
    parser.add_argument(
        "--group",
        default="banking-fraud-detection",
        help="Kafka consumer group ID",
    )
    args = parser.parse_args()

    consumer = TransactionConsumer(
        bootstrap_servers=args.brokers,
        group_id=args.group,
    )
    consumer.run()


if __name__ == "__main__":
    main()
