"""AC-11 regression: a version published through the API must be loadable by every read path.

Detected by the E9-S4 Playwright run (`e2e/tests/catalog-admin.spec.ts`): publishing a rule-set
version from the Product Catalog Manager appends a PUBLISHED ``rule_set_versions`` row, but no
``backend/policy_rules/<product>/v<N>.json`` file exists for it. Any code path that resolved rule
sets from disk answered ``NOT_FOUND — no rule file for product HOUSEHOLD v2``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.config.rule_loader import load_rule_set
from src.repository.rule_set_version_repository import RuleSetVersionRepository
from src.service.portfolio_service import PortfolioService, RepositoryRuleContentSource
from src.types.enums import ActorRole, PolicyStatus, ProductCode
from tests.conftest import actor_headers, rule_body
from tests.portfolio_helpers import AS_OF, FakeActor, seed_payment, seed_policy

pytestmark = pytest.mark.ac("AC-11")

HOUSEHOLD_VERSIONS = "/api/products/HOUSEHOLD/versions"
ADMIN = actor_headers(ActorRole.ADMIN)
_PREMIUM = Decimal("3100.00")

#: Synthetic HOUSEHOLD quote inputs accepted by the seeded rule set's eligibility fields.
_HOUSEHOLD_INPUTS = {
    "sum_insured": "2000000.00",
    "proposer_age": 40,
    "construction_type": "CONCRETE",
    "in_flood_zone": False,
    "has_security_system": True,
}


def _publish_household_v2(client: TestClient) -> None:
    """Draft and publish HOUSEHOLD v2 exactly as the admin UI does (AC-11)."""
    created = client.post(
        HOUSEHOLD_VERSIONS, json=rule_body(ProductCode.HOUSEHOLD, base_rate="0.0021"), headers=ADMIN
    )
    assert created.status_code == 201, created.text
    published = client.post(f"{HOUSEHOLD_VERSIONS}/2/publish", headers=ADMIN)
    assert published.status_code == 200, published.text
    assert published.json()["is_active"] is True


def _seed_policy_on_v2(engine: Engine) -> None:
    """One in-force HOUSEHOLD policy recorded against the newly published v2."""
    with Session(engine) as session:
        policy = seed_policy(
            session,
            policy_number="HH-2026-000009",
            product=ProductCode.HOUSEHOLD,
            status=PolicyStatus.ACTIVE,
            sum_insured=Decimal("2000000.00"),
            premium=_PREMIUM,
            effective_date=date(2026, 3, 2),
            expiry_date=date(2027, 3, 1),
            rule_version=2,
        )
        seed_payment(session, policy, due_date=date(2026, 3, 2), amount=_PREMIUM)
        session.commit()


def test_ac11_published_version_is_loadable_by_the_portfolio(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-11: the portfolio loads a UI-published version that has no file on disk."""
    _publish_household_v2(api_client)
    _seed_policy_on_v2(seeded_engine)

    response = api_client.get(
        "/api/admin/portfolio", params={"as_of": AS_OF.isoformat()}, headers=ADMIN
    )
    assert response.status_code == 200, response.text
    assert response.json()["active_by_product"]["HOUSEHOLD"] == 1


def test_ac11_published_version_is_loadable_by_the_quote_endpoint(api_client: TestClient) -> None:
    """AC-11: a quote after publish prices on the new version, not the seeded v1."""
    _publish_household_v2(api_client)
    response = api_client.post(
        "/api/quotes",
        json={
            "product": "HOUSEHOLD",
            "inputs": _HOUSEHOLD_INPUTS,
        },
        headers=actor_headers(ActorRole.CUSTOMER),
    )
    assert response.status_code == 201, response.text
    assert response.json()["rule_version"] == 2


def test_ac11_rule_set_resolution_is_database_first(
    api_client: TestClient, seeded_engine: Engine
) -> None:
    """AC-11: ``load_rule_set`` resolves v2 from the database and still falls back to v1 on disk."""
    _publish_household_v2(api_client)
    with Session(seeded_engine) as session:
        source = RepositoryRuleContentSource(RuleSetVersionRepository(session))
        published = load_rule_set(ProductCode.HOUSEHOLD, 2, source=source)
        assert published.premium.base_rate == Decimal("0.0021")
        seeded = load_rule_set(ProductCode.HOUSEHOLD, 1, source=source)
        assert seeded.premium.base_rate != Decimal("0.0021")


def test_ac11_portfolio_service_rejects_a_version_that_exists_nowhere(
    seeded_session: Session,
) -> None:
    """AC-11: an unknown version is still NOT_FOUND — the fallback does not invent rule sets."""
    policy_session = seeded_session
    seed_policy(
        policy_session,
        policy_number="HH-2026-000010",
        product=ProductCode.HOUSEHOLD,
        status=PolicyStatus.ACTIVE,
        sum_insured=Decimal("2000000.00"),
        premium=_PREMIUM,
        effective_date=date(2026, 3, 2),
        expiry_date=date(2027, 3, 1),
        rule_version=99,
    )
    policy_session.commit()
    with pytest.raises(Exception, match="no rule file for product HOUSEHOLD v99"):
        PortfolioService(policy_session).portfolio(AS_OF, FakeActor())
