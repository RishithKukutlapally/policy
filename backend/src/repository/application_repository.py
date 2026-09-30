"""Repository for the ``applications`` status projection (AC-03, AC-14).

Applications are a projection: the row's ``status`` moves via :meth:`transition`, which also
appends to ``status_history``. There is no delete. The calling service owns the transaction.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.lib.clock import now_utc
from src.repository.models import Application
from src.types.enums import ApplicationStatus


class ApplicationRepository:
    """Stages new applications, moves their status and reads them back."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        quote_id: str,
        customer_id: str,
        product: str,
        rule_version: int,
        status: ApplicationStatus,
        status_history: list[str],
        full_name: str,
        date_of_birth: date,
        address: str,
        aadhaar_masked: str,
        pan_masked: str,
        risk_inputs: dict[str, Any],
    ) -> Application:
        """Insert one application (masked KYC only) and flush it."""
        row = Application(
            quote_id=quote_id,
            customer_id=customer_id,
            product=product,
            rule_version=rule_version,
            status=status.value,
            status_history=list(status_history),
            full_name=full_name,
            date_of_birth=date_of_birth,
            address=address,
            aadhaar_masked=aadhaar_masked,
            pan_masked=pan_masked,
            risk_inputs=dict(risk_inputs),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, application_id: str) -> Application | None:
        """The application with ``application_id``, or ``None``."""
        return self._session.get(Application, application_id)

    def list_by_statuses(self, statuses: Iterable[ApplicationStatus]) -> list[Application]:
        """Applications in any of ``statuses``, oldest first."""
        wanted = [s.value for s in statuses]
        statement = (
            select(Application)
            .where(Application.status.in_(wanted))
            .order_by(Application.created_at.asc(), text("rowid"))
        )
        return list(self._session.execute(statement).scalars())

    def transition(self, application: Application, status: ApplicationStatus) -> Application:
        """Move ``application`` to ``status`` and append it to the status history."""
        application.status = status.value
        application.status_history = [*application.status_history, status.value]
        application.updated_at = now_utc()
        self._session.flush()
        return application
