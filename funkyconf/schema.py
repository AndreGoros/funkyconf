"""
funkyconf.schema
~~~~~~~~~~~~~~~~
Declarative validation rules for Node structures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .node import Node


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    """Holds the outcome of a Schema.validate() call."""

    valid: bool
    errors: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid

    def raise_if_invalid(self) -> None:
        """Raise a :class:`ValidationError` when the result is invalid."""
        if not self.valid:
            raise ValidationError(self.errors)

    def __repr__(self) -> str:
        status = "OK" if self.valid else f"INVALID ({len(self.errors)} error(s))"
        return f"ValidationResult({status})"


class ValidationError(Exception):
    """Raised by :meth:`ValidationResult.raise_if_invalid`."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


# ---------------------------------------------------------------------------
# Field descriptor used inside Schema
# ---------------------------------------------------------------------------

@dataclass
class _FieldRule:
    name: str
    required: bool = False
    expected_type: Optional[type] = None
    predicate: Optional[Callable[[Any], bool]] = None
    predicate_message: str = "failed predicate check"
    pattern: Optional[str] = None   # regex for string fields
    choices: Optional[list] = None  # allowed values


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class Schema:
    """
    A collection of validation rules for a :class:`~funkyconf.node.Node`.

    Usage::

        from funkyconf import Node, attr, Schema

        service_schema = (
            Schema("service")
            .require("image", str)
            .require("restart", str, choices=["always", "unless-stopped", "no"])
            .optional("ports", list)
        )

        result = my_node.validate(service_schema)
        result.raise_if_invalid()
    """

    def __init__(self, name: Optional[str] = None) -> None:
        self._name = name
        self._field_rules: List[_FieldRule] = []
        self._custom_checks: List[Callable[["Node"], Optional[str]]] = []

    # ------------------------------------------------------------------
    # Fluent builder API
    # ------------------------------------------------------------------

    def require(
        self,
        key: str,
        expected_type: Optional[type] = None,
        *,
        predicate: Optional[Callable[[Any], bool]] = None,
        predicate_message: str = "failed predicate check",
        pattern: Optional[str] = None,
        choices: Optional[list] = None,
    ) -> "Schema":
        """Declare a required attribute."""
        self._field_rules.append(
            _FieldRule(
                name=key,
                required=True,
                expected_type=expected_type,
                predicate=predicate,
                predicate_message=predicate_message,
                pattern=pattern,
                choices=choices,
            )
        )
        return self

    def optional(
        self,
        key: str,
        expected_type: Optional[type] = None,
        *,
        predicate: Optional[Callable[[Any], bool]] = None,
        predicate_message: str = "failed predicate check",
        pattern: Optional[str] = None,
        choices: Optional[list] = None,
    ) -> "Schema":
        """Declare an optional attribute with optional type / predicate checks."""
        self._field_rules.append(
            _FieldRule(
                name=key,
                required=False,
                expected_type=expected_type,
                predicate=predicate,
                predicate_message=predicate_message,
                pattern=pattern,
                choices=choices,
            )
        )
        return self

    def check(self, fn: Callable[["Node"], Optional[str]]) -> "Schema":
        """
        Add a custom validation function.

        The function receives the :class:`~funkyconf.node.Node` and must return
        ``None`` when the check passes, or an error string when it fails.
        """
        self._custom_checks.append(fn)
        return self

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    def validate(self, node: "Node") -> ValidationResult:
        """Return a :class:`ValidationResult` for *node*."""
        errors: List[str] = []
        attrs = node.attributes

        for rule in self._field_rules:
            value = attrs.get(rule.name, _MISSING)

            if value is _MISSING:
                if rule.required:
                    errors.append(
                        f"[{node.name}] Missing required attribute: '{rule.name}'"
                    )
                continue

            if rule.expected_type is not None and not isinstance(value, rule.expected_type):
                errors.append(
                    f"[{node.name}] Attribute '{rule.name}' expected "
                    f"{rule.expected_type.__name__}, got {type(value).__name__}"
                )
                continue  # skip further checks on this field

            if rule.choices is not None and value not in rule.choices:
                errors.append(
                    f"[{node.name}] Attribute '{rule.name}' must be one of "
                    f"{rule.choices!r}, got {value!r}"
                )

            if rule.pattern is not None and isinstance(value, str):
                if not re.fullmatch(rule.pattern, value):
                    errors.append(
                        f"[{node.name}] Attribute '{rule.name}' value {value!r} "
                        f"does not match pattern {rule.pattern!r}"
                    )

            if rule.predicate is not None:
                try:
                    ok = rule.predicate(value)
                except Exception as exc:
                    ok = False
                    errors.append(
                        f"[{node.name}] Attribute '{rule.name}' predicate raised "
                        f"an exception: {exc}"
                    )
                else:
                    if not ok:
                        errors.append(
                            f"[{node.name}] Attribute '{rule.name}' {rule.predicate_message}"
                        )

        # Custom whole-node checks
        for fn in self._custom_checks:
            msg = fn(node)
            if msg:
                errors.append(f"[{node.name}] {msg}")

        return ValidationResult(valid=len(errors) == 0, errors=errors)


_MISSING = object()
