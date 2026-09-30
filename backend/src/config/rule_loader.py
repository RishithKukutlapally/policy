"""Rule-file loading: JSON file -> schema validation -> frozen :class:`~src.types.rules.RuleSet`.

Canonical layout (docs/conventions.md -> "Products and rule files"):
``backend/policy_rules/<product_folder>/v<N>.json`` plus the append-only ledger
``backend/policy_rules/PUBLISHED.lock`` (``<sha256>  <relative path>`` per line).

Money and rates are read with ``json.loads(..., parse_float=Decimal)`` so a stray JSON number can
never become a ``float`` (NFR-01); the schema additionally requires them to be strings. Failures
raise the typed errors of :mod:`src.types.errors`: ``VALIDATION_ERROR`` for a bad file,
``NOT_FOUND`` for an unknown product or version.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, Protocol

from jsonschema import Draft7Validator

from src.types.enums import ProductCode, RuleSetStatus
from src.types.errors import NotFoundError, ValidationError
from src.types.rules import RuleSet

POLICY_RULES_ROOT: Final[Path] = Path(__file__).resolve().parents[2] / "policy_rules"
SCHEMA_RELATIVE_PATH: Final = Path("schema") / "rule-file.schema.json"
PUBLISHED_LOCK_NAME: Final = "PUBLISHED.lock"

PRODUCT_FOLDERS: Final[Mapping[ProductCode, str]] = {
    ProductCode.TERM_LIFE: "term_life",
    ProductCode.MOTOR: "motor",
    ProductCode.HOUSEHOLD: "household",
}


class RuleFileValidationError(ValidationError):
    """A rule file does not satisfy `policy_rules/schema/rule-file.schema.json` (AC-02)."""


class PublishedRuleFileTamperedError(ValidationError):
    """A PUBLISHED rule file's SHA-256 differs from its `PUBLISHED.lock` line (NFR-05)."""


@dataclass(frozen=True, slots=True)
class RuleFileRef:
    """One discovered rule file: where it is, what it declares and its content hash."""

    product: ProductCode
    version: int
    status: RuleSetStatus
    path: Path
    sha256: str

    @property
    def relative_path(self) -> str:
        """``<folder>/v<N>.json`` — the key used by `PUBLISHED.lock`."""
        return f"{PRODUCT_FOLDERS[self.product]}/v{self.version}.json"


def _root(rules_root: Path | None) -> Path:
    """Resolve the rule tree to read from (default: the packaged `backend/policy_rules`)."""
    return POLICY_RULES_ROOT if rules_root is None else Path(rules_root)


def rule_file_path(product: ProductCode, version: int, rules_root: Path | None = None) -> Path:
    """Return the canonical path of ``<product_folder>/v<version>.json``."""
    return _root(rules_root) / PRODUCT_FOLDERS[ProductCode(product)] / f"v{int(version)}.json"


def sha256_of_file(path: Path) -> str:
    """Lowercase hex SHA-256 of a file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rule_document(path: Path, *, as_decimal: bool = False) -> dict[str, Any]:
    """Parse a rule file; with ``as_decimal`` every JSON number becomes a :class:`Decimal`."""
    text = path.read_text(encoding="utf-8")
    try:
        document: Any = json.loads(text, parse_float=Decimal) if as_decimal else json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuleFileValidationError(
            f"{path.name} is not valid JSON: {exc.msg}",
            [{"field": path.name, "code": "SCHEMA_VIOLATION"}],
        ) from exc
    if not isinstance(document, dict):
        raise RuleFileValidationError(
            f"{path.name} must contain a JSON object",
            [{"field": path.name, "code": "SCHEMA_VIOLATION"}],
        )
    typed: dict[str, Any] = document
    return typed


def _schema(rules_root: Path | None = None) -> dict[str, Any]:
    """Load the rule-file JSON schema from the rule tree."""
    schema_path = _root(rules_root) / SCHEMA_RELATIVE_PATH
    schema: dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))
    return schema


def _details(errors: list[Any]) -> list[dict[str, str]]:
    """Render jsonschema errors as the API's ``details`` list (dotted JSON paths)."""
    return [
        {
            "field": ".".join(str(part) for part in error.absolute_path) or "<root>",
            "code": "SCHEMA_VIOLATION",
        }
        for error in errors
    ]


def _message(label: str, errors: list[Any]) -> str:
    """One-line summary naming the file and the first failing JSON paths."""
    paths = ", ".join(
        f"{'.'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors[:3]
    )
    return f"{label} violates the rule-file schema ({paths})"


def build_rule_set(
    document: Mapping[str, Any], *, label: str, rules_root: Path | None = None
) -> RuleSet:
    """Validate ``document`` against the schema and build the frozen rule set."""
    validator = Draft7Validator(_schema(rules_root))
    errors = sorted(validator.iter_errors(dict(document)), key=lambda e: list(e.absolute_path))
    if errors:
        raise RuleFileValidationError(_message(label, errors), _details(errors))
    try:
        return RuleSet.from_mapping(document)
    except (TypeError, ValueError, KeyError) as exc:
        raise RuleFileValidationError(
            f"{label} could not be parsed into a rule set: {exc}",
            [{"field": "<root>", "code": "SCHEMA_VIOLATION"}],
        ) from exc


