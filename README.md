# hello-world
This repository is for practicing the GitHub Flow.

## Python AML example

This repository includes a sample Anti-Money Laundering (AML) rules engine in `aml_rules_engine.py`.
The example uses USD-denominated amount thresholds for cash, wire, velocity, and structuring checks.
Those amount-based rules run only when a transaction is explicitly marked with `currency="USD"`; non-USD transactions are skipped by those threshold checks instead of being converted.

Run it with:

```bash
python aml_rules_engine.py
```
