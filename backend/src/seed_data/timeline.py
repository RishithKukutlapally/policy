"""The fixed demo calendar (DEC-012).

The seed never reads the wall clock: it pins the business date for each phase so the renewal and
lapse states land exactly where the guided tour in ``README.md`` says they do.

    2025-06-01  a HOUSEHOLD term starts -> expires 2026-05-31, grace ends 2026-07-01
    2025-07-01  a MOTOR term starts     -> expires 2026-06-30, renewal opens 2026-06-01
    2026-07-01  the demo "today": new business, endorsement, renewal payment and renewal
    2026-07-05  the cancellation date of the free-look showcase policy
    2026-07-02  the end-of-day run that lapses the unpaid 2025-06-01 term
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Final

from src.lib.clock import BUSINESS_DATE_ENV_VARS

#: The business date the demo database presents as "today".
DEMO_DATE: Final = date(2026, 7, 1)
#: Start of the term that ends up LAPSED (its grace period closes on ``DEMO_DATE``).
LAPSE_TERM_START: Final = date(2025, 6, 1)
#: Start of the term that ends up RENEWED (its renewal falls due on ``DEMO_DATE``).
RENEWAL_TERM_START: Final = date(2025, 7, 1)
#: Inside the 15-day free-look window of a policy issued on ``DEMO_DATE``.
CANCELLATION_DATE: Final = DEMO_DATE + timedelta(days=4)
#: One day past the grace end of the ``LAPSE_TERM_START`` term.
END_OF_DAY_DATE: Final = DEMO_DATE + timedelta(days=1)

_PRIMARY_ENV_VAR: Final = BUSINESS_DATE_ENV_VARS[0]


@contextmanager
def business_date(on: date) -> Iterator[date]:
    """Run the block with ``src.lib.clock.today()`` pinned to ``on``, restoring it afterwards."""
    previous = os.environ.get(_PRIMARY_ENV_VAR)
    os.environ[_PRIMARY_ENV_VAR] = on.isoformat()
    try:
        yield on
    finally:
        if previous is None:
            os.environ.pop(_PRIMARY_ENV_VAR, None)
        else:
            os.environ[_PRIMARY_ENV_VAR] = previous
