"""Synthetic demo data for ``python -m src.seed`` (E9-S3).

Nothing here is real: Aadhaar numbers start ``9999``, PANs follow ``AAAAA<4 digits>A`` and names
are ``Test Customer NN`` (``docs/conventions.md`` -> "Synthetic data"). Only masked values ever
reach the database, because every row is written by the production services.
"""

from src.seed_data.actors import SeedActor, admin, customer, system, underwriter
from src.seed_data.cases import CASES, LIFECYCLE_CASES, SeedCase, kyc_for
from src.seed_data.timeline import (
    CANCELLATION_DATE,
    DEMO_DATE,
    END_OF_DAY_DATE,
    LAPSE_TERM_START,
    RENEWAL_TERM_START,
    business_date,
)

__all__ = [
    "CANCELLATION_DATE",
    "CASES",
    "DEMO_DATE",
    "END_OF_DAY_DATE",
    "LAPSE_TERM_START",
    "LIFECYCLE_CASES",
    "RENEWAL_TERM_START",
    "SeedActor",
    "SeedCase",
    "admin",
    "business_date",
    "customer",
    "kyc_for",
    "system",
    "underwriter",
]
