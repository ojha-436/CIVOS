"""CIVOS core — country-agnostic.

Nothing in this package may name a country, a district, a language list, a
currency or a government scheme. Those live in `adapters/<iso>/`. The rule is
enforced by `scripts/lint_country_literals.py`, which runs in CI; it is evidence
for the cross-border claim (SPEC P0-14), not merely hygiene.
"""

__version__ = "0.1.0"
