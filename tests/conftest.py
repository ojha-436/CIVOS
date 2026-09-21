"""Shared test fixtures.

The rate limiter is per-process, in-memory, sliding-window state. That is the
right design for a cost-blast-radius control on Cloud Run and the wrong thing to
share between tests: whichever module happened to run first spent the budget, and
everything after it got 429s that looked like assertion failures in unrelated
features. The tests were not independent, and the failures pointed at the wrong
code.
"""

from __future__ import annotations

import pytest

from api import guards


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """Give every test the whole budget, and leave none of it behind."""
    guards._per_ip.clear()
    guards._global.hits.clear()
    yield
    guards._per_ip.clear()
    guards._global.hits.clear()
