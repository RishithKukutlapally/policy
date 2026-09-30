"""AC-06: an endorsement is one atomic, immutable, audited unit of work (E6-S2)."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.main import create_app
from src.repository.models import AuditRecord, Endorsement, Policy, PolicyStateTransition
from src.repository.policy_lifecycle_repository import (
    EndorsementRepository,
    PolicyStateTransitionRepository,
)
from src.service.unit_of_work import get_service_session
from src.types.enums import ActorRole
from tests.endorsement_helpers import (
    ADDRESS_BODY,
    SUM_BODY,
    audit_rows,
    count,
    endorse,
    endorsement_rows,
    issued_policy,
    policy_row,
    transition_rows,
)

ORIGINAL_ADDRESS = "1 Sample Street, Testville"


@pytest.mark.ac("AC-06")
def test_ac06_endorsement_record_created_and_linked(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    response = endorse(api_client, number, ADDRESS_BODY)
    assert response.status_code == 201, response.text
    rows = endorsement_rows(seeded_engine)
    assert len(rows) == 1
    assert rows[0].policy_id == policy_row(seeded_engine, number).id
    assert rows[0].before == {"address": ORIGINAL_ADDRESS}
    assert rows[0].after == {"address": "2 Sample Road, Testville"}
    assert rows[0].premium_delta == Decimal("0.00")


@pytest.mark.ac("AC-06")
def test_ac06_policy_attributes_updated_atomically(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    response = endorse(api_client, number, SUM_BODY, role=ActorRole.ADMIN)
    assert response.status_code == 201, response.text
    policy = policy_row(seeded_engine, number)
    assert (policy.sum_insured, policy.premium) == (Decimal("600000.00"), Decimal("18600.00"))
    assert policy.status == "ENDORSED"
    assert endorsement_rows(seeded_engine)[0].premium_delta == Decimal("1537.26")
    ended = [t for t in transition_rows(seeded_engine) if t.to_status == "ENDORSED"]
    assert [(t.from_status, t.to_status) for t in ended] == [("ACTIVE", "ENDORSED")]
    assert len(audit_rows(seeded_engine, "ENDORSEMENT_CREATED")) == 1


@pytest.mark.ac("AC-06")
def test_ac06_failure_rolls_back_both(
    seeded_engine: Engine, api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    before = policy_row(seeded_engine, number)
    models = (Endorsement, PolicyStateTransition, AuditRecord)
    counts = {m: count(seeded_engine, m) for m in models}
    app = create_app()

    def _session() -> Iterator[Session]:
        with Session(seeded_engine) as session:
            yield session

    app.dependency_overrides[get_service_session] = _session
    with (
        TestClient(app, raise_server_exceptions=False) as client,
        patch.object(PolicyStateTransitionRepository, "add", side_effect=RuntimeError("boom")),
    ):
        response = endorse(client, number, SUM_BODY, role=ActorRole.ADMIN)
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    after = policy_row(seeded_engine, number)
    assert (after.sum_insured, after.premium, after.address, after.status) == (
        before.sum_insured,
        before.premium,
        before.address,
        before.status,
    )
    assert {m: count(seeded_engine, m) for m in models} == counts


@pytest.mark.ac("AC-06")
def test_ac06_endorsement_record_has_no_update_path() -> None:
    names = [n for n in dir(EndorsementRepository) if not n.startswith("__")]
    assert not [n for n in names if any(w in n for w in ("update", "delete", "merge"))]


@pytest.mark.ac("AC-10")
def test_ac10_endorsing_cancelled_policy_is_409_and_writes_nothing(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        session.query(Policy).update({"status": "CANCELLED"})
        session.commit()
    response = endorse(api_client, number, ADDRESS_BODY)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_POLICY_STATE"
    assert count(seeded_engine, Endorsement) == 0
    assert policy_row(seeded_engine, number).address == ORIGINAL_ADDRESS


@pytest.mark.ac("AC-10")
def test_ac10_second_endorsement_on_endorsed_policy_succeeds(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    assert endorse(api_client, number, ADDRESS_BODY).status_code == 201
    assert endorse(api_client, number, SUM_BODY).status_code == 201
    assert count(seeded_engine, Endorsement) == 2
    pairs = [(t.from_status, t.to_status) for t in transition_rows(seeded_engine)]
    assert ("ENDORSED", "ENDORSED") in pairs