def parse_rule_file(path: Path, rules_root: Path | None = None) -> RuleSet:
    """Load, validate and parse the rule file at ``path``."""
    if not path.is_file():
        raise NotFoundError(f"rule file {path.name} does not exist")
    document = read_rule_document(path, as_decimal=True)
    return build_rule_set(document, label=path.name, rules_root=rules_root or path.parents[1])


def load_rule_file(product: ProductCode, version: int, rules_root: Path | None = None) -> RuleSet:
    """Load ``<product_folder>/v<version>.json`` as a frozen :class:`RuleSet` (AC-02)."""
    product = ProductCode(product)
    path = rule_file_path(product, version, rules_root)
    if not path.is_file():
        raise NotFoundError(f"no rule file for product {product.value} v{int(version)}")
    document = read_rule_document(path, as_decimal=True)
    return build_rule_set(document, label=path.name, rules_root=rules_root)


class RuleContentSource(Protocol):
    """A store of rule-set bodies that takes precedence over the on-disk files.

    The database is the system of record for versions published through the API (AC-11): they have
    a ``rule_set_versions`` row and no file in the repository tree, because committed rule files
    are immutable (NFR-02/05). Implemented in the repository/service layer — the config layer only
    depends on this structural protocol, never on `src.repository`.
    """

    def rule_content(self, product: ProductCode, version: int) -> Mapping[str, Any] | None:
        """Body of ``(product, version)``, or ``None`` when the store does not hold it."""


def load_rule_set(
    product: ProductCode,
    version: int,
    *,
    source: RuleContentSource | None = None,
    rules_root: Path | None = None,
) -> RuleSet:
    """Resolve a version database-first, falling back to ``<folder>/v<N>.json`` (AC-11).

    Every version is loadable through one code path: a UI-published version comes from ``source``,
    the seeded ``v1`` files still come from disk and stay the source of truth for the immutability
    ledger (`verify_published_lock`).
    """
    product = ProductCode(product)
    if source is not None:
        content = source.rule_content(product, int(version))
        if content is not None:
            return build_rule_set(
                content, label=f"{product.value} v{int(version)}", rules_root=rules_root
            )
    return load_rule_file(product, version, rules_root)


def discover_rule_files(rules_root: Path | None = None) -> tuple[RuleFileRef, ...]:
    """Return every ``<folder>/v<N>.json`` in the tree, ordered by product then version."""
    root = _root(rules_root)
    refs: list[RuleFileRef] = []
    for product, folder in PRODUCT_FOLDERS.items():
        for path in sorted((root / folder).glob("v*.json")):
            document = read_rule_document(path)
            refs.append(
                RuleFileRef(
                    product=product,
                    version=int(document["version"]),
                    status=RuleSetStatus(document["status"]),
                    path=path,
                    sha256=sha256_of_file(path),
                )
            )
    return tuple(sorted(refs, key=lambda ref: (ref.product.value, ref.version)))


def load_published_lock(rules_root: Path | None = None) -> Mapping[str, str]:
    """Parse `PUBLISHED.lock` into ``{relative path: sha256}``."""
    lock_path = _root(rules_root) / PUBLISHED_LOCK_NAME
    if not lock_path.is_file():
        raise NotFoundError(f"{PUBLISHED_LOCK_NAME} is missing from {lock_path.parent}")
    entries: dict[str, str] = {}
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, _, relative = line.partition("  ")
        if not relative.strip():
            raise PublishedRuleFileTamperedError(f"malformed {PUBLISHED_LOCK_NAME} line: {line!r}")
        entries[relative.strip()] = digest.strip()
    return entries


def verify_published_lock(rules_root: Path | None = None) -> Mapping[str, str]:
    """Recompute every PUBLISHED file's hash and compare it with the ledger (NFR-05)."""
    lock = load_published_lock(rules_root)
    published = {
        ref.relative_path: ref
        for ref in discover_rule_files(rules_root)
        if ref.status.value == "PUBLISHED"
    }
    problems = [
        f"{relative} is listed in {PUBLISHED_LOCK_NAME} but missing from the rule tree"
        for relative in lock
        if relative not in published
    ]
    problems += [
        f"{relative} is PUBLISHED but absent from {PUBLISHED_LOCK_NAME}"
        for relative in published
        if relative not in lock
    ]
    problems += [
        f"{relative} has been tampered with: sha256 {ref.sha256} != {lock[relative]}"
        for relative, ref in published.items()
        if relative in lock and ref.sha256 != lock[relative]
    ]
    if problems:
        raise PublishedRuleFileTamperedError("; ".join(problems))
    return lock
