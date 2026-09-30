"""End-of-day renewal / lapse job (AC-07, AC-18, NFR-02, NFR-04; DEC-011).

Two entry points share :class:`EndOfDayRunner`: ``POST /api/admin/end-of-day`` (actor = the admin)
and ``python -m src.jobs.end_of_day --as-of YYYY-MM-DD`` (actor ``system-eod``, ``SYSTEM``).
Every non-terminal policy is decided by ``end_of_day_action``: ``RENEW`` creates the successor
term, ``LAPSE`` moves the policy to ``LAPSED``, ``IN_GRACE`` / ``NONE`` change nothing. Each policy
runs in its own transaction and a failure is logged and skipped. Re-running the same date is
idempotent because a renewed or lapsed policy is terminal and a policy with a successor row is
never renewed again - there is no "processed" flag.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Final

from sqlalchemy.orm import Session

from src.config.settings import get_settings
from src.domain.policy_state_machine import is_terminal
from src.domain.renewal_rules import PolicyView, end_of_day_action
from src.lib.correlation import new_correlation_id, set_correlation_id
from src.lib.logging import get_logger
from src.repository.database import SessionLocal
from src.repository.models import AuditAction, AuditEntityType
from src.repository.policy_repository import PolicyRepository
from src.service.audit_service import AuditService
from src.service.policy_service import PolicyService
from src.service.quote_service import ActingActor
from src.service.renewal_service import RenewalService
from src.types.enums import ActorRole, EndOfDayAction, PolicyStatus
from src.types.errors import PolicyForgeError

SYSTEM_ACTOR_ID: Final = "system-eod"
LAPSE_REASON: Final = "GRACE_PERIOD_EXPIRED"
_logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SystemActor:
    """The scheduler identity (never accepted from a header, DEC-010)."""

    actor_id: str = SYSTEM_ACTOR_ID
    role: ActorRole = ActorRole.SYSTEM


@dataclass(frozen=True, slots=True)
class FailedPolicy:
    """A policy skipped because processing it raised."""

    policy_number: str
    error: str


@dataclass(slots=True)
class EndOfDayResult:
    """What one run did (contract 2.25)."""

    as_of: date
    renewed: list[tuple[str, str]] = field(default_factory=list)
    lapsed: list[str] = field(default_factory=list)
    in_grace: int = 0
    not_renewable: int = 0
    failed: list[FailedPolicy] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        """The numeric summary written to the audit row."""
        return {
            "renewed": len(self.renewed),
            "lapsed": len(self.lapsed),
            "in_grace": self.in_grace,
            "not_renewable": self.not_renewable,
            "failed": len(self.failed),
        }


class EndOfDayRunner:
    """Applies the renew / lapse decision to every live policy for one business date."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._policies = PolicyRepository(session)
        self._renewals = RenewalService(session)
        self._audit = AuditService(session)

    def run(self, as_of: date, actor: ActingActor) -> EndOfDayResult:
        """Process every non-terminal policy, then audit the run (one row per run)."""
        result = EndOfDayResult(as_of=as_of)
        numbers = [
            row.policy_number
            for row in self._policies.list_all()
            if not is_terminal(PolicyStatus(row.status))
        ]
        for number in numbers:
            try:
                self._process(number, as_of, actor, result)
                self._session.commit()
            except Exception as exc:
                self._session.rollback()
                error = exc.code if isinstance(exc, PolicyForgeError) else type(exc).__name__
                result.failed.append(FailedPolicy(number, error))
                _logger.error(
                    "end-of-day policy failed", extra={"policy_number": number, "error": error}
                )
        self._record_audit(as_of, actor, result)
        return result

    def _process(
        self, number: str, as_of: date, actor: ActingActor, result: EndOfDayResult
    ) -> None:
        """Decide and apply the action for one policy; the caller commits."""
        policy = self._policies.get_by_number(number)
        if policy is None or is_terminal(PolicyStatus(policy.status)):
            return
        if self._policies.successor_of(number) is not None:
            return
        context = self._renewals.build_context(policy)
        paid = self._renewals.payment_for(policy, context.schedule.due_date) is not None
        action = end_of_day_action(
            PolicyView(PolicyStatus(policy.status), policy.expiry_date, paid),
            as_of,
            context.rule_set,
            get_settings().renewal_window_days,
        )
        if action is EndOfDayAction.NONE:
            return
        if not context.renewable:
            result.not_renewable += 1
        elif action is EndOfDayAction.RENEW:
            successor = self._renewals.apply_renewal(number, as_of, actor)
            result.renewed.append((number, successor.policy_number))
        elif action is EndOfDayAction.LAPSE:
            PolicyService(self._session).transition(
                number, PolicyStatus.LAPSED, reason=LAPSE_REASON, actor=actor
            )
            result.lapsed.append(number)
        else:
            result.in_grace += 1

    def _record_audit(self, as_of: date, actor: ActingActor, result: EndOfDayResult) -> None:
        """Append the run's audit row and commit it."""
        self._audit.record(
            action=AuditAction.RUN_END_OF_DAY,
            actor_id=actor.actor_id,
            actor_role=actor.role,
            entity_type=AuditEntityType.END_OF_DAY,
            entity_id=as_of.isoformat(),
            detail={"as_of": as_of.isoformat(), **result.counts()},
        )
        self._session.commit()


def _parse_args(argv: Sequence[str] | None) -> date | None:
    """The ``--as-of`` date, or ``None`` when it is missing or malformed."""
    parser = argparse.ArgumentParser(prog="python -m src.jobs.end_of_day", exit_on_error=False)
    parser.add_argument("--as-of", required=True)
    try:
        return date.fromisoformat(parser.parse_args(argv).as_of)
    except (ValueError, argparse.ArgumentError, SystemExit):
        return None


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: print the result as JSON; exit 0 on success, 2 on a bad argument."""
    as_of = _parse_args(argv)
    if as_of is None:
        sys.stderr.write("usage: python -m src.jobs.end_of_day --as-of YYYY-MM-DD\n")
        return 2
    set_correlation_id(new_correlation_id())
    with SessionLocal() as session:
        result = EndOfDayRunner(session).run(as_of, SystemActor())
    summary = {
        "as_of": as_of.isoformat(),
        **result.counts(),
        "failed_policies": [
            {"policy_number": f.policy_number, "error": f.error} for f in result.failed
        ],
    }
    sys.stdout.write(json.dumps(summary) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
