"""Endorsement service and repository surface (E6-S2)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from src.api.deps import Actor
from src.repository.models import Endorsement
from src.repository.policy_lifecycle_repository import EndorsementRepository
from src.service.endorsement_service import EndorsementService
from src.types.enums import ActorRole, EndorsementType
from src.types.errors import NotFoundError, ValidationError
from tests.endorsement_helpers import count, endorsement_rows, issued_policy

CUSTOMER = Actor("cust-001", ActorRole.CUSTOMER)
_NOMINEE = {"nominee_name": "A", "relationship": "CHILD", "share_percent": "60"}
_BAD_REQUESTS: list[tuple[EndorsementType, dict[str, Any]]] = [
    (EndorsementType.CHANGE_ADDRESS, {"address": "1 Sample Street, Testville"}),
    (EndorsementType.CHANGE_ADDRESS, {"address": "a" * 301}),
    (EndorsementType.CHANGE_SUM_INSURED, {"new_sum_insured": 600000}),
    (EndorsementType.CHANGE_SUM_INSURED, {"new_sum_insured": "abc"}),
    (EndorsementType.ADD_NOMINEE, {**_NOMINEE, "relationship": "PET"}),
    (EndorsementType.ADD_NOMINEE, {**_NOMINEE, "share_percent": "0"}),
    (EndorsementType.ADD_NOMINEE, {"nominee_name": "A", "relationship": "CHILD"}),
]


def test_service_apply_returns_view_and_persists_once(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        view = EndorsementService(session).apply(
            number, EndorsementType.CHANGE_SUM_INSURED, {"new_sum_insured": "600000.00"}, CUSTOMER
        )
    assert view.premium_delta == Decimal("1537.26")
    assert view.endorsement_id is not None
    assert len(endorsement_rows(seeded_engine)) == 1


def test_service_preview_persists_nothing(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        view = EndorsementService(session).preview(
            number, EndorsementType.CHANGE_ADDRESS, {"address": "9 New Lane"}, CUSTOMER
        )
    assert view.endorsement_id is None
    assert view.preview
    assert count(seeded_engine, Endorsement) == 0


def test_service_rejects_other_customer_and_bad_shapes(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        service = EndorsementService(session)
        other = Actor("cust-999", ActorRole.CUSTOMER)
        with pytest.raises(NotFoundError):
            service.preview(number, EndorsementType.CHANGE_ADDRESS, {"address": "x"}, other)
        for kind, changes in _BAD_REQUESTS:
            with pytest.raises(ValidationError):
                service.preview(number, kind, changes, CUSTOMER)


def test_service_nominee_share_total_cannot_exceed_100(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        service = EndorsementService(session)
        service.apply(number, EndorsementType.ADD_NOMINEE, _NOMINEE, CUSTOMER)
        with pytest.raises(ValidationError) as caught:
            service.apply(number, EndorsementType.ADD_NOMINEE, _NOMINEE, CUSTOMER)
    assert caught.value.details == [{"field": "share_percent", "code": "SHARE_EXCEEDS_100"}]


def test_endorsement_history_is_stable_after_three_endorsements(
    api_client: TestClient, seeded_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = issued_policy(api_client, monkeypatch)
    with Session(seeded_engine) as session:
        service = EndorsementService(session)
        for i in range(3):
            changes = {"address": f"{i} Road"}
            service.apply(number, EndorsementType.CHANGE_ADDRESS, changes, CUSTOMER)
    rows = endorsement_rows(seeded_engine)
    assert sorted(r.after["address"] for r in rows) == ["0 Road", "1 Road", "2 Road"]
    assert not [n for n in dir(EndorsementRepository) if "update" in n or "delete" in n]
