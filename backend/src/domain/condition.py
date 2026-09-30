"""Pure evaluator for the rule `when` format (`docs/conventions.md` -> Rule `when` format).

Grammar: `<field> <op> <value>` clauses joined by ` and `; ops `< <= > >= == != in`.
No `eval`/`exec`: clauses are parsed with a regex and compared explicitly.
"""

import re
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from src.types.errors import ValidationError

_CLAUSE = re.compile(r"^\s*(\w+)\s+(<=|>=|==|!=|<|>|in)\s+(.+?)\s*$")
_ORDERED = frozenset({"<", "<=", ">", ">="})


def _number(token: Any) -> Decimal | None:
    """Return `token` as a `Decimal` when it is a non-bool int/Decimal or numeric string."""
    if isinstance(token, bool):
        return None
    if isinstance(token, Decimal):
        return token
    if isinstance(token, int):
        return Decimal(token)
    if isinstance(token, str):
        try:
            return Decimal(token)
        except InvalidOperation:
            return None
    return None


def _same(actual: Any, literal: str) -> bool:
    """Equality between a derived input and a literal token."""
    if isinstance(actual, bool):
        return literal in {"true", "false"} and actual == (literal == "true")
    left, right = _number(actual), _number(literal)
    if left is not None and right is not None:
        return left == right
    return str(actual) == literal


def _ordered(actual: Any, op: str, literal: str) -> bool:
    """Ordered comparison; both sides must be numeric."""
    left, right = _number(actual), _number(literal)
    if left is None or right is None:
        raise ValidationError(f"cannot order-compare {literal!r} with a non-numeric value")
    return {"<": left < right, "<=": left <= right, ">": left > right, ">=": left >= right}[op]


def _members(literal: str) -> list[str]:
    """Split a bracketed `[A, B]` list into its bare tokens."""
    if not (literal.startswith("[") and literal.endswith("]")):
        raise ValidationError(f"`in` needs a bracketed list, got {literal!r}")
    return [item.strip() for item in literal[1:-1].split(",") if item.strip()]


def _clause(text: str, values: Mapping[str, Any]) -> bool:
    """Evaluate one `<field> <op> <value>` clause."""
    match = _CLAUSE.match(text)
    if match is None:
        raise ValidationError(f"malformed condition clause: {text!r}")
    field, op, literal = match.group(1), match.group(2), match.group(3)
    if field not in values:
        raise ValidationError(f"unknown condition field: {field}")
    actual = values[field]
    if op in _ORDERED:
        return _ordered(actual, op, literal)
    if op == "in":
        return any(_same(actual, member) for member in _members(literal))
    return _same(actual, literal) == (op == "==")


def evaluate_condition(when: str, values: Mapping[str, Any]) -> bool:
    """True when every ` and `-joined clause of `when` holds for `values`."""
    return all(_clause(part, values) for part in when.split(" and "))
