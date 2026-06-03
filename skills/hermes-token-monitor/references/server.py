#!/usr/bin/env python3
"""
Token Monitor Server — Reference Pointer

The canonical implementation lives at:

    scripts/token_monitor.py

This file previously contained a full copy of the token monitor server.
It has been consolidated to avoid divergence between the two copies.

The scripts/ version is the authoritative source:
- sync.sh copies from ~/.hermes/token_monitor/server.py to scripts/token_monitor.py
- setup.sh copies from scripts/token_monitor.py to ~/.hermes/token_monitor/server.py
- Pricing data, model normalization, and UI features are maintained in one place

For the SKILL.md documentation on how to deploy and configure the monitor,
see the parent SKILL.md file and docs/shared/model-pricing.md.
"""

raise SystemExit(
    "This is a reference pointer. "
    "The canonical server is at scripts/token_monitor.py"
)
